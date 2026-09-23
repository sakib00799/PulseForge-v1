import pytest
from pydantic import ValidationError

from app.core.config import AppEnvironment, Settings


SECURE_JWT_SECRET = "jwt-production-secret-with-at-least-32-characters"
SECURE_API_KEY_PEPPER = "api-key-production-pepper-with-at-least-32-characters"


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": AppEnvironment.PRODUCTION,
        "app_debug": False,
        "database_url": "postgresql+psycopg://pulseforge:secret@db.internal/pulseforge",
        "cors_origins": "https://app.pulseforge.example",
        "jwt_secret_key": SECURE_JWT_SECRET,
        "api_key_pepper": SECURE_API_KEY_PEPPER,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_development_defaults_remain_usable() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == AppEnvironment.DEVELOPMENT
    assert settings.debug is True
    assert settings.cors_origins_list == ["http://localhost:3000"]


def test_production_accepts_secure_configuration() -> None:
    settings = production_settings()

    assert settings.environment == AppEnvironment.PRODUCTION
    assert settings.debug is False


def test_app_env_is_preferred_and_environment_is_backward_compatible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("APP_ENV", "test")

    settings = Settings(_env_file=None)

    assert settings.environment == AppEnvironment.TEST


@pytest.mark.parametrize("debug", [True, "true"])
def test_production_rejects_debug_mode(debug: object) -> None:
    with pytest.raises(ValidationError, match="Production requires DEBUG=false"):
        production_settings(app_debug=debug)


@pytest.mark.parametrize(
    "jwt_secret",
    ["weak", "change-this-development-secret-before-production", "replace-with-secret"],
)
def test_production_rejects_weak_or_placeholder_jwt_secret(jwt_secret: str) -> None:
    with pytest.raises(ValidationError, match="secure JWT_SECRET_KEY"):
        production_settings(jwt_secret_key=jwt_secret)


@pytest.mark.parametrize(
    "pepper",
    ["weak", "change-this-api-key-pepper-before-production", "replace-with-pepper"],
)
def test_production_rejects_weak_or_placeholder_api_key_pepper(pepper: str) -> None:
    with pytest.raises(ValidationError, match="secure API_KEY_PEPPER"):
        production_settings(api_key_pepper=pepper)


@pytest.mark.parametrize("cors_origins", ["*", "", "  "])
def test_production_rejects_wildcard_or_empty_cors(cors_origins: str) -> None:
    with pytest.raises(ValidationError, match="explicit CORS_ORIGINS"):
        production_settings(cors_origins=cors_origins)


@pytest.mark.parametrize(
    "database_url, expected_message",
    [
        ("sqlite:///pulseforge.db", "SQLite DATABASE_URL"),
        (
            "postgresql+psycopg://pulseforge:secret@localhost:5432/pulseforge",
            "local DATABASE_URL host",
        ),
        (
            "postgresql+psycopg://pulseforge:secret@127.0.0.1:5432/pulseforge",
            "local DATABASE_URL host",
        ),
    ],
)
def test_production_rejects_sqlite_and_local_database_urls(
    database_url: str,
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        production_settings(database_url=database_url)
