import os
import logging

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from tts.tts_service import generate_audio, get_available_voices
from config import TTS_OUTPUT_DIR, MAX_TEXT_LENGTH
from database import get_db
from models.job_tts import JobTTS
from models.user import User
from auth.dependencies import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter()


class TTSRequest(BaseModel):
    text: str = Field(..., json_schema_extra={"example": "Bonjour, comment allez-vous ?"})
    language: str = Field(default="fr", json_schema_extra={"example": "fr"})
    voice: str = Field(default="", json_schema_extra={"example": "ff_siwis"})
    speed: float = Field(default=1.0, json_schema_extra={"example": 1.0})


@router.get("/voices")
def list_voices():
    # Sync — retourne une liste statique, pas d'I/O
    return {"success": True, "voices": get_available_voices()}


@router.post("/tts")
async def text_to_speech(
    request: TTSRequest,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    # Validations métier — au-delà de ce que Pydantic peut vérifier seul
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide")

    if len(request.text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Texte trop long : {len(request.text)} > {MAX_TEXT_LENGTH} caractères"
        )

    if request.language not in ["fr", "en"]:
        raise HTTPException(
            status_code=400,
            detail=f"Langue non supportée : '{request.language}'. Utilisez 'fr' ou 'en'"
        )

    result = generate_audio(
        text=request.text,
        language=request.language,
        voice=request.voice,
        speed=request.speed
    )

    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Erreur génération audio : {result['error']}")

    # Historique persisté uniquement pour les utilisateurs connectés
    if current_user:
        try:
            job = JobTTS(
                user_id=current_user.id,
                input_text=request.text[:500],  # Troncature — 2000 chars trop long pour l'historique
                voice=result.get("voice", request.voice) or request.voice,
                language=request.language,
                audio_url=f"/audio/{result['filename']}",
            )
            db.add(job)
            await db.flush()
            await _cleanup_old_jobs_tts(current_user.id, db)
            logger.info(f"Historique TTS sauvegardé : {current_user.email}")

        except Exception as e:
            # Échec silencieux — l'audio est déjà généré, ne pas bloquer la réponse
            logger.error(f"Erreur sauvegarde historique TTS : {e}")

    logger.info(f"Audio généré : {result['filename']}")

    # Headers personnalisés — expose les métadonnées au frontend sans corps JSON séparé
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


async def _cleanup_old_jobs_tts(user_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(JobTTS)
        .where(JobTTS.user_id == user_id)
        .order_by(desc(JobTTS.created_at))
    )
    jobs = result.scalars().all()

    if len(jobs) > 5:
        jobs_to_delete = jobs[5:]
        for job in jobs_to_delete:
            await db.delete(job)
        logger.info(f"Nettoyage TTS : {len(jobs_to_delete)} job(s) supprimé(s)")


@router.get("/audio/{filename}")
def download_audio(filename: str):
    filepath = os.path.join(TTS_OUTPUT_DIR, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Fichier '{filename}' introuvable")

    return FileResponse(path=filepath, media_type="audio/wav", filename=filename)