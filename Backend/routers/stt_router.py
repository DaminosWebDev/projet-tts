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


async def _cleanup_old_jobs_stt(user_id: str, db: AsyncSession) -> None:
    # Conserve uniquement les 5 jobs les plus récents — tri par date décroissante
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
        logger.info(f"Nettoyage STT : {len(jobs_to_delete)} job(s) supprimé(s)")


async def _save_stt_history(
    user: User,
    filename: str,
    result: dict,
    db: AsyncSession
) -> None:
    try:
        job = JobSTT(
            user_id=user.id,
            filename=filename,
            detected_language=result.get("language"),
            transcription_text=result.get("text", "")[:2000],  # Troncature pour l'historique
        )
        db.add(job)
        await db.flush()
        await _cleanup_old_jobs_stt(user.id, db)
        logger.info(f"Historique STT sauvegardé : {user.email}")

    except Exception as e:
        logger.error(f"Erreur sauvegarde historique STT : {e}")
        # Échec silencieux — la transcription est déjà retournée au client


@router.get("/languages")
def list_stt_languages():
    # Fonction sync — get_supported_languages() ne fait pas d'I/O
    return {"success": True, "languages": get_supported_languages()}


@router.post("/upload")
async def speech_to_text_upload(
    file: UploadFile = File(...),
    language: str = "auto",
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Upload STT | fichier={file.filename} | langue={language}")

    # Validation du type MIME — liste blanche explicite
    allowed_types = [
        "audio/wav", "audio/wave", "audio/mp3", "audio/mpeg",
        "audio/ogg", "audio/webm", "audio/m4a"
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Format non supporté : {file.content_type}")

    # Lecture complète en mémoire pour vérifier la taille avant écriture sur disque
    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)

    if file_size_mb > STT_MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Fichier trop volumineux : {file_size_mb:.1f}MB > {STT_MAX_FILE_SIZE_MB}MB"
        )

    # Nom de fichier unique — évite les collisions entre requêtes simultanées
    unique_id = str(uuid.uuid4())[:8]
    extension = os.path.splitext(file.filename)[1] or ".wav"
    upload_filepath = os.path.join(STT_UPLOAD_DIR, f"upload_{unique_id}{extension}")

    with open(upload_filepath, "wb") as f:
        f.write(contents)

    # "auto" → None pour Whisper qui interprète None comme détection automatique
    language_param = None if language == "auto" else language
    result = transcribe_audio(upload_filepath, language=language_param)

    # Nettoyage du fichier temporaire — même en cas d'erreur de transcription
    try:
        os.remove(upload_filepath)
    except Exception as e:
        logger.warning(f"Fichier temporaire non supprimé : {e}")

    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Erreur transcription : {result['error']}")

    # Sauvegarde historique uniquement pour les utilisateurs connectés
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
    logger.info(f"Enregistrement micro STT | langue={language}")

    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)

    if file_size_mb > STT_MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Enregistrement trop volumineux : {file_size_mb:.1f}MB"
        )

    unique_id = str(uuid.uuid4())[:8]
    upload_filepath = os.path.join(STT_UPLOAD_DIR, f"record_{unique_id}.webm")

    with open(upload_filepath, "wb") as f:
        f.write(contents)

    language_param = None if language == "auto" else language
    result = transcribe_audio(upload_filepath, language=language_param)

    try:
        os.remove(upload_filepath)
    except Exception as e:
        logger.warning(f"Enregistrement temporaire non supprimé : {e}")

    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Erreur transcription : {result['error']}")

    if current_user:
        await _save_stt_history(
            current_user,
            f"enregistrement_micro_{str(uuid.uuid4())[:8]}.webm",
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