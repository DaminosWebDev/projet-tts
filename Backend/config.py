import os
from dotenv import load_dotenv

# Charge le .env avant tout os.getenv() — une seule fois au démarrage
load_dotenv()


# =============================================================================
# SERVEUR
# =============================================================================

HOST = "0.0.0.0"   # Écoute sur toutes les interfaces réseau
PORT = 8000


# =============================================================================
# BASE DE DONNÉES
# =============================================================================

# Driver async — utilisé par SQLAlchemy dans FastAPI
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://tts_user:tts_password@localhost:5432/tts_db"
)

# Driver sync — utilisé par Alembic (ne supporte pas asyncpg)
DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://tts_user:tts_password@localhost:5432/tts_db"
)


# =============================================================================
# AUTHENTIFICATION JWT
# =============================================================================

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_this_in_production_please")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30   # Token court — requêtes API
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30     # Token long — renouvellement access token


# =============================================================================
# OAUTH GOOGLE
# =============================================================================

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/auth/google/callback"
)


# =============================================================================
# SENDGRID
# =============================================================================

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@tondomaine.com")
SENDGRID_FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "TTS App")

EMAIL_VERIFICATION_EXPIRE_HOURS = 24  # Lien de vérification email
PASSWORD_RESET_EXPIRE_HOURS = 1       # Lien reset — court pour limiter l'exposition


# =============================================================================
# KOKORO TTS
# =============================================================================

DEFAULT_VOICE_FR = "ff_siwis"
DEFAULT_VOICE_EN = "af_heart"
DEFAULT_SPEED = 1.0
MAX_TEXT_LENGTH = 2000
TTS_OUTPUT_DIR = "tts/outputs"
AUDIO_FORMAT = "wav"


# =============================================================================
# FASTER-WHISPER STT
# =============================================================================

STT_MODEL_SIZE = "small"
STT_DEVICE = "cuda"            # GPU — fallback "cpu" si pas de GPU disponible
STT_COMPUTE_TYPE = "float16"   # Précision réduite — plus rapide sur GPU
STT_MAX_FILE_SIZE_MB = 25
STT_UPLOAD_DIR = "stt/uploads"


# =============================================================================
# YOUTUBE
# =============================================================================

YOUTUBE_TEMP_DIR = "youtube/temp"
YOUTUBE_OUTPUT_DIR = "youtube/outputs"
YOUTUBE_WHISPER_MODEL = "medium"   # Modèle plus précis que STT standard


# =============================================================================
# LIBRETRANSLATE
# =============================================================================

LIBRETRANSLATE_URL = "http://localhost:5000"
LIBRETRANSLATE_API_KEY = ""


# =============================================================================
# AUDIO
# =============================================================================

STRETCH_TOLERANCE = 0.20   # Écart max autorisé lors du time-stretching (±20%)


# =============================================================================
# LOGS
# =============================================================================

LOG_LEVEL = "INFO"