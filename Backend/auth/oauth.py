"""
==============================================================================
auth/oauth.py — OAuth Google (connexion via Google)
==============================================================================
QU'EST-CE QUE OAUTH 2.0 ?
  OAuth 2.0 = protocole d'autorisation standard.
  Permet à un utilisateur de se connecter avec son compte Google
  sans jamais partager son mot de passe Google avec notre app.

FLUX COMPLET OAUTH GOOGLE :
  1. Client → GET /auth/google
             → serveur génère une URL Google + un "state" aléatoire
             → redirige le navigateur vers Google

  2. Google → affiche la page de connexion Google
             → utilisateur accepte les permissions

  3. Google → redirige vers /auth/google/callback?code=xxx&state=yyy
             → notre serveur reçoit un "code" temporaire

  4. Serveur → échange le code contre un access_token Google
             → appelle l'API Google pour récupérer les infos du user
             → crée ou met à jour le user en DB
             → retourne nos propres tokens JWT

POURQUOI UN "STATE" ?
  Le state est un token aléatoire généré à l'étape 1 et vérifié à l'étape 3.
  SÉCURITÉ : empêche les attaques CSRF
  (un attaquant ne peut pas forger un callback valide sans connaître le state)

ANALOGIE COMPLÈTE :
  C'est comme utiliser votre carte d'identité dans un hôtel partenaire :
  1. Tu arrives à l'hôtel (notre app) sans réservation
  2. L'hôtel t'envoie à la mairie (Google) pour vérifier ton identité
  3. La mairie vérifie ton identité et te donne un bon (code)
  4. Tu reviens à l'hôtel avec le bon
  5. L'hôtel échange le bon contre une clé de chambre (JWT)
  6. Tu n'as jamais donné ton mot de passe à l'hôtel
==============================================================================
"""

import secrets
import logging
import httpx
# httpx = client HTTP async — pour appeler les APIs Google

from config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
)

logger = logging.getLogger(__name__)

# ── URLs Google OAuth ─────────────────────────────────────────────────────────

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
# URL où on redirige l'utilisateur pour qu'il se connecte avec Google

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
# URL où on échange le code contre un access_token Google

GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
# URL où on récupère les infos du user Google (email, nom, photo)

# ── Scopes ────────────────────────────────────────────────────────────────────

GOOGLE_SCOPES = [
    "openid",
    # openid = permission de base OAuth — identifie l'utilisateur

    "https://www.googleapis.com/auth/userinfo.email",
    # Permission de lire l'adresse email

    "https://www.googleapis.com/auth/userinfo.profile",
    # Permission de lire le nom et la photo de profil
]
# QU'EST-CE QUE LES SCOPES ?
# Ce sont les permissions que notre app demande à Google.
# L'utilisateur voit exactement ce qu'on demande sur la page Google.
# On demande le minimum nécessaire (email + profil) — bonne pratique.


# ── Étape 1 : Générer l'URL de connexion Google ───────────────────────────────

def get_google_auth_url() -> tuple[str, str]:
    import urllib.parse

    state = secrets.token_hex(16)

    # Encoder chaque paramètre individuellement
    client_id = urllib.parse.quote(GOOGLE_CLIENT_ID)
    redirect_uri = urllib.parse.quote(GOOGLE_REDIRECT_URI)
    scope = urllib.parse.quote(" ".join(GOOGLE_SCOPES))
    # urllib.parse.quote encode les espaces en %20
    # " ".join(GOOGLE_SCOPES) = "openid https://... https://..."
    # après quote = "openid%20https%3A%2F%2F...%20https%3A%2F%2F..."

    auth_url = (
        f"{GOOGLE_AUTH_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&state={state}"
        f"&access_type=offline"
        f"&prompt=select_account"
    )

    return auth_url, state


# ── Étape 2 : Échanger le code contre un token Google ────────────────────────

async def exchange_code_for_token(code: str) -> dict | None:
    """
    Échange le code d'autorisation Google contre un access_token.

    QU'EST-CE QUE C'EST : Appelle l'API Google pour convertir le code en token.
    QUAND L'UTILISER : dans GET /auth/google/callback après réception du code.

    POURQUOI CÔTÉ SERVEUR ?
        Le code est échangé côté serveur (pas dans le navigateur).
        Le client_secret n'est jamais exposé au navigateur.
        Si intercepté, le code est inutile sans le client_secret.

    Paramètres :
        code (str) : code d'autorisation reçu de Google dans le callback

    Retourne :
        dict : réponse Google contenant access_token, token_type, etc.
        None : si l'échange échoue
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
                # "authorization_code" = type d'échange standard OAuth 2.0
            }
        )

        if response.status_code != 200:
            logger.error(f"Google token exchange failed: {response.text}")
            return None

        return response.json()
        # Retourne : { access_token, token_type, expires_in, refresh_token, ... }


# ── Étape 3 : Récupérer les infos du user Google ─────────────────────────────

async def get_google_user_info(access_token: str) -> dict | None:
    """
    Récupère les informations du profil Google de l'utilisateur.

    QU'EST-CE QUE C'EST : Appelle l'API Google UserInfo avec l'access_token.
    QUAND L'UTILISER : après exchange_code_for_token(), avec le token obtenu.

    Paramètres :
        access_token (str) : token Google obtenu à l'étape précédente

    Retourne :
        dict : infos du user Google
               { id, email, verified_email, name, picture, ... }
        None : si l'appel échoue

    Exemple de réponse Google :
        {
            "id": "118234567890123456789",
            "email": "user@gmail.com",
            "verified_email": true,
            "name": "John Doe",
            "picture": "https://lh3.googleusercontent.com/a/..."
        }
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
            # On envoie l'access_token dans le header Authorization
            # Google vérifie le token et retourne les infos du user
        )

        if response.status_code != 200:
            logger.error(f"Google userinfo failed: {response.text}")
            return None

        return response.json()