from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID | None
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: UUID | None
    ip_address: str | None
    user_agent: str | None
    metadata: dict[str, object] = Field(validation_alias="metadata_json")
    created_at: datetime
