"""
==============================================================================
job_manager.py — Gestionnaire d'état des jobs asynchrones YouTube
==============================================================================
RESPONSABILITÉS :
  - Créer et stocker les jobs en mémoire (dict Python global)
  - Mettre à jour le statut et la progression de chaque job
  - Exposer des fonctions utilitaires pour lire/écrire l'état d'un job

ANALOGIE :
  C'est comme un tableau de bord d'aéroport : chaque vol (job) a un statut
  (en attente, en vol, atterri, annulé). Le tableau est mis à jour en temps
  réel sans que les passagers (clients HTTP) aient besoin d'appeler l'avion.

POURQUOI CE MODULE EXISTE :
  Le pipeline YouTube dure 30-180s. Sans ce système, le client HTTP devrait
  attendre toute la durée → timeout garanti.
  Avec ce système : POST répond en <100ms avec un job_id, le client poll GET.

CYCLE DE VIE D'UN JOB :
  PENDING → PROCESSING → DONE
  PENDING → PROCESSING → ERROR
==============================================================================
"""

# ── Imports ───────────────────────────────────────────────────────────────────

import uuid
# QU'EST-CE QUE C'EST : Génère des identifiants uniques universels (UUID v4).
# POURQUOI : Chaque job doit avoir un ID non-devinable et sans collision.
# COMMENT : uuid4() = 128 bits aléatoires → "a3f8c2d1-4b5e-41d4-a716-446655440000"

import time
# QU'EST-CE QUE C'EST : Module standard pour lire l'heure système.
# POURQUOI : Horodater création/fin de chaque job (debug, monitoring, TTL futur).
# COMMENT : time.time() retourne un float = secondes depuis l'epoch Unix (1970-01-01).

import threading
# QU'EST-CE QUE C'EST : Module de synchronisation multi-thread.
# POURQUOI : BackgroundTasks FastAPI tourne dans un thread séparé des requêtes GET.
#            Sans verrou, deux threads pourraient corrompre le dict simultanément.
# COMMENT : threading.Lock() = mutex — un seul thread à la fois peut modifier _jobs.

from typing import Optional, Dict, Any
# QU'EST-CE QUE C'EST : Annotations de types Python.
# POURQUOI : Code auto-documenté, erreurs détectées par les IDE et mypy.
# COMMENT : Optional[X] = X ou None ; Dict[K,V] = dict typé ; Any = type quelconque.

from enum import Enum
# QU'EST-CE QUE C'EST : Classe de base pour énumérations (constantes nommées).
# POURQUOI : Éviter les "magic strings" comme "pending" éparpillés dans le code.
# COMMENT : class JobStatus(str, Enum) → hérite de str pour être sérialisable en JSON.

