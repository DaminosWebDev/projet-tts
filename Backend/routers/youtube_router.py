"""
==============================================================================
youtube_router.py — Endpoints HTTP pour le pipeline YouTube asynchrone
==============================================================================
RESPONSABILITÉS :
  - POST /youtube/process          → démarre le pipeline en arrière-plan,
                                     retourne un job_id immédiatement (<100ms)
  - GET  /youtube/status/{job_id}  → retourne l'état courant du job (polling)
  - GET  /youtube/audio/{job_id}   → sert la piste WAV finale au client

CHANGEMENT MAJEUR vs version précédente :
  Avant  : POST bloquait 30-180s puis retournait le résultat final.
  Après  : POST retourne un job_id en <100ms. Le traitement tourne en
           arrière-plan. Le frontend poll GET /status toutes les 2s.

FLUX COMPLET :
  1. Client    → POST /youtube/process { url }
  2. Serveur   → { job_id: "abc123" }            (immédiat)
  3. [En fond] → Pipeline B→G tourne...
  4. Client    → GET /youtube/status/abc123       (toutes les 2s)
  5. Serveur   → { status: "processing", progress: 45, current_step: "D_translate" }
  6. [Quand done] Client → GET /youtube/audio/abc123
  7. Serveur   → stream du fichier WAV
==============================================================================
"""

# ── Imports ───────────────────────────────────────────────────────────────────

import os
# QU'EST-CE QUE C'EST : Accès au système de fichiers.
# POURQUOI : Vérifier l'existence du fichier WAV avant de le servir (évite crash).
# COMMENT : os.path.exists(path) retourne True/False.

import asyncio
# QU'EST-CE QUE C'EST : Module standard Python pour la programmation asynchrone.
# POURQUOI : Nos fonctions de pipeline (download, transcribe, tts, assemble) sont
#            synchrones (def, pas async def). Les appeler directement dans une
#            coroutine async bloquerait l'event loop — plus aucune requête GET /status
#            ne pourrait répondre pendant le traitement.
# COMMENT : asyncio.to_thread(fonction, arg1, arg2) exécute une fonction sync dans
#            un thread séparé du pool de threads, puis retourne son résultat via await.
#            L'event loop reste libre pendant ce temps → GET /status continue de répondre.
# ANALOGIE : C'est comme confier une tâche longue à un collègue (thread) plutôt que
#            de la faire soi-même et bloquer son bureau (l'event loop).

import logging
# QU'EST-CE QUE C'EST : Module standard de logging Python.
# POURQUOI : Tracer les événements importants (démarrage job, erreurs) sans print().
# COMMENT : getLogger(__name__) crée un logger nommé "routers.youtube_router"
#           qui hérite de la config du logger racine défini dans main.py.

from fastapi import APIRouter, BackgroundTasks, HTTPException
# QU'EST-CE QUE C'EST : Composants cœur de FastAPI.
# POURQUOI :
#   APIRouter      → groupe de routes montable dans main.py (organisation modulaire)
#   BackgroundTasks → lance une fonction APRÈS l'envoi de la réponse HTTP
#                     → client reçoit job_id pendant que le pipeline tourne
#   HTTPException  → erreurs HTTP standard (404, 500) avec message JSON automatique
# COMMENT : BackgroundTasks est injecté automatiquement par FastAPI (dependency injection).

from fastapi.responses import FileResponse
# QU'EST-CE QUE C'EST : Réponse FastAPI qui streame un fichier depuis le disque.
# POURQUOI : Envoyer le fichier WAV final au navigateur de manière efficace.
# COMMENT : Gère automatiquement Content-Type, Content-Length, support Range (seek audio).

from pydantic import BaseModel, Field
# QU'EST-CE QUE C'EST : Validation de données (inclus avec FastAPI).
# POURQUOI : Valider le corps des requêtes POST + générer la doc Swagger automatiquement.
# COMMENT : Chaque champ BaseModel est validé au moment de la désérialisation JSON.
#           Field(...) = champ obligatoire ; Field(default=X) = champ optionnel.

from typing import Optional
# POURQUOI : Typer les champs qui peuvent être None dans les modèles de réponse.

# Imports internes — gestionnaire de jobs
from youtube.job_manager import (
    create_job,       # Crée un nouveau job en mémoire, retourne son ID
    get_job,          # Lit l'état d'un job par son ID
    update_job_step,  # Met à jour étape + progression pendant le pipeline
    complete_job,     # Marque un job comme terminé avec résultats
    fail_job,         # Marque un job comme échoué avec message d'erreur
    PipelineStep,     # Enum des étapes B→G (pour update_job_step)
)
# QU'EST-CE QUE C'EST : Notre gestionnaire d'état en mémoire (voir job_manager.py).
# POURQUOI : Découpler la gestion d'état (job_manager) du transport HTTP (ce fichier).
# COMMENT : Toutes ces fonctions modifient/lisent _jobs de manière thread-safe.

