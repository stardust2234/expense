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


def get_settings() -> Settings:
    app_env = _required("APP_ENV", "development").lower()
    if app_env not in ALLOWED_APP_ENVS:
        raise ValueError(f"APP_ENV must be one of: {', '.join(sorted(ALLOWED_APP_ENVS))}")

    return Settings(
        app_name=_required("APP_NAME", "expense-categoriser"),
        app_env=app_env,
        database_url=_required("DATABASE_URL", DEFAULT_DATABASE_URL),
    )
