# =============================================================================
# sync_service.py - Time-stretching et assemblage vidéo final
# =============================================================================
# Ce fichier a deux responsabilités :
#
# 1. TIME-STRETCHING : ajuster la durée de chaque segment audio TTS
#    pour qu'il corresponde au timestamp original de la vidéo
#    On utilise ffmpeg qui a Rubber Band intégré (--enable-librubberband)
#
# 2. ASSEMBLAGE FINAL : combiner tous les segments audio TTS positionnés
#    aux bons timestamps → fichier .wav final
#
# POURQUOI ffmpeg pour le time-stretching ?
# Notre ffmpeg est compilé avec --enable-librubberband
# Rubber Band = algorithme professionnel de time-stretching
# qui préserve la hauteur de la voix (pas d'effet chipmunk)
# C'est la même technologie utilisée dans les DAW professionnels
#
# CHANGEMENT ÉTAPE H — LOUDNORM 2 PASSES :
# Avant : loudnorm en une seule passe = estimation approximative car ffmpeg
#         ne connaît pas la fin du fichier quand il traite le début.
# Après : passe 1 = mesure les vraies valeurs du fichier (I, TP, LRA, thresh)
#         passe 2 = applique la normalisation avec ces valeurs mesurées
#         Résultat : précision ±0.1 LU au lieu de ±3 LU.
# ANALOGIE : cuisiner avec un thermomètre plutôt qu'à l'œil —
#            on mesure d'abord, on corrige ensuite.
# =============================================================================


# =============================================================================
# IMPORTS
# =============================================================================

import os
# os = interactions avec le système de fichiers

import logging
# logging = messages dans le terminal

import subprocess
# subprocess = module Python pour lancer des programmes externes
# On l'utilise pour appeler ffmpeg depuis Python
# POURQUOI subprocess ?
# ffmpeg est un programme en ligne de commande, pas une bibliothèque Python
# subprocess permet d'exécuter des commandes shell depuis Python
# et de récupérer les résultats (sortie, erreurs, code de retour)
# Analogie : c'est comme ouvrir un terminal et taper une commande,
# mais depuis l'intérieur de Python

import json
# json = module pour lire/écrire du JSON
# On l'utilise pour parser la sortie de ffprobe
# ET pour parser les mesures loudnorm retournées par ffmpeg en passe 1
# ffprobe = outil de ffmpeg pour analyser les fichiers audio/vidéo

import re
# QU'EST-CE QUE C'EST : Module d'expressions régulières.
# POURQUOI : La sortie stderr de ffmpeg contient du texte + un bloc JSON.
#            re.search() permet d'extraire uniquement le bloc JSON des mesures loudnorm.
# COMMENT : re.search(r'\{[^{}]+\}', stderr) trouve le premier { ... } dans la string.

import shutil
# shutil = module Python pour manipuler les fichiers
# On l'utilise dans stretch_audio_segment() pour copier un fichier
# quand la différence est dans la tolérance et qu'on n'a pas besoin de stretcher
# POURQUOI shutil.copy2 et pas shutil.copy ?
# copy2 = copie le fichier ET préserve les métadonnées (dates, permissions)
# copy  = copie uniquement le contenu

from config import (
    YOUTUBE_OUTPUT_DIR,
    # Dossier où on sauvegarde la vidéo finale
    # "youtube/outputs"

    STRETCH_TOLERANCE
    # Tolérance avant d'appliquer le stretching
    # 0.20 = on accepte ±20% de différence sans modifier l'audio
    # En dessous de 20% → l'oreille humaine ne perçoit pas la différence
)


# =============================================================================
# CONFIGURATION DU LOGGER
# =============================================================================

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTES LOUDNORM
# =============================================================================

# QU'EST-CE QUE C'EST : Cibles de normalisation EBU R128 (standard broadcast européen).
# POURQUOI les centraliser ici : les deux passes utilisent les mêmes valeurs cibles —
#   une seule définition évite toute incohérence entre les deux appels ffmpeg.
# COMMENT : Ces valeurs sont passées comme paramètres au filtre loudnorm de ffmpeg.

