import secrets
import logging
import httpx
import urllib.parse

from config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
)

logger = logging.getLogger(__name__)

# Points d'entrée de l'API Google OAuth 2.0
GOOGLE_AUTH_URL      = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL     = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL  = "https://www.googleapis.com/oauth2/v2/userinfo"

# Permissions demandées à Google — minimum nécessaire
GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def get_google_auth_url() -> tuple[str, str]:
    # State aléatoire — vérifié au retour pour bloquer les attaques CSRF
    state = secrets.token_hex(16)

    # Encodage des paramètres pour une URL valide
    auth_url = (
        f"{GOOGLE_AUTH_URL}"
        f"?client_id={urllib.parse.quote(GOOGLE_CLIENT_ID)}"
        f"&redirect_uri={urllib.parse.quote(GOOGLE_REDIRECT_URI)}"
        f"&response_type=code"
        f"&scope={urllib.parse.quote(' '.join(GOOGLE_SCOPES))}"
        f"&state={state}"
        f"&access_type=offline"
        f"&prompt=select_account"
    )

    return auth_url, state  # Les deux sont retournés — state doit être stocké en session


async def exchange_code_for_token(code: str) -> dict | None:
    # Échange côté serveur — client_secret n'est jamais exposé au navigateur
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        )

        if response.status_code != 200:
            logger.error(f"Google token exchange failed: {response.text}")
            return None

        return response.json()


async def get_google_user_info(access_token: str) -> dict | None:
    # Token Google dans le header — Google retourne le profil correspondant
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if response.status_code != 200:
            logger.error(f"Google userinfo failed: {response.text}")
            return None

        return response.json()
