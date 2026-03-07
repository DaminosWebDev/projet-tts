"""
==============================================================================
email/email_service.py — Envoi d'emails transactionnels via SendGrid
==============================================================================
QU'EST-CE QU'UN EMAIL TRANSACTIONNEL ?
  Un email déclenché par une action utilisateur (pas du marketing).
  Exemples : confirmation d'inscription, reset de mot de passe, alertes.
  Différent des newsletters → meilleure délivrabilité (moins de spam).

POURQUOI SENDGRID ?
  - API simple et bien documentée
  - 100 emails/jour gratuits (suffisant pour un portfolio)
  - Très reconnu dans l'industrie
  - Gère la délivrabilité (évite les spams) automatiquement

FLUX EMAIL DE VÉRIFICATION :
  1. Utilisateur s'inscrit → on génère un token unique
  2. On stocke le token en DB (colonne verification_token)
  3. On envoie un email avec un lien contenant ce token
  4. Utilisateur clique le lien → GET /auth/verify-email?token=xxx
  5. On vérifie le token en DB → is_verified = True

FLUX EMAIL RESET MOT DE PASSE :
  1. Utilisateur clique "mot de passe oublié" → POST /auth/forgot-password
  2. On génère un token + date d'expiration (1h)
  3. On envoie un email avec le lien de reset
  4. Utilisateur clique → POST /auth/reset-password { token, new_password }
  5. On vérifie token + expiration → met à jour hashed_password
==============================================================================
"""

import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
# Mail    → objet représentant un email complet
# Email   → adresse expéditeur
# To      → adresse destinataire
# Content → corps de l'email (HTML ou texte)

from config import (
    SENDGRID_API_KEY,
    SENDGRID_FROM_EMAIL,
    SENDGRID_FROM_NAME,
    EMAIL_VERIFICATION_EXPIRE_HOURS,
    PASSWORD_RESET_EXPIRE_HOURS,
)

logger = logging.getLogger(__name__)


# ── Fonction d'envoi bas niveau ───────────────────────────────────────────────

async def _send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Envoie un email via l'API SendGrid.

    QU'EST-CE QUE C'EST : Fonction interne utilisée par toutes les autres.
    POURQUOI async : pour ne pas bloquer le serveur pendant l'envoi
    POURQUOI prefixe _ : convention Python pour "fonction privée"
                         ne pas appeler directement depuis l'extérieur

    Paramètres :
        to_email     (str) : adresse email du destinataire
        subject      (str) : sujet de l'email
        html_content (str) : corps HTML de l'email

    Retourne :
        bool : True si envoyé avec succès, False sinon
    """
    if not SENDGRID_API_KEY:
        # Mode développement sans SendGrid configuré
        # On log l'email au lieu de l'envoyer → pratique pour tester
        logger.warning("SENDGRID_API_KEY non configurée — email simulé")
        logger.info(f"EMAIL SIMULÉ → {to_email} | Sujet: {subject}")
        logger.info(f"Contenu HTML: {html_content[:200]}...")
        return True
        # On retourne True pour ne pas bloquer le flow de développement
        # Tu peux tester l'inscription même sans SendGrid configuré

    try:
        message = Mail(
            from_email=Email(SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME),
            # Email(adresse, nom_affiché)
            # Ex: Email("noreply@monapp.com", "TTS App")
            # Le destinataire verra "TTS App <noreply@monapp.com>"

            to_emails=To(to_email),
            # Adresse du destinataire

            subject=subject,
            # Sujet affiché dans la boîte mail

            html_content=Content("text/html", html_content),
            # Corps HTML de l'email
            # "text/html" = indique au client mail que c'est du HTML
        )

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        # Crée un client SendGrid avec notre clé API

        response = sg.send(message)
        # Envoie l'email via l'API SendGrid
        # Retourne un objet Response avec status_code

        if response.status_code in (200, 202):
            # 200 = OK, 202 = Accepted (SendGrid utilise 202)
            logger.info(f"Email envoyé → {to_email} | {subject}")
            return True
        else:
            logger.error(f"SendGrid erreur {response.status_code} → {to_email}")
            return False

    except Exception as e:
        logger.error(f"Erreur envoi email → {to_email} : {e}")
        return False


# ── Templates HTML ────────────────────────────────────────────────────────────

def _get_verification_email_html(verification_url: str) -> str:
    """
    Génère le HTML de l'email de vérification.

    QU'EST-CE QUE C'EST : Template HTML pour l'email de confirmation d'inscription.
    POURQUOI HTML : les emails HTML ont un meilleur taux de clic que le texte brut.
    """
    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Vérification de votre email</title>
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
        <div style="background-color: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">

            <h1 style="color: #333; text-align: center; margin-bottom: 10px;">
                🎙️ TTS App
            </h1>

            <h2 style="color: #555; text-align: center; font-weight: normal;">
                Confirmez votre adresse email
            </h2>

            <p style="color: #666; line-height: 1.6;">
                Bonjour,<br><br>
                Merci de vous être inscrit sur TTS App.
                Cliquez sur le bouton ci-dessous pour confirmer votre adresse email
                et activer votre compte.
            </p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{verification_url}"
                   style="background-color: #4F46E5;
                          color: white;
                          padding: 15px 30px;
                          text-decoration: none;
                          border-radius: 5px;
                          font-size: 16px;
                          font-weight: bold;
                          display: inline-block;">
                    ✅ Confirmer mon email
                </a>
            </div>

            <p style="color: #999; font-size: 14px; line-height: 1.6;">
                Ce lien est valable <strong>{EMAIL_VERIFICATION_EXPIRE_HOURS} heures</strong>.<br>
                Si vous n'avez pas créé de compte, ignorez cet email.
            </p>

            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">

            <p style="color: #bbb; font-size: 12px; text-align: center;">
                Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur :<br>
                <a href="{verification_url}" style="color: #4F46E5; word-break: break-all;">
                    {verification_url}
                </a>
            </p>
        </div>
    </body>
    </html>
    """


