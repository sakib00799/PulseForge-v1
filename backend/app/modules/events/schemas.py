import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.events.models import EventLevel


class EventCreate(BaseModel):
    event_id: str = Field(min_length=1, max_length=120)
    event_type: str = Field(min_length=1, max_length=120)
    level: EventLevel
    message: str = Field(min_length=1, max_length=10_000)
    occurred_at: datetime
    metadata: dict = Field(default_factory=dict)
    trace_id: str | None = Field(default=None, max_length=120)
    request_id: str | None = Field(default=None, max_length=120)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return value

    @field_validator("metadata")
    @classmethod
    def limit_metadata_size(cls, value: dict) -> dict:
        encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(encoded) > 32 * 1024:
            raise ValueError("metadata must not exceed 32768 bytes")
        return value


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    service_id: UUID
    event_id: str
    event_type: str
    level: EventLevel
    message: str
    occurred_at: datetime
    received_at: datetime
    fingerprint: str
    metadata: dict = Field(validation_alias="metadata_json", serialization_alias="metadata")
    trace_id: str | None
    request_id: str | None


class EventIngestResponse(BaseModel):
    event: EventResponse
    duplicate: bool
    incident_id: UUID | None = None
