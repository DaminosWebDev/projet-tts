"""
==============================================================================
models/user.py — Modèle SQLAlchemy de la table "users"
==============================================================================
QU'EST-CE QU'UN MODÈLE SQLALCHEMY ?
  Un modèle = une classe Python qui représente une table en base de données.
  Chaque attribut de la classe = une colonne de la table.

  ANALOGIE : C'est comme un formulaire papier —
    Le formulaire lui-même = la classe User
    Chaque champ du formulaire = chaque colonne (id, email, etc.)
    Un formulaire rempli = une ligne dans la table (un utilisateur)

CE QUE SQLALCHEMY FAIT AUTOMATIQUEMENT :
  Quand tu écris : user = User(email="test@test.com")
  SQLAlchemy traduit en SQL : INSERT INTO users (email) VALUES ('test@test.com')

  Quand tu écris : await db.execute(select(User).where(User.email == "test@test.com"))
  SQLAlchemy traduit en SQL : SELECT * FROM users WHERE email = 'test@test.com'
==============================================================================
"""

# ── Imports ───────────────────────────────────────────────────────────────────

import uuid
# Pour générer des IDs uniques (UUID v4)
# Ex: "a3f8c2d1-4b5e-41d4-a716-446655440000"

from datetime import datetime, timezone
# datetime = type Python pour les dates et heures
# timezone = pour stocker les dates en UTC (standard international)
# POURQUOI UTC : évite les problèmes de fuseaux horaires
# Un utilisateur en France et un en Japon ont le même timestamp UTC

from sqlalchemy import String, Boolean, DateTime, Text
# Types de colonnes SQLAlchemy :
#   String  → VARCHAR en SQL  → texte de longueur limitée (ex: email)
#   Boolean → BOOLEAN en SQL  → vrai/faux
#   DateTime→ TIMESTAMP en SQL→ date + heure
#   Text    → TEXT en SQL     → texte de longueur illimitée

from sqlalchemy.orm import Mapped, mapped_column, relationship
# Mapped et mapped_column = syntaxe moderne SQLAlchemy 2.0
# POURQUOI cette syntaxe ?
#   Ancienne syntaxe (SQLAlchemy 1.x) :
#     id = Column(Integer, primary_key=True)
#   Nouvelle syntaxe (SQLAlchemy 2.x) :
#     id: Mapped[int] = mapped_column(primary_key=True)
#   La nouvelle syntaxe est typée → les IDE détectent les erreurs automatiquement

from database import Base
# Base = la classe parente définie dans database.py
# Tous les modèles héritent de Base pour être reconnus par SQLAlchemy


# ── Modèle User ───────────────────────────────────────────────────────────────

