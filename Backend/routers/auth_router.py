"""
==============================================================================
routers/auth_router.py — Endpoints d'authentification
==============================================================================
ROUTES IMPLÉMENTÉES :
  POST /auth/register          → créer un compte email/password
  GET  /auth/verify-email      → vérifier l'email via le token reçu par mail
  POST /auth/login             → connexion, retourne access + refresh tokens
  POST /auth/refresh           → renouveler l'access token
  POST /auth/forgot-password   → demander un email de reset
  POST /auth/reset-password    → appliquer le nouveau mot de passe
  GET  /auth/me                → profil de l'utilisateur connecté

SÉCURITÉ :
  - Mots de passe hachés avec bcrypt (jamais en clair)
  - Tokens JWT signés avec HS256
  - Tokens de vérification à usage unique (supprimés après utilisation)
  - Tokens de reset avec expiration (1h)
  - Messages d'erreur génériques (pas d'info sur l'existence d'un email)
==============================================================================
"""

import secrets
# secrets.token_hex() = génère des tokens cryptographiquement sécurisés
# POURQUOI secrets et pas random :
#   random = pseudo-aléatoire → prévisible → dangereux pour la sécurité
#   secrets = aléatoire cryptographique → imprévisible → sûr

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
# EmailStr = type Pydantic qui valide automatiquement le format email
# Ex: "pas_un_email" → 422 Unprocessable Entity automatiquement

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.user import User
from auth.password import hash_password, verify_password, is_password_strong
from auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from auth.dependencies import get_current_user
from emails.email_service import (
    send_verification_email,
    send_reset_password_email,
)
from config import PASSWORD_RESET_EXPIRE_HOURS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
# tags=["Authentication"] → groupe les routes dans la doc Swagger


# ── Modèles Pydantic ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Corps de la requête POST /auth/register"""
    email: EmailStr = Field(
        ...,
        description="Adresse email valide",
        json_schema_extra={"example": "user@example.com"}
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Mot de passe (min 8 caractères)",
        json_schema_extra={"example": "MonMotDePasse123"}
    )


class LoginRequest(BaseModel):
    """Corps de la requête POST /auth/login"""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Corps de la requête POST /auth/refresh"""
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Corps de la requête POST /auth/forgot-password"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Corps de la requête POST /auth/reset-password"""
    token: str
    new_password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    """Réponse contenant les tokens JWT"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # token_type = "bearer" → standard OAuth2
    # Le client doit envoyer : "Authorization: Bearer <access_token>"


class UserResponse(BaseModel):
    """Réponse contenant les infos publiques d'un utilisateur"""
    id: str
    email: str
    is_verified: bool
    avatar_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
        # from_attributes=True → permet de créer ce schéma depuis un objet SQLAlchemy
        # Sans ça → Pydantic ne sait pas lire les attributs d'un objet User


# ── POST /auth/register ───────────────────────────────────────────────────────

