import logging
from pathlib import Path
import sendgrid
from sendgrid.helpers.mail import Mail, To, From

from config import (
    SENDGRID_API_KEY,
    SENDGRID_FROM_EMAIL,
    SENDGRID_FROM_NAME,
    FRONTEND_URL
)

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_template(filename: str) -> str:
    path = TEMPLATES_DIR / filename
    return path.read_text(encoding="utf-8")


def _send_email(to_email: str, subject: str, html_content: str) -> bool:
    try:
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)

        message = Mail(
            from_email=From(SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME),
            to_emails=To(to_email),
            subject=subject,
            html_content=html_content
        )

        response = sg.send(message)

        if response.status_code in (200, 202):
            logger.info(f"Email envoyé à {to_email} | status={response.status_code}")
            return True
        else:
            logger.error(f"SendGrid erreur {response.status_code} pour {to_email}")
            return False

    except Exception as e:
        logger.error(f"Erreur envoi email à {to_email} : {e}")
        return False


def send_verification_email(to_email: str, token: str) -> bool:
    verification_url = f"{FRONTEND_URL}/verify-email?token={token}"

    html = _load_template("verification.html")
    html = html.replace("{{ verification_url }}", verification_url)

    return _send_email(
        to_email=to_email,
        subject="Verify your VoxBridge account",
        html_content=html
    )


def send_reset_password_email(to_email: str, token: str) -> bool:
    reset_url = f"{FRONTEND_URL}/reset-password?token={token}"

    html = _load_template("reset_password.html")
    html = html.replace("{{ reset_url }}", reset_url)

    return _send_email(
        to_email=to_email,
        subject="Reset your VoxBridge password",
        html_content=html
    )