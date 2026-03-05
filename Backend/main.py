# =============================================================================
# main.py - Point d'entrée de l'API
# =============================================================================
# Ce fichier est volontairement léger — il configure l'application
# et délègue les endpoints aux routers spécialisés.
# =============================================================================

import os
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# =============================================================================
# LOGGING — avant tout le reste
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIG — après logging, avant les services
# =============================================================================
from config import (
    HOST, PORT,
    TTS_OUTPUT_DIR, STT_UPLOAD_DIR,
    YOUTUBE_TEMP_DIR, YOUTUBE_OUTPUT_DIR
)

# =============================================================================
# ROUTERS — endpoints organisés par domaine
# =============================================================================
from routers.tts_router import router as tts_router
from routers.stt_router import router as stt_router
from routers.youtube_router import router as youtube_router

# =============================================================================
# APPLICATION
# =============================================================================
app = FastAPI(
    title="Kokoro TTS API",
    description="API de synthèse vocale — TTS, STT, et traduction vidéo YouTube",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# DOSSIERS — créés au démarrage si inexistants
# =============================================================================
for directory in [TTS_OUTPUT_DIR, STT_UPLOAD_DIR, YOUTUBE_TEMP_DIR, YOUTUBE_OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)
    logger.info(f"Dossier prêt : {directory}")

# =============================================================================
# INCLUSION DES ROUTERS
# =============================================================================
app.include_router(tts_router)
app.include_router(stt_router)
app.include_router(youtube_router)

# =============================================================================
# ENDPOINT DE SANTÉ
# =============================================================================
@app.get("/health")
def health_check():
    """Vérifie que l'API est opérationnelle."""
    return {"status": "ok", "message": "L'API Kokoro TTS est opérationnelle"}

# =============================================================================
# POINT D'ENTRÉE
# =============================================================================
if __name__ == "__main__":
    logger.info(f"Démarrage du serveur sur http://{HOST}:{PORT}")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)