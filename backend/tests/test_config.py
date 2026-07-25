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
