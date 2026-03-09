"""
==============================================================================
job_manager.py — Gestionnaire d'état des jobs asynchrones YouTube
==============================================================================
RESPONSABILITÉS :
  - Créer et stocker les jobs en mémoire (dict Python global)
  - Mettre à jour le statut et la progression de chaque job
  - Exposer des fonctions utilitaires pour lire/écrire l'état d'un job
  - Nettoyer automatiquement les jobs expirés (TTL)

CYCLE DE VIE D'UN JOB :
  PENDING → PROCESSING → DONE
  PENDING → PROCESSING → ERROR

TTL (Time-To-Live) :
  Les jobs terminés (DONE ou ERROR) sont supprimés après JOB_TTL_SECONDS.
  Le nettoyage tourne en arrière-plan toutes les CLEANUP_INTERVAL_SECONDS.
==============================================================================
"""

import uuid
import time
import threading
import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


# ── Constantes TTL ────────────────────────────────────────────────────────────

JOB_TTL_SECONDS = 3600          # 1 heure — durée de vie d'un job terminé
CLEANUP_INTERVAL_SECONDS = 600  # 10 minutes — fréquence du nettoyage automatique


# ── Énumérations ──────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    """
    États possibles d'un job YouTube.

    Hérite de str ET Enum :
    - str  → valeurs directement sérialisables JSON sans .value
    - Enum → typage fort, pas de faute de frappe possible
    """
    PENDING    = "pending"
    PROCESSING = "processing"
    DONE       = "done"
    ERROR      = "error"


class PipelineStep(str, Enum):
    """
    Étapes du pipeline YouTube dans l'ordre d'exécution.
    Préfixes alphabétiques — ordre visible dans les logs et le frontend.
    """
    DOWNLOAD   = "B_download"
    TRANSCRIBE = "C_transcribe"
    TRANSLATE  = "D_translate"
    TTS        = "E_tts"
    STRETCH    = "F_stretch"
    ASSEMBLE   = "G_assemble"


# ── Stockage global ───────────────────────────────────────────────────────────

# Dict global — zéro dépendance externe (pas de Redis, pas de DB).
# Attention : données perdues au redémarrage serveur.
_jobs: Dict[str, Dict[str, Any]] = {}

# Mutex — protège _jobs contre les race conditions entre threads.
# BackgroundTasks tourne dans un thread pool séparé des requêtes GET.
_lock = threading.Lock()


# ── TTL — Nettoyage automatique ───────────────────────────────────────────────

def _cleanup_expired_jobs() -> None:
    """
    Supprime les jobs terminés (DONE ou ERROR) dont le finished_at
    dépasse JOB_TTL_SECONDS.

    QU'EST-CE QUE C'EST : Garbage collector des jobs expirés.
    POURQUOI : Sans nettoyage, _jobs grossit indéfiniment — fuite mémoire lente.
    COMMENT :
        1. Calcule le timestamp limite (maintenant - TTL)
        2. Identifie les jobs expirés (finished_at < cutoff)
        3. Les supprime sous verrou
    """
    cutoff = time.time() - JOB_TTL_SECONDS

    with _lock:
        expired_ids = [
            job_id
            for job_id, job in _jobs.items()
            if job.get("finished_at") and job["finished_at"] < cutoff
        ]
        for job_id in expired_ids:
            del _jobs[job_id]

    if expired_ids:
        logger.info(f"TTL cleanup : {len(expired_ids)} job(s) expiré(s) supprimé(s)")


def _schedule_cleanup() -> None:
    """
    Boucle infinie qui exécute _cleanup_expired_jobs() toutes les
    CLEANUP_INTERVAL_SECONDS.

    QU'EST-CE QUE C'EST : Le "thread de ménage" — tourne en arrière-plan
                          pendant toute la durée de vie du serveur.
    POURQUOI time.sleep() et pas asyncio.sleep() :
        Ce thread est synchrone — il est lancé avec threading.Thread,
        pas dans la boucle asyncio. time.sleep() est correct ici.
    POURQUOI daemon=True (voir _start_cleanup_thread) :
        Un thread daemon est tué automatiquement quand le processus principal
        se termine. Sans ça, le serveur ne s'arrêterait jamais proprement.
    """
    while True:
        time.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            _cleanup_expired_jobs()
        except Exception as e:
            # Ne jamais laisser une exception tuer le thread de nettoyage
            logger.error(f"Erreur TTL cleanup : {e}")


def _start_cleanup_thread() -> None:
    """
    Démarre le thread de nettoyage en arrière-plan au chargement du module.

    QU'EST-CE QUE C'EST : Initialisation unique — appelée une seule fois
                          quand job_manager.py est importé.
    POURQUOI daemon=True :
        Quand FastAPI s'arrête (Ctrl+C ou SIGTERM), Python attend que tous
        les threads non-daemon se terminent avant de quitter. Un thread qui
        dort 10 minutes bloquerait l'arrêt. daemon=True = "ce thread n'est
        pas critique, tue-le avec le processus principal".
    """
    cleanup_thread = threading.Thread(
        target=_schedule_cleanup,
        daemon=True,
        name="job-ttl-cleanup"   # Nom visible dans les profilers et les logs système
    )
    cleanup_thread.start()
    logger.info(
        f"Thread TTL démarré — nettoyage toutes les "
        f"{CLEANUP_INTERVAL_SECONDS}s, TTL={JOB_TTL_SECONDS}s"
    )


# Démarrage automatique au chargement du module
_start_cleanup_thread()


# ── Fonctions publiques ───────────────────────────────────────────────────────

def create_job(youtube_url: str) -> str:
    """
    Crée un nouveau job en mémoire et retourne son identifiant.

    Paramètres :
        youtube_url (str) : URL YouTube soumise par l'utilisateur.

    Retourne :
        str : UUID v4 du job.
    """
    job_id = str(uuid.uuid4())

    job_data: Dict[str, Any] = {
        "job_id":       job_id,
        "status":       JobStatus.PENDING,
        "youtube_url":  youtube_url,
        "current_step": None,
        "progress":     0,
        "created_at":   time.time(),
        "updated_at":   time.time(),
        "finished_at":  None,   # Rempli par complete_job() ou fail_job()
        "result": {
            "video_id":  None,
            "audio_url": None,
        },
        "error": None,
    }

    with _lock:
        _jobs[job_id] = job_data

    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère l'état actuel d'un job par son identifiant.

    Retourne une copie du dict — évite les mutations hors verrou.
    Retourne None si le job est inconnu ou a été supprimé par le TTL.
    """
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def update_job_step(job_id: str, step: PipelineStep, progress: int) -> None:
    """
    Met à jour l'étape courante et le pourcentage de progression d'un job.
    Passe automatiquement le statut à PROCESSING.
    """
    with _lock:
        if job_id not in _jobs:
            return  # Job inconnu ou expiré — ne pas crasher le pipeline

        _jobs[job_id]["status"]       = JobStatus.PROCESSING
        _jobs[job_id]["current_step"] = step
        _jobs[job_id]["progress"]     = progress
        _jobs[job_id]["updated_at"]   = time.time()


