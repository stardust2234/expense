import pytest

from app.api.auth_dependencies import get_application_settings
from app.config import get_settings
from app.main import create_app


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


def test_auth0_configuration_is_loaded(monkeypatch) -> None:
    monkeypatch.setenv("AUTH0_DOMAIN", "tenant.eu.auth0.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "client-id")
    monkeypatch.setenv("AUTH0_AUDIENCE", "https://api.example.com")

    settings = get_settings()

    assert settings.auth0_domain == "tenant.eu.auth0.com"
    assert settings.auth0_client_id == "client-id"
    assert settings.auth0_audience == "https://api.example.com"


def test_auth0_domain_rejects_a_url(monkeypatch) -> None:
    monkeypatch.setenv("AUTH0_DOMAIN", "https://tenant.auth0.com/")

    with pytest.raises(ValueError, match="hostname"):
        get_settings()


def test_production_rejects_placeholder_auth0_configuration(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("AUTH0_DOMAIN", raising=False)
    monkeypatch.delenv("AUTH0_CLIENT_ID", raising=False)
    monkeypatch.delenv("AUTH0_AUDIENCE", raising=False)

    with pytest.raises(ValueError, match="Production Auth0"):
        get_settings()


@pytest.mark.anyio
async def test_auth_dependencies_use_application_factory_settings() -> None:
    settings = get_settings()
    application = create_app(settings)
    request = type("RequestStub", (), {"app": application})()

    assert await get_application_settings(request) is settings
