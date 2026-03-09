import os
import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from youtube.job_manager import (
    create_job, get_job, update_job_step,
    complete_job, fail_job, PipelineStep,
)
from youtube.youtube_service import (
    download_youtube, transcribe_youtube_audio, generate_tts_segments,
)
from translation.translate_service import translate_segments
from youtube.sync_service import assemble_audio_track
from config import YOUTUBE_OUTPUT_DIR
from database import get_db
from models.job_youtube import JobYoutube
from models.user import User
from auth.dependencies import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/youtube")


# ── Schémas ───────────────────────────────────────────────────────────────────

class YouTubeRequest(BaseModel):
    url: str = Field(..., json_schema_extra={"example": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    source_language: Optional[str] = Field(default=None)  # None = détection auto Whisper
    target_language: str = Field(default="fr")


class JobStatusResponse(BaseModel):
    job_id:       str
    status:       str
    current_step: Optional[str]
    progress:     int
    video_id:     Optional[str]
    audio_url:    Optional[str]
    error:        Optional[str]


# ── Nettoyage historique ──────────────────────────────────────────────────────

async def _cleanup_old_jobs_youtube(user_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(JobYoutube)
        .where(JobYoutube.user_id == user_id)
        .order_by(desc(JobYoutube.created_at))
    )
    jobs = result.scalars().all()

    if len(jobs) > 5:
        jobs_to_delete = jobs[5:]
        for job in jobs_to_delete:
            await db.delete(job)
        logger.info(f"Nettoyage YouTube : {len(jobs_to_delete)} job(s) supprimé(s)")


# ── Pipeline arrière-plan ─────────────────────────────────────────────────────

async def _run_pipeline(job_id: str, request: YouTubeRequest, user: User | None = None) -> None:
    try:
        # Étape B — Téléchargement via yt-dlp
        update_job_step(job_id, PipelineStep.DOWNLOAD, 5)
        download_result = await asyncio.to_thread(download_youtube, request.url, job_id)
        if not download_result["success"]:
            raise RuntimeError(f"Téléchargement : {download_result['error']}")
        update_job_step(job_id, PipelineStep.DOWNLOAD, 15)

        # Étape C — Transcription Whisper
        update_job_step(job_id, PipelineStep.TRANSCRIBE, 20)
        transcribe_result = await asyncio.to_thread(
            transcribe_youtube_audio,
            download_result["audio_path"],
            request.source_language
        )
        if not transcribe_result["success"]:
            raise RuntimeError(f"Transcription : {transcribe_result['error']}")
        update_job_step(job_id, PipelineStep.TRANSCRIBE, 35)

        # Étape D — Traduction LibreTranslate
        update_job_step(job_id, PipelineStep.TRANSLATE, 40)
        translate_result = await translate_segments(
            segments=transcribe_result["segments"],
            source_lang=transcribe_result["language"],
            target_lang=request.target_language
        )
        if not translate_result["success"]:
            raise RuntimeError(f"Traduction : {translate_result['error']}")
        update_job_step(job_id, PipelineStep.TRANSLATE, 50)

        # Étape E — Synthèse vocale Kokoro par segment
        update_job_step(job_id, PipelineStep.TTS, 55)
        tts_result = await asyncio.to_thread(
            generate_tts_segments,
            translate_result["segments"],
            download_result["job_dir"],
            request.target_language,
            "", 1.0
        )
        if not tts_result["success"]:
            raise RuntimeError(f"TTS : {tts_result['error']}")
        update_job_step(job_id, PipelineStep.TTS, 70)

        # Étapes F+G — Time-stretching + assemblage ffmpeg
        update_job_step(job_id, PipelineStep.STRETCH, 75)
        assembly_result = await asyncio.to_thread(
            assemble_audio_track,
            tts_result["audio_segments"],
            job_id,
            download_result["job_dir"],
            download_result["duration"]
        )
        if not assembly_result["success"]:
            raise RuntimeError(f"Assemblage : {assembly_result['error']}")
        update_job_step(job_id, PipelineStep.ASSEMBLE, 99)

        # Finalisation en mémoire
        complete_job(
            job_id=job_id,
            video_id=download_result["video_id"],
            audio_url=f"/youtube/audio/{job_id}",
        )
        logger.info(f"[{job_id}] Pipeline terminé")

        # Persistance en DB — session indépendante car hors contexte de la requête HTTP
        if user:
            try:
                async with get_db() as db:
                    job_db = JobYoutube(
                        user_id=user.id,
                        youtube_url=request.url,
                        video_id=download_result.get("video_id"),
                        video_title=download_result.get("title"),
                        source_language=transcribe_result.get("language"),
                        target_language=request.target_language,
                        audio_url=f"/youtube/audio/{job_id}",
                        status="done",
                    )
                    db.add(job_db)
                    await db.flush()
                    await _cleanup_old_jobs_youtube(user.id, db)
                    await db.commit()
                    logger.info(f"Historique YouTube sauvegardé : {user.email}")
            except Exception as e:
                logger.error(f"Erreur sauvegarde historique YouTube : {e}")

    except Exception as e:
        logger.error(f"[{job_id}] Pipeline échoué : {e}")
        fail_job(job_id, str(e))

        # Persistance de l'échec en DB
        if user:
            try:
                async with get_db() as db:
                    db.add(JobYoutube(
                        user_id=user.id,
                        youtube_url=request.url,
                        target_language=request.target_language,
                        status="error",
                    ))
                    await db.commit()
            except Exception:
                pass  # Échec silencieux — ne pas masquer l'erreur principale


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/process", status_code=202)
async def youtube_process(
    request: YouTubeRequest,
    background_tasks: BackgroundTasks,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    # Crée le job en mémoire et retourne immédiatement — pipeline en arrière-plan
    job_id = create_job(request.url)
    background_tasks.add_task(_run_pipeline, job_id, request, current_user)
    logger.info(f"Job créé : {job_id} | {request.url}")

    return {
        "job_id":     job_id,
        "status":     "pending",
        "status_url": f"/youtube/status/{job_id}",
    }


@router.get("/status/{job_id}", response_model=JobStatusResponse)
def youtube_status(job_id: str):
    # Sync — lecture en mémoire uniquement, pas d'I/O
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job introuvable : {job_id}")

    result = job.get("result", {})
    return JobStatusResponse(
        job_id       = job["job_id"],
        status       = job["status"],
        current_step = job.get("current_step"),
        progress     = job.get("progress", 0),
        video_id     = result.get("video_id"),
        audio_url    = result.get("audio_url"),
        error        = job.get("error"),
    )


@router.get("/audio/{job_id}")
def get_audio_track(job_id: str):
    # Sync — lecture disque uniquement
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job introuvable : {job_id}")

    # 409 Conflict — la ressource existe mais n'est pas encore prête
    if job["status"] != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Job pas encore terminé — statut : {job['status']}"
        )

    filepath = os.path.join(YOUTUBE_OUTPUT_DIR, f"audio_{job_id}.wav")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Fichier audio introuvable : {job_id}")

    return FileResponse(
        path=filepath,
        media_type="audio/wav",
        filename=f"audio_traduit_{job_id}.wav"
    )
