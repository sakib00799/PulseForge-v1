from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.incidents.models import IncidentSeverity, IncidentStatus


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    service_id: UUID
    title: str
    description: str | None
    severity: IncidentSeverity
    status: IncidentStatus
    detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    assigned_to: UUID | None
    fingerprint: str
    created_at: datetime
    updated_at: datetime
