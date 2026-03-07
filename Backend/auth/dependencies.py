"""
==============================================================================
auth/dependencies.py — Dépendances FastAPI pour l'authentification
==============================================================================
QU'EST-CE QU'UNE DÉPENDANCE FASTAPI ?
  FastAPI a un système d'injection de dépendances.
  Au lieu de répéter le même code dans chaque route protégée,
  on définit une fonction UNE FOIS et FastAPI l'injecte automatiquement.

ANALOGIE :
  C'est comme un vigile à l'entrée d'une boîte de nuit.
  Au lieu que chaque serveur vérifie les IDs lui-même,
  le vigile (dépendance) vérifie UNE FOIS à l'entrée.
  Si le vigile dit OK → la personne entre (la route s'exécute)
  Si le vigile dit NON → la personne est refusée (401 Unauthorized)

UTILISATION DANS UNE ROUTE :
  # Route publique — pas besoin du vigile
  @router.get("/public")
  async def public_route():
      return {"message": "Tout le monde peut accéder"}

  # Route protégée — le vigile vérifie le token
  @router.get("/private")
  async def private_route(current_user: User = Depends(get_current_user)):
      return {"message": f"Bonjour {current_user.email}"}

  # Route admin — vérifie token + rôle admin
  @router.delete("/admin/users/{id}")
  async def delete_user(current_user: User = Depends(get_current_admin)):
      ...

FLUX DE VÉRIFICATION :
  Requête HTTP
  → Header "Authorization: Bearer eyJhbGci..."
  → get_current_user()
  → Extrait le token du header
  → Vérifie la signature JWT
  → Lit user_id depuis le payload
  → Charge l'utilisateur depuis la DB
  → Vérifie is_active et is_verified
  → Injecte l'objet User dans la route
==============================================================================
"""

from fastapi import Depends, HTTPException, status
# Depends      → système d'injection de dépendances FastAPI
# HTTPException→ erreurs HTTP avec codes et messages
# status       → constantes HTTP (status.HTTP_401_UNAUTHORIZED = 401)

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# HTTPBearer   → extrait le token du header "Authorization: Bearer xxx"
# HTTPAuthorizationCredentials → objet contenant le token extrait

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.user import User
from auth.jwt import verify_access_token


# ── Extracteur de token ───────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)
# QU'EST-CE QUE C'EST : Lit le header "Authorization: Bearer <token>"
# auto_error=False → si pas de token, retourne None au lieu de lever une erreur
#                    On gère l'erreur nous-mêmes pour un message plus précis
# UTILISATION : le client doit envoyer le header :
#   Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...


# ── Dépendance principale ─────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dépendance FastAPI — vérifie le token JWT et retourne l'utilisateur connecté.

    QU'EST-CE QUE C'EST : Le "vigile" injecté dans toutes les routes protégées.
    QUAND L'UTILISER : dans chaque route qui nécessite d'être connecté.

    CE QUE CETTE FONCTION FAIT :
        1. Extrait le token du header Authorization
        2. Vérifie la signature et l'expiration du token JWT
        3. Lit le user_id depuis le payload du token
        4. Charge l'utilisateur depuis PostgreSQL
        5. Vérifie que le compte est actif et vérifié
        6. Retourne l'objet User complet

    Paramètres (injectés automatiquement par FastAPI) :
        credentials : token extrait du header par HTTPBearer
        db          : session PostgreSQL injectée par get_db()

    Retourne :
        User : l'utilisateur authentifié et actif

    Lève :
        HTTPException 401 : token manquant, invalide ou expiré
        HTTPException 401 : utilisateur introuvable en DB
        HTTPException 403 : compte inactif ou non vérifié
    """

    # ── Étape 1 : Vérifier qu'un token est présent ────────────────────────────
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            # 401 = Unauthorized = "tu n'es pas authentifié"
            detail="Token d'authentification manquant",
            headers={"WWW-Authenticate": "Bearer"},
            # WWW-Authenticate = header standard qui dit au client
            # "j'attends un token Bearer"
        )

    token = credentials.credentials
    # credentials.credentials = le token brut extrait du header
    # Ex: "eyJhbGciOiJIUzI1NiJ9..."

    # ── Étape 2 : Valider le token JWT ────────────────────────────────────────
    payload = verify_access_token(token)
    # verify_access_token() retourne le payload si valide, None sinon
    # Vérifie : signature, expiration, type="access"

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    # "sub" = subject = user_id stocké dans le token
    # Ex: "a3f8c2d1-4b5e-41d4-a716-446655440000"

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide : user_id manquant",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Étape 3 : Charger l'utilisateur depuis la DB ──────────────────────────
    result = await db.execute(
        select(User).where(User.id == user_id)
        # SELECT * FROM users WHERE id = 'user_id'
    )
    user = result.scalar_one_or_none()
    # scalar_one_or_none() = retourne l'objet User ou None si pas trouvé
    # (jamais d'erreur si absent — contrairement à scalar_one() qui lève une exception)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Étape 4 : Vérifier le statut du compte ────────────────────────────────
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            # 403 = Forbidden = "tu es authentifié mais pas autorisé"
            # DIFFÉRENCE avec 401 :
            #   401 = on ne sait pas qui tu es (pas de token valide)
            #   403 = on sait qui tu es, mais tu n'as pas le droit
            detail="Compte désactivé. Contactez le support.",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email non vérifié. Vérifiez votre boîte mail.",
        )

    return user
    # FastAPI injecte cet objet User dans le paramètre de la route
    # La route peut alors accéder à user.id, user.email, etc.


# ── Dépendance admin ──────────────────────────────────────────────────────────

async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dépendance FastAPI — vérifie que l'utilisateur connecté est admin.

    QU'EST-CE QUE C'EST : Extension de get_current_user() avec vérification du rôle.
    QUAND L'UTILISER : dans les routes d'administration uniquement.

    CHAÎNAGE DE DÉPENDANCES :
        get_current_admin dépend de get_current_user
        FastAPI résout automatiquement la chaîne :
        Requête → get_current_user() → get_current_admin() → route

    Paramètres :
        current_user : utilisateur retourné par get_current_user()
                       (injecté automatiquement par FastAPI)

    Retourne :
        User : l'utilisateur authentifié et admin

    Lève :
        HTTPException 403 : utilisateur non admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return current_user


# ── Dépendance optionnelle ────────────────────────────────────────────────────

async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> User | None:
    """
    Dépendance FastAPI — retourne l'utilisateur connecté OU None.

    QU'EST-CE QUE C'EST : Version "soft" de get_current_user().
    QUAND L'UTILISER : routes accessibles aux anonymes ET aux connectés,
                       mais avec un comportement différent selon le cas.

    EXEMPLE D'UTILISATION :
        @router.get("/voices")
        async def get_voices(user: User | None = Depends(get_optional_user)):
            if user:
                return {"voices": ALL_VOICES, "favorites": user.favorites}
            else:
                return {"voices": DEFAULT_VOICES}

    Retourne :
        User : si token valide présent dans le header
        None : si pas de token ou token invalide
    """
    if not credentials:
        return None

    try:
        payload = verify_access_token(credentials.credentials)
        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            return None

        return user

    except Exception:
        return None