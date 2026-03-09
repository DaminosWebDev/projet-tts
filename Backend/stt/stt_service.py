import logging
import time

from faster_whisper import WhisperModel
from config import STT_MODEL_SIZE, STT_DEVICE, STT_COMPUTE_TYPE

logger = logging.getLogger(__name__)

# Chargement unique au démarrage — Whisper small ~465MB téléchargé depuis HuggingFace
logger.info(f"Chargement Faster-Whisper ({STT_MODEL_SIZE})...")
stt_model = WhisperModel(
    STT_MODEL_SIZE,
    device=STT_DEVICE,
    compute_type=STT_COMPUTE_TYPE
)
logger.info("Faster-Whisper prêt")


def transcribe_audio(filepath: str, language: str = None) -> dict:
    start_time = time.time()

    try:
        logger.info(f"Transcription : {filepath} | langue={language or 'auto'}")

        # transcribe() retourne un générateur de segments + des infos sur l'audio
        segments, info = stt_model.transcribe(
            filepath,
            language=language,      # None = détection automatique de la langue
            beam_size=5,            # Précision vs vitesse — 5 est le standard
            word_timestamps=True    # Timestamps mot par mot — utile pour la synchro vidéo
        )

        # Consommation du générateur — les segments ne sont calculés qu'à l'itération
        segments_list = []
        full_text = ""

        for segment in segments:
            segments_list.append({
                "start": round(segment.start, 2),
                "end":   round(segment.end, 2),
                "text":  segment.text.strip()
            })
            full_text += segment.text

        full_text = full_text.strip()

        if not full_text:
            raise ValueError("Aucun texte transcrit — audio vide ou inaudible")

        duration = round(time.time() - start_time, 2)
        logger.info(f"Transcription réussie en {duration}s | langue={info.language}")

        return {
            "success":              True,
            "text":                 full_text,
            "language":             info.language,
            "language_probability": round(info.language_probability, 2),
            "segments":             segments_list,
            "duration":             duration,
            "error":                None
        }

    except Exception as e:
        duration = round(time.time() - start_time, 2)
        logger.error(f"Erreur transcription : {e}")

        return {
            "success":              False,
            "text":                 None,
            "language":             None,
            "language_probability": None,
            "segments":             [],
            "duration":             duration,
            "error":                str(e)
        }


def get_supported_languages() -> list:
    # Sous-ensemble des 99 langues Whisper — uniquement celles exposées par l'API
    return [
        {"code": "fr",   "label": "Français"},
        {"code": "en",   "label": "English"},
        {"code": "auto", "label": "Détection automatique"}
    ]