@router.post("/register", status_code=201)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Crée un nouveau compte utilisateur.

    FLUX :
        1. Valide le format email + force du mot de passe
        2. Vérifie que l'email n'est pas déjà utilisé
        3. Hache le mot de passe avec bcrypt
        4. Génère un token de vérification email
        5. Crée l'utilisateur en DB
        6. Envoie l'email de vérification
        7. Retourne un message de succès

    Retourne (201 Created) :
        { "message": "Compte créé. Vérifiez votre email." }
    """

    # ── Étape 1 : Valider la force du mot de passe ────────────────────────────
    is_strong, reason = is_password_strong(request.password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=reason
        )

    # ── Étape 2 : Vérifier que l'email n'existe pas déjà ─────────────────────
    existing_user = await db.execute(
        select(User).where(User.email == request.email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            # 409 Conflict = "la ressource existe déjà"
            detail="Un compte existe déjà avec cet email"
        )

    # ── Étape 3 : Hacher le mot de passe ─────────────────────────────────────
    hashed = hash_password(request.password)
    # "MonMotDePasse123" → "$2b$12$..."
    # On ne stocke JAMAIS request.password en DB

    # ── Étape 4 : Générer le token de vérification ────────────────────────────
    verification_token = secrets.token_hex(32)
    # token_hex(32) = 64 caractères hexadécimaux aléatoires
    # Ex: "a3f8c2d14b5e41d4a716446655440000bcd123ef456789ab..."
    # Cryptographiquement sécurisé → impossible à deviner

    # ── Étape 5 : Créer l'utilisateur en DB ──────────────────────────────────
    new_user = User(
        email=request.email,
        hashed_password=hashed,
        verification_token=verification_token,
        is_verified=False,
        # False → l'email doit être confirmé avant de pouvoir se connecter
    )
    db.add(new_user)
    # db.add() = ajoute l'objet à la session (pas encore en DB)
    # Le commit() dans get_db() enverra réellement le INSERT

    await db.flush()
    # flush() = envoie le INSERT sans committer la transaction
    # POURQUOI flush() avant commit() :
    #   On a besoin que l'user soit en DB pour envoyer l'email
    #   Mais si l'email échoue on veut pouvoir rollback
    #   flush() = "envoie à PostgreSQL mais garde la transaction ouverte"

    # ── Étape 6 : Envoyer l'email de vérification ─────────────────────────────
    await send_verification_email(new_user.email, verification_token)
    # Si l'envoi échoue → on log l'erreur mais on ne bloque pas l'inscription
    # L'utilisateur peut demander un renvoi de l'email plus tard

    logger.info(f"Nouveau compte créé : {new_user.email}")

    return {
        "message": "Compte créé avec succès. Vérifiez votre boîte email pour activer votre compte.",
        "email": new_user.email
    }


# ── GET /auth/verify-email ────────────────────────────────────────────────────

@router.get("/verify-email")
async def verify_email(
    token: str,
    # token = paramètre de query string
    # Ex: GET /auth/verify-email?token=a3f8c2d1...
    db: AsyncSession = Depends(get_db)
):
    """
    Vérifie l'adresse email via le token reçu par email.

    FLUX :
        1. Cherche un utilisateur avec ce token de vérification
        2. Vérifie que le token existe (pas déjà utilisé)
        3. Marque l'email comme vérifié
        4. Supprime le token (usage unique)
        5. Retourne les tokens JWT → connexion automatique

    Retourne (200 OK) :
        TokenResponse avec access_token + refresh_token
    """

    # ── Chercher l'utilisateur avec ce token ──────────────────────────────────
    result = await db.execute(
        select(User).where(User.verification_token == token)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de vérification invalide ou déjà utilisé"
        )

    # ── Marquer comme vérifié + supprimer le token ────────────────────────────
    user.is_verified = True
    user.verification_token = None
    # None = supprime le token → usage unique
    # Si quelqu'un essaie de réutiliser le lien → "token invalide"

    logger.info(f"Email vérifié : {user.email}")

    # ── Connecter automatiquement l'utilisateur ───────────────────────────────
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )
    # On connecte automatiquement après vérification
    # Meilleure UX : l'utilisateur n'a pas à se reconnecter


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Connecte un utilisateur et retourne les tokens JWT.

    FLUX :
        1. Cherche l'utilisateur par email
        2. Vérifie le mot de passe avec bcrypt
        3. Vérifie que le compte est actif et vérifié
        4. Crée et retourne access_token + refresh_token

    SÉCURITÉ — Messages génériques :
        On retourne toujours "Email ou mot de passe incorrect"
        Jamais "Email introuvable" ou "Mot de passe incorrect" séparément.
        POURQUOI : évite l'énumération des emails
        (un attaquant ne peut pas savoir si un email existe dans la DB)

    Retourne (200 OK) :
        TokenResponse avec access_token + refresh_token
    """

    GENERIC_ERROR = "Email ou mot de passe incorrect"
    # Message générique réutilisé partout dans cette route
    # Jamais de message spécifique sur ce qui est incorrect

    # ── Chercher l'utilisateur ────────────────────────────────────────────────
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_ERROR
        )

    # ── Vérifier le mot de passe ──────────────────────────────────────────────
    if not user.hashed_password:
        # Compte Google → pas de mot de passe local
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ce compte utilise la connexion Google"
        )

    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_ERROR
        )

    # ── Vérifier le statut du compte ──────────────────────────────────────────
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé. Contactez le support."
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email non vérifié. Vérifiez votre boîte mail."
        )

    # ── Créer et retourner les tokens ─────────────────────────────────────────
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)

    logger.info(f"Connexion réussie : {user.email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Renouvelle l'access token via le refresh token.

    FLUX :
        1. Valide le refresh token JWT
        2. Charge l'utilisateur depuis la DB
        3. Crée un nouvel access token + nouveau refresh token
        4. Retourne les deux tokens

    POURQUOI renouveler aussi le refresh token ?
        "Refresh token rotation" = bonne pratique de sécurité.
        Chaque utilisation du refresh token en génère un nouveau.
        Si un refresh token est volé et utilisé → l'ancien est "consommé"
        → l'attaquant ne peut pas l'utiliser une 2ème fois.

    Retourne (200 OK) :
        TokenResponse avec nouveaux access_token + refresh_token
    """

    # ── Valider le refresh token ──────────────────────────────────────────────
    user_id = verify_refresh_token(request.refresh_token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide ou expiré"
        )

    # ── Charger l'utilisateur ─────────────────────────────────────────────────
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable ou inactif"
        )

    # ── Créer les nouveaux tokens (rotation) ──────────────────────────────────
    new_access_token = create_access_token(user.id, user.email)
    new_refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


# ── POST /auth/forgot-password ────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Envoie un email de réinitialisation de mot de passe.

    SÉCURITÉ — Réponse identique email existant ou non :
        On retourne TOUJOURS le même message de succès.
        POURQUOI : si on retournait une erreur quand l'email n'existe pas,
        un attaquant pourrait énumérer tous les emails de la DB.

    Retourne (200 OK) :
        { "message": "Si cet email existe, un lien a été envoyé." }
    """

    GENERIC_RESPONSE = {
        "message": "Si un compte existe avec cet email, vous recevrez un lien de réinitialisation."
    }
    # Même réponse dans tous les cas → pas d'info sur l'existence de l'email

    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Email inexistant → on retourne quand même la réponse générique
        return GENERIC_RESPONSE

    if not user.is_verified:
        # Compte non vérifié → pas de reset (l'email n'est peut-être pas valide)
        return GENERIC_RESPONSE

    # ── Générer le token de reset ─────────────────────────────────────────────
    reset_token = secrets.token_hex(32)
    reset_expires = datetime.now(timezone.utc) + timedelta(
        hours=PASSWORD_RESET_EXPIRE_HOURS
    )
    # Expiration dans 1 heure

    user.reset_password_token = reset_token
    user.reset_password_expires = reset_expires

    # ── Envoyer l'email ───────────────────────────────────────────────────────
    await send_reset_password_email(user.email, reset_token)

    logger.info(f"Reset password demandé : {user.email}")

    return GENERIC_RESPONSE


# ── POST /auth/reset-password ─────────────────────────────────────────────────

@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Applique le nouveau mot de passe via le token de reset.

    FLUX :
        1. Cherche l'utilisateur avec ce token de reset
        2. Vérifie que le token n'est pas expiré
        3. Valide la force du nouveau mot de passe
        4. Hache et enregistre le nouveau mot de passe
        5. Supprime le token de reset (usage unique)

    Retourne (200 OK) :
        { "message": "Mot de passe modifié avec succès." }
    """

    # ── Chercher l'utilisateur avec ce token ──────────────────────────────────
    result = await db.execute(
        select(User).where(User.reset_password_token == request.token)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de réinitialisation invalide ou déjà utilisé"
        )

    # ── Vérifier l'expiration ─────────────────────────────────────────────────
    if not user.reset_password_expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de réinitialisation invalide"
        )

    if datetime.now(timezone.utc) > user.reset_password_expires:
        # Token expiré → on le supprime proprement
        user.reset_password_token = None
        user.reset_password_expires = None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token expiré. Faites une nouvelle demande de réinitialisation."
        )

    # ── Valider le nouveau mot de passe ───────────────────────────────────────
    is_strong, reason = is_password_strong(request.new_password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=reason
        )

    # ── Mettre à jour le mot de passe ─────────────────────────────────────────
    user.hashed_password = hash_password(request.new_password)
    user.reset_password_token = None
    # Supprime le token → usage unique
    user.reset_password_expires = None

    logger.info(f"Mot de passe réinitialisé : {user.email}")

    return {"message": "Mot de passe modifié avec succès. Vous pouvez vous connecter."}


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user)
    # get_current_user = notre dépendance qui vérifie le token JWT
    # Si token invalide → 401 automatiquement avant d'entrer dans la route
):
    """
    Retourne le profil de l'utilisateur connecté.

    QUAND L'UTILISER :
        - Au chargement de l'app pour récupérer les infos du user connecté
        - Pour vérifier que le token est encore valide

    Retourne (200 OK) :
        UserResponse avec id, email, is_verified, avatar_url, created_at
    """
    return current_user

    # ── OAuth Google ──────────────────────────────────────────────────────────────

from fastapi.responses import RedirectResponse
from auth.oauth import get_google_auth_url, exchange_code_for_token, get_google_user_info

# Stockage temporaire des states CSRF en mémoire
# QU'EST-CE QUE C'EST : dict qui associe state → True pour vérification
# POURQUOI en mémoire : les states sont valides quelques minutes seulement
# EN PRODUCTION : utiliser Redis pour partager entre plusieurs instances
_oauth_states: dict[str, bool] = {}


@router.get("/google")
async def google_login():
    """
    Redirige l'utilisateur vers la page de connexion Google.

    FLUX :
        1. Génère une URL Google + state CSRF
        2. Stocke le state en mémoire
        3. Redirige le navigateur vers Google

    Retourne :
        RedirectResponse → navigateur redirigé vers Google
    """
    auth_url, state = get_google_auth_url()

    # Stocker le state pour vérification dans le callback
    _oauth_states[state] = True

    logger.info(f"OAuth Google : redirection vers Google (state={state[:8]}...)")

    return RedirectResponse(url=auth_url)
    # RedirectResponse = réponse HTTP 307 qui redirige le navigateur
    # Le navigateur suit automatiquement la redirection vers Google


@router.get("/google/callback")
async def google_callback(
    code: str,
    # code = code d'autorisation envoyé par Google dans l'URL
    # Ex: ?code=4/0AX4XfWj...

    state: str,
    # state = notre token CSRF qu'on avait généré à l'étape 1
    # Google le renvoie tel quel dans le callback

    db: AsyncSession = Depends(get_db)
):
    """
    Callback OAuth Google — reçoit le code et connecte l'utilisateur.

    FLUX :
        1. Vérifie le state CSRF
        2. Échange le code contre un token Google
        3. Récupère les infos du user depuis Google
        4. Crée le compte si premier login, sinon met à jour
        5. Retourne nos tokens JWT

    Retourne (200 OK) :
        TokenResponse avec access_token + refresh_token
    """

    # ── Étape 1 : Vérifier le state CSRF ─────────────────────────────────────
    if state not in _oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State OAuth invalide — possible attaque CSRF"
        )

    del _oauth_states[state]
    # Supprimer le state après utilisation → usage unique
    # Empêche la réutilisation du même callback

    # ── Étape 2 : Échanger le code contre un token Google ────────────────────
    token_data = await exchange_code_for_token(code)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible d'échanger le code Google"
        )

    google_access_token = token_data.get("access_token")
    if not google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token Google manquant dans la réponse"
        )

     # ── Étape 3 : Récupérer les infos du user Google ──────────────────────────
    google_user = await get_google_user_info(google_access_token)
    if not google_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de récupérer les infos Google"
        )

    google_id    = google_user.get("id")
    email        = google_user.get("email")
    avatar_url   = google_user.get("picture")

    if not email or not google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email ou ID Google manquant"
        )

    # ── Étape 4 : Créer ou mettre à jour l'utilisateur ───────────────────────
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Premier login Google → créer le compte
        user = User(
            email=email,
            google_id=google_id,
            avatar_url=avatar_url,
            hashed_password=None,
            # Pas de mot de passe pour les comptes Google
            is_verified=True,
            # Email déjà vérifié par Google → pas besoin de vérification
            is_active=True,
        )
        db.add(user)
        await db.flush()
        logger.info(f"Nouveau compte Google créé : {email}")

    else:
        # Compte existant → mettre à jour les infos Google
        user.google_id  = google_id
        user.avatar_url = avatar_url
        # Met à jour la photo au cas où elle aurait changé
        if not user.is_verified:
            user.is_verified = True
            # Si l'utilisateur avait un compte email non vérifié
            # → on le vérifie automatiquement via Google
        logger.info(f"Connexion Google existante : {email}")

    # ── Étape 5 : Retourner nos tokens JWT ────────────────────────────────────
    access_token  = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )