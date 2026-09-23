from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import create_access_token
from app.modules.organizations.models import Organization, OrganizationMember, OrganizationRole
from app.modules.users.models import User


def test_engineer_cannot_escalate_role_and_viewer_cannot_create_service(
    security_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = security_client
    with session_factory() as session:
        owner = User(email="rbac-owner@example.com", password_hash="x", full_name="Owner")
        engineer = User(
            email="rbac-engineer@example.com", password_hash="x", full_name="Engineer"
        )
        viewer = User(email="rbac-viewer@example.com", password_hash="x", full_name="Viewer")
        session.add_all([owner, engineer, viewer])
        session.flush()
        organization = Organization(
            name="RBAC Org",
            slug="rbac-org",
            created_by_id=owner.id,
        )
        session.add(organization)
        session.flush()
        owner_member = OrganizationMember(
            organization_id=organization.id,
            user_id=owner.id,
            role=OrganizationRole.OWNER,
        )
        engineer_member = OrganizationMember(
            organization_id=organization.id,
            user_id=engineer.id,
            role=OrganizationRole.ENGINEER,
        )
        viewer_member = OrganizationMember(
            organization_id=organization.id,
            user_id=viewer.id,
            role=OrganizationRole.VIEWER,
        )
        session.add_all([owner_member, engineer_member, viewer_member])
        session.commit()
        values = {
            "organization_id": organization.id,
            "owner_member_id": owner_member.id,
            "engineer_id": engineer.id,
            "viewer_id": viewer.id,
        }

    engineer_headers = {
        "Authorization": f"Bearer {create_access_token(str(values['engineer_id']))}"
    }
    escalation = client.patch(
        f"/api/v1/organizations/{values['organization_id']}/members/"
        f"{values['owner_member_id']}",
        headers=engineer_headers,
        json={"role": "ADMIN"},
    )
    viewer_headers = {
        "Authorization": f"Bearer {create_access_token(str(values['viewer_id']))}"
    }
    create_service = client.post(
        "/api/v1/services",
        headers=viewer_headers,
        json={
            "organization_id": str(values["organization_id"]),
            "name": "Forbidden Service",
            "slug": "forbidden-service",
            "environment": "development",
        },
    )

    assert escalation.status_code == 403
    assert create_service.status_code == 403
    assert escalation.json()["error"]["code"] == "PERMISSION_DENIED"
