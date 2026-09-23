from uuid import UUID

from app.core.permissions import Permission

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.modules.audit_logs.service import AuditAction, record_audit_log
from app.modules.organizations.models import OrganizationMember, OrganizationRole
from app.modules.organizations.permissions import (
    can_manage_role, require_permission, get_tenant_resource_or_404,
)
from app.modules.organizations.schemas import MemberAdd, MemberResponse, MemberRoleUpdate
from app.modules.users.models import User

router = APIRouter(prefix="/organizations/{organization_id}/members")


def to_member_response(membership: OrganizationMember) -> MemberResponse:
    return MemberResponse(
        id=membership.id,
        user_id=membership.user_id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
        joined_at=membership.joined_at,
    )


def get_target_member(
    session: DbSession, organization_id: UUID, member_id: UUID
) -> OrganizationMember:
    membership = session.scalar(
        select(OrganizationMember)
        .options(selectinload(OrganizationMember.user))
        .where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.id == member_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return membership


@router.get("", response_model=list[MemberResponse])
def list_members(
    organization_id: UUID, session: DbSession, current_user: CurrentUser
) -> list[MemberResponse]:
    require_permission(Permission.MEMBER_READ)(session, organization_id, current_user.id)
    memberships = session.scalars(
        select(OrganizationMember)
        .options(selectinload(OrganizationMember.user))
        .where(OrganizationMember.organization_id == organization_id)
        .order_by(OrganizationMember.joined_at.asc())
    ).all()
    return [to_member_response(membership) for membership in memberships]


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    organization_id: UUID,
    payload: MemberAdd,
    session: DbSession,
    current_user: CurrentUser,
) -> MemberResponse:
    actor = require_permission(Permission.MEMBER_MANAGE)(session, organization_id, current_user.id)
    if payload.role == OrganizationRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ownership transfer is not supported by this endpoint",
        )
    if not can_manage_role(actor.role, payload.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins can assign only engineer or viewer roles",
        )

    user = session.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active registered user found with this email",
        )

    existing = session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already an organization member",
        )

    membership = OrganizationMember(
        organization_id=organization_id,
        user_id=user.id,
        role=payload.role,
        user=user,
    )
    session.add(membership)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already an organization member",
        ) from error
    session.refresh(membership)
    return to_member_response(membership)


@router.patch("/{member_id}", response_model=MemberResponse)
def update_member_role(
    organization_id: UUID,
    member_id: UUID,
    payload: MemberRoleUpdate,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
) -> MemberResponse:
    actor = require_permission(Permission.MEMBER_MANAGE)(session, organization_id, current_user.id)
    target = get_target_member(session, organization_id, member_id)

    if payload.role == OrganizationRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ownership transfer is not supported by this endpoint",
        )
    if not can_manage_role(actor.role, target.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot change this member's role",
        )
    if not can_manage_role(actor.role, payload.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot assign this role",
        )

    previous_role = target.role
    target.role = payload.role
    record_audit_log(
        session,
        action=AuditAction.MEMBER_ROLE_CHANGED,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        resource_type="organization_member",
        resource_id=target.id,
        request=request,
        metadata={
            "target_user_id": target.user_id,
            "previous_role": previous_role.value,
            "new_role": payload.role.value,
        },
    )
    session.commit()
    session.refresh(target)
    return to_member_response(target)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    organization_id: UUID,
    member_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> Response:
    actor = require_permission(Permission.MEMBER_MANAGE)(session, organization_id, current_user.id)
    target = get_target_member(session, organization_id, member_id)

    if target.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot remove your own membership",
        )
    if not can_manage_role(actor.role, target.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot remove this member",
        )

    session.delete(target)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
