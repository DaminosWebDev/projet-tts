# =============================================================================
# tts_router.py - Endpoints Text-to-Speech
# =============================================================================

import os
import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tts.tts_service import generate_audio, get_available_voices
from config import TTS_OUTPUT_DIR, MAX_TEXT_LENGTH
from database import get_db
from models.job_tts import JobTTS
from models.user import User
from auth.dependencies import get_optional_user
# get_optional_user → retourne l'user si connecté, None si anonyme
# Pas get_current_user → on ne force pas la connexion

logger = logging.getLogger(__name__)
router = APIRouter()


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
async def text_to_speech(
    request: TTSRequest,
    current_user: User | None = Depends(get_optional_user),
    # current_user = User si connecté, None si anonyme
    # Même comportement qu'avant pour les anonymes
    db: AsyncSession = Depends(get_db)
):
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

    # ── Sauvegarde historique (uniquement si connecté) ────────────────────────
    if current_user:
        try:
            # Construire l'URL audio accessible depuis le frontend
            audio_url = f"/audio/{result['filename']}"

            job = JobTTS(
                user_id=current_user.id,
                input_text=request.text[:500],
                # On limite à 500 chars pour l'historique
                # Le texte complet peut faire 2000 chars → trop long à afficher
                voice=result.get("voice", request.voice) or request.voice,
                language=request.language,
                audio_url=audio_url,
            )
            db.add(job)
            await db.flush()

            # Garder seulement les 5 derniers jobs TTS pour cet utilisateur
            await _cleanup_old_jobs_tts(current_user.id, db)

            logger.info(f"Historique TTS sauvegardé pour {current_user.email}")

        except Exception as e:
            # Si la sauvegarde échoue → on log mais on ne bloque pas la réponse
            # L'audio a déjà été généré → l'utilisateur doit le recevoir quoi qu'il arrive
            logger.error(f"Erreur sauvegarde historique TTS : {e}")

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


async def _cleanup_old_jobs_tts(user_id: str, db: AsyncSession) -> None:
    """
    Garde seulement les 5 derniers jobs TTS pour un utilisateur.

    QU'EST-CE QUE C'EST : Supprime les anciens jobs au-delà de la limite.
    POURQUOI : On ne veut pas accumuler des milliers de jobs en DB.
    COMMENT :
        1. Récupère tous les jobs triés du plus récent au plus ancien
        2. Garde les 5 premiers
        3. Supprime le reste
    """
    from sqlalchemy import select, desc

    result = await db.execute(
        select(JobTTS)
        .where(JobTTS.user_id == user_id)
        .order_by(desc(JobTTS.created_at))
    )
    jobs = result.scalars().all()

    if len(jobs) > 5:
        # Supprimer les jobs au-delà de la limite
        jobs_to_delete = jobs[5:]
        for job in jobs_to_delete:
            await db.delete(job)
        logger.info(f"Nettoyage historique TTS : {len(jobs_to_delete)} job(s) supprimé(s)")


@router.get("/audio/{filename}")
def download_audio(filename: str):
    """Télécharge un fichier audio précédemment généré."""
    filepath = os.path.join(TTS_OUTPUT_DIR, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Fichier '{filename}' introuvable")

    return FileResponse(path=filepath, media_type="audio/wav", filename=filename)