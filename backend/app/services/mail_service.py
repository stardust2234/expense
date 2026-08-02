import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import Settings

logger = logging.getLogger(__name__)


def send_account_token(settings: Settings, *, email: str, purpose: str, token: str) -> None:
    verification = purpose in {"email_verification", "email_change"}
    path = "verify-email" if verification else "reset-password"
    link = f"{settings.public_app_url.rstrip('/')}/{path}?token={token}"
    if not settings.smtp_host:
        if settings.app_env == "production":
            raise RuntimeError("Email delivery is not configured")
        logger.warning("Development %s link for %s: %s", purpose, email, link)
        return
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = email
    message["Subject"] = "Verify your Folio email" if verification else "Reset your Folio password"
    message.set_content(f"Open this single-use link within one hour:\n\n{link}\n")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)