def _get_reset_password_email_html(reset_url: str) -> str:
    """
    Génère le HTML de l'email de reset de mot de passe.
    """
    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Réinitialisation de votre mot de passe</title>
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
        <div style="background-color: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">

            <h1 style="color: #333; text-align: center; margin-bottom: 10px;">
                🎙️ TTS App
            </h1>

            <h2 style="color: #555; text-align: center; font-weight: normal;">
                Réinitialisation du mot de passe
            </h2>

            <p style="color: #666; line-height: 1.6;">
                Bonjour,<br><br>
                Vous avez demandé la réinitialisation de votre mot de passe.
                Cliquez sur le bouton ci-dessous pour choisir un nouveau mot de passe.
            </p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}"
                   style="background-color: #DC2626;
                          color: white;
                          padding: 15px 30px;
                          text-decoration: none;
                          border-radius: 5px;
                          font-size: 16px;
                          font-weight: bold;
                          display: inline-block;">
                    🔑 Réinitialiser mon mot de passe
                </a>
            </div>

            <p style="color: #999; font-size: 14px; line-height: 1.6;">
                Ce lien est valable <strong>{PASSWORD_RESET_EXPIRE_HOURS} heure(s)</strong>.<br>
                Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.
                Votre mot de passe ne sera pas modifié.
            </p>

            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">

            <p style="color: #bbb; font-size: 12px; text-align: center;">
                Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur :<br>
                <a href="{reset_url}" style="color: #DC2626; word-break: break-all;">
                    {reset_url}
                </a>
            </p>
        </div>
    </body>
    </html>
    """


# ── Fonctions publiques ───────────────────────────────────────────────────────

async def send_verification_email(to_email: str, verification_token: str) -> bool:
    """
    Envoie l'email de vérification d'adresse email.

    QU'EST-CE QUE C'EST : Email envoyé après l'inscription pour confirmer l'email.
    QUAND L'UTILISER : dans POST /auth/register après création du compte.

    Paramètres :
        to_email           (str) : email du nouvel utilisateur
        verification_token (str) : token unique généré à l'inscription

    Retourne :
        bool : True si envoyé avec succès

    Exemple :
        >>> await send_verification_email(
        ...     "user@test.com",
        ...     "a3f8c2d14b5e41d4a716446655440000"
        ... )
    """
    verification_url = (
        f"http://localhost:8000/auth/verify-email?token={verification_token}"
    )
    # En production → remplacer localhost par le vrai domaine
    # Ex: "https://monapp.com/auth/verify-email?token=..."

    html = _get_verification_email_html(verification_url)

    return await _send_email(
        to_email=to_email,
        subject="🎙️ TTS App — Confirmez votre adresse email",
        html_content=html,
    )


async def send_reset_password_email(to_email: str, reset_token: str) -> bool:
    """
    Envoie l'email de réinitialisation de mot de passe.

    QU'EST-CE QUE C'EST : Email envoyé quand l'utilisateur clique "mot de passe oublié".
    QUAND L'UTILISER : dans POST /auth/forgot-password.

    Paramètres :
        to_email    (str) : email de l'utilisateur
        reset_token (str) : token unique valable 1 heure

    Retourne :
        bool : True si envoyé avec succès
    """
    reset_url = (
        f"http://localhost:8000/auth/reset-password?token={reset_token}"
    )

    html = _get_reset_password_email_html(reset_url)

    return await _send_email(
        to_email=to_email,
        subject="🔑 TTS App — Réinitialisation de votre mot de passe",
        html_content=html,
    )