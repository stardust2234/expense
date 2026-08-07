import re
from dataclasses import dataclass
from os import getenv
from pathlib import Path

ALLOWED_APP_ENVS = {"development", "test", "staging", "production"}
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "expense.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DATABASE_PATH}"


def _required(key: str, default: str) -> str:
    value = getenv(key, default).strip()
    if not value:
        raise ValueError(f"{key} must not be empty")
    return value


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    database_url: str
    auth0_domain: str
    auth0_client_id: str
    auth0_audience: str
    auth0_email_claim: str
    auth0_name_claim: str


def get_settings() -> Settings:
    app_env = _required("APP_ENV", "development").lower()
    if app_env not in ALLOWED_APP_ENVS:
        raise ValueError(f"APP_ENV must be one of: {', '.join(sorted(ALLOWED_APP_ENVS))}")

    auth0_domain = _required("AUTH0_DOMAIN", "example.auth0.com")
    if not re.fullmatch(
        r"(?=.{1,253}\Z)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
        r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",
        auth0_domain,
    ):
        raise ValueError("AUTH0_DOMAIN must be a hostname without a scheme or path")
    auth0_client_id = _required("AUTH0_CLIENT_ID", "missing-client-id")
    auth0_audience = _required("AUTH0_AUDIENCE", "https://api.folio.local")
    if app_env in {"staging", "production"} and (
        auth0_domain == "example.auth0.com"
        or auth0_client_id == "missing-client-id"
        or auth0_audience == "https://api.folio.local"
    ):
        raise ValueError("Production Auth0 tenant, client ID and audience must be configured")
    return Settings(
        app_name=_required("APP_NAME", "expense-categoriser"),
        app_env=app_env,
        database_url=_required("DATABASE_URL", DEFAULT_DATABASE_URL),
        auth0_domain=auth0_domain,
        auth0_client_id=auth0_client_id,
        auth0_audience=auth0_audience,
        auth0_email_claim=_required("AUTH0_EMAIL_CLAIM", "https://folio.app/email"),
        auth0_name_claim=_required("AUTH0_NAME_CLAIM", "https://folio.app/name"),
    )
