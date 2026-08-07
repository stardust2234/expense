from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient

from app.config import Settings


class Auth0TokenError(ValueError):
    pass


@dataclass(frozen=True)
class Auth0Identity:
    subject: str
    email: str
    display_name: str


class Auth0TokenVerifier:
    def __init__(self, settings: Settings) -> None:
        self.issuer = f"https://{settings.auth0_domain}/"
        self.audience = settings.auth0_audience
        self.email_claim = settings.auth0_email_claim
        self.name_claim = settings.auth0_name_claim
        self.jwks = PyJWKClient(f"{self.issuer}.well-known/jwks.json", cache_keys=True)

    def verify(self, token: str) -> Auth0Identity:
        try:
            signing_key = self.jwks.get_signing_key_from_jwt(token).key
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "iss", "sub", "aud"]},
            )
        except jwt.PyJWTError as error:
            raise Auth0TokenError("Access token is invalid or expired") from error
        subject = claims.get("sub")
        email = claims.get(self.email_claim)
        display_name = claims.get(self.name_claim) or email
        if not isinstance(subject, str) or not subject:
            raise Auth0TokenError("Access token has no subject")
        if not isinstance(email, str) or email.count("@") != 1:
            raise Auth0TokenError("Access token has no trusted email claim")
        return Auth0Identity(
            subject=subject,
            email=email.strip().casefold(),
            display_name=str(display_name).strip()[:100] or email,
        )
