from pathlib import Path

import pytest

from app.config import get_settings


def test_env_example_contains_expected_keys() -> None:
    env_example = Path(__file__).resolve().parents[2] / ".env.example"

    assert env_example.exists()

    keys = {
        line.split("=", 1)[0]
        for line in env_example.read_text().splitlines()
        if line and not line.startswith("#")
    }

    assert keys == {
        "APP_NAME",
        "APP_ENV",
        "APP_HOST",
        "APP_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "CADDY_SITE_ADDRESS",
    }


def test_get_settings_returns_defaults_when_env_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "APP_NAME",
        "APP_ENV",
        "APP_HOST",
        "APP_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = get_settings()

    assert settings.app_name == "starter-app"
    assert settings.app_env == "development"
    assert settings.app_host == "0.0.0.0"
    assert settings.app_port == 8000
    assert settings.postgres_host == "db"


@pytest.mark.parametrize(
    ("env_key", "env_value", "message"),
    [
        ("APP_NAME", "   ", "APP_NAME must not be empty"),
        ("APP_ENV", "local", "APP_ENV must be one of"),
        ("APP_HOST", "   ", "APP_HOST must not be empty"),
        ("APP_PORT", "abc", "APP_PORT must be a numeric string"),
        ("APP_PORT", "70000", "APP_PORT must be between 1 and 65535"),
        ("POSTGRES_HOST", "   ", "POSTGRES_HOST must not be empty"),
        ("POSTGRES_PORT", "abc", "POSTGRES_PORT must be a numeric string"),
    ],
)
def test_get_settings_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch, env_key: str, env_value: str, message: str
) -> None:
    monkeypatch.setenv("APP_NAME", "starter-app")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_HOST", "0.0.0.0")
    monkeypatch.setenv("APP_PORT", "8000")
    monkeypatch.setenv("POSTGRES_DB", "app")
    monkeypatch.setenv("POSTGRES_USER", "app")
    monkeypatch.setenv("POSTGRES_PASSWORD", "app")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv(env_key, env_value)

    with pytest.raises(ValueError, match=message):
        get_settings()
