from collections.abc import Mapping
from enum import StrEnum
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.modules.audit_logs.models import AuditLog


class AuditAction(StrEnum):
    ORGANIZATION_CREATED = "ORGANIZATION_CREATED"
    SERVICE_CREATED = "SERVICE_CREATED"
    API_KEY_CREATED = "API_KEY_CREATED"
    API_KEY_ROTATED = "API_KEY_ROTATED"
    API_KEY_REVOKED = "API_KEY_REVOKED"
    MEMBER_ROLE_CHANGED = "MEMBER_ROLE_CHANGED"
    INCIDENT_ACKNOWLEDGED = "INCIDENT_ACKNOWLEDGED"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    LOGIN_FAILED = "LOGIN_FAILED"


SENSITIVE_KEY_PARTS = (
    "password",
    "token",
    "secret",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "credential",
)


def _safe_value(value: Any) -> object:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return sanitize_audit_metadata(value)
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item) for item in list(value)[:50]]
    return str(value)[:500]


def sanitize_audit_metadata(metadata: Mapping[str, Any] | None) -> dict[str, object]:
    if not metadata:
        return {}
    sanitized: dict[str, object] = {}
    for raw_key, value in metadata.items():
        key = str(raw_key)[:100]
        normalized = key.lower().replace("-", "_")
        if any(part in normalized for part in SENSITIVE_KEY_PARTS):
            continue
        sanitized[key] = _safe_value(value)
    return sanitized


def record_audit_log(
    session: Session,
    *,
    action: AuditAction | str,
    resource_type: str,
    request: Request | None = None,
    organization_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    resource_id: UUID | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> AuditLog:
    ip_address = None
    user_agent = None
    if request is not None:
        if request.client and request.client.host:
            ip_address = request.client.host[:45]
        raw_user_agent = request.headers.get("user-agent")
        user_agent = raw_user_agent[:500] if raw_user_agent else None

    entry = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=str(action),
        resource_type=resource_type[:80],
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=sanitize_audit_metadata(metadata),
    )
    session.add(entry)
    return entry
