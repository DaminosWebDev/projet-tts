"""
==============================================================================
schemas/history.py — Schémas Pydantic pour l'historique des jobs
==============================================================================
QU'EST-CE QU'UN SCHÉMA PYDANTIC ICI ?
  Les modèles SQLAlchemy (models/) définissent comment les données sont
  stockées en DB. Les schémas Pydantic (schemas/) définissent comment
  les données sont exposées via l'API — ce que le client reçoit.

POURQUOI SÉPARER LES DEUX ?
  Le modèle DB peut contenir des données sensibles ou internes
  qu'on ne veut pas exposer (ex: reset_password_token).
  Le schéma API expose uniquement ce dont le frontend a besoin.

  ANALOGIE : Le modèle DB = le dossier complet d'un patient à l'hôpital
             Le schéma API = le résumé donné au patient
==============================================================================
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── Schémas individuels ───────────────────────────────────────────────────────

class JobYoutubeResponse(BaseModel):
    """Représente un job YouTube dans l'historique."""
    id: str
    youtube_url: str
    video_id: Optional[str]
    video_title: Optional[str]
    source_language: Optional[str]
    target_language: str
    audio_url: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
        # from_attributes=True → permet de créer ce schéma depuis un objet SQLAlchemy


class JobTTSResponse(BaseModel):
    """Représente un job TTS dans l'historique."""
    id: str
    input_text: str
    voice: str
    language: str
    audio_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class JobSTTResponse(BaseModel):
    """Représente un job STT dans l'historique."""
    id: str
    filename: str
    detected_language: Optional[str]
    transcription_text: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Schéma global ─────────────────────────────────────────────────────────────

class HistoryResponse(BaseModel):
    """
    Réponse complète de GET /users/me/history.
    Contient les 5 derniers jobs de chaque type.
    """
    youtube: list[JobYoutubeResponse]
    tts: list[JobTTSResponse]
    stt: list[JobSTTResponse]
    total: int
    # total = nombre total de jobs tous types confondus
    # Utile pour afficher un badge dans le frontend