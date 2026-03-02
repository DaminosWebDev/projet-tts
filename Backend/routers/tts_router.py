# =============================================================================
# tts_router.py - Endpoints Text-to-Speech
# =============================================================================

import os
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from tts.tts_service import generate_audio, get_available_voices
from config import TTS_OUTPUT_DIR, MAX_TEXT_LENGTH

logger = logging.getLogger(__name__)

router = APIRouter()
# APIRouter = version "modulaire" de FastAPI
# On définit les endpoints ici, et main.py les inclut avec app.include_router()


class TTSRequest(BaseModel):
    text: str = Field(..., json_schema_extra={"example": "Bonjour, comment allez-vous ?"})
    language: str = Field(default="fr", json_schema_extra={"example": "fr"})
    voice: str = Field(default="", json_schema_extra={"example": "ff_siwis"})
    speed: float = Field(default=1.0, json_schema_extra={"example": 1.0})


@router.get("/voices")
def list_voices():
    """Retourne la liste de toutes les voix disponibles."""
    return {"success": True, "voices": get_available_voices()}


@router.post("/tts")
def text_to_speech(request: TTSRequest):
    """Convertit un texte en fichier audio WAV."""
    logger.info(f"Requête TTS | langue={request.language} | texte={request.text[:50]}...")

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide")

    if len(request.text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=400, detail=f"Texte trop long : {len(request.text)} > {MAX_TEXT_LENGTH} caractères")

    if request.language not in ["fr", "en"]:
        raise HTTPException(status_code=400, detail=f"Langue non supportée : '{request.language}'. Utilisez 'fr' ou 'en'")

    result = generate_audio(
        text=request.text,
        language=request.language,
        voice=request.voice,
        speed=request.speed
    )

    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Erreur génération audio : {result['error']}")

    logger.info(f"Audio généré : {result['filename']}")
    return FileResponse(
        path=result["filepath"],
        media_type="audio/wav",
        filename=result["filename"],
        headers={
            "X-Generation-Duration": str(result["duration"]),
            "X-Audio-Filename": result["filename"],
            "Access-Control-Expose-Headers": "X-Generation-Duration, X-Audio-Filename, Content-Disposition"
        }
    )


@router.get("/audio/{filename}")
def download_audio(filename: str):
    """Télécharge un fichier audio précédemment généré."""
    filepath = os.path.join(TTS_OUTPUT_DIR, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Fichier '{filename}' introuvable")

    return FileResponse(path=filepath, media_type="audio/wav", filename=filename)