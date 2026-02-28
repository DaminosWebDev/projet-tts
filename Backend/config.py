# config.py - Fichier de configuration centralisée de l'API
# Toutes les valeurs réglables sont ici, pas besoin de toucher aux autres fichiers pour les modifier

# --- Serveur ---
HOST = "0.0.0.0"       # Adresse d'écoute du serveur (0.0.0.0 = accessible depuis n'importe quelle adresse réseau)
PORT = 8000            # Port sur lequel l'API sera disponible (ex: http://localhost:8000)

# --- Modèle Kokoro (TTS) ---
DEFAULT_VOICE_FR = "ff_siwis"   # Voix française par défaut (disponible dans Kokoro)
DEFAULT_VOICE_EN = "af_heart"   # Voix anglaise par défaut
DEFAULT_SPEED = 1.0              # Vitesse de lecture (1.0 = normale, 0.5 = lent, 2.0 = rapide)

# --- Limites TTS ---
MAX_TEXT_LENGTH = 2000   # Nombre maximum de caractères acceptés dans une requête
                         # Evite les abus et les générations trop longues qui surchargent le modèle

# --- Stockage TTS ---
TTS_OUTPUT_DIR = "tts/outputs"  # Dossier où les fichiers audio générés par Kokoro sont sauvegardés
AUDIO_FORMAT = "wav"            # Format des fichiers audio générés

# --- Modèle Faster-Whisper (STT) ---
STT_MODEL_SIZE = "small"        # Taille du modèle : tiny, base, small, medium, large
                                # small = bon compromis vitesse/précision pour le français
STT_DEVICE = "cuda"             # "cuda" = GPU NVIDIA, "cpu" = processeur
                                # cuda est beaucoup plus rapide si tu as un GPU
STT_COMPUTE_TYPE = "float16"    # Précision des calculs sur GPU
                                # float16 = plus rapide, float32 = plus précis mais plus lent

# --- Limites STT ---
STT_MAX_FILE_SIZE_MB = 25       # Taille maximum des fichiers audio uploadés en MB
STT_UPLOAD_DIR = "stt/uploads"  # Dossier où les fichiers audio uploadés sont sauvegardés

# --- Logs ---
LOG_LEVEL = "INFO"   # Niveau de détail des logs : DEBUG (très verbeux) > INFO > WARNING > ERROR