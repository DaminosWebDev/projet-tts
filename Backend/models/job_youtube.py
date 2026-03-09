import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class JobYoutube(Base):
    __tablename__ = "jobs_youtube"

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

    # URL soumise par l'utilisateur — conservée pour l'historique
    youtube_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    # ID extrait par yt-dlp — permet au frontend de reconstruire l'iframe YouTube
    video_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default=None
    )

    # Titre récupéré par yt-dlp — affiché dans l'historique
    video_title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None
    )

    # Langue source détectée par Whisper — None si détection échouée
    source_language: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        default=None
    )

    # Langue cible choisie par l'utilisateur
    target_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="fr"
    )

    # URL de la piste audio traduite — None tant que le traitement n'est pas terminé
    audio_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None
    )

    # Statut final — seuls les jobs terminés sont persistés en historique
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="done"
    )

    # Horodatage UTC — lambda pour évaluation à l'insertion
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Relation ORM bidirectionnelle — job.user et user.youtube_jobs
    user: Mapped["User"] = relationship(
        "User",
        back_populates="youtube_jobs"
    )

    def __repr__(self) -> str:
        return f"<JobYoutube id={self.id} user_id={self.user_id} url={self.youtube_url[:30]}>"