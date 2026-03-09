import os
import sys
import logging
import uuid
import time

import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from kokoro import KPipeline

from config import (
    DEFAULT_VOICE_FR,
    DEFAULT_VOICE_EN,
    DEFAULT_SPEED,
    TTS_OUTPUT_DIR,
    AUDIO_FORMAT
)

# Chargement du token HuggingFace avant l'initialisation des pipelines
load_dotenv()
os.environ["HF_TOKEN"] = os.getenv("HF_TOKEN", "")

logger = logging.getLogger(__name__)

# Chargement unique au démarrage — modèle 82M paramètres téléchargé depuis HuggingFace
logger.info("Chargement des pipelines Kokoro...")
pipeline_fr = KPipeline(lang_code='f', repo_id='hexgrad/Kokoro-82M')
pipeline_en = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
logger.info("Pipelines Kokoro chargés")

# Voix disponibles par langue — exposées via GET /voices
AVAILABLE_VOICES = {
    "fr": ["ff_siwis"],
    "en": ["af_heart", "af_bella", "af_sarah", "af_sky",
           "am_adam", "am_michael", "bf_emma", "bf_isabella",
           "bm_george", "bm_lewis"]
}


def get_pipeline_and_voice(language: str, voice: str) -> tuple:
    # Centralisé ici — évite le if/else répété dans generate_audio et generate_tts_segments
    if language == "fr":
        return pipeline_fr, voice or DEFAULT_VOICE_FR
    else:
        # Tout ce qui n'est pas "fr" → pipeline anglais
        return pipeline_en, voice or DEFAULT_VOICE_EN


def generate_audio(
    text: str,
    language: str = "fr",
    voice: str = "",
    speed: float = DEFAULT_SPEED
) -> dict:
    start_time = time.time()

    try:
        pipeline, selected_voice = get_pipeline_and_voice(language, voice)
        logger.info(f"TTS | langue={language} | voix={selected_voice} | texte={text[:50]}...")

        # Kokoro retourne un générateur — chaque itération produit un chunk audio
        generator = pipeline(text, voice=selected_voice, speed=speed)

        audio_chunks = []
        for (gs, ps, audio) in generator:
            # gs = graphèmes (texte du chunk), ps = phonèmes, audio = numpy array
            audio_chunks.append(audio)

        if not audio_chunks:
            raise ValueError("Aucun audio généré — texte vide ou erreur Kokoro")

        # Assemblage de tous les chunks en un seul tableau continu
        full_audio = np.concatenate(audio_chunks)

        # Nom de fichier unique — évite les collisions entre requêtes simultanées
        unique_id = str(uuid.uuid4())[:8]
        filename = f"audio_{unique_id}.{AUDIO_FORMAT}"
        filepath = os.path.join(TTS_OUTPUT_DIR, filename)

        # 24000 Hz = fréquence d'échantillonnage native de Kokoro
        sf.write(filepath, full_audio, 24000)

        duration = round(time.time() - start_time, 2)
        logger.info(f"Audio généré : {filename} en {duration}s")

        return {
            "success":  True,
            "filename": filename,
            "filepath": filepath,
            "voice":    selected_voice,
            "duration": duration,
            "error":    None
        }

    except Exception as e:
        duration = round(time.time() - start_time, 2)
        logger.error(f"Erreur génération audio : {e}")

        return {
            "success":  False,
            "filename": None,
            "filepath": None,
            "voice":    None,
            "duration": duration,
            "error":    str(e)
        }


def get_available_voices() -> dict:
    return AVAILABLE_VOICES