def complete_job(job_id: str, video_id: str, audio_url: str) -> None:
    """
    Marque un job comme terminé avec succès.
    Le job sera supprimé automatiquement après JOB_TTL_SECONDS.
    """
    with _lock:
        if job_id not in _jobs:
            return

        _jobs[job_id]["status"]              = JobStatus.DONE
        _jobs[job_id]["current_step"]        = None
        _jobs[job_id]["progress"]            = 100
        _jobs[job_id]["updated_at"]          = time.time()
        _jobs[job_id]["finished_at"]         = time.time()  # Démarre le TTL
        _jobs[job_id]["result"]["video_id"]  = video_id
        _jobs[job_id]["result"]["audio_url"] = audio_url


def fail_job(job_id: str, error_message: str) -> None:
    """
    Marque un job comme échoué.
    Le job sera supprimé automatiquement après JOB_TTL_SECONDS.
    """
    with _lock:
        if job_id not in _jobs:
            return

        _jobs[job_id]["status"]      = JobStatus.ERROR
        _jobs[job_id]["error"]       = error_message
        _jobs[job_id]["updated_at"]  = time.time()
        _jobs[job_id]["finished_at"] = time.time()  # Démarre le TTL


def get_stats() -> Dict[str, int]:
    """
    Retourne un snapshot des compteurs de jobs par statut.

    Utile pour un endpoint de monitoring (/health ou /admin/stats)
    sans exposer le contenu des jobs.

    Retourne :
        {
            "total":      12,
            "pending":    1,
            "processing": 2,
            "done":       8,
            "error":      1
        }
    """
    with _lock:
        stats: Dict[str, int] = {
            "total":      len(_jobs),
            "pending":    0,
            "processing": 0,
            "done":       0,
            "error":      0,
        }
        for job in _jobs.values():
            status = job["status"]
            if status in stats:
                stats[status] += 1

    return stats