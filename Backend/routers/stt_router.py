# =============================================================================
# stt_router.py - Endpoints Speech-to-Text
# =============================================================================

import os
import uuid
import logging
from fastapi import APIRouter, HTTPException, File, UploadFile, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from stt.stt_service import transcribe_audio, get_supported_languages
from config import STT_UPLOAD_DIR, STT_MAX_FILE_SIZE_MB
from database import get_db
from models.job_stt import JobSTT
from models.user import User
from auth.dependencies import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stt")


# ── Fonction utilitaire nettoyage ─────────────────────────────────────────────

async def _cleanup_old_jobs_stt(user_id: str, db: AsyncSession) -> None:
    """Garde seulement les 5 derniers jobs STT pour un utilisateur."""
    result = await db.execute(
        select(JobSTT)
        .where(JobSTT.user_id == user_id)
        .order_by(desc(JobSTT.created_at))
    )
    jobs = result.scalars().all()

    if len(jobs) > 5:
        jobs_to_delete = jobs[5:]
        for job in jobs_to_delete:
            await db.delete(job)
        logger.info(f"Nettoyage historique STT : {len(jobs_to_delete)} job(s) supprimé(s)")


# ── Fonction utilitaire sauvegarde ────────────────────────────────────────────

async def _save_stt_history(
    user: User,
    filename: str,
    result: dict,
    db: AsyncSession
) -> None:
    """
    Sauvegarde un job STT dans l'historique de l'utilisateur.

    QU'EST-CE QUE C'EST : Fonction partagée par /upload et /record.
    POURQUOI séparée : évite la duplication de code entre les deux routes.
    """
    try:
        job = JobSTT(
            user_id=user.id,
            filename=filename,
            detected_language=result.get("language"),
            transcription_text=result.get("text", "")[:2000],
            # Limite à 2000 chars pour l'historique
            # La transcription complète peut être très longue
        )
        db.add(job)
        await db.flush()
        await _cleanup_old_jobs_stt(user.id, db)
        logger.info(f"Historique STT sauvegardé pour {user.email}")

    except Exception as e:
        logger.error(f"Erreur sauvegarde historique STT : {e}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/languages")
def list_stt_languages():
    """Retourne la liste des langues supportées par Faster-Whisper."""
    return {"success": True, "languages": get_supported_languages()}


@router.post("/upload")
async def speech_to_text_upload(
    file: UploadFile = File(...),
    language: str = "auto",
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
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

    # ── Sauvegarde historique (uniquement si connecté) ────────────────────────
    if current_user:
        await _save_stt_history(current_user, file.filename, result, db)

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
    language: str = "auto",
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
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

    # ── Sauvegarde historique (uniquement si connecté) ────────────────────────
    if current_user:
        await _save_stt_history(
            current_user,
            f"enregistrement_micro_{uuid.uuid4()[:8]}.webm",
            result,
            db
        )

    return {
        "success": True,
        "text": result["text"],
        "language": result["language"],
        "language_probability": result["language_probability"],
        "segments": result["segments"],
        "duration": result["duration"]
    }