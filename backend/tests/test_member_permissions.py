import pytest

from app.modules.organizations.models import OrganizationRole
from app.modules.organizations.permissions import can_manage_role


@pytest.mark.parametrize(
    ("target_role", "expected"),
    [
        (OrganizationRole.OWNER, False),
        (OrganizationRole.ADMIN, True),
        (OrganizationRole.ENGINEER, True),
        (OrganizationRole.VIEWER, True),
    ],
)
def test_owner_role_management(target_role: OrganizationRole, expected: bool) -> None:
    assert can_manage_role(OrganizationRole.OWNER, target_role) is expected


@pytest.mark.parametrize(
    ("target_role", "expected"),
    [
        (OrganizationRole.OWNER, False),
        (OrganizationRole.ADMIN, False),
        (OrganizationRole.ENGINEER, True),
        (OrganizationRole.VIEWER, True),
    ],
)
def test_admin_role_management(target_role: OrganizationRole, expected: bool) -> None:
    assert can_manage_role(OrganizationRole.ADMIN, target_role) is expected
