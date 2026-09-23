from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import create_access_token
from app.modules.organizations.models import Organization, OrganizationMember, OrganizationRole
from app.modules.services.models import Service, ServiceEnvironment
from app.modules.users.models import User


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def test_cross_tenant_resource_id_and_random_uuid_return_not_found(
    security_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = security_client
    with session_factory() as session:
        user_a = User(
            email="tenant-a@example.com",
            password_hash="unused",
            full_name="Tenant A",
        )
        user_b = User(
            email="tenant-b@example.com",
            password_hash="unused",
            full_name="Tenant B",
        )
        session.add_all([user_a, user_b])
        session.flush()
        organization_a = Organization(
            name="Tenant A",
            slug="tenant-a",
            created_by_id=user_a.id,
        )
        organization_b = Organization(
            name="Tenant B",
            slug="tenant-b",
            created_by_id=user_b.id,
        )
        session.add_all([organization_a, organization_b])
        session.flush()
        session.add_all(
            [
                OrganizationMember(
                    organization_id=organization_a.id,
                    user_id=user_a.id,
                    role=OrganizationRole.OWNER,
                ),
                OrganizationMember(
                    organization_id=organization_b.id,
                    user_id=user_b.id,
                    role=OrganizationRole.OWNER,
                ),
            ]
        )
        foreign_service = Service(
            organization_id=organization_b.id,
            name="Private Service",
            slug="private-service",
            environment=ServiceEnvironment.DEVELOPMENT,
        )
        session.add(foreign_service)
        session.commit()
        user_a_id = user_a.id
        foreign_service_id = foreign_service.id

    headers = {"Authorization": f"Bearer {create_access_token(str(user_a_id))}"}
    foreign = client.get(f"/api/v1/services/{foreign_service_id}", headers=headers)
    random = client.get(f"/api/v1/services/{uuid4()}", headers=headers)

    assert foreign.status_code == 404
    assert random.status_code == 404
    assert foreign.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
