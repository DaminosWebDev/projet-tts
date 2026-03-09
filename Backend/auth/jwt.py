from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt

from config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
)


def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,      # Identifiant principal — lu par get_current_user
        "email": email,      # Évite une requête DB pour récupérer l'email
        "type": "access",    # Empêche un refresh token d'être utilisé ici
        "iat": now,          # Date de création
        "exp": expire,       # PyJWT vérifie cette date automatiquement au decode
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    # Payload minimal — le refresh token n'a besoin que de l'identité
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]  # Liste explicite — bloque l'attaque "alg: none"
        )

        # Refuse un refresh token utilisé à la place d'un access token
        if payload.get("type") != "access":
            return None

        return payload

    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def verify_refresh_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

        # Refuse un access token utilisé à la place d'un refresh token
        if payload.get("type") != "refresh":
            return None

        return payload.get("sub")  # Seul le user_id est nécessaire pour la suite

    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ⚠️ Debug uniquement — ne jamais utiliser pour l'authentification
def decode_token_unsafe(token: str) -> Optional[dict]:
    try:
        return jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False},
            algorithms=[JWT_ALGORITHM]
        )
    except jwt.InvalidTokenError:
        return None