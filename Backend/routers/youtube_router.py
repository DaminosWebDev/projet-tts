"""
==============================================================================
youtube_router.py — Endpoints HTTP pour le pipeline YouTube asynchrone
==============================================================================
"""

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


# ── Modèles Pydantic ──────────────────────────────────────────────────────────

class YouTubeRequest(BaseModel):
    url: str = Field(
        ...,
        description="URL complète de la vidéo YouTube",
        json_schema_extra={"example": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    )
    source_language: Optional[str] = Field(
        default=None,
        description="Langue source (None = détection automatique par Whisper)"
    )
    target_language: str = Field(
        default="fr",
        description="Langue cible de la traduction"
    )


class JobStatusResponse(BaseModel):
    job_id:       str
    status:       str
    current_step: Optional[str]
    progress:     int
    video_id:     Optional[str]
    audio_url:    Optional[str]
    error:        Optional[str]


# ── Fonction utilitaire nettoyage ─────────────────────────────────────────────

async def _cleanup_old_jobs_youtube(user_id: str, db: AsyncSession) -> None:
    """Garde seulement les 5 derniers jobs YouTube pour un utilisateur."""
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
        logger.info(f"Nettoyage historique YouTube : {len(jobs_to_delete)} job(s) supprimé(s)")


# ── Fonction pipeline (arrière-plan) ──────────────────────────────────────────

async def _run_pipeline(
    job_id: str,
    request: YouTubeRequest,
    user: User | None = None
) -> None:
    """
    Exécute le pipeline complet YouTube en arrière-plan (étapes B → G).
    Si user est fourni → sauvegarde l'historique en DB après completion.
    """
    try:
        # ── Étape B : Téléchargement ──────────────────────────────────────────
        update_job_step(job_id, PipelineStep.DOWNLOAD, 5)
        logger.info(f"[{job_id}] Étape B : téléchargement {request.url}")

        download_result = await asyncio.to_thread(download_youtube, request.url, job_id)
        if not download_result["success"]:
            raise RuntimeError(f"Téléchargement : {download_result['error']}")

        update_job_step(job_id, PipelineStep.DOWNLOAD, 15)

        # ── Étape C : Transcription ───────────────────────────────────────────
        update_job_step(job_id, PipelineStep.TRANSCRIBE, 20)
        logger.info(f"[{job_id}] Étape C : transcription")

        transcribe_result = await asyncio.to_thread(
            transcribe_youtube_audio,
            download_result["audio_path"],
            request.source_language
        )
        if not transcribe_result["success"]:
            raise RuntimeError(f"Transcription : {transcribe_result['error']}")

        update_job_step(job_id, PipelineStep.TRANSCRIBE, 35)

        # ── Étape D : Traduction ──────────────────────────────────────────────
        update_job_step(job_id, PipelineStep.TRANSLATE, 40)
        logger.info(f"[{job_id}] Étape D : traduction → {request.target_language}")

        translate_result = await translate_segments(
            segments=transcribe_result["segments"],
            source_lang=transcribe_result["language"],
            target_lang=request.target_language
        )
        if not translate_result["success"]:
            raise RuntimeError(f"Traduction : {translate_result['error']}")

        update_job_step(job_id, PipelineStep.TRANSLATE, 50)

        # ── Étape E : TTS ─────────────────────────────────────────────────────
        update_job_step(job_id, PipelineStep.TTS, 55)
        logger.info(f"[{job_id}] Étape E : génération TTS")

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

        # ── Étapes F+G : Assemblage ───────────────────────────────────────────
        update_job_step(job_id, PipelineStep.STRETCH, 75)
        logger.info(f"[{job_id}] Étapes F+G : assemblage audio")

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

        # ── Finalisation ──────────────────────────────────────────────────────
        complete_job(
            job_id=job_id,
            video_id=download_result["video_id"],
            audio_url=f"/youtube/audio/{job_id}",
        )
        logger.info(f"[{job_id}] ✅ Pipeline terminé")

        # ── Sauvegarde historique (uniquement si connecté) ────────────────────
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
                    logger.info(f"Historique YouTube sauvegardé pour {user.email}")

            except Exception as e:
                logger.error(f"Erreur sauvegarde historique YouTube : {e}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[{job_id}] ❌ Pipeline échoué : {error_msg}")
        fail_job(job_id, error_msg)

        # Sauvegarde en DB avec status="error" si connecté
        if user:
            try:
                async with get_db() as db:
                    job_db = JobYoutube(
                        user_id=user.id,
                        youtube_url=request.url,
                        target_language=request.target_language,
                        status="error",
                    )
                    db.add(job_db)
                    await db.commit()
            except Exception:
                pass


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/process", status_code=202)
async def youtube_process(
    request: YouTubeRequest,
    background_tasks: BackgroundTasks,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    """Démarre le pipeline YouTube en arrière-plan et retourne un job_id."""
    job_id = create_job(request.url)
    logger.info(f"Job créé : {job_id} | {request.url}")

    background_tasks.add_task(_run_pipeline, job_id, request, current_user)
    # On passe current_user au pipeline pour la sauvegarde historique

    return {
        "job_id":     job_id,
        "status":     "pending",
        "status_url": f"/youtube/status/{job_id}",
    }


@router.get("/status/{job_id}", response_model=JobStatusResponse)
def youtube_status(job_id: str):
    """Retourne l'état courant d'un job."""
    job = get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job introuvable : {job_id}")

    result    = job.get("result", {})
    video_id  = result.get("video_id")
    audio_url = result.get("audio_url")

    return JobStatusResponse(
        job_id       = job["job_id"],
        status       = job["status"],
        current_step = job.get("current_step"),
        progress     = job.get("progress", 0),
        video_id     = video_id,
        audio_url    = audio_url,
        error        = job.get("error"),
    )


@router.get("/audio/{job_id}")
def get_audio_track(job_id: str):
    """Sert la piste audio WAV finale pour un job terminé."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job introuvable : {job_id}")

    if job["status"] != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Job pas encore terminé — statut actuel : {job['status']}"
        )

    filepath = os.path.join(YOUTUBE_OUTPUT_DIR, f"audio_{job_id}.wav")

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=404,
            detail=f"Fichier audio introuvable pour le job {job_id}"
        )

    return FileResponse(
        path=filepath,
        media_type="audio/wav",
        filename=f"audio_traduit_{job_id}.wav"
    )