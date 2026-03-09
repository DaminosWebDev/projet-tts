import os
import logging

import numpy as np
import soundfile as sf
import yt_dlp
from faster_whisper import WhisperModel

from tts.tts_service import get_pipeline_and_voice
from config import (
    YOUTUBE_TEMP_DIR,
    YOUTUBE_WHISPER_MODEL,
    STT_DEVICE,
    STT_COMPUTE_TYPE,
)

logger = logging.getLogger(__name__)

# Whisper medium — plus précis que small pour les timestamps de synchro
logger.info(f"Chargement Whisper YouTube ({YOUTUBE_WHISPER_MODEL})...")
youtube_whisper_model = WhisperModel(
    YOUTUBE_WHISPER_MODEL,
    device=STT_DEVICE,
    compute_type=STT_COMPUTE_TYPE
)
logger.info("Whisper YouTube prêt")

# Marqueurs non verbaux que Whisper génère — pas de TTS à produire pour ces segments
_NON_VERBAL_MARKERS = frozenset([
    "[music]", "[musique]", "[intro]", "[instrumental]",
    "[silence]", "[no speech]", "[background music]"
])


def download_youtube(url: str, job_id: str) -> dict:
    try:
        job_dir = os.path.join(YOUTUBE_TEMP_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)

        audio_path = os.path.join(job_dir, "audio.wav")

        logger.info(f"Téléchargement audio : {url}")

        audio_opts = {
            "format": "bestaudio/best",
            # Meilleur flux audio disponible — pas de vidéo téléchargée
            "outtmpl": os.path.join(job_dir, "audio.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",      # WAV sans perte — optimal pour Whisper
                "preferredquality": "192",
            }],
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # extract_info() télécharge ET retourne les métadonnées simultanément
            video_id = info.get("id", "")
            video_info = {
                "title":       info.get("title", "Sans titre"),
                "duration":    info.get("duration", 0),
                "channel":     info.get("channel", "Inconnu"),
                "video_id":    video_id,
                "youtube_url": url,
            }

        logger.info(f"Audio téléchargé : {video_info['title']} ({video_info['duration']}s)")

        if not os.path.exists(audio_path):
            # yt-dlp peut échouer silencieusement sans lever d'exception
            raise FileNotFoundError(f"WAV introuvable après téléchargement : {audio_path}")

        return {
            "success":     True,
            "job_dir":     job_dir,
            "audio_path":  audio_path,
            "youtube_url": video_info["youtube_url"],
            "video_id":    video_info["video_id"],
            "title":       video_info["title"],
            "duration":    video_info["duration"],
            "channel":     video_info["channel"],
            "error":       None
        }

    except Exception as e:
        logger.error(f"Erreur téléchargement YouTube : {e}")
        return {
            "success": False, "job_dir": None, "audio_path": None,
            "youtube_url": None, "video_id": None, "title": None,
            "duration": None, "channel": None, "error": str(e)
        }


def transcribe_youtube_audio(audio_path: str, source_language: str = None) -> dict:
    try:
        logger.info(f"Transcription : {audio_path} | langue={source_language or 'auto'}")

        segments, info = youtube_whisper_model.transcribe(
            audio_path,
            language=source_language,
            beam_size=5,
            word_timestamps=False  # Segments entiers — plus stables que le mot par mot
        )

        segments_list = []
        for segment in segments:
            segments_list.append({
                "start":    round(segment.start, 3),
                "end":      round(segment.end, 3),
                "text":     segment.text.strip(),
                "duration": round(segment.end - segment.start, 3)
                # Durée précalculée — évite le recalcul dans chaque étape suivante
            })

        if not segments_list:
            raise ValueError("Aucun segment transcrit — audio vide ou inaudible")

        logger.info(
            f"Transcription OK : {len(segments_list)} segments | "
            f"langue={info.language} ({info.language_probability:.0%})"
        )

        return {
            "success":              True,
            "segments":             segments_list,
            "language":             info.language,
            "language_probability": round(info.language_probability, 2),
            "error":                None
        }

    except Exception as e:
        logger.error(f"Erreur transcription YouTube : {e}")
        return {
            "success": False, "segments": [],
            "language": None, "language_probability": None, "error": str(e)
        }


def generate_tts_segments(
    translated_segments: list,
    job_dir: str,
    target_language: str = "fr",
    voice: str = "",
    speed: float = 1.0
) -> dict:
    try:
        segments_dir = os.path.join(job_dir, "segments")
        os.makedirs(segments_dir, exist_ok=True)

        pipeline, selected_voice = get_pipeline_and_voice(target_language, voice)
        logger.info(f"TTS {len(translated_segments)} segments | {target_language} | {selected_voice}")

        audio_segments = []

        for i, segment in enumerate(translated_segments):
            text_to_speak = segment["translated_text"]

            # Filtre les segments non verbaux — Whisper les génère souvent
            if not text_to_speak.strip() or text_to_speak.lower() in _NON_VERBAL_MARKERS:
                logger.info(f"Segment {i:03d} ignoré : '{text_to_speak[:60]}'")
                continue

            try:
                generator = pipeline(text_to_speak, voice=selected_voice, speed=speed)

                audio_chunks = []
                for (gs, ps, audio) in generator:
                    audio_chunks.append(audio)

                if not audio_chunks:
                    logger.warning(f"Segment {i:03d} : Kokoro n'a rien généré")
                    continue

                full_audio = np.concatenate(audio_chunks)

                # durée = échantillons / fréquence_échantillonnage (24000 Hz Kokoro)
                audio_duration = len(full_audio) / 24000

                segment_path = os.path.join(segments_dir, f"segment_{i:03d}.wav")
                sf.write(segment_path, full_audio, 24000)

                logger.info(
                    f"Segment {i:03d} | orig={segment['duration']:.2f}s | "
                    f"tts={audio_duration:.2f}s | '{text_to_speak[:40]}...'"
                )

                audio_segments.append({
                    "index":           i,
                    "start":          segment["start"],
                    "end":            segment["end"],
                    "duration":       segment["duration"],       # Durée ORIGINALE
                    "original_text":  segment["original_text"],
                    "translated_text": segment["translated_text"],
                    "audio_path":     segment_path,
                    "audio_duration": round(audio_duration, 3), # Durée TTS réelle
                })

            except Exception as e:
                # Échec d'un segment → on log et on continue
                # Un segment raté ne doit pas faire échouer toute la vidéo
                logger.error(f"Erreur segment {i:03d} : {e}")
                continue

        if not audio_segments:
            raise ValueError("Aucun segment audio généré")

        logger.info(f"TTS terminé : {len(audio_segments)}/{len(translated_segments)} segments")

        return {
            "success":       True,
            "segments_dir":  segments_dir,
            "audio_segments": audio_segments,
            "error":         None
        }

    except Exception as e:
        logger.error(f"Erreur génération TTS segments : {e}")
        return {
            "success": False, "segments_dir": None,
            "audio_segments": [], "error": str(e)
        }