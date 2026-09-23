from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiKeyScope(StrEnum):
    EVENTS_WRITE = "events:write"


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[ApiKeyScope] = Field(default_factory=lambda: [ApiKeyScope.EVENTS_WRITE])
    expires_at: datetime | None = None

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, scopes: list[ApiKeyScope]) -> list[ApiKeyScope]:
        if not scopes:
            raise ValueError("At least one scope is required")
        if len(scopes) != len(set(scopes)):
            raise ValueError("Scopes must be unique")
        return scopes

    @field_validator("expires_at")
    @classmethod
    def validate_expiration(cls, expires_at: datetime | None) -> datetime | None:
        if expires_at is None:
            return None
        if expires_at.tzinfo is None:
            raise ValueError("Expiration must include a timezone")
        if expires_at <= datetime.now(timezone.utc):
            raise ValueError("Expiration must be in the future")
        return expires_at


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    service_id: UUID
    name: str
    prefix: str
    scopes: list[ApiKeyScope]
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreatedResponse(ApiKeyResponse):
    api_key: str
