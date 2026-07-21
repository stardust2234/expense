from dataclasses import dataclass
from os import getenv


ALLOWED_APP_ENVS = {"development", "test", "staging", "production"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_host: str
    app_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def _require_non_empty(key: str, value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{key} must not be empty")
    return cleaned


def _parse_port(key: str, value: str) -> int:
    cleaned = value.strip()
    if not cleaned.isdigit():
        raise ValueError(f"{key} must be a numeric string")
    port = int(cleaned)
    if not 1 <= port <= 65535:
        raise ValueError(f"{key} must be between 1 and 65535")
    return port


def get_settings() -> Settings:
    app_name = _require_non_empty("APP_NAME", getenv("APP_NAME", "starter-app"))
    app_env = _require_non_empty("APP_ENV", getenv("APP_ENV", "development")).lower()
    app_host = _require_non_empty("APP_HOST", getenv("APP_HOST", "0.0.0.0"))
    app_port = _parse_port("APP_PORT", getenv("APP_PORT", "8000"))
    postgres_db = _require_non_empty("POSTGRES_DB", getenv("POSTGRES_DB", "app"))
    postgres_user = _require_non_empty("POSTGRES_USER", getenv("POSTGRES_USER", "app"))
    postgres_password = _require_non_empty("POSTGRES_PASSWORD", getenv("POSTGRES_PASSWORD", "app"))
    postgres_host = _require_non_empty("POSTGRES_HOST", getenv("POSTGRES_HOST", "db"))
    postgres_port = _parse_port("POSTGRES_PORT", getenv("POSTGRES_PORT", "5432"))

    if app_env not in ALLOWED_APP_ENVS:
        raise ValueError(f"APP_ENV must be one of: {', '.join(sorted(ALLOWED_APP_ENVS))}")

    return Settings(
        app_name=app_name,
        app_env=app_env,
        app_host=app_host,
        app_port=app_port,
        postgres_db=postgres_db,
        postgres_user=postgres_user,
        postgres_password=postgres_password,
        postgres_host=postgres_host,
        postgres_port=postgres_port,
    )
