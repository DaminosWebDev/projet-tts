import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class JobTTS(Base):
    __tablename__ = "jobs_tts"

    # Clé primaire UUID — généré côté Python
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    # Clé étrangère — suppression en cascade si l'utilisateur est supprimé
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Texte soumis — Text car peut atteindre MAX_TEXT_LENGTH (2000 chars)
    input_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # Voix Kokoro utilisée — stockée pour reproduire la synthèse depuis l'historique
    voice: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ff_siwis"
    )

    # Langue de synthèse — "fr" ou "en" selon le modèle Kokoro chargé
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="fr"
    )

    # URL du fichier audio — None tant que la génération n'est pas terminée
    audio_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None
    )

    # Horodatage UTC — lambda pour évaluation à l'insertion, pas à la définition
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Relation ORM — accès à job.user sans requête manuelle
    user: Mapped["User"] = relationship(
        "User",
        back_populates="tts_jobs"
    )

    def __repr__(self) -> str:
        return f"<JobTTS id={self.id} user_id={self.user_id} text={self.input_text[:30]}>"