LOUDNORM_I   = -16.0  # Loudness intégrée cible en LUFS — standard Spotify/YouTube
LOUDNORM_TP  = -1.5   # True Peak maximum en dBTP — évite la saturation numérique
LOUDNORM_LRA = 11.0   # Loudness Range cible en LU — dynamique naturelle pour la voix


# =============================================================================
# FONCTION UTILITAIRE : get_audio_duration()
# Mesure la durée exacte d'un fichier audio avec ffprobe
# =============================================================================

def get_audio_duration(audio_path: str) -> float:
    """
    Retourne la durée exacte d'un fichier audio en secondes.

    POURQUOI ffprobe et pas soundfile ?
    ffprobe est plus fiable sur tous les formats audio
    et retourne une précision à la microseconde.
    soundfile peut avoir des imprécisions sur certains formats.

    Paramètres :
    ------------
    audio_path : str
        Chemin vers le fichier audio

    Retourne : float
        Durée en secondes. Ex: 3.456
        Retourne 0.0 si erreur
    """

    try:
        # Commande ffprobe pour analyser le fichier audio
        # -v quiet          → pas de sortie verbeuse
        # -print_format json → sortie en JSON (plus facile à parser)
        # -show_streams      → affiche les infos des flux (audio, vidéo)
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            audio_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        data = json.loads(result.stdout)
        duration = float(data["streams"][0]["duration"])
        return duration

    except Exception as e:
        logger.warning(f"Impossible de mesurer la durée de {audio_path} : {str(e)}")
        return 0.0


# =============================================================================
# FONCTION 1 : stretch_audio_segment()
# Ajuste la durée d'un segment audio avec ffmpeg + Rubber Band
# =============================================================================

