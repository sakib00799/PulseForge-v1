from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DbSession
from app.core.permissions import permissions_for_role
from app.modules.audit_logs.service import AuditAction, record_audit_log
from app.modules.organizations.models import Organization, OrganizationMember, OrganizationRole
from app.modules.organizations.schemas import OrganizationCreate, OrganizationMembershipResponse, OrganizationResponse

router = APIRouter(prefix="/organizations")


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
) -> Organization:
    organization = Organization(name=payload.name.strip(), slug=payload.slug, created_by_id=current_user.id)
    organization.members.append(OrganizationMember(user_id=current_user.id, role=OrganizationRole.OWNER))
    session.add(organization)
    try:
        session.flush()
        record_audit_log(
            session,
            action=AuditAction.ORGANIZATION_CREATED,
            organization_id=organization.id,
            actor_user_id=current_user.id,
            resource_type="organization",
            resource_id=organization.id,
            request=request,
            metadata={"slug": organization.slug},
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organization slug is already in use") from error
    session.refresh(organization)
    return organization


@router.get("", response_model=list[OrganizationMembershipResponse])
def list_organizations(session: DbSession, current_user: CurrentUser) -> list[OrganizationMembershipResponse]:
    memberships = session.scalars(select(OrganizationMember).where(OrganizationMember.user_id == current_user.id).join(OrganizationMember.organization).order_by(Organization.created_at.desc())).all()
    return [OrganizationMembershipResponse(
        organization=item.organization, role=item.role,
        permissions=sorted(permissions_for_role(item.role)),
    ) for item in memberships]
