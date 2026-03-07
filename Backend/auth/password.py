"""
==============================================================================
auth/password.py — Hachage et vérification des mots de passe avec bcrypt
==============================================================================
QU'EST-CE QUE BCRYPT ?
  bcrypt est un algorithme de hachage conçu SPÉCIFIQUEMENT pour les mots de passe.
  Il est intentionnellement LENT — c'est une feature, pas un bug.

POURQUOI LENT EST UNE BONNE CHOSE ?
  Un attaquant qui vole ta DB essaie de retrouver les mots de passe
  en testant des millions de combinaisons (attaque par force brute).
  Si chaque test prend 0.0001s → 1 million de tests = 100 secondes
  Si chaque test prend 0.1s    → 1 million de tests = 100 000 secondes
  La lenteur de bcrypt rend les attaques par force brute impraticables.

COMMENT FONCTIONNE LE HACHAGE ?
  "password123" → bcrypt → "$2b$12$K8HvbNmXqZpLmN3YkR9O4uW7..."
                            │    │  │
                            │    │  └── sel aléatoire (128 bits)
                            │    └───── facteur de coût (12 = 2^12 itérations)
                            └────────── version bcrypt

  PROPRIÉTÉ CLÉ : irréversible
  On ne peut PAS retrouver "password123" depuis le hash.
  On peut seulement VÉRIFIER qu'un mot de passe correspond au hash.

LE SEL (SALT) :
  Chaque hash contient un "sel" aléatoire unique.
  Deux utilisateurs avec le même mot de passe auront des hashes DIFFÉRENTS.
  POURQUOI : empêche les attaques par "rainbow table"
  (dictionnaire de hashes précalculés)

  "password123" → hash1 = "$2b$12$ABC..."
  "password123" → hash2 = "$2b$12$XYZ..."  ← différent !
==============================================================================
"""

import bcrypt
# bcrypt = librairie Python qui encapsule l'algorithme bcrypt en C
# Très rapide à l'exécution malgré la lenteur intentionnelle de l'algo


# ── Constante ─────────────────────────────────────────────────────────────────

BCRYPT_ROUNDS = 12
# QU'EST-CE QUE C'EST : Le "facteur de coût" de bcrypt.
# COMMENT : bcrypt effectue 2^ROUNDS itérations de hachage
#   rounds=10 → 2^10 =  1 024 itérations → ~0.05s par hash
#   rounds=12 → 2^12 =  4 096 itérations → ~0.25s par hash  ← notre choix
#   rounds=14 → 2^14 = 16 384 itérations → ~1.0s  par hash
# POURQUOI 12 : standard recommandé en 2024
#   Assez lent pour décourager la force brute
#   Assez rapide pour ne pas gêner l'utilisateur au login


