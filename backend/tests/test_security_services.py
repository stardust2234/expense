from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models import User
from app.services import email_token_workflow, mail_service
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


def test_smtp_readiness_checks_tls_authentication_and_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FakeSmtp:
        def __init__(self, host, port, *, timeout):
            assert (host, port, timeout) == ("smtp.example.com", 587, 10)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self, *, context):
            assert context.check_hostname is True
            calls.append("starttls")

        def login(self, username, password):
            assert (username, password) == ("user", "secret")
            calls.append("login")

        def noop(self):
            calls.append("noop")
            return 250, b"OK"

    monkeypatch.setattr(mail_service.smtplib, "SMTP", FakeSmtp)
    settings = SimpleNamespace(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="user",
        smtp_password="secret",
        mail_from="Folio <noreply@example.com>",
    )

    mail_service.check_smtp_readiness(settings)

    assert calls == ["starttls", "login", "noop"]


def test_delivery_test_sends_only_to_requested_recipient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivered: dict[str, str] = {}

    class FakeSmtp:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self, *, context):
            pass

        def send_message(self, message):
            delivered["to"] = message["To"]
            delivered["subject"] = message["Subject"]

    monkeypatch.setattr(mail_service.smtplib, "SMTP", FakeSmtp)
    settings = SimpleNamespace(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username=None,
        smtp_password=None,
        mail_from="Folio <noreply@example.com>",
    )

    mail_service.send_delivery_test(settings, email="owner@example.com")

    assert delivered == {
        "to": "owner@example.com",
        "subject": "Folio email delivery test",
    }


def test_mail_configuration_rejects_partial_credentials() -> None:
    settings = SimpleNamespace(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="user",
        smtp_password=None,
        mail_from="noreply@example.com",
    )

    with pytest.raises(mail_service.MailConfigurationError, match="must be set together"):
        mail_service.validate_mail_configuration(settings)


@pytest.mark.anyio
async def test_email_token_delivery_uses_threadpool_for_configured_smtp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, tuple, dict]] = []

    async def fake_threadpool(function, *args, **kwargs):
        calls.append((function, args, kwargs))

    monkeypatch.setattr(email_token_workflow, "run_in_threadpool", fake_threadpool)
    settings = SimpleNamespace(smtp_host="smtp.example.com")
    delivery = email_token_workflow.EmailTokenDelivery(
        recipient="person@example.com",
        purpose="email_verification",
        raw_token="secret-token",
    )

    await email_token_workflow.deliver_email_token(settings, delivery)

    assert calls == [
        (
            mail_service.send_account_token,
            (settings,),
            {
                "email": "person@example.com",
                "purpose": "email_verification",
                "token": "secret-token",
            },
        )
    ]
