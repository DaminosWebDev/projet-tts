import os
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Logging initialisé en premier pour capturer les erreurs d'import éventuelles
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

from config import (
    HOST, PORT,
    TTS_OUTPUT_DIR, STT_UPLOAD_DIR,
    YOUTUBE_TEMP_DIR, YOUTUBE_OUTPUT_DIR
)

from database import engine

# Imports nécessaires pour enregistrer les modèles dans SQLAlchemy Base
from models.user import User           # noqa: F401
from models.job_youtube import JobYoutube  # noqa: F401
from models.job_tts import JobTTS      # noqa: F401
from models.job_stt import JobSTT      # noqa: F401

from routers.tts_router import router as tts_router
from routers.stt_router import router as sst_router
from routers.youtube_router import router as youtube_router
from routers.auth_router import router as auth_router
from routers.user_router import router as users_router

# Cycle de vie déclaré avant app pour pouvoir être passé en paramètre
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Création des répertoires de travail si absents
    for directory in [TTS_OUTPUT_DIR, STT_UPLOAD_DIR, YOUTUBE_TEMP_DIR, YOUTUBE_OUTPUT_DIR]:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Dossier prêt : {directory}")
    logger.info("Base de données connectée")

    yield  # Serveur actif — traitement des requêtes

    # Libération du pool de connexions PostgreSQL
    await engine.dispose()
    logger.info("Connexions base de données fermées")

app = FastAPI(
    title="Kokoro TTS API",
    description="API de synthèse vocale — TTS, STT, et traduction vidéo YouTube",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS permissif — à restreindre aux origines connues en production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enregistrement des routers — chaque domaine gère son propre préfixe
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tts_router)
app.include_router(sst_router)
app.include_router(youtube_router)

# Endpoint de santé — utilisé par les load balancers et outils de monitoring
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "L'API Kokoro TTS est opérationnelle",
        "version": "2.0.0"
    }

# Lancement direct uniquement en développement — en prod, uvicorn est appelé en CLI
if __name__ == "__main__":
    logger.info(f"Démarrage du serveur sur http://{HOST}:{PORT}")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)