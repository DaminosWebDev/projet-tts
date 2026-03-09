import bcrypt

# Facteur de coût — 2^12 = 4096 itérations, ~0.25s par hash
# Standard recommandé : assez lent pour la force brute, assez rapide pour l'UX
BCRYPT_ROUNDS = 12


def hash_password(plain_password: str) -> str:
    # bcrypt travaille en bytes — conversion obligatoire
    password_bytes = plain_password.encode("utf-8")

    # Sel aléatoire unique — intégré dans le hash final, pas besoin de le stocker
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)

    # Hash complet : version + rounds + sel + hash en une seule chaîne
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)

    # Reconversion en string pour stockage PostgreSQL
    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")

        # Temps constant quelle que soit la réponse — protection contre les timing attacks
        return bcrypt.checkpw(password_bytes, hashed_bytes)

    except Exception:
        # Hash malformé ou erreur inattendue — False sans détail pour ne pas informer l'attaquant
        return False


def is_password_strong(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères"

    if not any(c.isupper() for c in password):
        return False, "Le mot de passe doit contenir au moins une majuscule"

    if not any(c.islower() for c in password):
        return False, "Le mot de passe doit contenir au moins une minuscule"

    if not any(c.isdigit() for c in password):
        return False, "Le mot de passe doit contenir au moins un chiffre"

    return True, ""