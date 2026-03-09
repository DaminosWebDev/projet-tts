# =============================================================================
# email_service.py - Envoi des emails transactionnels
# =============================================================================

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    FRONTEND_URL  # Ex: "http://localhost:5173"
)

logger = logging.getLogger(__name__)

# Dossier des templates HTML — chemin absolu peu importe d'où Python est lancé
TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_template(filename: str) -> str:
    """
    Charge un template HTML depuis le dossier templates/.
    Lève FileNotFoundError si le fichier est introuvable.
    """
    path = TEMPLATES_DIR / filename
    return path.read_text(encoding="utf-8")


def _send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Envoie un email HTML via SMTP.

    Retourne True si envoi réussi, False sinon.
    Ne lève jamais d'exception — les erreurs sont loggées.
    """
    try:
        # Construction du message MIME multipart
        # multipart/alternative = le client mail choisit entre texte et HTML
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"]    = f"VoxBridge <{SMTP_USER}>"
        message["To"]      = to_email

        # Partie HTML — la seule qu'on fournit ici
        html_part = MIMEText(html_content, "html", "utf-8")
        message.attach(html_part)

        # Connexion SMTP avec TLS
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()          # Chiffrement TLS
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(
                SMTP_USER,
                to_email,
                message.as_string()
            )

        logger.info(f"Email envoyé à {to_email} | sujet='{subject}'")
        return True

    except Exception as e:
        logger.error(f"Erreur envoi email à {to_email} : {e}")
        return False


def send_verification_email(to_email: str, token: str) -> bool:
    """
    Envoie l'email de vérification de compte.

    Paramètres :
        to_email : adresse du nouvel utilisateur
        token    : verification_token stocké dans User.verification_token
    """
    verification_url = f"{FRONTEND_URL}/verify-email?token={token}"

    html = _load_template("verification.html")
    html = html.replace("{{ verification_url }}", verification_url)

    return _send_email(
        to_email=to_email,
        subject="Verify your VoxBridge account",
        html_content=html
    )


def send_reset_password_email(to_email: str, token: str) -> bool:
    """
    Envoie l'email de réinitialisation de mot de passe.

    Paramètres :
        to_email : adresse du compte concerné
        token    : reset_password_token stocké dans User.reset_password_token
    """
    reset_url = f"{FRONTEND_URL}/reset-password?token={token}"

    html = _load_template("reset_password.html")
    html = html.replace("{{ reset_url }}", reset_url)

    return _send_email(
        to_email=to_email,
        subject="Reset your VoxBridge password",
        html_content=html
    )