# Imports internes — services métier (inchangés vs version précédente)
from youtube.youtube_service import (
    download_youtube,          # Étape B : télécharge l'audio WAV via yt-dlp
    transcribe_youtube_audio,  # Étape C : transcrit avec Faster-Whisper
    generate_tts_segments,     # Étape E : génère les WAV TTS avec Kokoro
)
from translation.translate_service import translate_segments  # Étape D : LibreTranslate
from youtube.sync_service import assemble_audio_track         # Étapes F+G : stretch + assemblage

from config import YOUTUBE_OUTPUT_DIR
# QU'EST-CE QUE C'EST : Constante de configuration — dossier de sortie des fichiers WAV.
# POURQUOI : Centraliser les chemins dans config.py évite les "magic strings" éparpillés.
# COMMENT : Ex: YOUTUBE_OUTPUT_DIR = "backend/youtube/output"

# ── Setup ─────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)
# __name__ = "routers.youtube_router"
# Les logs apparaîtront comme : "routers.youtube_router | INFO | Job abc123 démarré"

router = APIRouter(prefix="/youtube")
# prefix="/youtube" → toutes les routes de ce fichier sont préfixées /youtube
# Ex: @router.post("/process") → POST /youtube/process
#     @router.get("/status/{job_id}") → GET /youtube/status/abc123


# ── Modèles Pydantic ──────────────────────────────────────────────────────────

