from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import get_settings
from app.services.auth0_service import Auth0TokenError, Auth0TokenVerifier


def verifier(monkeypatch: pytest.MonkeyPatch) -> tuple[Auth0TokenVerifier, object]:
    monkeypatch.setenv("AUTH0_DOMAIN", "tenant.auth0.com")
    monkeypatch.setenv("AUTH0_AUDIENCE", "https://api.example.com")
    value = Auth0TokenVerifier(get_settings())
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    value.jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=private_key.public_key())
    )
    return value, private_key


def test_auth0_access_token_validates_issuer_audience_signature_and_claims(monkeypatch) -> None:
    value, private_key = verifier(monkeypatch)
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": "https://tenant.auth0.com/",
            "aud": "https://api.example.com",
            "sub": "auth0|123",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "https://folio.app/email": "Owner@Example.com",
            "https://folio.app/name": "Owner",
        },
        private_key,
        algorithm="RS256",
    )

    identity = value.verify(token)

    assert identity.subject == "auth0|123"
    assert identity.email == "owner@example.com"


def test_auth0_access_token_rejects_wrong_audience(monkeypatch) -> None:
    value, private_key = verifier(monkeypatch)
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": "https://tenant.auth0.com/",
            "aud": "wrong",
            "sub": "auth0|123",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "https://folio.app/email": "owner@example.com",
        },
        private_key,
        algorithm="RS256",
    )

    with pytest.raises(Auth0TokenError):
        value.verify(token)