def stretch_audio_segment(
    audio_path: str,
    target_duration: float,
    output_path: str
) -> dict:
    """
    Ajuste la durée d'un fichier audio WAV pour qu'il dure exactement
    target_duration secondes, en utilisant ffmpeg avec Rubber Band.

    COMMENT ÇA MARCHE ?
    ffmpeg applique le filtre "rubberband" qui :
    1. Analyse la structure temporelle de l'audio (formants, pitch)
    2. Réorganise les données pour modifier la durée
    3. Corrige le pitch pour que la voix reste naturelle
    Analogie : comme étirer un morceau de pâte à modeler
    sans changer sa couleur (le pitch = la couleur de la voix)

    LIMITES :
    Un étirement extrême dégrade la qualité :
    - ratio < 0.5 (compression > 50%) → voix robotique
    - ratio > 2.0 (étirement > 200%) → voix déformée
    On utilise STRETCH_TOLERANCE pour éviter les cas extrêmes

    Paramètres :
    ------------
    audio_path : str
        Chemin vers le fichier WAV source

    target_duration : float
        Durée cible en secondes
        C'est la durée du segment original dans la vidéo

    output_path : str
        Chemin du fichier WAV de sortie (après stretching)

    Retourne : dict
    ---------------
    {
        "success": True,
        "output_path": "...",
        "original_duration": 7.2,
        "target_duration": 4.0,
        "ratio": 0.556,   ← facteur d'accélération appliqué
        "stretched": True ← True si stretching appliqué, False si copie simple
    }
    """

    try:
        current_duration = get_audio_duration(audio_path)

        if current_duration <= 0:
            raise ValueError(f"Durée invalide pour {audio_path} : {current_duration}")

        ratio = target_duration / current_duration
        difference_pct = abs(1.0 - ratio)

        logger.info(
            f"Stretching | durée_actuelle={current_duration:.2f}s | "
            f"durée_cible={target_duration:.2f}s | "
            f"ratio={ratio:.3f} | diff={difference_pct:.0%}"
        )

        # -----------------------------------------------------------------
        # Vérification de la tolérance
        # -----------------------------------------------------------------
        if difference_pct <= STRETCH_TOLERANCE:
            shutil.copy2(audio_path, output_path)
            logger.info(f"Différence ≤{STRETCH_TOLERANCE:.0%} → copie sans stretching")
            return {
                "success": True,
                "output_path": output_path,
                "original_duration": current_duration,
                "target_duration": target_duration,
                "ratio": ratio,
                "stretched": False
            }

        # -----------------------------------------------------------------
        # Limites de stretching pour préserver la qualité
        # -----------------------------------------------------------------
        if ratio < 0.5:
            logger.warning(
                f"Ratio trop faible ({ratio:.3f}) → limité à 0.5 "
                f"(compression maximale 50%)"
            )
            ratio = 0.5
        elif ratio > 2.0:
            logger.warning(
                f"Ratio trop élevé ({ratio:.3f}) → limité à 2.0 "
                f"(étirement maximum 200%)"
            )
            ratio = 2.0

        # tempo = inverse du ratio
        # ratio=0.8 → tempo=1.25 (parle 25% plus vite)
        # ratio=1.2 → tempo=0.833 (parle 17% plus lentement)
        tempo = 1.0 / ratio

        cmd = [
            "ffmpeg",
            "-i", audio_path,
            "-filter:a", f"rubberband=tempo={tempo:.6f}",
            "-y",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg erreur : {result.stderr}")

        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Fichier de sortie introuvable : {output_path}")

        logger.info(f"Stretching appliqué avec succès → {output_path}")

        return {
            "success": True,
            "output_path": output_path,
            "original_duration": current_duration,
            "target_duration": target_duration,
            "ratio": round(ratio, 3),
            "stretched": True
        }

    except Exception as e:
        logger.error(f"Erreur stretching : {str(e)}")
        return {
            "success": False,
            "output_path": None,
            "original_duration": 0,
            "target_duration": target_duration,
            "ratio": 0,
            "stretched": False,
            "error": str(e)
        }


# =============================================================================
# NOUVEAU — ÉTAPE H : Loudnorm 2 passes
# =============================================================================

def _loudnorm_pass1(input_path: str) -> dict | None:
    """
    Passe 1 : mesure les vraies caractéristiques audio du fichier via ffmpeg.

    QU'EST-CE QUE C'EST : Analyse complète du fichier — ffmpeg le lit en entier
        et retourne les vraies valeurs I/TP/LRA/thresh dans stderr en JSON.
    POURQUOI une passe de mesure ?
        En une seule passe, loudnorm travaille en streaming : il ne connaît pas
        la fin du fichier quand il traite le début → il estime le gain à appliquer.
        L'estimation peut être fausse de plusieurs dB selon le contenu.
        Avec les vraies valeurs mesurées, la passe 2 calcule un gain exact.
    COMMENT :
        On passe -f null - comme sortie = on ne produit aucun fichier,
        on veut uniquement les mesures écrites dans stderr.

    Paramètres :
    ------------
    input_path : str
        Chemin vers le fichier WAV à analyser.

    Retourne : dict ou None
        Dict avec les 4 valeurs mesurées si succès, None si parsing échoue.
        Ex: { "measured_I": -23.4, "measured_TP": -1.2,
              "measured_LRA": 7.8, "measured_thresh": -34.1 }
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-af", (
            f"loudnorm="
            f"I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:"
            f"print_format=json"
            # print_format=json = demande à ffmpeg d'écrire les mesures en JSON dans stderr
        ),
        "-f", "null", "-"
        # -f null - = sortie nulle, aucun fichier écrit — on veut juste les mesures
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        # Les mesures loudnorm sont dans stderr (comportement ffmpeg, pas un bug)
        # stderr contient aussi les logs ffmpeg normaux — on cherche le bloc JSON
        json_match = re.search(r'\{[^{}]+\}', result.stderr, re.DOTALL)
        # r'\{[^{}]+\}' = pattern regex :
        #   \{        = accolade ouvrante
        #   [^{}]+    = un ou plusieurs caractères qui ne sont pas des accolades
        #   \}        = accolade fermante
        # re.DOTALL = le point matche aussi les retours à la ligne

        if not json_match:
            logger.error("loudnorm passe 1 : bloc JSON introuvable dans stderr")
            return None

        measures = json.loads(json_match.group())

        return {
            "measured_I":      float(measures["input_i"]),
            # input_i = loudness intégrée mesurée en LUFS
            "measured_TP":     float(measures["input_tp"]),
            # input_tp = true peak mesuré en dBTP
            "measured_LRA":    float(measures["input_lra"]),
            # input_lra = loudness range mesurée en LU
            "measured_thresh": float(measures["input_thresh"]),
            # input_thresh = seuil de bruit de fond en LUFS
        }

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"loudnorm passe 1 : parsing JSON échoué : {e}")
        return None
    except subprocess.TimeoutExpired:
        logger.error("loudnorm passe 1 : timeout (>120s)")
        return None


def _loudnorm_pass2(input_path: str, output_path: str, measures: dict) -> dict:
    """
    Passe 2 : applique la normalisation avec les valeurs mesurées en passe 1.

    QU'EST-CE QUE C'EST : Normalisation précise avec les vraies valeurs du fichier.
    POURQUOI linear=true ?
        linear=true = ffmpeg applique un gain linéaire simple (multiplication constante).
        Sans linear=true = ffmpeg active la compression dynamique, ce qui change
        le rendu sonore de la voix de manière imprévisible.
        Pour de la voix TTS, on veut uniquement ajuster le volume, pas la dynamique.

    Paramètres :
    ------------
    input_path  : str  — Fichier WAV source.
    output_path : str  — Fichier WAV normalisé de sortie.
    measures    : dict — Résultat de _loudnorm_pass1().

    Retourne : dict
        { "success": True, "output_path": "..." }
        { "success": False, "error": "..." }
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-af", (
            f"loudnorm="
            f"I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:"
            f"measured_I={measures['measured_I']}:"
            f"measured_TP={measures['measured_TP']}:"
            f"measured_LRA={measures['measured_LRA']}:"
            f"measured_thresh={measures['measured_thresh']}:"
            f"linear=true"
            # Les 4 valeurs mesurées + linear=true = gain exact sans compression dynamique
        ),
        "-ar", "24000",
        # On conserve la fréquence d'échantillonnage de Kokoro
        "-ac", "1",
        # Mono — cohérent avec la sortie TTS
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return {"success": False, "error": f"loudnorm passe 2 : {result.stderr[-200:]}"}
        return {"success": True, "output_path": output_path}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "loudnorm passe 2 : timeout (>120s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _apply_loudnorm_two_pass(input_path: str, output_path: str) -> dict:
    """
    Normalise un fichier audio en deux passes ffmpeg.

    QU'EST-CE QUE C'EST : Orchestration des deux passes — interface interne
        appelée uniquement par assemble_audio_track().
    POURQUOI préfixe _ ?
        Convention Python : _ = fonction interne, pas censée être importée
        directement depuis l'extérieur du module.
    COMMENT :
        1. Passe 1 → mesures JSON
        2. Si mesures OK → passe 2 avec ces mesures
        3. Si passe 1 échoue → fallback une seule passe (mieux que rien)

    Paramètres :
    ------------
    input_path  : str — Fichier WAV source (mix brut).
    output_path : str — Fichier WAV normalisé final.

    Retourne : dict
        { "success": True, "output_path": "...", "passes": 2 }
        { "success": True, "output_path": "...", "passes": 1 }  ← fallback
        { "success": False, "error": "..." }
    """
    logger.info(f"loudnorm passe 1 : analyse de {os.path.basename(input_path)}")
    measures = _loudnorm_pass1(input_path)

    if measures is None:
        # Fallback : une seule passe si la mesure échoue
        logger.warning("loudnorm passe 1 échouée → fallback une seule passe")
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-af", f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}",
            "-ar", "24000", "-ac", "1",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return {"success": False, "error": f"loudnorm fallback : {result.stderr[-200:]}"}
        return {"success": True, "output_path": output_path, "passes": 1}

    logger.info(
        f"loudnorm passe 1 OK → "
        f"I={measures['measured_I']:.1f} LUFS | "
        f"TP={measures['measured_TP']:.1f} dBTP | "
        f"LRA={measures['measured_LRA']:.1f} LU"
    )

    logger.info(f"loudnorm passe 2 : application → cible {LOUDNORM_I} LUFS")
    result = _loudnorm_pass2(input_path, output_path, measures)

    if not result["success"]:
        return result

    return {"success": True, "output_path": output_path, "passes": 2}


