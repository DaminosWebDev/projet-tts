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
# FONCTION 2 : assemble_video()
# Assemble la vidéo muette + les segments audio TTS avec ffmpeg
# =============================================================================

def assemble_video(
    video_path: str,
    audio_segments: list,
    job_id: str,
    job_dir: str
) -> dict:
    """
    Assemble la vidéo finale :
    1. Applique le time-stretching sur chaque segment audio
    2. Crée une piste audio complète en plaçant chaque segment
       au bon timestamp
    3. Combine la vidéo muette + la piste audio → .mp4 final

    COMMENT FFMPEG POSITIONNE L'AUDIO ?
    On utilise le filtre "adelay" de ffmpeg qui ajoute un délai
    au début d'un fichier audio.
    Ex: segment_000.wav avec adelay=5000ms → commence à t=5s
    Ensuite "amix" mélange tous les segments sur une seule piste.

    Paramètres :
    ------------
    video_path : str
        Chemin vers la vidéo SANS son (téléchargée à l'étape B)

    audio_segments : list
        Liste des segments audio de generate_tts_segments()
        Chaque segment contient audio_path, start, end, duration

    job_id : str
        Identifiant du job (pour nommer le fichier final)

    job_dir : str
        Dossier de travail du job

    Retourne : dict
    ---------------
    {
        "success": True,
        "output_path": "youtube/outputs/video_a3f8c2d1.mp4",
        "error": None
    }
    """

    try:
        # -----------------------------------------------------------------
        # Étape 1 : Time-stretching de tous les segments
        # -----------------------------------------------------------------
        stretched_dir = os.path.join(job_dir, "stretched")
        os.makedirs(stretched_dir, exist_ok=True)
        # Dossier séparé pour les fichiers après stretching
        # youtube/temp/a3f8c2d1/stretched/

        logger.info(f"Time-stretching de {len(audio_segments)} segments...")

        stretched_segments = []
        for segment in audio_segments:
            stretched_path = os.path.join(
                stretched_dir,
                f"stretched_{segment['index']:03d}.wav"
            )

            stretch_result = stretch_audio_segment(
                audio_path=segment["audio_path"],
                # Le fichier WAV généré par Kokoro à l'étape E

                target_duration=segment["duration"],
                # La durée ORIGINALE du segment dans la vidéo
                # C'est la durée cible après stretching

                output_path=stretched_path
            )

            if stretch_result["success"]:
                stretched_segments.append({
                    **segment,
                    # ** = décompresse le dict segment
                    # Copie toutes les clés/valeurs existantes
                    # Puis on ajoute/remplace avec les nouvelles valeurs

                    "audio_path": stretch_result["output_path"],
                    # On remplace le chemin par le fichier stretchéé
                    "stretched": stretch_result["stretched"]
                })
            else:
                # Si le stretching échoue, on utilise l'audio original
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
        # C'est la partie la plus complexe — on construit une commande
        # ffmpeg avec plusieurs inputs et filtres audio

        output_path = os.path.join(YOUTUBE_OUTPUT_DIR, f"video_{job_id}.mp4")

        # On commence à construire la commande ffmpeg
        # Structure : ffmpeg -i video.mp4 -i seg1.wav -i seg2.wav ...
        #             -filter_complex "..." -map 0:v -map "[audio_out]"
        #             output.mp4

        cmd = ["ffmpeg", "-y"]
        # -y = écrase le fichier de sortie sans confirmation

        # --- Ajout de la vidéo muette comme premier input ---
        cmd += ["-i", video_path]
        # L'index de cet input sera 0 dans le filtre_complex

        # --- Ajout de chaque segment audio comme input séparé ---
        for segment in stretched_segments:
            cmd += ["-i", segment["audio_path"]]
        # Les segments auront les index 1, 2, 3, ... dans filter_complex

        # --- Construction du filter_complex ---
        # filter_complex = ensemble de filtres audio/vidéo enchaînés
        # C'est comme un câblage de studio d'enregistrement

        filter_parts = []
        # Liste des filtres, on les assemblera en string à la fin

        for i, segment in enumerate(stretched_segments):
            input_index = i + 1
            # +1 car l'index 0 est la vidéo, les audios commencent à 1

            delay_ms = int(segment["start"] * 1000)
            # Conversion des secondes en millisecondes
            # adelay attend des millisecondes
            # Ex: start=5.5s → delay_ms=5500ms

            filter_parts.append(
                f"[{input_index}:a]adelay={delay_ms}|{delay_ms}[a{i}]"
                # [{input_index}:a] = flux audio de l'input {input_index}
                # adelay={delay_ms}|{delay_ms} = délai en ms pour canal gauche|droit
                # [a{i}] = nom du flux de sortie de ce filtre
                # Ex: "[1:a]adelay=5500|5500[a0]"
            )

        # Mélange de tous les flux audio avec amix
        audio_inputs = "".join([f"[a{i}]" for i in range(len(stretched_segments))])
        # Construit : "[a0][a1][a2]...[aN]"

        filter_parts.append(
            f"{audio_inputs}amix=inputs={len(stretched_segments)}:"
            f"duration=longest:dropout_transition=0,"
            f"volume=4.0,"              # ← boost ×4 (tu peux tester 3.0 à 6.0)
            f"loudnorm=I=-16:TP=-1.5:LRA=11[audio_out]"   # normalisation EBU R128 (standard YouTube)
            # amix = mélange plusieurs flux audio en un seul
            # inputs = nombre de flux à mélanger
            # duration=longest = la durée est celle du flux le plus long
            # dropout_transition=0 = pas de transition en fondu
            # [audio_out] = nom du flux de sortie final
        )

        filter_complex = ";".join(filter_parts)
        # On joint tous les filtres avec ";" = séparateur ffmpeg

        # --- Finalisation de la commande ---
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "0:v",
            # -map 0:v = utilise le flux vidéo de l'input 0 (la vidéo)

            "-map", "[audio_out]",
            # -map [audio_out] = utilise notre piste audio assemblée

            "-c:v", "copy",
            # -c:v copy = copie le flux vidéo sans ré-encoder
            # Beaucoup plus rapide et sans perte de qualité

            "-c:a", "aac",
            # -c:a aac = encode l'audio en AAC
            # AAC = format audio standard pour les fichiers MP4

            "-shortest",
            # -shortest = arrête quand le flux le plus court se termine
            # Évite que la vidéo dure trop longtemps si l'audio déborde

            output_path
        ]

        logger.info(f"Assemblage vidéo finale : {output_path}")

        # Exécution de la commande ffmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg assemblage erreur : {result.stderr[-500:]}")
            # [-500:] = on prend seulement les 500 derniers caractères
            # stderr peut être très long, on garde l'essentiel

        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Vidéo finale introuvable : {output_path}")

        logger.info(f"Vidéo finale assemblée avec succès : {output_path}")

        return {
            "success": True,
            "output_path": output_path,
            "error": None
        }

    except Exception as e:
        logger.error(f"Erreur assemblage vidéo : {str(e)}")
        return {
            "success": False,
            "output_path": None,
            "error": str(e)
        }
                    