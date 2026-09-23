from uuid import UUID

from app.core.permissions import Permission

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.modules.audit_logs.models import AuditLog
from app.modules.audit_logs.schemas import AuditLogResponse
from app.modules.organizations.permissions import require_permission, get_tenant_resource_or_404

router = APIRouter(prefix="/audit-logs")


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    organization_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLog]:
    require_permission(Permission.AUDIT_LOG_READ)(session, organization_id, current_user.id)
    return list(
        session.scalars(
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
