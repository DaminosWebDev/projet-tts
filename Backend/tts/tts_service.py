# tts_service.py - Le "moteur" de notre API
# Ce fichier s'occupe uniquement de Kokoro : charger les modèles et générer l'audio
# main.py appellera les fonctions d'ici sans avoir besoin de savoir comment Kokoro fonctionne

from dotenv import load_dotenv
import sys
import os
import logging
import uuid
import time
import soundfile as sf
from kokoro import KPipeline

from config import (
    DEFAULT_VOICE_FR,
    DEFAULT_VOICE_EN,
    DEFAULT_SPEED,
    TTS_OUTPUT_DIR,
    AUDIO_FORMAT
)


load_dotenv()
os.environ["HF_TOKEN"] = os.getenv("HF_TOKEN", "")

logger = logging.getLogger(__name__)

logger.info("Chargement des pipelines Kokoro...")

pipeline_fr = KPipeline(lang_code='f', repo_id='hexgrad/Kokoro-82M')
logger.info("Pipeline français chargé")

pipeline_en = KPipeline(lang_code='a')
logger.info("Pipeline anglais chargé")

AVAILABLE_VOICES = {
    "fr": ["ff_siwis"],
    "en": ["af_heart", "af_bella", "af_sarah", "af_sky", "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis"]
}


def get_pipeline_and_voice(language: str, voice: str):
    """
    Retourne le bon pipeline et la bonne voix selon la langue choisie.
    
    C'est une fonction utilitaire (helper) : elle évite de répéter 
    la même logique if/else dans plusieurs endroits du code.
    
    Paramètres :
    - language : "fr" ou "en"
    - voice : nom de la voix, ou "" pour utiliser la voix par défaut
    """
    if language == "fr":
        # Si aucune voix spécifiée, on utilise la voix française par défaut de config.py
        selected_voice = voice if voice else DEFAULT_VOICE_FR
        return pipeline_fr, selected_voice
    else:
        # Pour tout ce qui n'est pas français, on utilise le pipeline anglais
        selected_voice = voice if voice else DEFAULT_VOICE_EN
        return pipeline_en, selected_voice


def generate_audio(text: str, language: str = "fr", voice: str = "", speed: float = DEFAULT_SPEED) -> dict:
    """
    Fonction principale : prend un texte et génère un fichier audio.
    
    C'est CETTE fonction que main.py appellera quand une requête arrive sur /tts
    
    Paramètres :
    - text     : le texte à transformer en audio
    - language : la langue ("fr" ou "en"), "fr" par défaut
    - voice    : la voix à utiliser, voix par défaut si vide
    - speed    : la vitesse de lecture (1.0 = normale)
    
    Retourne un dictionnaire avec :
    - "success"   : True si tout s'est bien passé, False sinon
    - "filename"  : le nom du fichier audio généré
    - "filepath"  : le chemin complet vers le fichier
    - "duration"  : le temps de génération en secondes
    - "error"     : le message d'erreur si success = False
    """
    
    start_time = time.time()  # On note l'heure de début pour mesurer la durée

    try:
        # --- Sélection du pipeline et de la voix ---
        pipeline, selected_voice = get_pipeline_and_voice(language, voice)
        logger.info(f"Génération audio | langue={language} | voix={selected_voice} | texte={text[:50]}...")
        # On affiche seulement les 50 premiers caractères du texte dans les logs
        # pour ne pas les surcharger avec des textes très longs

        # --- Génération de l'audio avec Kokoro ---
        # pipeline() retourne un générateur (comme dans ton test.py)
        # Kokoro découpe automatiquement les textes longs en "chunks"
        # et génère un morceau audio pour chaque chunk
        generator = pipeline(text, voice=selected_voice, speed=speed)

        # --- Assemblage des chunks audio ---
        import numpy as np
        audio_chunks = []  # Liste pour stocker tous les morceaux audio

        for (gs, ps, audio) in generator:
            # gs = graphemes (texte original du chunk)
            # ps = phonemes (représentation phonétique)
            # audio = le tableau numpy contenant les données audio
            audio_chunks.append(audio)

        if not audio_chunks:
            # Si Kokoro n'a rien généré (texte vide ou problème)
            raise ValueError("Kokoro n'a généré aucun audio")

        # On assemble tous les morceaux en un seul tableau audio
        # np.concatenate colle les tableaux numpy bout à bout
        full_audio = np.concatenate(audio_chunks)

        # --- Sauvegarde du fichier audio ---
        # uuid4() génère un identifiant unique aléatoire (ex: "a3f8c2d1-...")
        # Ça évite d'avoir des conflits si deux utilisateurs génèrent en même temps
        unique_id = str(uuid.uuid4())[:8]  # On prend seulement les 8 premiers caractères
        filename = f"audio_{unique_id}.{AUDIO_FORMAT}"
        filepath = os.path.join(TTS_OUTPUT_DIR, filename)
        # os.path.join construit le chemin correct selon l'OS
        # Sur Windows : "audio_files\audio_a3f8c2d1.wav"
        # Sur Linux   : "audio_files/audio_a3f8c2d1.wav"

        # Sauvegarde du fichier WAV (24000 = fréquence d'échantillonnage de Kokoro)
        sf.write(filepath, full_audio, 24000)

        duration = round(time.time() - start_time, 2)  # Durée en secondes, arrondie à 2 décimales
        logger.info(f"Audio généré avec succès : {filename} en {duration}s")

        return {
            "success": True,
            "filename": filename,
            "filepath": filepath,
            "duration": duration,
            "error": None
        }

    except Exception as e:
        # --- Gestion des erreurs ---
        # Si QUOI QUE CE SOIT plante dans le try{}, on arrive ici
        # On logue l'erreur et on retourne un dictionnaire d'échec
        # L'API ne plantera pas, elle retournera une réponse d'erreur propre
        duration = round(time.time() - start_time, 2)
        logger.error(f"Erreur lors de la génération audio : {str(e)}")
        
        return {
            "success": False,
            "filename": None,
            "filepath": None,
            "duration": duration,
            "error": str(e)  # str(e) convertit l'erreur en texte lisible
        }


def get_available_voices() -> dict:
    """
    Retourne la liste des voix disponibles par langue.
    Cette fonction sera appelée par un endpoint /voices dans main.py
    pour que le frontend puisse afficher les voix disponibles à l'utilisateur.
    """
    return AVAILABLE_VOICES