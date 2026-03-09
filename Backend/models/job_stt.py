import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class JobSTT(Base):
    __tablename__ = "jobs_stt"

    # Clé primaire UUID — généré côté Python pour cohérence avec les autres modèles
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

    # Nom original du fichier — affiché dans l'historique utilisateur
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    # Langue détectée par Whisper — None si la détection a échoué
    detected_language: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        default=None
    )

    # Transcription complète — Text car potentiellement très long
    transcription_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None
    )

    # Horodatage UTC — pour tri et affichage dans l'historique
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Relation ORM — permet d'accéder à job.user directement sans requête manuelle
    user: Mapped["User"] = relationship(
        "User",
        back_populates="stt_jobs"
    )

    def __repr__(self) -> str:
        return f"<JobSTT id={self.id} user_id={self.user_id} file={self.filename}>"