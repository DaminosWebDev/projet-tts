"""
==============================================================================
auth/jwt.py — Création et validation des tokens JWT
==============================================================================
QU'EST-CE QU'UN JWT ?
  JWT = JSON Web Token
  C'est un token signé que le serveur donne à l'utilisateur après connexion.
  L'utilisateur l'envoie à chaque requête pour prouver son identité.

ANALOGIE :
  C'est comme un bracelet de festival :
  - Tu montres ta carte d'identité UNE FOIS à l'entrée (login)
  - On te donne un bracelet (JWT)
  - Ensuite tu montres juste le bracelet à chaque attraction (requête)
  - Le staff vérifie le bracelet sans rappeler l'entrée (pas de DB)
  - Le bracelet expire à la fin du festival (expiration du token)

STRUCTURE D'UN JWT :
  Un JWT est composé de 3 parties séparées par des points :
  eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk

  HEADER.PAYLOAD.SIGNATURE
  │              │          │
  │              │          └── Signature HMAC-SHA256 avec JWT_SECRET_KEY
  │              │               Garantit que le token n'a pas été modifié
  │              └────────────── Données (user_id, expiration, type...)
  └───────────────────────────── Algorithme utilisé (HS256)

POURQUOI DEUX TYPES DE TOKENS ?
  access_token  (30 min) → utilisé pour les requêtes API
                           Court pour limiter le risque si volé
  refresh_token (30 j)   → utilisé UNIQUEMENT pour renouveler l'access_token
                           Long pour ne pas déconnecter l'utilisateur souvent

FLUX COMPLET :
  1. Login → serveur crée access_token + refresh_token
  2. Client envoie access_token dans chaque requête (Header: Bearer xxx)
  3. access_token expire → client envoie refresh_token à POST /auth/refresh
  4. Serveur vérifie refresh_token → crée un nouvel access_token
  5. refresh_token expire (30j) → client doit se reconnecter
==============================================================================
"""

from datetime import datetime, timedelta, timezone
# datetime  = manipulation des dates
# timedelta = durée (ex: timedelta(minutes=30) = 30 minutes)
# timezone  = fuseau horaire UTC

from typing import Optional

import jwt
# PyJWT = librairie pour créer et valider des tokens JWT
# jwt.encode() = crée un token
# jwt.decode() = valide et lit un token

from config import (
    JWT_SECRET_KEY,
    # Clé secrète pour signer les tokens
    # Si quelqu'un connaît cette clé → il peut créer de faux tokens
    # → JAMAIS exposer cette clé (pas dans le code, pas sur GitHub)

    JWT_ALGORITHM,
    # "HS256" = HMAC avec SHA-256
    # Algorithme symétrique : même clé pour signer et vérifier

    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    # 30 minutes par défaut

    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    # 30 jours par défaut
)