class YouTubeRequest(BaseModel):
    """
    Corps de la requête POST /youtube/process.

    QU'EST-CE QUE C'EST : Schéma de validation de la requête de lancement d'un job.
    POURQUOI : FastAPI valide automatiquement — URL manquante → 422 Unprocessable Entity.
    COMMENT : Inchangé vs version précédente, compatible avec le frontend existant.
    """
    url: str = Field(
        ...,  # "..." = champ obligatoire
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
    """
    Réponse de GET /youtube/status/{job_id}.

    QU'EST-CE QUE C'EST : Schéma exact de ce que le frontend reçoit lors du polling.
    POURQUOI : Documenter le contrat API → le frontend sait exactement quels champs
               existent et à quel moment ils sont remplis.

    Cycle de remplissage des champs :
        Toujours présents  : job_id, status, progress
        Pendant processing : current_step (ex: "C_transcribe")
        Quand done         : result.video_id, result.audio_url
        Quand error        : error (message d'erreur)
    """
    job_id:       str
    status:       str            # "pending" | "processing" | "done" | "error"
    current_step: Optional[str]  # Ex: "D_translate" — None si pas démarré ou terminé
    progress:     int            # 0-100
    video_id:     Optional[str]  # Rempli quand done. Ex: "dQw4w9WgXcQ"
    audio_url:    Optional[str]  # Rempli quand done. Ex: "/youtube/audio/abc123"
    error:        Optional[str]  # Rempli quand error. Ex: "yt-dlp: unavailable"


# ── Fonction pipeline (arrière-plan) ──────────────────────────────────────────

async def _run_pipeline(job_id: str, request: YouTubeRequest) -> None:
    """
    Exécute le pipeline complet YouTube en arrière-plan (étapes B → G).

    QU'EST-CE QUE C'EST : Fonction async qui orchestre toutes les étapes du traitement.
    POURQUOI : Lancée via BackgroundTasks → s'exécute APRÈS l'envoi de la réponse HTTP.
               Le client a déjà son job_id et peut commencer à poller GET /status
               pendant que cette fonction tourne.
    COMMENT : Chaque étape appelle update_job_step() pour mettre à jour la progression.
              Un try/except global attrape toute erreur et appelle fail_job().

    ANALOGIE : C'est la chaîne de production en coulisses d'un restaurant.
               Le client a reçu son ticket de commande (job_id) et peut voir
               l'avancement sur l'écran de la salle — sans être en cuisine.

    Paramètres :
        job_id  (str)            : UUID du job à traiter.
        request (YouTubeRequest) : Paramètres de la requête originale.

    Retourne :
        None — les résultats sont écrits dans job_manager via complete_job() ou fail_job().
    """
    try:
        # ── Étape B : Téléchargement audio ────────────────────────────────────
        # Cible : 0% → 15%
        # download_youtube est une fonction SYNC → on l'exécute dans un thread
        # via asyncio.to_thread pour ne pas bloquer l'event loop pendant ~8s
        update_job_step(job_id, PipelineStep.DOWNLOAD, 5)
        logger.info(f"[{job_id}] Étape B : téléchargement {request.url}")

        download_result = await asyncio.to_thread(
            download_youtube, request.url, job_id
            # asyncio.to_thread(fonction, *args) = appel non bloquant d'une fonction sync
            # Équivalent de : download_youtube(request.url, job_id)
            # mais dans un thread séparé → GET /status continue de répondre pendant ce temps
        )
        if not download_result["success"]:
            raise RuntimeError(f"Téléchargement : {download_result['error']}")

        update_job_step(job_id, PipelineStep.DOWNLOAD, 15)
        logger.info(f"[{job_id}] Étape B OK — durée: {download_result['duration']}s")

        # ── Étape C : Transcription Faster-Whisper ────────────────────────────
        # Cible : 15% → 35%
        # transcribe_youtube_audio est SYNC et peut durer 20-60s sur Whisper medium
        # → obligatoirement dans un thread séparé
        update_job_step(job_id, PipelineStep.TRANSCRIBE, 20)
        logger.info(f"[{job_id}] Étape C : transcription")

        transcribe_result = await asyncio.to_thread(
            transcribe_youtube_audio,
            download_result["audio_path"],
            request.source_language
            # asyncio.to_thread ne supporte pas les kwargs → on passe les args positionnels
            # transcribe_youtube_audio(audio_path, source_language) dans la définition
        )
        if not transcribe_result["success"]:
            raise RuntimeError(f"Transcription : {transcribe_result['error']}")

        update_job_step(job_id, PipelineStep.TRANSCRIBE, 35)
        logger.info(f"[{job_id}] Étape C OK — {len(transcribe_result['segments'])} segments")

        # ── Étape D : Traduction LibreTranslate ──────────────────────────────
        # Cible : 35% → 50%
        # translate_segments est déjà ASYNC (asyncio.gather en interne)
        # → on l'appelle directement avec await, pas besoin de to_thread
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
        logger.info(f"[{job_id}] Étape D OK")

        # ── Étape E : Génération TTS Kokoro ──────────────────────────────────
        # Cible : 50% → 70%
        # generate_tts_segments est SYNC et peut durer 30-60s (un appel Kokoro par segment)
        # → dans un thread séparé
        update_job_step(job_id, PipelineStep.TTS, 55)
        logger.info(f"[{job_id}] Étape E : génération TTS")

        tts_result = await asyncio.to_thread(
            generate_tts_segments,
            translate_result["segments"],  # translated_segments
            download_result["job_dir"],    # job_dir
            request.target_language,       # target_language
            "",                            # voice = défaut
            1.0                            # speed = normal
        )
        if not tts_result["success"]:
            raise RuntimeError(f"TTS : {tts_result['error']}")

        update_job_step(job_id, PipelineStep.TTS, 70)
        logger.info(f"[{job_id}] Étape E OK — {len(tts_result['audio_segments'])} fichiers WAV")

        # ── Étapes F + G : Time-stretching + Assemblage ───────────────────────
        # Cible : 70% → 99%
        # assemble_audio_track est SYNC et appelle ffmpeg plusieurs fois (~30s)
        # → dans un thread séparé
        update_job_step(job_id, PipelineStep.STRETCH, 75)
        logger.info(f"[{job_id}] Étapes F+G : assemblage audio")

        assembly_result = await asyncio.to_thread(
            assemble_audio_track,
            tts_result["audio_segments"],  # audio_segments
            job_id,                        # job_id
            download_result["job_dir"],    # job_dir
            download_result["duration"]    # total_duration
        )
        if not assembly_result["success"]:
            raise RuntimeError(f"Assemblage : {assembly_result['error']}")

        update_job_step(job_id, PipelineStep.ASSEMBLE, 99)
        logger.info(f"[{job_id}] Étapes F+G OK — {assembly_result['output_path']}")

        # ── Finalisation ─────────────────────────────────────────────────────
        # On marque le job comme terminé avec les données dont le frontend a besoin
        complete_job(
            job_id=job_id,
            video_id=download_result["video_id"],       # Pour l'iframe YouTube
            audio_url=f"/youtube/audio/{job_id}",       # Pour l'Audio Web API
        )
        logger.info(f"[{job_id}] ✅ Pipeline terminé")

    except Exception as e:
        # Attrape TOUTE exception non gérée dans les étapes ci-dessus
        # → le job passe en status="error" avec le message d'erreur
        # → le frontend peut afficher l'erreur plutôt que boucler en polling
        error_msg = str(e)
        logger.error(f"[{job_id}] ❌ Pipeline échoué : {error_msg}")
        fail_job(job_id, error_msg)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/process", status_code=202)
async def youtube_process(request: YouTubeRequest, background_tasks: BackgroundTasks):
    """
    Démarre le pipeline YouTube en arrière-plan et retourne un job_id immédiatement.

    QU'EST-CE QUE C'EST : Point d'entrée principal — remplace l'ancien POST bloquant.
    POURQUOI status_code=202 : HTTP 202 Accepted = "requête reçue, traitement en cours"
                               (vs 200 OK qui signifie "traitement terminé").
    COMMENT : 
        1. Crée le job en mémoire (status=pending)
        2. Ajoute _run_pipeline à la file BackgroundTasks
        3. Retourne le job_id IMMÉDIATEMENT (avant que le pipeline démarre)
        4. FastAPI envoie la réponse → PUIS lance _run_pipeline en arrière-plan

    Paramètres (body JSON) :
        url             (str) : URL YouTube obligatoire
        source_language (str) : Langue source, optionnel (défaut: None = auto)
        target_language (str) : Langue cible, optionnel (défaut: "fr")

    Retourne (202 Accepted) :
        {
            "job_id": "a3f8c2d1-4b5e-41d4-a716-446655440000",
            "status": "pending",
            "status_url": "/youtube/status/a3f8c2d1-..."
        }
    """
    # Créer le job en mémoire → status=pending, progress=0
    job_id = create_job(request.url)
    logger.info(f"Job créé : {job_id} | {request.url}")

    # Ajouter le pipeline à la file d'arrière-plan de FastAPI
    # IMPORTANT : _run_pipeline ne démarre PAS ici — il démarre après l'envoi
    #             de la réponse HTTP. C'est le comportement de BackgroundTasks.
    background_tasks.add_task(_run_pipeline, job_id, request)

    # Réponse immédiate — le pipeline n'a pas encore démarré à ce stade
    return {
        "job_id":     job_id,
        "status":     "pending",
        "status_url": f"/youtube/status/{job_id}",
        # status_url = URL que le frontend doit poller toutes les 2s
    }


@router.get("/status/{job_id}", response_model=JobStatusResponse)
def youtube_status(job_id: str):
    """
    Retourne l'état courant d'un job (endpoint de polling du frontend).

    QU'EST-CE QUE C'EST : Endpoint interrogé toutes les 2s par le frontend React.
    POURQUOI : Permet au frontend de suivre la progression sans connexion persistante
               (pas besoin de WebSocket pour ce cas d'usage).
    COMMENT : Lit le job depuis job_manager (thread-safe), formate la réponse.

    Paramètres (URL) :
        job_id (str) : UUID du job retourné par POST /youtube/process

    Retourne :
        JobStatusResponse avec les champs appropriés selon le statut courant.
        Exemple quand processing :
            { job_id, status:"processing", current_step:"C_transcribe", progress:25 }
        Exemple quand done :
            { job_id, status:"done", progress:100, video_id:"dQw4...", audio_url:"/youtube/audio/..." }
        Exemple quand error :
            { job_id, status:"error", error:"yt-dlp: video unavailable" }
    """
    job = get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job introuvable : {job_id}"
        )

    # Extraire les champs du résultat (présents seulement si status==done)
    result   = job.get("result", {})
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
    """
    Sert la piste audio WAV finale pour un job terminé.

    QU'EST-CE QUE C'EST : Endpoint de téléchargement du résultat final.
    POURQUOI : Inchangé vs version précédente — seul le nom de route change.
               Le frontend appelle cette URL quand status=="done" pour récupérer le WAV.
    COMMENT : Vérifie l'existence du fichier, retourne un FileResponse streamé.

    Paramètres (URL) :
        job_id (str) : UUID du job

    Retourne :
        Stream du fichier audio/wav si trouvé, 404 sinon.
    """
    # Vérifier d'abord que le job existe et est bien terminé
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job introuvable : {job_id}")

    if job["status"] != "done":
        # Le fichier n'existe peut-être pas encore si le job tourne encore
        raise HTTPException(
            status_code=409,  # 409 Conflict = "la ressource existe mais pas dans l'état attendu"
            detail=f"Job pas encore terminé — statut actuel : {job['status']}"
        )

    filepath = os.path.join(YOUTUBE_OUTPUT_DIR, f"audio_{job_id}.wav")

    if not os.path.exists(filepath):
        # Le job est done mais le fichier a disparu (redémarrage, nettoyage) → 404
        raise HTTPException(
            status_code=404,
            detail=f"Fichier audio introuvable pour le job {job_id}"
        )

    logger.info(f"Envoi piste audio job {job_id}")

    return FileResponse(
        path=filepath,
        media_type="audio/wav",
        filename=f"audio_traduit_{job_id}.wav"
        # filename = nom suggéré si l'utilisateur télécharge le fichier
    )