# ── Fonctions publiques ───────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """
    Hache un mot de passe en clair avec bcrypt.

    QU'EST-CE QUE C'EST : Transforme un mot de passe lisible en hash irréversible.
    QUAND L'UTILISER : uniquement à l'inscription et au changement de mot de passe.
    NE JAMAIS : stocker plain_password en DB, le logger, le retourner dans une réponse.

    Paramètres :
        plain_password (str) : mot de passe en clair saisi par l'utilisateur
                               Ex: "MonMotDePasse123!"

    Retourne :
        str : le hash bcrypt à stocker en DB
              Ex: "$2b$12$K8HvbNmXqZpLmN3YkR9O4uW7xQzP1sT6vY2mA8nB5cD3eF0gH..."

    Exemple :
        >>> hashed = hash_password("MonMotDePasse123!")
        >>> print(hashed)
        "$2b$12$..."
        >>> # On stocke hashed en DB, jamais plain_password
    """
    password_bytes = plain_password.encode("utf-8")
    # encode("utf-8") = convertit la string Python en bytes
    # POURQUOI : bcrypt travaille avec des bytes, pas des strings
    # "utf-8" = encodage qui supporte tous les caractères (accents, émojis...)
    # Ex: "password" → b"password"
    #     "mötdepasse" → b"m\xc3\xb6tdepasse"

    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    # gensalt() = génère un sel aléatoire unique
    # rounds=12 → le sel encode aussi le facteur de coût
    # Ce sel sera intégré dans le hash final — pas besoin de le stocker séparément

    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    # hashpw() = applique l'algorithme bcrypt
    # Prend le mot de passe + le sel → retourne le hash complet
    # Le hash inclut : version + rounds + sel + hash = tout en un seul string

    return hashed_bytes.decode("utf-8")
    # decode("utf-8") = reconvertit les bytes en string Python
    # Pour pouvoir stocker dans PostgreSQL (colonne String)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Vérifie qu'un mot de passe en clair correspond à un hash bcrypt.

    QU'EST-CE QUE C'EST : Compare un mot de passe saisi avec le hash stocké en DB.
    QUAND L'UTILISER : à chaque tentative de connexion (POST /auth/login).
    COMMENT ÇA MARCHE :
        bcrypt extrait le sel du hash existant
        → re-hache le mot de passe avec ce même sel
        → compare les deux hashes
        → True si identiques, False sinon

    Paramètres :
        plain_password  (str) : mot de passe saisi par l'utilisateur au login
        hashed_password (str) : hash stocké en DB pour cet utilisateur

    Retourne :
        bool : True si le mot de passe est correct, False sinon

    Exemple :
        >>> hashed = hash_password("MonMotDePasse123!")
        >>> verify_password("MonMotDePasse123!", hashed)
        True
        >>> verify_password("mauvais_mdp", hashed)
        False

    SÉCURITÉ — Timing attack :
        bcrypt.checkpw() prend le même temps que le mot de passe soit bon ou non.
        POURQUOI : si la vérification était plus rapide pour les mauvais mots de passe,
        un attaquant pourrait déduire des informations en mesurant le temps de réponse.
        C'est une "timing attack" — bcrypt s'en protège automatiquement.
    """
    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        # Même principe que hash_password : conversion en bytes

        return bcrypt.checkpw(password_bytes, hashed_bytes)
        # checkpw() = vérifie le mot de passe contre le hash
        # Retourne True ou False
        # Temps constant quelle que soit la réponse → protection timing attack

    except Exception:
        # Si le hash est malformé ou une erreur inattendue → False
        # On ne propage pas l'erreur pour ne pas donner d'info à un attaquant
        return False


def is_password_strong(password: str) -> tuple[bool, str]:
    """
    Vérifie qu'un mot de passe respecte les règles de sécurité minimales.

    QU'EST-CE QUE C'EST : Validation côté serveur de la force du mot de passe.
    POURQUOI côté serveur ET pas seulement frontend :
        Le frontend peut être contourné (Postman, curl...).
        La validation serveur est la seule garantie réelle.

    Règles :
        - Minimum 8 caractères
        - Au moins une majuscule
        - Au moins une minuscule
        - Au moins un chiffre

    Paramètres :
        password (str) : mot de passe à valider

    Retourne :
        tuple[bool, str] :
            (True, "")               → mot de passe valide
            (False, "raison")        → mot de passe invalide + explication

    Exemple :
        >>> is_password_strong("abc")
        (False, "Le mot de passe doit contenir au moins 8 caractères")
        >>> is_password_strong("MonMotDePasse123!")
        (True, "")
    """
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères"

    if not any(c.isupper() for c in password):
        # any() = retourne True si au moins un élément est True
        # c.isupper() = True si le caractère est une majuscule
        return False, "Le mot de passe doit contenir au moins une majuscule"

    if not any(c.islower() for c in password):
        return False, "Le mot de passe doit contenir au moins une minuscule"

    if not any(c.isdigit() for c in password):
        return False, "Le mot de passe doit contenir au moins un chiffre"

    return True, ""