# =============================================================================
# sync_service.py - Time-stretching et assemblage vidéo final
# =============================================================================
# Ce fichier a deux responsabilités :
#
# 1. TIME-STRETCHING : ajuster la durée de chaque segment audio TTS
#    pour qu'il corresponde au timestamp original de la vidéo
#    On utilise ffmpeg qui a Rubber Band intégré (--enable-librubberband)
#
# 2. ASSEMBLAGE FINAL : combiner la vidéo muette + tous les segments
#    audio TTS positionnés aux bons timestamps → fichier .mp4 final
#
# POURQUOI ffmpeg pour le time-stretching ?
# Notre ffmpeg est compilé avec --enable-librubberband
# Rubber Band = algorithme professionnel de time-stretching
# qui préserve la hauteur de la voix (pas d'effet chipmunk)
# C'est la même technologie utilisée dans les DAW professionnels
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
# ffprobe = outil de ffmpeg pour analyser les fichiers audio/vidéo

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
            # cmd = liste de strings = la commande et ses arguments
            # subprocess.run prend soit une string soit une liste
            # La liste est recommandée pour éviter les problèmes
            # avec les espaces dans les chemins de fichiers

            capture_output=True,
            # capture_output=True → capture stdout ET stderr
            # Sans ça, la sortie s'affiche directement dans le terminal
            # On veut la récupérer dans result.stdout pour la parser

            text=True,
            # text=True → retourne des strings au lieu de bytes
            # Plus facile à manipuler

            check=True
            # check=True → lève une exception si le code de retour != 0
            # Code 0 = succès, autre = erreur
        )

        # Parse le JSON retourné par ffprobe
        data = json.loads(result.stdout)
        # json.loads = convertit une string JSON en dict Python

        # Récupère la durée du premier flux audio
        duration = float(data["streams"][0]["duration"])
        # data["streams"] = liste des flux du fichier
        # [0] = premier flux (l'audio WAV n'a qu'un seul flux)
        # ["duration"] = durée en secondes sous forme de string
        # float() = convertit la string en nombre décimal

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
        # Mesure la durée actuelle du fichier audio TTS
        current_duration = get_audio_duration(audio_path)

        if current_duration <= 0:
            raise ValueError(f"Durée invalide pour {audio_path} : {current_duration}")

        # Calcul du ratio de stretching
        ratio = target_duration / current_duration
        # ratio = ce par quoi on multiplie la durée
        # ratio = 0.8 → on compresse à 80% de la durée (plus rapide)
        # ratio = 1.2 → on étire à 120% de la durée (plus lent)
        # ratio = 1.0 → pas de changement

        # Calcul de la différence en pourcentage
        difference_pct = abs(1.0 - ratio)
        # abs() = valeur absolue (toujours positif)
        # Ex: ratio=0.8 → difference_pct = abs(1.0 - 0.8) = 0.2 = 20%

        logger.info(
            f"Stretching | durée_actuelle={current_duration:.2f}s | "
            f"durée_cible={target_duration:.2f}s | "
            f"ratio={ratio:.3f} | diff={difference_pct:.0%}"
        )

        # -----------------------------------------------------------------
        # Vérification de la tolérance
        # -----------------------------------------------------------------
        if difference_pct <= STRETCH_TOLERANCE:
            # La différence est dans la tolérance (≤20%)
            # L'oreille humaine ne percevra pas la différence
            # On copie simplement le fichier sans stretching
            shutil.copy2(audio_path, output_path)
            # shutil.copy2 = copie le fichier en préservant les métadonnées

            logger.info(f"Différence ≤{STRETCH_TOLERANCE:.0%} → copie sans stretching")
            return {
                "success": True,
                "output_path": output_path,
                "original_duration": current_duration,
                "target_duration": target_duration,
                "ratio": ratio,
                "stretched": False
                # False = pas de stretching appliqué
            }

        # -----------------------------------------------------------------
        # Limites de stretching pour préserver la qualité
        # -----------------------------------------------------------------
        # Si le ratio est trop extrême, on le limite
        # pour éviter une dégradation trop importante
        if ratio < 0.5:
            logger.warning(
                f"Ratio trop faible ({ratio:.3f}) → limité à 0.5 "
                f"(compression maximale 50%)"
            )
            ratio = 0.5
            # On accepte une légère désynchronisation plutôt
            # qu'une voix incompréhensible

        elif ratio > 2.0:
            logger.warning(
                f"Ratio trop élevé ({ratio:.3f}) → limité à 2.0 "
                f"(étirement maximum 200%)"
            )
            ratio = 2.0

        # -----------------------------------------------------------------
        # Application du time-stretching avec ffmpeg + Rubber Band
        # -----------------------------------------------------------------
        # Le filtre rubberband de ffmpeg prend un paramètre "tempo"
        # tempo = inverse du ratio de durée
        # Si on veut que la durée soit × 0.8 → le tempo doit être × 1.25
        # tempo = 1.0 / ratio
        tempo = 1.0 / ratio
        # Ex: ratio=0.8 → tempo=1.25 (parle 25% plus vite)
        #     ratio=1.2 → tempo=0.833 (parle 17% plus lentement)

        cmd = [
            "ffmpeg",
            "-i", audio_path,
            # -i = input = fichier d'entrée

            "-filter:a", f"rubberband=tempo={tempo:.6f}",
            # -filter:a = applique un filtre audio
            # rubberband = le filtre Rubber Band intégré à ffmpeg
            # tempo={tempo} = facteur de vitesse
            # :.6f = 6 décimales pour la précision

            "-y",
            # -y = écrase le fichier de sortie sans demander confirmation

            output_path
            # Le fichier WAV de sortie
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            # returncode != 0 = ffmpeg a rencontré une erreur
            raise RuntimeError(f"ffmpeg erreur : {result.stderr}")

        # Vérification que le fichier de sortie existe
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

    COMMENT FFMPEG POSITIONNE L'AUDIO ?
    On utilise le filtre "adelay" qui ajoute un silence au début d'un fichier audio.
    Ex: segment_000.wav avec adelay=5000ms → ce segment commence à t=5s dans la piste finale
    Ensuite "amix" mélange tous les segments décalés en une seule piste continue.
    Analogie : comme coller des post-its sur une frise chronologique,
    chacun à sa bonne position, puis photographier la frise entière.

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
        Utilisé pour créer le dossier "stretched" des segments après time-stretching

    total_duration : float
        Durée totale de la vidéo originale en secondes
        Ex: 213.0 pour une vidéo de 3min33s
        Utilisé pour que la piste audio finale ait la bonne durée

    Retourne : dict
    ---------------
    Succès :
    {
        "success": True,
        "output_path": "youtube/outputs/audio_a3f8c2d1.wav",
        "error": None
    }
    Échec :
    {
        "success": False,
        "output_path": None,
        "error": "Message d'erreur"
    }
    """

    try:
        # -----------------------------------------------------------------
        # Étape 1 : Time-stretching de tous les segments
        # -----------------------------------------------------------------
        # Chaque segment TTS a une durée différente de la durée originale
        # On doit les ajuster pour qu'ils s'alignent sur les bons timestamps
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
                # Le fichier WAV généré par Kokoro

                target_duration=segment["duration"],
                # La durée ORIGINALE du segment dans la vidéo
                # C'est la durée cible après stretching

                output_path=stretched_path
            )

            if stretch_result["success"]:
                stretched_segments.append({
                    **segment,
                    # ** = décompresse le dict segment
                    # Copie toutes les clés/valeurs existantes du segment original
                    # Puis on remplace/ajoute les nouvelles valeurs ci-dessous

                    "audio_path": stretch_result["output_path"],
                    # On remplace le chemin par le fichier après stretching

                    "stretched": stretch_result["stretched"]
                    # True si stretching appliqué, False si copie simple
                })
            else:
                # Si le stretching échoue sur UN segment, on utilise l'audio original
                # On ne veut pas que toute la piste échoue pour un seul segment
                logger.warning(
                    f"Stretching échoué pour segment {segment['index']}, "
                    f"audio original utilisé"
                )
                stretched_segments.append({
                    **segment,
                    "stretched": False
                })

        # -----------------------------------------------------------------
        # Étape 2 : Construction de la commande ffmpeg d'assemblage
        # -----------------------------------------------------------------
        # On construit une piste audio WAV complète en plaçant chaque segment
        # au bon timestamp avec "adelay" puis en mélangeant avec "amix"

        output_path = os.path.join(YOUTUBE_OUTPUT_DIR, f"audio_{job_id}.wav")
        # CHANGEMENT : on produit un .wav au lieu d'un .mp4
        # "audio_{job_id}.wav" = piste audio finale synchronisée

        # Structure de la commande ffmpeg :
        # ffmpeg -i seg1.wav -i seg2.wav -i seg3.wav ...
        #        -filter_complex "[1:a]adelay=0|0[a0];[2:a]adelay=5000|5000[a1];...
        #                         [a0][a1]...amix=inputs=N[out]"
        #        -map "[out]" output.wav

        cmd = ["ffmpeg", "-y"]
        # -y = écrase le fichier de sortie sans demander confirmation
        # POURQUOI une liste et pas une string ?
        # subprocess.run avec une liste gère automatiquement les espaces dans les chemins
        # Ex: "C:\mon dossier\fichier.wav" ne causerait pas de problème

        # --- Ajout de chaque segment audio comme input séparé ---
        for segment in stretched_segments:
            cmd += ["-i", segment["audio_path"]]
            # -i = input = fichier d'entrée
            # On ajoute un "-i fichier" pour chaque segment
            # ffmpeg leur assignera automatiquement les index 0, 1, 2, 3...

        # --- Construction du filter_complex ---
        # filter_complex = ensemble de filtres audio enchaînés
        # C'est la partie la plus complexe de la commande ffmpeg
        # Analogie : c'est comme le câblage d'une table de mixage audio

        filter_parts = []
        # Liste des filtres — on les assemblera avec ";" à la fin

        for i, segment in enumerate(stretched_segments):
            # enumerate() donne l'INDEX (i) et la VALEUR (segment)

            delay_ms = int(segment["start"] * 1000)
            # Conversion secondes → millisecondes
            # adelay attend des millisecondes
            # Ex: start=5.5s → delay_ms=5500ms

            filter_parts.append(
                f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]"
                # [{i}:a]         = flux audio de l'input numéro i
                #                   (i=0 → premier segment, i=1 → deuxième, etc.)
                # adelay={delay_ms}|{delay_ms}
                #                 = ajoute un silence de delay_ms ms au début
                #                   Le | sépare canal gauche et canal droit
                #                   On met la même valeur pour les deux = son centré
                # [a{i}]          = nom qu'on donne au flux de sortie de ce filtre
                #                   Ex: [a0], [a1], [a2]...
                # Exemple complet : "[0:a]adelay=0|0[a0]"
                #                   "[1:a]adelay=5500|5500[a1]"
            )

        # Mélange de tous les flux audio avec amix
        audio_inputs = "".join([f"[a{i}]" for i in range(len(stretched_segments))])
        # Construit la string "[a0][a1][a2]...[aN]"
        # C'est la liste des flux à mélanger

        filter_parts.append(
            f"{audio_inputs}amix=inputs={len(stretched_segments)}:"
            f"duration=longest:dropout_transition=0,"
            f"loudnorm=I=-16:TP=-1.5:LRA=11[audio_out]"
            # amix = mélange plusieurs flux audio en un seul
            # inputs={N} = nombre de flux à mélanger
            # duration=longest = la durée finale = celle du flux le plus long
            #   POURQUOI longest et pas first ?
            #   "first" = durée du premier segment (trop court)
            #   "longest" = durée du segment le plus long = couvre toute la vidéo
            # dropout_transition=0 = pas de fondu quand un flux se termine
            # loudnorm = normalisation du volume selon le standard EBU R128
            #   I=-16   = niveau sonore moyen cible (-16 LUFS = standard streaming)
            #   TP=-1.5 = pic maximum à -1.5 dB (évite la saturation)
            #   LRA=11  = plage dynamique cible (11 LU = naturel pour la voix)
            # [audio_out] = nom du flux de sortie final
        )

        filter_complex = ";".join(filter_parts)
        # On joint tous les filtres avec ";" = séparateur ffmpeg entre les filtres
        # Résultat ex:
        # "[0:a]adelay=0|0[a0];[1:a]adelay=5500|5500[a1];[a0][a1]amix=inputs=2:..."

        # --- Finalisation de la commande ---
        cmd += [
            "-filter_complex", filter_complex,

            "-map", "[audio_out]",
            # -map = dit à ffmpeg QUOI inclure dans le fichier de sortie
            # [audio_out] = notre piste audio assemblée et normalisée

            "-ar", "24000",
            # -ar = audio rate = fréquence d'échantillonnage de sortie
            # 24000 Hz = fréquence de Kokoro
            # On garde la même fréquence pour éviter toute conversion inutile

            "-ac", "1",
            # -ac = audio channels = nombre de canaux
            # 1 = mono (un seul canal)
            # POURQUOI mono ?
            # Kokoro génère du mono, pas besoin de stéréo pour la voix
            # Fichier plus léger

            "-t", str(total_duration),
            # -t = time = durée maximale du fichier de sortie en secondes
            # On limite à la durée de la vidéo originale
            # Évite que la piste audio soit plus longue que la vidéo

            output_path
            # Le fichier WAV de sortie final
        ]

        logger.info(f"Assemblage piste audio : {output_path}")

        # Exécution de la commande ffmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            # capture_output=True = on capture stdout ET stderr
            # Sans ça ffmpeg afficherait tout dans le terminal

            text=True
            # text=True = retourne des strings au lieu de bytes
        )

        if result.returncode != 0:
            # returncode != 0 = ffmpeg a rencontré une erreur
            # On prend les 500 derniers caractères de stderr car il peut être très long
            raise RuntimeError(f"ffmpeg erreur : {result.stderr[-500:]}")

        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Piste audio introuvable : {output_path}")

        logger.info(f"Piste audio assemblée avec succès : {output_path}")

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
                    