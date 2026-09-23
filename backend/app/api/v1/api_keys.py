from datetime import datetime, timezone
from uuid import UUID

from app.core.permissions import Permission

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.core.security import create_api_key
from app.modules.api_keys.models import ApiKey
from app.modules.api_keys.schemas import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse
from app.modules.audit_logs.service import AuditAction, record_audit_log
from app.modules.organizations.permissions import require_permission, get_tenant_resource_or_404
from app.modules.services.models import Service, ServiceEnvironment

service_router = APIRouter(prefix="/services/{service_id}/api-keys")
key_router = APIRouter(prefix="/api-keys")


def issue_api_key(
    service: Service,
    payload: ApiKeyCreate,
    session: DbSession,
    *,
    request: Request,
    actor_user_id: UUID,
    action: AuditAction,
    metadata: dict[str, object] | None = None,
) -> ApiKeyCreatedResponse:
    raw_key, prefix, key_hash = create_api_key(
        production=service.environment == ServiceEnvironment.PRODUCTION
    )
    api_key = ApiKey(
        organization_id=service.organization_id,
        service_id=service.id,
        name=payload.name.strip(),
        key_hash=key_hash,
        prefix=prefix,
        scopes=[scope.value for scope in payload.scopes],
        expires_at=payload.expires_at,
    )
    session.add(api_key)
    session.flush()
    record_audit_log(
        session,
        action=action,
        organization_id=service.organization_id,
        actor_user_id=actor_user_id,
        resource_type="api_key",
        resource_id=api_key.id,
        request=request,
        metadata=metadata,
    )
    session.commit()
    session.refresh(api_key)
    public_fields = ApiKeyResponse.model_validate(api_key).model_dump()
    return ApiKeyCreatedResponse(**public_fields, api_key=raw_key)


@service_router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_service_api_key(
    service_id: UUID,
    payload: ApiKeyCreate,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
) -> ApiKeyCreatedResponse:
    service = get_tenant_resource_or_404(session, Service, service_id, current_user.id)
    require_permission(Permission.API_KEY_MANAGE)(session, service.organization_id, current_user.id)
    return issue_api_key(
        service,
        payload,
        session,
        request=request,
        actor_user_id=current_user.id,
        action=AuditAction.API_KEY_CREATED,
    )


@service_router.get("", response_model=list[ApiKeyResponse])
def list_service_api_keys(
    service_id: UUID, session: DbSession, current_user: CurrentUser
) -> list[ApiKey]:
    service = get_tenant_resource_or_404(session, Service, service_id, current_user.id)
    require_permission(Permission.API_KEY_READ)(session, service.organization_id, current_user.id)
    return list(
        session.scalars(
            select(ApiKey)
            .where(ApiKey.service_id == service.id)
            .order_by(ApiKey.created_at.desc())
        ).all()
    )


@key_router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    api_key_id: UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
) -> Response:
    api_key = get_tenant_resource_or_404(session, ApiKey, api_key_id, current_user.id)
    require_permission(Permission.API_KEY_MANAGE)(session, api_key.organization_id, current_user.id)
    if api_key.revoked_at is None:
        api_key.revoked_at = datetime.now(timezone.utc)
        record_audit_log(
            session,
            action=AuditAction.API_KEY_REVOKED,
            organization_id=api_key.organization_id,
            actor_user_id=current_user.id,
            resource_type="api_key",
            resource_id=api_key.id,
            request=request,
        )
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@key_router.post("/{api_key_id}/rotate", response_model=ApiKeyCreatedResponse)
def rotate_api_key(
    api_key_id: UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
) -> ApiKeyCreatedResponse:
    old_key = get_tenant_resource_or_404(session, ApiKey, api_key_id, current_user.id)
    require_permission(Permission.API_KEY_MANAGE)(session, old_key.organization_id, current_user.id)
    if old_key.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Revoked API keys cannot be rotated",
        )
    if old_key.expires_at is not None and old_key.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Expired API keys cannot be rotated",
        )

    service = get_tenant_resource_or_404(session, Service, old_key.service_id, current_user.id)
    old_key.revoked_at = datetime.now(timezone.utc)
    payload = ApiKeyCreate(
        name=old_key.name,
        scopes=old_key.scopes,
        expires_at=old_key.expires_at,
    )
    return issue_api_key(
        service,
        payload,
        session,
        request=request,
        actor_user_id=current_user.id,
        action=AuditAction.API_KEY_ROTATED,
        metadata={"previous_resource_id": old_key.id},
    )
