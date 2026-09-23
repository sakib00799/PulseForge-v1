"""Explicit, default-deny permissions for organization roles."""

from enum import StrEnum
from types import MappingProxyType

from app.modules.organizations.models import OrganizationRole


class Permission(StrEnum):
    ORGANIZATION_READ = "organization:read"
    ORGANIZATION_DELETE = "organization:delete"
    MEMBER_READ = "member:read"
    MEMBER_MANAGE = "member:manage"
    SERVICE_READ = "service:read"
    SERVICE_CREATE = "service:create"
    SERVICE_UPDATE = "service:update"
    SERVICE_DELETE = "service:delete"
    API_KEY_READ = "api_key:read"
    API_KEY_MANAGE = "api_key:manage"
    EVENT_READ = "event:read"
    INCIDENT_READ = "incident:read"
    INCIDENT_ACKNOWLEDGE = "incident:acknowledge"
    INCIDENT_RESOLVE = "incident:resolve"
    AUDIT_LOG_READ = "audit_log:read"


READ_PERMISSIONS = frozenset({
    Permission.ORGANIZATION_READ, Permission.MEMBER_READ, Permission.SERVICE_READ,
    Permission.API_KEY_READ, Permission.EVENT_READ, Permission.INCIDENT_READ,
})
OPERATOR_PERMISSIONS = READ_PERMISSIONS | {
    Permission.INCIDENT_ACKNOWLEDGE, Permission.INCIDENT_RESOLVE,
}
ROLE_PERMISSIONS = MappingProxyType({
    OrganizationRole.OWNER: frozenset(Permission),
    OrganizationRole.ADMIN: OPERATOR_PERMISSIONS | {
        Permission.SERVICE_CREATE, Permission.SERVICE_UPDATE, Permission.SERVICE_DELETE,
        Permission.MEMBER_MANAGE, Permission.AUDIT_LOG_READ,
    },
    OrganizationRole.ENGINEER: OPERATOR_PERMISSIONS,
    OrganizationRole.VIEWER: READ_PERMISSIONS,
})


def permissions_for_role(role: str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())
