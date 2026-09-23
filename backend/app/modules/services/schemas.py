from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.services.models import ServiceEnvironment, ServiceStatus

slug_field = Field(
    pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    min_length=2,
    max_length=80,
)


class ServiceCreate(BaseModel):
    organization_id: UUID
    name: str = Field(min_length=2, max_length=120)
    slug: str = slug_field
    description: str | None = Field(default=None, max_length=2000)
    environment: ServiceEnvironment


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    slug: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        min_length=2,
        max_length=80,
    )
    description: str | None = Field(default=None, max_length=2000)
    environment: ServiceEnvironment | None = None
    status: ServiceStatus | None = None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    slug: str
    description: str | None
    environment: ServiceEnvironment
    status: ServiceStatus
    created_at: datetime
    updated_at: datetime