# ── Création des tokens ───────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str) -> str:
    """
    Crée un token d'accès JWT (courte durée).

    QU'EST-CE QUE C'EST : Token envoyé à chaque requête API pour s'authentifier.
    DURÉE : JWT_ACCESS_TOKEN_EXPIRE_MINUTES (30 min par défaut)
    CONTENU : user_id, email, type, expiration

    Paramètres :
        user_id (str) : UUID de l'utilisateur
        email   (str) : email de l'utilisateur

    Retourne :
        str : token JWT signé
              Ex: "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.SflK..."

    Exemple :
        >>> token = create_access_token("abc-123", "user@test.com")
        >>> # Stocker dans un cookie ou retourner au client
    """
    now = datetime.now(timezone.utc)
    # Heure actuelle en UTC — toujours UTC pour éviter les problèmes de fuseaux

    expire = now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    # Date d'expiration = maintenant + 30 minutes

    payload = {
        "sub": user_id,
        # "sub" = subject = identifiant principal du token
        # Convention JWT : "sub" contient l'ID de l'utilisateur
        # C'est ce qu'on lit pour savoir QUI fait la requête

        "email": email,
        # Email inclus pour éviter une requête DB à chaque vérification
        # Le token contient déjà l'email → pas besoin de recharger le user

        "type": "access",
        # Type du token — permet de refuser un refresh_token là où on attend un access_token
        # Sécurité : empêche l'utilisation d'un token dans le mauvais contexte

        "iat": now,
        # "iat" = issued at = date de création du token
        # Convention JWT standard

        "exp": expire,
        # "exp" = expiration = date limite de validité
        # PyJWT vérifie automatiquement cette date lors du decode()
        # Token expiré → jwt.ExpiredSignatureError levée automatiquement
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    # jwt.encode() = sérialise le payload en JSON + signe avec JWT_SECRET_KEY
    # Retourne une string "header.payload.signature"


def create_refresh_token(user_id: str) -> str:
    """
    Crée un token de rafraîchissement JWT (longue durée).

    QU'EST-CE QUE C'EST : Token utilisé UNIQUEMENT pour renouveler l'access_token.
    DURÉE : JWT_REFRESH_TOKEN_EXPIRE_DAYS (30 jours par défaut)
    CONTENU : user_id, type, expiration (pas d'email — données minimales)

    SÉCURITÉ :
        Le refresh_token contient moins d'infos que l'access_token.
        Si volé, l'attaquant ne peut que renouveler des access_tokens
        (et on peut invalider le refresh_token côté serveur).

    Paramètres :
        user_id (str) : UUID de l'utilisateur

    Retourne :
        str : refresh token JWT signé
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": user_id,
        "type": "refresh",
        # Type "refresh" → sera vérifié dans verify_refresh_token()
        # Un access_token ne peut pas être utilisé comme refresh_token
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ── Validation des tokens ─────────────────────────────────────────────────────

def verify_access_token(token: str) -> Optional[dict]:
    """
    Valide un token d'accès et retourne son contenu.

    QU'EST-CE QUE C'EST : Vérifie la signature et l'expiration du token.
    QUAND L'UTILISER : dans get_current_user() (dependencies.py) à chaque requête.

    CE QUE PYJWT VÉRIFIE AUTOMATIQUEMENT :
        ✅ La signature est valide (token non modifié)
        ✅ Le token n'est pas expiré (champ "exp")
        ✅ L'algorithme est correct (HS256)

    Paramètres :
        token (str) : token JWT reçu dans le header Authorization

    Retourne :
        dict : payload du token si valide
               Ex: {"sub": "abc-123", "email": "user@test.com", "type": "access", ...}
        None : si token invalide, expiré ou malformé

    Exemple :
        >>> payload = verify_access_token("eyJhbGci...")
        >>> if payload:
        ...     user_id = payload["sub"]
        ... else:
        ...     raise HTTPException(401)  # Non autorisé
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
            # algorithms = liste des algorithmes acceptés
            # SÉCURITÉ : toujours spécifier la liste explicitement
            # Évite l'attaque "algorithm confusion" (alg: none)
        )

        if payload.get("type") != "access":
            # Vérifie qu'on a bien un access_token
            # Empêche d'utiliser un refresh_token comme access_token
            return None

        return payload

    except jwt.ExpiredSignatureError:
        # Token expiré → l'utilisateur doit se reconnecter ou utiliser son refresh_token
        return None

    except jwt.InvalidTokenError:
        # Token malformé, signature invalide, algorithme incorrect...
        # On retourne None sans détailler l'erreur (pas d'info pour l'attaquant)
        return None


def verify_refresh_token(token: str) -> Optional[str]:
    """
    Valide un refresh token et retourne l'user_id.

    QU'EST-CE QUE C'EST : Vérifie le refresh token pour renouveler l'access_token.
    QUAND L'UTILISER : dans POST /auth/refresh uniquement.

    Paramètres :
        token (str) : refresh token JWT

    Retourne :
        str  : user_id si token valide
        None : si token invalide ou expiré

    Exemple :
        >>> user_id = verify_refresh_token("eyJhbGci...")
        >>> if user_id:
        ...     new_access_token = create_access_token(user_id, email)
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

        if payload.get("type") != "refresh":
            # Vérifie qu'on a bien un refresh_token
            # Empêche d'utiliser un access_token comme refresh_token
            return None

        return payload.get("sub")
        # "sub" = user_id
        # C'est tout ce dont on a besoin pour créer un nouvel access_token

    except jwt.ExpiredSignatureError:
        return None

    except jwt.InvalidTokenError:
        return None


def decode_token_unsafe(token: str) -> Optional[dict]:
    """
    Décode un token SANS vérifier la signature ni l'expiration.

    ⚠️  ATTENTION : NE JAMAIS UTILISER POUR L'AUTHENTIFICATION ⚠️

    QU'EST-CE QUE C'EST : Lecture du contenu d'un token sans validation.
    QUAND L'UTILISER : debug uniquement — pour inspecter le contenu d'un token.
    POURQUOI EXISTE-T-IL : utile en développement pour voir ce que contient un token
                           sans avoir à le décoder manuellement sur jwt.io

    Paramètres :
        token (str) : n'importe quel token JWT

    Retourne :
        dict : payload brut sans validation
        None : si token malformé (pas un JWT valide du tout)
    """
    try:
        return jwt.decode(
            token,
            options={
                "verify_signature": False,
                # Désactive la vérification de signature
                "verify_exp": False,
                # Désactive la vérification d'expiration
            },
            algorithms=[JWT_ALGORITHM]
        )
    except jwt.InvalidTokenError:
        return None