from datetime import datetime, timezone
from uuid import UUID

from app.core.permissions import Permission

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.modules.audit_logs.service import AuditAction, record_audit_log
from app.modules.incidents.models import Incident, IncidentStatus
from app.modules.incidents.schemas import IncidentResponse
from app.modules.organizations.permissions import (
    can_manage_role, require_permission, get_tenant_resource_or_404,
)

router = APIRouter(prefix="/incidents")


@router.get("", response_model=list[IncidentResponse])
def list_incidents(
    organization_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    incident_status: IncidentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[Incident]:
    require_permission(Permission.INCIDENT_READ)(session, organization_id, current_user.id)
    query = select(Incident).where(Incident.organization_id == organization_id)
    if incident_status is not None:
        query = query.where(Incident.status == incident_status)
    return list(
        session.scalars(query.order_by(Incident.detected_at.desc()).limit(limit)).all()
    )


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(
    incident_id: UUID, session: DbSession, current_user: CurrentUser
) -> Incident:
    incident = get_tenant_resource_or_404(session, Incident, incident_id, current_user.id)
    require_permission(Permission.INCIDENT_READ)(session, incident.organization_id, current_user.id)
    return incident


@router.post("/{incident_id}/acknowledge", response_model=IncidentResponse)
def acknowledge_incident(
    incident_id: UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
) -> Incident:
    incident = get_tenant_resource_or_404(session, Incident, incident_id, current_user.id)
    require_permission(Permission.INCIDENT_ACKNOWLEDGE)(session, incident.organization_id, current_user.id)
    if incident.status == IncidentStatus.RESOLVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resolved incidents cannot be acknowledged",
        )
    if incident.status == IncidentStatus.OPEN:
        incident.status = IncidentStatus.ACKNOWLEDGED
        incident.acknowledged_at = datetime.now(timezone.utc)
        incident.assigned_to = current_user.id
        record_audit_log(
            session,
            action=AuditAction.INCIDENT_ACKNOWLEDGED,
            organization_id=incident.organization_id,
            actor_user_id=current_user.id,
            resource_type="incident",
            resource_id=incident.id,
            request=request,
        )
        session.commit()
        session.refresh(incident)
    return incident


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
def resolve_incident(
    incident_id: UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
) -> Incident:
    incident = get_tenant_resource_or_404(session, Incident, incident_id, current_user.id)
    require_permission(Permission.INCIDENT_RESOLVE)(session, incident.organization_id, current_user.id)
    if incident.status != IncidentStatus.RESOLVED:
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now(timezone.utc)
        if incident.assigned_to is None:
            incident.assigned_to = current_user.id
        record_audit_log(
            session,
            action=AuditAction.INCIDENT_RESOLVED,
            organization_id=incident.organization_id,
            actor_user_id=current_user.id,
            resource_type="incident",
            resource_id=incident.id,
            request=request,
        )
        session.commit()
        session.refresh(incident)
    return incident
