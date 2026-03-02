# =============================================================================
# youtube_router.py - Endpoints YouTube
# =============================================================================

import os
import uuid
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from youtube.youtube_service import download_youtube, transcribe_youtube_audio, generate_tts_segments
from translation.translate_service import translate_segments
from youtube.sync_service import assemble_video
from config import YOUTUBE_OUTPUT_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/youtube")
# prefix="/youtube" = tous les endpoints commencent par /youtube


class YouTubeRequest(BaseModel):
    url: str = Field(..., description="URL complète de la vidéo YouTube")
    source_language: str = Field(default=None, description="Langue de la vidéo (None = auto)")
    target_language: str = Field(default="fr", description="Langue cible de la traduction")


@router.post("/process")
async def youtube_process(request: YouTubeRequest):
    """
    Pipeline YouTube complet :
    - Télécharge vidéo + audio
    - Transcrit avec Whisper
    - Traduit avec LibreTranslate
    - Génère TTS par segment avec Kokoro
    - Time-stretching + assemblage final avec ffmpeg
    """
    job_id = str(uuid.uuid4())[:8]
    logger.info(f"Nouveau job YouTube : {job_id} | url={request.url}")

    # --- Étape B : Téléchargement ---
    download_result = download_youtube(request.url, job_id)
    if not download_result["success"]:
        raise HTTPException(status_code=500, detail=f"Erreur téléchargement : {download_result['error']}")

    # --- Étape C : Transcription ---
    transcribe_result = transcribe_youtube_audio(
        download_result["audio_path"],
        source_language=request.source_language
    )
    if not transcribe_result["success"]:
        raise HTTPException(status_code=500, detail=f"Erreur transcription : {transcribe_result['error']}")

    # --- Étape D : Traduction ---
    translate_result = await translate_segments(
        segments=transcribe_result["segments"],
        source_lang=transcribe_result["language"],
        target_lang=request.target_language
    )
    if not translate_result["success"]:
        raise HTTPException(status_code=500, detail=f"Erreur traduction : {translate_result['error']}")

    # --- Étape E : Génération TTS ---
    tts_result = generate_tts_segments(
        translated_segments=translate_result["segments"],
        job_dir=download_result["job_dir"],
        target_language=request.target_language,
        speed=1.0
    )
    if not tts_result["success"]:
        raise HTTPException(status_code=500, detail=f"Erreur TTS : {tts_result['error']}")

    # --- Étapes F+G : Time-stretching + Assemblage ---
    assembly_result = assemble_video(
        video_path=download_result["video_path"],
        audio_segments=tts_result["audio_segments"],
        job_id=job_id,
        job_dir=download_result["job_dir"]
    )
    if not assembly_result["success"]:
        raise HTTPException(status_code=500, detail=f"Erreur assemblage : {assembly_result['error']}")

    return {
        "success": True,
        "job_id": job_id,
        "video_info": {
            "title": download_result["title"],
            "duration": download_result["duration"],
            "channel": download_result["channel"],
        },
        "transcription": {
            "language": transcribe_result["language"],
            "segments_count": len(transcribe_result["segments"]),
        },
        "translation": {
            "source_lang": translate_result["source_lang"],
            "target_lang": translate_result["target_lang"],
            "segments_count": len(translate_result["segments"]),
        },
        "tts": {
            "segments_generated": len(tts_result["audio_segments"]),
        },
        "output": {
            "video_path": assembly_result["output_path"],
            "download_url": f"/youtube/download/{job_id}"
        }
    }


@router.get("/download/{job_id}")
def download_youtube_video(job_id: str):
    """Télécharge la vidéo finale assemblée."""
    filepath = os.path.join(YOUTUBE_OUTPUT_DIR, f"video_{job_id}.mp4")

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Vidéo introuvable pour le job {job_id}")

    logger.info(f"Téléchargement vidéo job {job_id}")
    return FileResponse(
        path=filepath,
        media_type="video/mp4",
        filename=f"video_traduite_{job_id}.mp4"
    )