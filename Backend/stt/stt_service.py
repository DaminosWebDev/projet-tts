# stt_service.py - Le moteur Speech-to-Text
# Ce fichier s'occupe uniquement de Faster-Whisper : charger le modèle et transcrire l'audio
# main.py appellera les fonctions d'ici sans savoir comment Faster-Whisper fonctionne

import sys
import os
import logging
import time

from faster_whisper import WhisperModel
from config import (
    STT_MODEL_SIZE,
    STT_DEVICE,
    STT_COMPUTE_TYPE,
    STT_UPLOAD_DIR
)

# --- Configuration des logs ---
logger = logging.getLogger(__name__)

# --- Chargement du modèle Faster-Whisper ---
# Comme pour Kokoro, on charge le modèle UNE SEULE FOIS au démarrage
# Le modèle "small" fait ~465MB, il sera téléchargé automatiquement
# depuis HuggingFace la première fois
logger.info(f"Chargement du modèle Faster-Whisper ({STT_MODEL_SIZE})...")

stt_model = WhisperModel(
    STT_MODEL_SIZE,
    device=STT_DEVICE,          # "cuda" pour GPU, "cpu" pour processeur
    compute_type=STT_COMPUTE_TYPE  # "float16" pour GPU, "int8" pour CPU
)

logger.info("Modèle Faster-Whisper chargé !")


def transcribe_audio(filepath: str, language: str = None) -> dict:
    """
    Fonction principale : prend un fichier audio et retourne sa transcription.

    Paramètres :
    - filepath : chemin vers le fichier audio à transcrire
    - language : langue de l'audio ("fr", "en", ou None pour détection automatique)
                 None = Faster-Whisper détecte automatiquement la langue

    Retourne un dictionnaire avec :
    - "success"     : True si tout s'est bien passé
    - "text"        : le texte transcrit complet
    - "language"    : la langue détectée
    - "segments"    : liste des segments avec timestamps
    - "duration"    : temps de transcription en secondes
    - "error"       : message d'erreur si success = False
    """

    start_time = time.time()

    try:
        logger.info(f"Transcription de : {filepath} | langue={language or 'auto'}")

        # --- Transcription avec Faster-Whisper ---
        # transcribe() retourne deux choses :
        # - segments : un générateur de morceaux de texte avec timestamps
        # - info     : informations sur l'audio (langue détectée, durée...)
        segments, info = stt_model.transcribe(
            filepath,
            language=language,      # None = détection automatique
            beam_size=5,            # Nombre de candidats explorés à chaque étape
                                    # Plus c'est élevé, plus c'est précis mais lent
                                    # 5 est un bon compromis
            word_timestamps=True    # Retourne les timestamps mot par mot
                                    # Utile pour la synchronisation vidéo plus tard !
        )

        # --- Assemblage des segments ---
        # segments est un générateur, on doit l'itérer pour obtenir les données
        segments_list = []
        full_text = ""

        for segment in segments:
            # Chaque segment contient :
            # - segment.start : timestamp de début en secondes
            # - segment.end   : timestamp de fin en secondes
            # - segment.text  : le texte du segment
            segment_data = {
                "start": round(segment.start, 2),   # Ex: 2.30
                "end": round(segment.end, 2),        # Ex: 5.45
                "text": segment.text.strip()         # Ex: "Bonjour tout le monde"
            }
            segments_list.append(segment_data)
            full_text += segment.text

        # On nettoie le texte complet (espaces superflus, etc.)
        full_text = full_text.strip()

        if not full_text:
            raise ValueError("Aucun texte transcrit - le fichier audio est peut-être vide ou inaudible")

        duration = round(time.time() - start_time, 2)
        logger.info(f"Transcription réussie en {duration}s | langue détectée={info.language}")

        return {
            "success": True,
            "text": full_text,
            "language": info.language,          # Langue détectée automatiquement
            "language_probability": round(info.language_probability, 2),
            # language_probability = niveau de confiance de la détection (0 à 1)
            # Ex: 0.98 = Faster-Whisper est sûr à 98% que c'est du français
            "segments": segments_list,          # Liste des segments avec timestamps
            "duration": duration,
            "error": None
        }

    except Exception as e:
        duration = round(time.time() - start_time, 2)
        logger.error(f"Erreur lors de la transcription : {str(e)}")

        return {
            "success": False,
            "text": None,
            "language": None,
            "language_probability": None,
            "segments": [],
            "duration": duration,
            "error": str(e)
        }


def get_supported_languages() -> list:
    """
    Retourne la liste des langues supportées par Faster-Whisper.
    Faster-Whisper supporte 99 langues !
    On retourne uniquement celles qu'on supporte dans notre app pour l'instant.
    """
    return [
        {"code": "fr", "label": "Français"},
        {"code": "en", "label": "English"},
        {"code": "auto", "label": "Détection automatique"}
    ]