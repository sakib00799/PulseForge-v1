from uuid import UUID

from app.core.permissions import Permission

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DbSession
from app.modules.audit_logs.service import AuditAction, record_audit_log
from app.modules.organizations.permissions import (
    can_manage_role, require_permission, get_tenant_resource_or_404,
)
from app.modules.services.models import Service
from app.modules.services.schemas import ServiceCreate, ServiceResponse, ServiceUpdate

router = APIRouter(prefix="/services")


def commit_service(session: DbSession, service: Service) -> Service:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service slug is already in use in this organization",
        ) from error
    session.refresh(service)
    return service


@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
) -> Service:
    require_permission(Permission.SERVICE_CREATE)(session, payload.organization_id, current_user.id)
    service = Service(
        organization_id=payload.organization_id,
        name=payload.name.strip(),
        slug=payload.slug,
        description=payload.description,
        environment=payload.environment,
    )
    session.add(service)
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service slug is already in use in this organization",
        ) from error
    record_audit_log(
        session,
        action=AuditAction.SERVICE_CREATED,
        organization_id=service.organization_id,
        actor_user_id=current_user.id,
        resource_type="service",
        resource_id=service.id,
        request=request,
        metadata={"slug": service.slug, "environment": service.environment.value},
    )
    return commit_service(session, service)


@router.get("", response_model=list[ServiceResponse])
def list_services(
    organization_id: UUID = Query(),
    *,
    session: DbSession,
    current_user: CurrentUser,
) -> list[Service]:
    require_permission(Permission.SERVICE_READ)(session, organization_id, current_user.id)
    return list(
        session.scalars(
            select(Service)
            .where(Service.organization_id == organization_id)
            .order_by(Service.created_at.desc())
        ).all()
    )


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(service_id: UUID, session: DbSession, current_user: CurrentUser) -> Service:
    service = get_tenant_resource_or_404(session, Service, service_id, current_user.id)
    require_permission(Permission.SERVICE_READ)(session, service.organization_id, current_user.id)
    return service


@router.patch("/{service_id}", response_model=ServiceResponse)
def update_service(
    service_id: UUID,
    payload: ServiceUpdate,
    session: DbSession,
    current_user: CurrentUser,
) -> Service:
    service = get_tenant_resource_or_404(session, Service, service_id, current_user.id)
    require_permission(Permission.SERVICE_UPDATE)(session, service.organization_id, current_user.id)

    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    for field, value in changes.items():
        setattr(service, field, value)
    return commit_service(session, service)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(
    service_id: UUID, session: DbSession, current_user: CurrentUser
) -> Response:
    service = get_tenant_resource_or_404(session, Service, service_id, current_user.id)
    require_permission(Permission.SERVICE_DELETE)(session, service.organization_id, current_user.id)
    session.delete(service)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
