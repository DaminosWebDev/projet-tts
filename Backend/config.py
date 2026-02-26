# config.py - Fichier de configuration centralisée de l'API
# Toutes les valeurs réglables sont ici, pas besoin de toucher aux autres fichiers pour les modifier

# --- Serveur ---
HOST = "0.0.0.0"       # Adresse d'écoute du serveur (0.0.0.0 = accessible depuis n'importe quelle adresse réseau)
PORT = 8000            # Port sur lequel l'API sera disponible (ex: http://localhost:8000)

# --- Modèle Kokoro ---
DEFAULT_VOICE_FR = "ff_siwis"   # Voix française par défaut (disponible dans Kokoro)
DEFAULT_VOICE_EN = "af_heart"   # Voix anglaise par défaut
DEFAULT_SPEED = 1.0              # Vitesse de lecture (1.0 = normale, 0.5 = lent, 2.0 = rapide)

# --- Limites ---
MAX_TEXT_LENGTH = 2000   # Nombre maximum de caractères acceptés dans une requête
                         # Evite les abus et les générations trop longues qui surchargent le modèle

# --- Stockage audio ---
AUDIO_DIR = "audio_files"   # Nom du dossier où les fichiers audio générés seront sauvegardés
AUDIO_FORMAT = "wav"        # Format des fichiers audio générés

# --- Logs ---
LOG_LEVEL = "INFO"   # Niveau de détail des logs : DEBUG (très verbeux) > INFO > WARNING > ERROR