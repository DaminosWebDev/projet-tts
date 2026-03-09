import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.user import User
from auth.password import hash_password, verify_password, is_password_strong
from auth.jwt import create_access_token, create_refresh_token, verify_refresh_token
from auth.dependencies import get_current_user
from auth.oauth import get_google_auth_url, exchange_code_for_token, get_google_user_info
from emails.email_service import send_verification_email, send_reset_password_email
from config import PASSWORD_RESET_EXPIRE_HOURS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Schémas Pydantic ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., json_schema_extra={"example": "user@example.com"})
    password: str = Field(..., min_length=8)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # Standard OAuth2 — client envoie "Authorization: Bearer <token>"

class UserResponse(BaseModel):
    id: str
    email: str
    is_verified: bool
    avatar_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True  # Permet la sérialisation depuis un objet SQLAlchemy


# ── POST /auth/register ───────────────────────────────────────────────────────

@router.post("/register", status_code=201)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Validation force du mot de passe — au-delà de la longueur minimale Pydantic
    is_strong, reason = is_password_strong(request.password)
    if not is_strong:
        raise HTTPException(status_code=422, detail=reason)

    # Email déjà utilisé — 409 et non 400 car c'est un conflit de ressource
    existing = await db.execute(select(User).where(User.email == request.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Un compte existe déjà avec cet email")

    # Token de vérification — 64 caractères hex cryptographiquement sécurisés
    verification_token = secrets.token_hex(32)

    new_user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
        verification_token=verification_token,
        is_verified=False,
    )
    db.add(new_user)

    # flush() envoie le INSERT sans committer — permet rollback si l'email échoue
    await db.flush()

    await send_verification_email(new_user.email, verification_token)
    logger.info(f"Nouveau compte créé : {new_user.email}")

    return {"message": "Compte créé. Vérifiez votre boîte email.", "email": new_user.email}


# ── GET /auth/verify-email ────────────────────────────────────────────────────

@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.verification_token == token))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Token invalide ou déjà utilisé")

    # Marque l'email comme vérifié et invalide le token
    user.is_verified = True
    user.verification_token = None

    logger.info(f"Email vérifié : {user.email}")

    # Connexion automatique après vérification — meilleure UX
    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=create_refresh_token(user.id),
    )


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Message générique — ne révèle pas si l'email existe ou non
    GENERIC_ERROR = "Email ou mot de passe incorrect"

    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail=GENERIC_ERROR)

    # Compte OAuth — pas de mot de passe local, message spécifique acceptable ici
    if not user.hashed_password:
        raise HTTPException(status_code=401, detail="Ce compte utilise la connexion Google")

    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail=GENERIC_ERROR)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé. Contactez le support.")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email non vérifié. Vérifiez votre boîte mail.")

    logger.info(f"Connexion réussie : {user.email}")

    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=create_refresh_token(user.id),
    )


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    user_id = verify_refresh_token(request.refresh_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Refresh token invalide ou expiré")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou inactif")

    # Rotation — chaque utilisation génère un nouveau refresh token
    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=create_refresh_token(user.id),
    )


# ── POST /auth/forgot-password ────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    # Réponse identique que l'email existe ou non — bloque l'énumération d'emails
    GENERIC_RESPONSE = {"message": "Si un compte existe avec cet email, vous recevrez un lien."}

    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not user.is_verified:
        return GENERIC_RESPONSE

    user.reset_password_token = secrets.token_hex(32)
    user.reset_password_expires = datetime.now(timezone.utc) + timedelta(hours=PASSWORD_RESET_EXPIRE_HOURS)

    await send_reset_password_email(user.email, user.reset_password_token)
    logger.info(f"Reset password demandé : {user.email}")

    return GENERIC_RESPONSE


# ── POST /auth/reset-password ─────────────────────────────────────────────────

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.reset_password_token == request.token))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Token invalide ou déjà utilisé")

    if not user.reset_password_expires:
        raise HTTPException(status_code=400, detail="Token invalide")

    # Token expiré — nettoyage avant de rejeter
    if datetime.now(timezone.utc) > user.reset_password_expires:
        user.reset_password_token = None
        user.reset_password_expires = None
        raise HTTPException(status_code=400, detail="Token expiré. Faites une nouvelle demande.")

    is_strong, reason = is_password_strong(request.new_password)
    if not is_strong:
        raise HTTPException(status_code=422, detail=reason)

    user.hashed_password = hash_password(request.new_password)
    user.reset_password_token = None
    user.reset_password_expires = None

    logger.info(f"Mot de passe réinitialisé : {user.email}")
    return {"message": "Mot de passe modifié. Vous pouvez vous connecter."}


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ── OAuth Google ──────────────────────────────────────────────────────────────

# States CSRF en mémoire — en production, remplacer par Redis
_oauth_states: dict[str, bool] = {}


@router.get("/google")
async def google_login():
    auth_url, state = get_google_auth_url()
    _oauth_states[state] = True
    logger.info(f"OAuth Google : redirection (state={state[:8]}...)")
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    # Vérification CSRF — state inconnu = callback forgé
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="State OAuth invalide")
    del _oauth_states[state]

    # Échange du code contre un token Google
    token_data = await exchange_code_for_token(code)
    if not token_data or not token_data.get("access_token"):
        raise HTTPException(status_code=400, detail="Échange de code Google échoué")

    # Récupération du profil Google
    google_user = await get_google_user_info(token_data["access_token"])
    if not google_user:
        raise HTTPException(status_code=400, detail="Profil Google inaccessible")

    email = google_user.get("email")
    google_id = google_user.get("id")
    avatar_url = google_user.get("picture")

    if not email or not google_id:
        raise HTTPException(status_code=400, detail="Email ou ID Google manquant")

    # Création ou mise à jour du compte
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            email=email,
            google_id=google_id,
            avatar_url=avatar_url,
            hashed_password=None,
            is_verified=True,  # Google a déjà vérifié l'email
            is_active=True,
        )
        db.add(user)
        await db.flush()
        logger.info(f"Nouveau compte Google : {email}")
    else:
        # Mise à jour des infos Google — photo peut avoir changé
        user.google_id = google_id
        user.avatar_url = avatar_url
        if not user.is_verified:
            user.is_verified = True
        logger.info(f"Connexion Google existante : {email}")

    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=create_refresh_token(user.id),
    )