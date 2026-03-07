"""
==============================================================================
routers/users_router.py — Endpoints utilisateur et historique
==============================================================================
ROUTES :
  GET /users/me/history          → les 5 derniers de chaque type
  GET /users/me/history/youtube  → 5 derniers jobs YouTube
  GET /users/me/history/tts      → 5 derniers jobs TTS
  GET /users/me/history/stt      → 5 derniers jobs STT

TOUTES CES ROUTES SONT PROTÉGÉES :
  Requires get_current_user → token JWT obligatoire
  Un utilisateur ne peut voir QUE son propre historique
==============================================================================
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from database import get_db
from models.user import User
from models.job_youtube import JobYoutube
from models.job_tts import JobTTS
from models.job_stt import JobSTT
from auth.dependencies import get_current_user
from schemas.history import (
    HistoryResponse,
    JobYoutubeResponse,
    JobTTSResponse,
    JobSTTResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["Users"])

HISTORY_LIMIT = 5
# Nombre maximum de jobs retournés par type
# Centralisé ici pour changer facilement


# ── Fonction utilitaire ───────────────────────────────────────────────────────

async def _get_youtube_history(user_id: str, db: AsyncSession) -> list[JobYoutube]:
    """Récupère les N derniers jobs YouTube d'un utilisateur."""
    result = await db.execute(
        select(JobYoutube)
        .where(JobYoutube.user_id == user_id)
        # WHERE user_id = 'xxx' → seulement les jobs de cet utilisateur
        .order_by(desc(JobYoutube.created_at))
        # ORDER BY created_at DESC → du plus récent au plus ancien
        .limit(HISTORY_LIMIT)
        # LIMIT 5 → maximum 5 résultats
    )
    return result.scalars().all()
    # scalars() = retourne les objets SQLAlchemy directement (pas des tuples)
    # all() = retourne une liste


async def _get_tts_history(user_id: str, db: AsyncSession) -> list[JobTTS]:
    """Récupère les N derniers jobs TTS d'un utilisateur."""
    result = await db.execute(
        select(JobTTS)
        .where(JobTTS.user_id == user_id)
        .order_by(desc(JobTTS.created_at))
        .limit(HISTORY_LIMIT)
    )
    return result.scalars().all()


async def _get_stt_history(user_id: str, db: AsyncSession) -> list[JobSTT]:
    """Récupère les N derniers jobs STT d'un utilisateur."""
    result = await db.execute(
        select(JobSTT)
        .where(JobSTT.user_id == user_id)
        .order_by(desc(JobSTT.created_at))
        .limit(HISTORY_LIMIT)
    )
    return result.scalars().all()


# ── GET /users/me/history ─────────────────────────────────────────────────────

@router.get("/me/history", response_model=HistoryResponse)
async def get_full_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retourne les 5 derniers jobs de chaque type pour l'utilisateur connecté.

    QUAND L'UTILISER :
        Au chargement de la page historique du frontend.
        Récupère tout en une seule requête.

    Retourne (200 OK) :
        {
            "youtube": [...5 derniers jobs YouTube],
            "tts":     [...5 derniers jobs TTS],
            "stt":     [...5 derniers jobs STT],
            "total":   15  ← nombre total
        }
    """
    youtube_jobs = await _get_youtube_history(current_user.id, db)
    tts_jobs     = await _get_tts_history(current_user.id, db)
    stt_jobs     = await _get_stt_history(current_user.id, db)

    return HistoryResponse(
        youtube=[JobYoutubeResponse.model_validate(j) for j in youtube_jobs],
        tts=[JobTTSResponse.model_validate(j) for j in tts_jobs],
        stt=[JobSTTResponse.model_validate(j) for j in stt_jobs],
        total=len(youtube_jobs) + len(tts_jobs) + len(stt_jobs),
    )
    # model_validate() = crée un schéma Pydantic depuis un objet SQLAlchemy
    # Équivalent de from_orm() dans les anciennes versions de Pydantic


# ── GET /users/me/history/youtube ────────────────────────────────────────────

@router.get("/me/history/youtube", response_model=list[JobYoutubeResponse])
async def get_youtube_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retourne les 5 derniers jobs YouTube de l'utilisateur connecté.

    Retourne (200 OK) :
        Liste de JobYoutubeResponse
    """
    jobs = await _get_youtube_history(current_user.id, db)
    return [JobYoutubeResponse.model_validate(j) for j in jobs]


# ── GET /users/me/history/tts ─────────────────────────────────────────────────

@router.get("/me/history/tts", response_model=list[JobTTSResponse])
async def get_tts_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retourne les 5 derniers jobs TTS de l'utilisateur connecté.

    Retourne (200 OK) :
        Liste de JobTTSResponse
    """
    jobs = await _get_tts_history(current_user.id, db)
    return [JobTTSResponse.model_validate(j) for j in jobs]


# ── GET /users/me/history/stt ─────────────────────────────────────────────────

@router.get("/me/history/stt", response_model=list[JobSTTResponse])
async def get_stt_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retourne les 5 derniers jobs STT de l'utilisateur connecté.

    Retourne (200 OK) :
        Liste de JobSTTResponse
    """
    jobs = await _get_stt_history(current_user.id, db)
    return [JobSTTResponse.model_validate(j) for j in jobs]