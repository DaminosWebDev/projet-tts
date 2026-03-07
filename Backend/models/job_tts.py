"""
==============================================================================
models/job_tts.py — Modèle SQLAlchemy de la table "jobs_tts"
==============================================================================
RESPONSABILITÉ :
  Stocker l'historique des synthèses vocales (TTS) de chaque utilisateur.
  On garde les 5 dernières par utilisateur.
==============================================================================
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class JobTTS(Base):

    __tablename__ = "jobs_tts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    input_text: Mapped[str] = mapped_column(
        Text,
        # Text et pas String car le texte TTS peut être long (jusqu'à 2000 chars)
        nullable=False
    )

    voice: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ff_siwis"
        # Voix Kokoro utilisée pour la synthèse
        # Ex: "ff_siwis", "af_heart"
    )

    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="fr"
    )

    audio_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None
        # URL du fichier audio généré
        # Permet de réécouter depuis l'historique
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="tts_jobs"
    )

    def __repr__(self) -> str:
        return f"<JobTTS id={self.id} user_id={self.user_id} text={self.input_text[:30]}>"