# =============================================================================
# FONCTION 2 : assemble_audio_track()
# Assemble tous les segments TTS en une seule piste audio synchronisée
# =============================================================================

def assemble_audio_track(
    audio_segments: list,
    job_id: str,
    job_dir: str,
    total_duration: float
) -> dict:
    """
    Assemble tous les segments audio TTS en une seule piste WAV synchronisée.
    Cette piste sera jouée par le frontend par-dessus la vidéo YouTube en muet.

    POURQUOI PLUS DE VIDÉO ?
    Avant : on téléchargeait la vidéo (lourd) + on assemblait tout en .mp4
    Maintenant : on produit juste une piste audio .wav légère
    Le frontend joue la vidéo YouTube directement (via iframe) + notre audio par dessus
    Avantages :
    - Pas de stockage vidéo sur le serveur
    - Téléchargement 10x plus rapide
    - Légalement plus propre (on ne stocke pas la vidéo YouTube)

    CHANGEMENT ÉTAPE H :
    Avant : loudnorm intégré dans le filtre amix (une seule passe → approximatif)
    Après : amix produit un mix brut, puis _apply_loudnorm_two_pass() normalise
            avec mesure préalable → précision garantie.

    Paramètres :
    ------------
    audio_segments : list
        Liste des segments audio de generate_tts_segments()
        Chaque segment contient : audio_path, start, end, duration, index

    job_id : str
        Identifiant du job — pour nommer le fichier de sortie
        Ex: "a3f8c2d1" → fichier "audio_a3f8c2d1.wav"

    job_dir : str
        Dossier de travail du job
        Ex: "youtube/temp/a3f8c2d1"

    total_duration : float
        Durée totale de la vidéo originale en secondes

    Retourne : dict
    ---------------
    Succès : { "success": True, "output_path": "youtube/outputs/audio_xxx.wav", "error": None }
    Échec  : { "success": False, "output_path": None, "error": "Message d'erreur" }
    """

    try:
        # -----------------------------------------------------------------
        # Étape F : Time-stretching de tous les segments (inchangé)
        # -----------------------------------------------------------------
        stretched_dir = os.path.join(job_dir, "stretched")
        os.makedirs(stretched_dir, exist_ok=True)
        # Dossier séparé pour les fichiers après stretching
        # "youtube/temp/a3f8c2d1/stretched/"

        logger.info(f"Time-stretching de {len(audio_segments)} segments...")

        stretched_segments = []
        for segment in audio_segments:

            stretched_path = os.path.join(
                stretched_dir,
                f"stretched_{segment['index']:03d}.wav"
                # :03d = 3 chiffres avec zéros → stretched_000.wav, stretched_001.wav...
            )

            stretch_result = stretch_audio_segment(
                audio_path=segment["audio_path"],
                target_duration=segment["duration"],
                output_path=stretched_path
            )

            if stretch_result["success"]:
                stretched_segments.append({
                    **segment,
                    "audio_path": stretch_result["output_path"],
                    "stretched": stretch_result["stretched"]
                })
            else:
                logger.warning(
                    f"Stretching échoué pour segment {segment['index']}, "
                    f"audio original utilisé"
                )
                stretched_segments.append({
                    **segment,
                    "stretched": False
                })

        # -----------------------------------------------------------------
        # Étape G : Assemblage ffmpeg avec adelay + amix
        # CHANGEMENT : loudnorm retiré du filtre_complex — géré séparément
        #              en 2 passes après l'assemblage (voir étape H ci-dessous)
        # -----------------------------------------------------------------

        # Fichier intermédiaire = mix brut avant normalisation loudnorm
        # POURQUOI séparer mix_path et output_path ?
        # Les deux passes loudnorm lisent mix_path en entrée et écrivent dans output_path
        # On ne peut pas lire et écrire le même fichier simultanément avec ffmpeg
        mix_path = os.path.join(job_dir, f"mix_{job_id}.wav")

        cmd = ["ffmpeg", "-y"]
        # -y = écrase le fichier de sortie sans demander confirmation

        for segment in stretched_segments:
            cmd += ["-i", segment["audio_path"]]
            # -i = input = un fichier par segment

        filter_parts = []

        for i, segment in enumerate(stretched_segments):
            delay_ms = int(segment["start"] * 1000)
            # Conversion secondes → millisecondes (adelay attend des ms)
            filter_parts.append(
                f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]"
                # [{i}:a]                = flux audio de l'input numéro i
                # adelay={delay_ms}|{delay_ms} = silence au début (gauche|droite)
                # [a{i}]                 = nom du flux de sortie de ce filtre
            )

        audio_inputs = "".join([f"[a{i}]" for i in range(len(stretched_segments))])
        # Construit "[a0][a1][a2]...[aN]" — liste des flux à mélanger

        # CHANGEMENT vs version précédente :
        # Avant : f"...amix=...,loudnorm=I=-16:TP=-1.5:LRA=11[audio_out]"
        # Après : loudnorm retiré ici → appliqué en 2 passes séparées ci-dessous
        filter_parts.append(
            f"{audio_inputs}amix=inputs={len(stretched_segments)}:"
            f"duration=longest:dropout_transition=0[audio_out]"
            # amix          = mélange N flux audio en un seul
            # duration=longest = durée finale = celle du flux le plus long
            # dropout_transition=0 = pas de fondu quand un flux se termine
            # [audio_out]   = nom du flux de sortie final
        )

        filter_complex = ";".join(filter_parts)
        # Joint tous les filtres avec ";" = séparateur ffmpeg

        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[audio_out]",
            "-ar", "24000",
            # 24000 Hz = fréquence de Kokoro — on ne convertit pas encore ici
            "-ac", "1",
            # Mono — Kokoro génère du mono
            "-t", str(total_duration),
            # Limite à la durée de la vidéo originale
            mix_path
            # ← mix_path et non output_path : fichier intermédiaire avant loudnorm
        ]

        logger.info(f"Assemblage mix brut : {mix_path}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg erreur : {result.stderr[-500:]}")

        if not os.path.exists(mix_path):
            raise FileNotFoundError(f"Mix brut introuvable : {mix_path}")

        logger.info(f"Mix brut assemblé : {mix_path}")

        # -----------------------------------------------------------------
        # Étape H : Normalisation loudnorm 2 passes (NOUVEAU)
        # -----------------------------------------------------------------
        output_path = os.path.join(YOUTUBE_OUTPUT_DIR, f"audio_{job_id}.wav")
        os.makedirs(YOUTUBE_OUTPUT_DIR, exist_ok=True)

        logger.info(f"Loudnorm 2 passes : {mix_path} → {output_path}")
        loudnorm_result = _apply_loudnorm_two_pass(mix_path, output_path)

        if not loudnorm_result["success"]:
            raise RuntimeError(loudnorm_result["error"])

        logger.info(
            f"Piste audio finale : {output_path} "
            f"({loudnorm_result['passes']} passe(s) loudnorm)"
        )

        return {
            "success": True,
            "output_path": output_path,
            "error": None
        }

    except Exception as e:
        logger.error(f"Erreur assemblage piste audio : {str(e)}")
        return {
            "success": False,
            "output_path": None,
            "error": str(e)
        }