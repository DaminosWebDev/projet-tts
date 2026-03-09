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

# Centralisé — changer ici affecte toutes les routes d'historique
HISTORY_LIMIT = 5


# ── Requêtes DB partagées ─────────────────────────────────────────────────────

async def _get_youtube_history(user_id: str, db: AsyncSession) -> list[JobYoutube]:
    result = await db.execute(
        select(JobYoutube)
        .where(JobYoutube.user_id == user_id)
        .order_by(desc(JobYoutube.created_at))
        .limit(HISTORY_LIMIT)
    )
    return result.scalars().all()


async def _get_tts_history(user_id: str, db: AsyncSession) -> list[JobTTS]:
    result = await db.execute(
        select(JobTTS)
        .where(JobTTS.user_id == user_id)
        .order_by(desc(JobTTS.created_at))
        .limit(HISTORY_LIMIT)
    )
    return result.scalars().all()


async def _get_stt_history(user_id: str, db: AsyncSession) -> list[JobSTT]:
    result = await db.execute(
        select(JobSTT)
        .where(JobSTT.user_id == user_id)
        .order_by(desc(JobSTT.created_at))
        .limit(HISTORY_LIMIT)
    )
    return result.scalars().all()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/me/history", response_model=HistoryResponse)
async def get_full_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Trois requêtes parallélisables — voir note sur asyncio.gather ci-dessous
    youtube_jobs = await _get_youtube_history(current_user.id, db)
    tts_jobs     = await _get_tts_history(current_user.id, db)
    stt_jobs     = await _get_stt_history(current_user.id, db)

    return HistoryResponse(
        youtube=[JobYoutubeResponse.model_validate(j) for j in youtube_jobs],
        tts=[JobTTSResponse.model_validate(j) for j in tts_jobs],
        stt=[JobSTTResponse.model_validate(j) for j in stt_jobs],
        total=len(youtube_jobs) + len(tts_jobs) + len(stt_jobs),
    )


@router.get("/me/history/youtube", response_model=list[JobYoutubeResponse])
async def get_youtube_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    jobs = await _get_youtube_history(current_user.id, db)
    return [JobYoutubeResponse.model_validate(j) for j in jobs]


@router.get("/me/history/tts", response_model=list[JobTTSResponse])
async def get_tts_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    jobs = await _get_tts_history(current_user.id, db)
    return [JobTTSResponse.model_validate(j) for j in jobs]


@router.get("/me/history/stt", response_model=list[JobSTTResponse])
async def get_stt_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    jobs = await _get_stt_history(current_user.id, db)
    return [JobSTTResponse.model_validate(j) for j in jobs]