"""
==============================================================================
models/job_youtube.py — Modèle SQLAlchemy de la table "jobs_youtube"
==============================================================================
RESPONSABILITÉ :
  Stocker l'historique des traductions YouTube de chaque utilisateur.
  On garde les 5 dernières par utilisateur (logique dans le router).

RELATION AVEC USER :
  Chaque job appartient à un utilisateur → clé étrangère user_id
  ANALOGIE : comme une commande dans un restaurant —
             chaque commande appartient à un client précis
==============================================================================
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class JobYoutube(Base):

    __tablename__ = "jobs_youtube"

    # ── Identifiant ───────────────────────────────────────────────────────────

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    # ── Clé étrangère vers users ──────────────────────────────────────────────

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        # ForeignKey("users.id") → cette colonne référence la colonne "id" de la table "users"
        # ANALOGIE : comme un numéro de client sur une commande —
        #            il pointe vers un client existant dans la table clients
        #
        # ondelete="CASCADE" → si l'utilisateur est supprimé,
        #                      tous ses jobs sont supprimés automatiquement
        # POURQUOI CASCADE : évite les "jobs orphelins" sans utilisateur
        nullable=False,
        index=True
        # index=True → on cherche souvent "tous les jobs de l'user X"
        # L'index rend cette requête rapide
    )

    # ── Données du job ────────────────────────────────────────────────────────

    youtube_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False
        # L'URL YouTube originale soumise par l'utilisateur
        # Ex: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )

    video_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default=None
        # L'ID YouTube extrait par yt-dlp
        # Ex: "dQw4w9WgXcQ"
        # Utilisé par le frontend pour construire l'iframe YouTube
    )

    video_title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None
        # Titre de la vidéo récupéré par yt-dlp
        # Ex: "Rick Astley - Never Gonna Give You Up"
        # Affiché dans l'historique pour que l'user reconnaisse la vidéo
    )

    source_language: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        default=None
        # Langue détectée par Whisper
        # Ex: "en", "es", "de"
        # None si la détection a échoué
    )

    target_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="fr"
        # Langue cible de la traduction
        # Ex: "fr"
    )

    audio_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None
        # URL de la piste audio traduite
        # Ex: "/youtube/audio/c885522d-..."
        # Permet de réécouter depuis l'historique
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="done"
        # Statut final du job : "done" ou "error"
        # On ne sauvegarde en historique que les jobs terminés
    )

    # ── Timestamps ────────────────────────────────────────────────────────────

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # ── Relation SQLAlchemy ───────────────────────────────────────────────────

    user: Mapped["User"] = relationship(
        "User",
        back_populates="youtube_jobs"
        # QU'EST-CE QUE C'EST : Lien Python entre JobYoutube et User.
        # POURQUOI : Permet d'écrire job.user pour accéder à l'utilisateur
        #            et user.youtube_jobs pour accéder à tous ses jobs
        # back_populates = dit à SQLAlchemy que la relation est bidirectionnelle
        # ANALOGIE : comme un lien hypertexte dans les deux sens —
        #            depuis le job on peut aller vers l'user, et vice-versa
    )

    def __repr__(self) -> str:
        return f"<JobYoutube id={self.id} user_id={self.user_id} url={self.youtube_url[:30]}>"