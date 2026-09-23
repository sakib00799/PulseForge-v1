from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.modules.audit_logs.models import AuditLog
from app.modules.audit_logs.service import AuditAction, record_audit_log
from app.modules.organizations.models import Organization, OrganizationMember, OrganizationRole
from app.modules.users.models import User


@pytest.fixture
def audit_client() -> Generator[tuple[TestClient, sessionmaker[Session], dict[str, object]], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Organization.__table__,
            OrganizationMember.__table__,
            AuditLog.__table__,
        ],
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    with testing_session() as session:
        users = {
            role: User(
                email=f"{role.lower()}-{uuid4().hex}@example.com",
                password_hash="unused",
                full_name=role.title(),
            )
            for role in ("OWNER", "ADMIN", "ENGINEER", "OUTSIDER")
        }
        session.add_all(users.values())
        session.flush()
        organization = Organization(
            name="Audit Org",
            slug=f"audit-{uuid4().hex}",
            created_by_id=users["OWNER"].id,
        )
        session.add(organization)
        session.flush()
        session.add_all(
            [
                OrganizationMember(
                    organization_id=organization.id,
                    user_id=users[role].id,
                    role=OrganizationRole(role),
                )
                for role in ("OWNER", "ADMIN", "ENGINEER")
            ]
        )
        record_audit_log(
            session,
            action=AuditAction.SERVICE_CREATED,
            organization_id=organization.id,
            actor_user_id=users["OWNER"].id,
            resource_type="service",
            resource_id=uuid4(),
            metadata={
                "slug": "payments",
                "password": "must-not-be-stored",
                "nested": {"access_token": "must-not-be-stored", "safe": True},
            },
        )
        session.commit()
        context: dict[str, object] = {"organization": organization, **users}

    def override_session() -> Generator[Session, None, None]:
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as client:
        yield client, testing_session, context
    app.dependency_overrides.pop(get_db_session, None)
    engine.dispose()


def authorization(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest.mark.parametrize("role", ["OWNER", "ADMIN"])
def test_owner_and_admin_can_read_sanitized_audit_logs(
    audit_client: tuple[TestClient, sessionmaker[Session], dict[str, object]],
    role: str,
) -> None:
    client, _, context = audit_client
    organization = context["organization"]
    user = context[role]

    response = client.get(
        "/api/v1/audit-logs",
        params={"organization_id": str(organization.id)},
        headers=authorization(user),
    )

    assert response.status_code == 200
    metadata = response.json()[0]["metadata"]
    assert metadata == {"slug": "payments", "nested": {"safe": True}}
    assert "must-not-be-stored" not in response.text


def test_engineer_cannot_read_audit_logs(
    audit_client: tuple[TestClient, sessionmaker[Session], dict[str, object]],
) -> None:
    client, _, context = audit_client
    response = client.get(
        "/api/v1/audit-logs",
        params={"organization_id": str(context["organization"].id)},
        headers=authorization(context["ENGINEER"]),
    )
    assert response.status_code == 403


def test_outsider_receives_not_found_to_avoid_tenant_leak(
    audit_client: tuple[TestClient, sessionmaker[Session], dict[str, object]],
) -> None:
    client, _, context = audit_client
    response = client.get(
        "/api/v1/audit-logs",
        params={"organization_id": str(context["organization"].id)},
        headers=authorization(context["OUTSIDER"]),
    )
    assert response.status_code == 404
