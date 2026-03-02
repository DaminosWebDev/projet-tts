# =============================================================================
# stt_router.py - Endpoints Speech-to-Text
# =============================================================================

import os
import uuid
import logging
from fastapi import APIRouter, HTTPException, File, UploadFile
from stt.stt_service import transcribe_audio, get_supported_languages
from config import STT_UPLOAD_DIR, STT_MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stt")
# prefix="/stt" = tous les endpoints de ce router commencent par /stt
# Ex: @router.get("/languages") → accessible via GET /stt/languages


@router.get("/languages")
def list_stt_languages():
    """Retourne la liste des langues supportées par Faster-Whisper."""
    return {"success": True, "languages": get_supported_languages()}


@router.post("/upload")
async def speech_to_text_upload(
    file: UploadFile = File(...),
    language: str = "auto"
):
    """Transcrit un fichier audio uploadé."""
    logger.info(f"Upload STT | fichier={file.filename} | langue={language}")

    allowed_types = ["audio/wav", "audio/wave", "audio/mp3", "audio/mpeg",
                     "audio/ogg", "audio/webm", "audio/m4a"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Format non supporté : {file.content_type}")

    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)

    if file_size_mb > STT_MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"Fichier trop volumineux : {file_size_mb:.1f}MB > {STT_MAX_FILE_SIZE_MB}MB")

    unique_id = str(uuid.uuid4())[:8]
    extension = os.path.splitext(file.filename)[1] or ".wav"
    upload_filepath = os.path.join(STT_UPLOAD_DIR, f"upload_{unique_id}{extension}")

    with open(upload_filepath, "wb") as f:
        f.write(contents)

    language_param = None if language == "auto" else language
    result = transcribe_audio(upload_filepath, language=language_param)

    try:
        os.remove(upload_filepath)
    except Exception as e:
        logger.warning(f"Impossible de supprimer le fichier temporaire : {str(e)}")

    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Erreur transcription : {result['error']}")

    logger.info(f"Transcription réussie | langue={result['language']}")
    return {
        "success": True,
        "text": result["text"],
        "language": result["language"],
        "language_probability": result["language_probability"],
        "segments": result["segments"],
        "duration": result["duration"]
    }


@router.post("/record")
async def speech_to_text_record(
    file: UploadFile = File(...),
    language: str = "auto"
):
    """Transcrit un audio enregistré depuis le microphone."""
    logger.info(f"Enregistrement micro STT | langue={language}")

    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)

    if file_size_mb > STT_MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"Enregistrement trop volumineux : {file_size_mb:.1f}MB")

    unique_id = str(uuid.uuid4())[:8]
    upload_filepath = os.path.join(STT_UPLOAD_DIR, f"record_{unique_id}.webm")

    with open(upload_filepath, "wb") as f:
        f.write(contents)

    language_param = None if language == "auto" else language
    result = transcribe_audio(upload_filepath, language=language_param)

    try:
        os.remove(upload_filepath)
    except Exception as e:
        logger.warning(f"Impossible de supprimer l'enregistrement : {str(e)}")

    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Erreur transcription : {result['error']}")

    return {
        "success": True,
        "text": result["text"],
        "language": result["language"],
        "language_probability": result["language_probability"],
        "segments": result["segments"],
        "duration": result["duration"]
    }