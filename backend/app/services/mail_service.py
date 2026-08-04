import logging
import smtplib
import ssl
from collections.abc import Iterator
from contextlib import contextmanager
from email.message import EmailMessage
from email.utils import parseaddr

from app.config import Settings

logger = logging.getLogger(__name__)
SMTP_TIMEOUT_SECONDS = 10


class MailConfigurationError(ValueError):
    pass


def validate_mail_configuration(settings: Settings) -> None:
    if not settings.smtp_host:
        raise MailConfigurationError("SMTP_HOST is required")
    if settings.smtp_port < 1 or settings.smtp_port > 65535:
        raise MailConfigurationError("SMTP_PORT must be between 1 and 65535")
    _name, address = parseaddr(settings.mail_from)
    if not address or address.count("@") != 1:
        raise MailConfigurationError("MAIL_FROM must contain a valid email address")
    if bool(settings.smtp_username) != bool(settings.smtp_password):
        raise MailConfigurationError("SMTP_USERNAME and SMTP_PASSWORD must be set together")


@contextmanager
def _smtp_connection(settings: Settings) -> Iterator[smtplib.SMTP]:
    validate_mail_configuration(settings)
    with smtplib.SMTP(
        settings.smtp_host,
        settings.smtp_port,
        timeout=SMTP_TIMEOUT_SECONDS,
    ) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        yield smtp


def check_smtp_readiness(settings: Settings) -> None:
    """Verify DNS/TCP, certificate-checked STARTTLS, authentication, and SMTP readiness."""
    with _smtp_connection(settings) as smtp:
        code, _message = smtp.noop()
        if code >= 400:
            raise RuntimeError(f"SMTP readiness check failed with status {code}")


def send_delivery_test(settings: Settings, *, email: str) -> None:
    _name, address = parseaddr(email)
    if not address or address.count("@") != 1:
        raise MailConfigurationError("Test recipient must be a valid email address")
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = address
    message["Subject"] = "Folio email delivery test"
    message.set_content(
        "Folio successfully connected to the configured SMTP service and delivered this test.\n"
    )
    with _smtp_connection(settings) as smtp:
        smtp.send_message(message)


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
    with _smtp_connection(settings) as smtp:
        smtp.send_message(message)
