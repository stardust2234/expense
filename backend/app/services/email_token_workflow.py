from dataclasses import dataclass

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.models import User
from app.services.account_security_service import issue_token
from app.services.mail_service import send_account_token


@dataclass(frozen=True)
class EmailTokenDelivery:
    recipient: str
    purpose: str
    raw_token: str


def prepare_email_token(
    session: Session,
    *,
    user: User,
    purpose: str,
    recipient: str | None = None,
    minutes: int = 60,
) -> EmailTokenDelivery:
    raw = issue_token(session, user=user, purpose=purpose, minutes=minutes)
    return EmailTokenDelivery(
        recipient=recipient or user.email,
        purpose=purpose,
        raw_token=raw,
    )


async def deliver_email_token(settings: Settings, delivery: EmailTokenDelivery) -> None:
    if not settings.smtp_host:
        send_account_token(
            settings,
            email=delivery.recipient,
            purpose=delivery.purpose,
            token=delivery.raw_token,
        )
        return
    await run_in_threadpool(
        send_account_token,
        settings,
        email=delivery.recipient,
        purpose=delivery.purpose,
        token=delivery.raw_token,
    )
