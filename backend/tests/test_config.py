import pytest

from app.config import get_settings


def test_settings_use_sqlite_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = get_settings()

    assert settings.app_name == "expense-categoriser"
    assert settings.app_env == "development"
    assert settings.database_url.endswith("/data/expense.db")


def test_invalid_environment_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "invalid")

    with pytest.raises(ValueError, match="APP_ENV must be one of"):
        get_settings()


def test_render_external_url_is_the_default_public_url(monkeypatch) -> None:
    monkeypatch.delenv("PUBLIC_APP_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://expense-app.onrender.com")

    settings = get_settings()

    assert settings.public_app_url == "https://expense-app.onrender.com"


def test_public_url_overrides_render_external_url(monkeypatch) -> None:
    monkeypatch.setenv("PUBLIC_APP_URL", "https://expenses.example.com")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://expense-app.onrender.com")

    settings = get_settings()

    assert settings.public_app_url == "https://expenses.example.com"
