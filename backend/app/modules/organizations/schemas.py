from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.organizations.models import OrganizationRole
from app.core.permissions import Permission


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=80)


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    created_at: datetime


class OrganizationMembershipResponse(BaseModel):
    organization: OrganizationResponse
    role: OrganizationRole
    permissions: list[Permission] = Field(default_factory=list)


class MemberAdd(BaseModel):
    email: EmailStr
    role: OrganizationRole = OrganizationRole.ENGINEER


class MemberRoleUpdate(BaseModel):
    role: OrganizationRole


class MemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    email: EmailStr
    full_name: str
    role: OrganizationRole
    joined_at: datetime
