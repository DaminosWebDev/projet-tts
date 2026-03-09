import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    # Clé primaire UUID — imprévisible, unique globalement
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    # Email unique avec index — colonne de recherche principale au login
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    # Hash bcrypt — None pour les comptes OAuth Google
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None
    )

    # Flags de statut du compte
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Identifiant Google — None si inscription classique, unique si OAuth
    google_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        default=None
    )

    # URL photo de profil — Text car les URLs Google peuvent être longues
    avatar_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None
    )

    # Token de vérification email — supprimé après validation
    verification_token: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None
    )

    # Token de reset mot de passe + date d'expiration (1h)
    reset_password_token: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None
    )
    reset_password_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None
    )

    # Horodatages UTC
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # onupdate — mis à jour automatiquement à chaque modification
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relations ORM — triées du plus récent au plus ancien
    # cascade="all, delete-orphan" — jobs supprimés si l'utilisateur est supprimé
    youtube_jobs: Mapped[list["JobYoutube"]] = relationship(
        "JobYoutube",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="JobYoutube.created_at.desc()"
    )

    tts_jobs: Mapped[list["JobTTS"]] = relationship(
        "JobTTS",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="JobTTS.created_at.desc()"
    )

    stt_jobs: Mapped[list["JobSTT"]] = relationship(
        "JobSTT",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="JobSTT.created_at.desc()"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} verified={self.is_verified}>"