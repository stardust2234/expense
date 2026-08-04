from dataclasses import dataclass
from ipaddress import ip_network
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
    allow_registration: bool
    auth_cookie_secure: bool
    session_days: int
    auth_throttle_secret: str
    admin_bootstrap_secret: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    mail_from: str
    public_app_url: str
    trusted_proxy_cidrs: tuple[str, ...]


def _boolean(key: str, default: bool) -> bool:
    value = getenv(key)
    if value is None:
        return default
    normalised = value.strip().casefold()
    if normalised in {"1", "true", "yes", "on"}:
        return True
    if normalised in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key} must be a boolean")


def get_settings() -> Settings:
    app_env = _required("APP_ENV", "development").lower()
    if app_env not in ALLOWED_APP_ENVS:
        raise ValueError(f"APP_ENV must be one of: {', '.join(sorted(ALLOWED_APP_ENVS))}")

    session_days = int(_required("AUTH_SESSION_DAYS", "7"))
    if session_days < 1 or session_days > 90:
        raise ValueError("AUTH_SESSION_DAYS must be between 1 and 90")
    throttle_secret = _required("AUTH_THROTTLE_SECRET", "development-only-auth-throttle-secret")
    if app_env == "production" and len(throttle_secret) < 32:
        raise ValueError("AUTH_THROTTLE_SECRET must be at least 32 characters in production")
    admin_bootstrap_secret = getenv("ADMIN_BOOTSTRAP_SECRET")
    if not admin_bootstrap_secret and app_env != "production":
        admin_bootstrap_secret = "development-only-admin-bootstrap-secret"
    trusted_proxy_cidrs = tuple(
        item.strip()
        for item in getenv("TRUSTED_PROXY_CIDRS", "127.0.0.1/32,::1/128").split(",")
        if item.strip()
    )
    try:
        for cidr in trusted_proxy_cidrs:
            ip_network(cidr, strict=False)
    except ValueError as error:
        raise ValueError("TRUSTED_PROXY_CIDRS must contain valid IP networks") from error
    return Settings(
        app_name=_required("APP_NAME", "expense-categoriser"),
        app_env=app_env,
        database_url=_required("DATABASE_URL", DEFAULT_DATABASE_URL),
        allow_registration=_boolean("ALLOW_REGISTRATION", app_env != "production"),
        auth_cookie_secure=_boolean("AUTH_COOKIE_SECURE", app_env == "production"),
        session_days=session_days,
        auth_throttle_secret=throttle_secret,
        admin_bootstrap_secret=admin_bootstrap_secret,
        smtp_host=getenv("SMTP_HOST") or None,
        smtp_port=int(getenv("SMTP_PORT", "587")),
        smtp_username=getenv("SMTP_USERNAME") or None,
        smtp_password=getenv("SMTP_PASSWORD") or None,
        mail_from=_required("MAIL_FROM", "noreply@localhost"),
        public_app_url=_required(
            "PUBLIC_APP_URL", getenv("RENDER_EXTERNAL_URL", "https://localhost:5173")
        ),
        trusted_proxy_cidrs=trusted_proxy_cidrs,
    )
