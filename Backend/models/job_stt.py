"""
==============================================================================
models/job_stt.py — Modèle SQLAlchemy de la table "jobs_stt"
==============================================================================
RESPONSABILITÉ :
  Stocker l'historique des transcriptions audio (STT) de chaque utilisateur.
  On garde les 5 dernières par utilisateur.
==============================================================================
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class JobSTT(Base):

    __tablename__ = "jobs_stt"

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

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
        # Nom original du fichier uploadé par l'utilisateur
        # Ex: "interview.wav", "podcast_episode_12.mp3"
        # Affiché dans l'historique pour que l'user reconnaisse le fichier
    )

    detected_language: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        default=None
        # Langue détectée par Whisper
        # Ex: "fr", "en"
    )

    transcription_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None
        # Le texte transcrit complet
        # Peut être très long → Text (pas String)
        # Affiché dans l'historique pour que l'user retrouve sa transcription
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="stt_jobs"
    )

    def __repr__(self) -> str:
        return f"<JobSTT id={self.id} user_id={self.user_id} file={self.filename}>"