from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models import User
from app.services import mail_service
from app.services.account_security_service import AccountTokenError, consume_token, issue_token


def test_account_token_can_only_be_consumed_once() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = User(
            email="secure@example.com",
            display_name="Secure User",
            password_hash="unused-in-this-test",
            email_verified_at=datetime.now(UTC),
        )
        session.add(user)
        session.commit()
        raw = issue_token(session, user=user, purpose="password_reset", minutes=60)

        assert consume_token(session, raw=raw, purpose="password_reset").id == user.id
        session.commit()
        with pytest.raises(AccountTokenError):
            consume_token(session, raw=raw, purpose="password_reset")


def test_smtp_starttls_uses_a_verified_ssl_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    class FakeSmtp:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self, *, context):
            calls["context"] = context

        def login(self, *_args):
            pass

        def send_message(self, _message):
            pass

    monkeypatch.setattr(mail_service.smtplib, "SMTP", FakeSmtp)
    settings = SimpleNamespace(
        public_app_url="https://example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="user",
        smtp_password="secret",
        mail_from="noreply@example.com",
        app_env="production",
    )

    mail_service.send_account_token(
        settings, email="person@example.com", purpose="email_verification", token="secret-token"
    )

    context = calls["context"]
    assert context.check_hostname is True
    assert context.verify_mode.name == "CERT_REQUIRED"