class User(Base):
    """
    Table "users" — stocke tous les comptes utilisateurs.

    Un utilisateur peut s'inscrire de deux façons :
    1. Email + mot de passe (inscription classique)
    2. OAuth Google (connexion via Google)

    Les deux méthodes créent une ligne dans cette table.
    La différence : connexion Google → hashed_password est None
    """

    __tablename__ = "users"
    # QU'EST-CE QUE C'EST : Nom de la table en base de données.
    # CONVENTION : toujours en minuscules, pluriel, avec underscores
    # Ex: User → "users", JobYoutube → "jobs_youtube"

    # ── Identifiant ───────────────────────────────────────────────────────────

    id: Mapped[str] = mapped_column(
        String(36),
        # String(36) = VARCHAR(36) en SQL
        # 36 caractères = taille exacte d'un UUID v4
        # Ex: "a3f8c2d1-4b5e-41d4-a716-446655440000" = 36 caractères

        primary_key=True,
        # primary_key=True → cette colonne identifie chaque ligne de manière unique
        # PostgreSQL crée automatiquement un index sur cette colonne (recherche rapide)

        default=lambda: str(uuid.uuid4())
        # default = valeur automatique si non fournie
        # lambda = fonction anonyme appelée à chaque création d'un User
        # uuid.uuid4() génère un UUID aléatoire
        # str() le convertit en string "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        # POURQUOI UUID et pas un entier auto-incrémenté (1, 2, 3...) ?
        # - UUID : impossible à deviner → sécurité (pas de /users/1, /users/2...)
        # - UUID : unique globalement → utile si on fusionne des DBs
        # - Entier : plus lisible mais prédictible → risque d'énumération
    )

    # ── Email ─────────────────────────────────────────────────────────────────

    email: Mapped[str] = mapped_column(
        String(255),
        # 255 = longueur max standard pour un email (RFC 5321)

        unique=True,
        # unique=True → PostgreSQL interdit deux users avec le même email
        # Tentative de doublon → IntegrityError (qu'on catchera dans le router)

        nullable=False,
        # nullable=False → la colonne ne peut pas être NULL (valeur obligatoire)
        # Équivalent SQL : NOT NULL

        index=True,
        # index=True → PostgreSQL crée un index sur cette colonne
        # POURQUOI : on cherche souvent un user par son email (login)
        # Avec index : recherche O(log n) au lieu de O(n) → beaucoup plus rapide
    )

    # ── Mot de passe ──────────────────────────────────────────────────────────

    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        # nullable=True → peut être NULL
        # POURQUOI nullable : les utilisateurs OAuth Google n'ont pas de mot de passe
        # Ils se connectent via Google → pas besoin de mot de passe local
        default=None
    )
    # SÉCURITÉ IMPORTANTE :
    # On ne stocke JAMAIS le mot de passe en clair.
    # "password123" → bcrypt → "$2b$12$K8Hvb..." (hash irréversible)
    # Même si la DB est compromise → impossible de retrouver les vrais mots de passe

    # ── Statut du compte ──────────────────────────────────────────────────────

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        # False par défaut → l'email n'est pas encore vérifié
        # Devient True quand l'utilisateur clique le lien dans l'email de vérification
        nullable=False
    )
    # POURQUOI vérifier l'email ?
    # - Évite les inscriptions avec des emails inventés
    # - Permet de contacter l'utilisateur (reset password, notifications)
    # - Réduit le spam et les faux comptes

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        # True par défaut → compte actif dès la création
        # False = compte suspendu (admin peut désactiver un user sans le supprimer)
        nullable=False
    )

    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        # False par défaut → utilisateur normal
        # True = accès aux routes d'administration (si on en ajoute)
        nullable=False
    )

    # ── OAuth Google ──────────────────────────────────────────────────────────

    google_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        # None si l'utilisateur s'est inscrit par email/password
        # Rempli si l'utilisateur s'est connecté via Google
        # Ex: "118234567890123456789" (ID unique Google)
        unique=True,
        default=None
    )

    avatar_url: Mapped[str | None] = mapped_column(
        Text,
        # Text (pas String) car les URLs peuvent être longues
        nullable=True,
        default=None
        # URL de la photo de profil Google
        # Ex: "https://lh3.googleusercontent.com/a/..."
    )

    # ── Tokens de vérification ────────────────────────────────────────────────

    verification_token: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None
        # Token envoyé par email pour vérifier l'adresse
        # Généré à l'inscription, supprimé après vérification
        # Ex: "a3f8c2d14b5e41d4a716446655440000" (hex aléatoire)
    )

    reset_password_token: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None
        # Token envoyé par email pour réinitialiser le mot de passe
        # Valide seulement pendant PASSWORD_RESET_EXPIRE_HOURS (1h)
    )

    reset_password_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        # timezone=True → stocke le fuseau horaire avec la date
        # Toujours en UTC dans notre app
        nullable=True,
        default=None
        # Date d'expiration du token de reset
        # Si datetime.now() > reset_password_expires → token expiré
    )

    # ── Timestamps ────────────────────────────────────────────────────────────

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
        # datetime.now(timezone.utc) = heure actuelle en UTC
        # lambda = appelé à chaque création d'un User (pas une valeur fixe)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
        # onupdate = mis à jour automatiquement à chaque modification du User
        # Pratique pour savoir quand un compte a été modifié pour la dernière fois
    )
        # ── Relations vers l'historique ───────────────────────────────────────────

    youtube_jobs: Mapped[list["JobYoutube"]] = relationship(
        "JobYoutube",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="JobYoutube.created_at.desc()"
        # order_by → les jobs sont triés du plus récent au plus ancien
        # cascade="all, delete-orphan" → si l'user est supprimé,
        #                                tous ses jobs sont supprimés aussi
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

    # ── Représentation ────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        """Représentation lisible pour le debug."""
        return f"<User id={self.id} email={self.email} verified={self.is_verified}>"
    # __repr__ = ce qui s'affiche quand tu print() un objet User
    # Ex: print(user) → <User id=a3f8... email=test@test.com verified=False>