# ── Énumérations ──────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    """
    États possibles d'un job YouTube.

    Hérite de str ET Enum :
    - str  → valeurs directement sérialisables JSON sans .value
    - Enum → typage fort, pas de faute de frappe possible
    """
    PENDING    = "pending"     # Créé, pas encore démarré
    PROCESSING = "processing"  # Pipeline en cours (étapes B→G)
    DONE       = "done"        # Terminé avec succès
    ERROR      = "error"       # Échec (message dans job["error"])


class PipelineStep(str, Enum):
    """
    Étapes du pipeline YouTube dans l'ordre d'exécution.
    Utilisées pour afficher la barre de progression côté frontend.

    ANALOGIE : Les étapes d'un vol affiché sur le tableau de bord :
    "Embarquement → Décollage → Croisière → Atterrissage"
    """
    DOWNLOAD   = "B_download"    # Téléchargement audio WAV via yt-dlp
    TRANSCRIBE = "C_transcribe"  # Transcription Faster-Whisper → segments horodatés
    TRANSLATE  = "D_translate"   # Traduction LibreTranslate (en parallèle)
    TTS        = "E_tts"         # Génération TTS Kokoro par segment
    STRETCH    = "F_stretch"     # Time-stretching ffmpeg + RubberBand
    ASSEMBLE   = "G_assemble"    # Assemblage piste audio finale + loudnorm 2 passes

# ── Stockage global ───────────────────────────────────────────────────────────

# QU'EST-CE QUE C'EST : Dict global contenant TOUS les jobs actifs de l'application.
# POURQUOI : Solution zéro-dépendance (pas de Redis, pas de DB). Suffisant pour
#            une instance unique. Attention : données perdues au redémarrage serveur.
# COMMENT : Clé = job_id (str UUID), Valeur = dict complet du job.
_jobs: Dict[str, Dict[str, Any]] = {}

# QU'EST-CE QUE C'EST : Verrou mutex pour accès concurrent à _jobs.
# POURQUOI : FastAPI lance BackgroundTasks dans un thread pool ; les requêtes GET
#            arrivent depuis d'autres threads → risque de race condition sans verrou.
# COMMENT : Utilisé comme "with _lock:" → bloc atomique, un seul thread à la fois.
_lock = threading.Lock()

# ── Fonctions publiques ───────────────────────────────────────────────────────

def create_job(youtube_url: str) -> str:
    """
    Crée un nouveau job en mémoire et retourne son identifiant.

    QU'EST-CE QUE C'EST : Initialisation complète d'un job YouTube.
    POURQUOI : Centralise la structure d'un job — un seul endroit à modifier si
               on ajoute un champ.
    COMMENT : Génère un UUID, construit le dict avec statut PENDING, l'insère
              dans _jobs de manière thread-safe.

    Paramètres :
        youtube_url (str) : URL YouTube soumise par l'utilisateur.
                            Ex: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    Retourne :
        str : UUID v4 du job. Ex: "a3f8c2d1-4b5e-41d4-a716-446655440000"

    Exemple :
        >>> job_id = create_job("https://youtu.be/dQw4w9WgXcQ")
        >>> get_job(job_id)["status"]
        'pending'
    """
    job_id = str(uuid.uuid4())

    job_data: Dict[str, Any] = {
        "job_id":       job_id,
        "status":       JobStatus.PENDING,
        "youtube_url":  youtube_url,
        "current_step": None,          # Aucune étape en cours au démarrage
        "progress":     0,             # 0% au démarrage
        "created_at":   time.time(),
        "updated_at":   time.time(),
        "finished_at":  None,          # Rempli à la fin (succès ou erreur)
        "result": {
            "video_id":  None,         # Ex: "dQw4w9WgXcQ" — pour l'iframe YouTube
            "audio_url": None,         # Ex: "/youtube/audio/job_id" — piste WAV traduite
        },
        "error": None,                 # Message d'erreur si status == ERROR
    }

    with _lock:
        _jobs[job_id] = job_data

    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère l'état actuel d'un job par son identifiant.

    QU'EST-CE QUE C'EST : Lecture thread-safe d'un job dans le dict global.
    POURQUOI : Appelé toutes les 2s par le frontend via GET /youtube/status/{job_id}.
    COMMENT : Retourne une copie du dict pour éviter les mutations externes
              hors du verrou.

    Paramètres :
        job_id (str) : UUID du job.

    Retourne :
        Optional[Dict] : Copie du dict du job, ou None si job_id inconnu.

    Exemple :
        >>> job = get_job("a3f8c2d1-...")
        >>> job["progress"]
        45
    """
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def update_job_step(job_id: str, step: PipelineStep, progress: int) -> None:
    """
    Met à jour l'étape courante et le pourcentage de progression d'un job.

    QU'EST-CE QUE C'EST : Notification de progression pendant le pipeline.
    POURQUOI : Permet au frontend d'afficher "Étape C — Transcription… 25%"
               plutôt qu'un spinner générique.
    COMMENT : Passe le status à PROCESSING si ce n'est pas encore le cas,
              met à jour step, progress et updated_at.

    Paramètres :
        job_id   (str)          : UUID du job.
        step     (PipelineStep) : Étape courante (ex: PipelineStep.TRANSCRIBE).
        progress (int)          : Avancement global en % (0-100).

    Exemple :
        >>> update_job_step(job_id, PipelineStep.TRANSCRIBE, 25)
        # → status="processing", current_step="C_transcribe", progress=25
    """
    with _lock:
        if job_id not in _jobs:
            return  # Job inconnu → on ignore (ne pas crasher le pipeline)

        _jobs[job_id]["status"]       = JobStatus.PROCESSING
        _jobs[job_id]["current_step"] = step
        _jobs[job_id]["progress"]     = progress
        _jobs[job_id]["updated_at"]   = time.time()


def complete_job(job_id: str, video_id: str, audio_url: str) -> None:
    """
    Marque un job comme terminé avec succès et stocke le résultat final.

    QU'EST-CE QUE C'EST : Finalisation d'un job après traitement complet.
    POURQUOI : Le frontend poll GET /status jusqu'à voir status="done",
               puis lit video_id et audio_url pour lancer le player.
    COMMENT : Status → DONE, progress → 100, résultats stockés, finished_at horodaté.

    Paramètres :
        job_id    (str) : UUID du job.
        video_id  (str) : ID YouTube pour l'iframe. Ex: "dQw4w9WgXcQ"
        audio_url (str) : URL de la piste WAV. Ex: "/youtube/audio/job_id"

    Exemple :
        >>> complete_job(job_id, "dQw4w9WgXcQ", "/youtube/audio/abc-123")
        >>> get_job(job_id)["status"]
        'done'
    """
    with _lock:
        if job_id not in _jobs:
            return

        _jobs[job_id]["status"]              = JobStatus.DONE
        _jobs[job_id]["current_step"]        = None   # Plus d'étape active
        _jobs[job_id]["progress"]            = 100
        _jobs[job_id]["updated_at"]          = time.time()
        _jobs[job_id]["finished_at"]         = time.time()
        _jobs[job_id]["result"]["video_id"]  = video_id
        _jobs[job_id]["result"]["audio_url"] = audio_url


def fail_job(job_id: str, error_message: str) -> None:
    """
    Marque un job comme échoué et stocke le message d'erreur.

    QU'EST-CE QUE C'EST : Gestion d'échec du pipeline.
    POURQUOI : Sans ça, le frontend resterait en polling infini si une étape
               plante — il doit pouvoir afficher "Erreur : <détail>".
    COMMENT : Status → ERROR, error stocké, finished_at horodaté.

    Paramètres :
        job_id        (str) : UUID du job.
        error_message (str) : Description de l'erreur.
                              Ex: "yt-dlp: video unavailable"

    Exemple :
        >>> fail_job(job_id, "LibreTranslate timeout after 30s")
        >>> get_job(job_id)["status"]
        'error'
    """
    with _lock:
        if job_id not in _jobs:
            return

        _jobs[job_id]["status"]      = JobStatus.ERROR
        _jobs[job_id]["error"]       = error_message
        _jobs[job_id]["updated_at"]  = time.time()
        _jobs[job_id]["finished_at"] = time.time()