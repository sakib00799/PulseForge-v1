from uuid import UUID
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError
from app.core.permissions import Permission, permissions_for_role
from app.db.base import Base
from app.modules.organizations.models import OrganizationMember, OrganizationRole


def require_permission(permission: Permission):
    """Resolve membership on every request; never trust a client-supplied role."""
    def check(session: Session, organization_id: UUID, user_id: UUID) -> OrganizationMember:
        membership = get_membership_or_404(session, organization_id, user_id)
        if permission not in permissions_for_role(membership.role):
            raise PermissionDeniedError()
        return membership
    return check


Resource = TypeVar("Resource", bound=Base)


def get_tenant_resource_or_404(
    session: Session, model: type[Resource], resource_id: UUID, user_id: UUID,
) -> Resource:
    """Scope the lookup itself. Missing and inaccessible UUIDs have one response."""
    resource = session.scalar(
        select(model).join(
            OrganizationMember,
            OrganizationMember.organization_id == model.organization_id,
        ).where(model.id == resource_id, OrganizationMember.user_id == user_id)
    )
    if resource is None:
        raise ResourceNotFoundError()
    return resource


def get_membership_or_404(
    session: Session, organization_id: UUID, user_id: UUID
) -> OrganizationMember:
    membership = session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if membership is None:
        # Returning 404 avoids revealing the existence of another tenant's organization.
        raise ResourceNotFoundError(
            "Organization not found",
            code="ORGANIZATION_NOT_FOUND",
        )
    return membership


# Compatibility names delegate to the same policy as the API routes.
require_member_manager = require_permission(Permission.MEMBER_MANAGE)
require_owner = require_permission(Permission.API_KEY_MANAGE)
require_incident_operator = require_permission(Permission.INCIDENT_ACKNOWLEDGE)


def can_manage_role(actor_role: OrganizationRole, target_role: OrganizationRole) -> bool:
    if target_role == OrganizationRole.OWNER:
        return False
    if actor_role == OrganizationRole.OWNER:
        return True
    return actor_role == OrganizationRole.ADMIN and target_role in {
        OrganizationRole.ENGINEER,
        OrganizationRole.VIEWER,
    }
