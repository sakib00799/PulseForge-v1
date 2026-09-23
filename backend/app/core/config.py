from enum import StrEnum
from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


DEVELOPMENT_JWT_SECRET = "change-this-development-secret-before-production"
DEVELOPMENT_API_KEY_PEPPER = "change-this-api-key-pepper-before-production"
MINIMUM_PRODUCTION_SECRET_LENGTH = 32


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized.startswith(("change-this", "replace-with", "example", "development"))


class Settings(BaseSettings):
    app_name: str = "PulseForge API"
    environment: AppEnvironment = Field(
        default=AppEnvironment.DEVELOPMENT,
        validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"),
    )
    app_debug: bool = Field(default=True, validation_alias="APP_DEBUG")
    database_url: str = "postgresql+psycopg://pulseforge:pulseforge@127.0.0.1:5434/pulseforge"
    cors_origins: str = "http://localhost:3000"
    jwt_secret_key: str = DEVELOPMENT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_reset_expire_minutes: int = 30
    refresh_cookie_name: str = "pulseforge_refresh"
    api_key_pepper: str = DEVELOPMENT_API_KEY_PEPPER

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.environment != AppEnvironment.PRODUCTION:
            return self

        if self.app_debug:
            raise ValueError("Production requires DEBUG=false")

        if (
            len(self.jwt_secret_key) < MINIMUM_PRODUCTION_SECRET_LENGTH
            or self.jwt_secret_key == DEVELOPMENT_JWT_SECRET
            or _looks_like_placeholder(self.jwt_secret_key)
        ):
            raise ValueError(
                "Production requires a secure JWT_SECRET_KEY of at least "
                f"{MINIMUM_PRODUCTION_SECRET_LENGTH} characters"
            )

        if (
            len(self.api_key_pepper) < MINIMUM_PRODUCTION_SECRET_LENGTH
            or self.api_key_pepper == DEVELOPMENT_API_KEY_PEPPER
            or _looks_like_placeholder(self.api_key_pepper)
        ):
            raise ValueError(
                "Production requires a secure API_KEY_PEPPER of at least "
                f"{MINIMUM_PRODUCTION_SECRET_LENGTH} characters"
            )

        origins = self.cors_origins_list
        if not origins or "*" in origins:
            raise ValueError("Production requires explicit CORS_ORIGINS; wildcard origins are forbidden")

        try:
            database = make_url(self.database_url)
        except Exception as error:
            raise ValueError("Production requires a valid DATABASE_URL") from error
        if database.drivername.startswith("sqlite"):
            raise ValueError("Production does not allow a SQLite DATABASE_URL")
        if database.host in {None, "localhost", "127.0.0.1", "::1"}:
            raise ValueError("Production does not allow a local DATABASE_URL host")

        return self

    @property
    def debug(self) -> bool:
        return self.app_debug

    @property
    def refresh_cookie_secure(self) -> bool:
        return self.environment == AppEnvironment.PRODUCTION

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
