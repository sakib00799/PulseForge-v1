from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_api_key
from app.modules.api_keys.models import ApiKey
from app.modules.organizations.models import Organization
from app.modules.services.models import Service, ServiceEnvironment, ServiceStatus
from app.modules.users.models import User


def seed_key(session: Session, *, state: str) -> str:
    user = User(
        email=f"api-key-{state}-{uuid4().hex}@example.com",
        password_hash="unused",
        full_name="API Key Test",
    )
    session.add(user)
    session.flush()
    organization = Organization(
        name="API Key Org",
        slug=f"api-key-{state}-{uuid4().hex}",
        created_by_id=user.id,
    )
    session.add(organization)
    session.flush()
    service = Service(
        organization_id=organization.id,
        name="API Key Service",
        slug="api-key-service",
        environment=ServiceEnvironment.DEVELOPMENT,
        status=ServiceStatus.DISABLED if state == "disabled" else ServiceStatus.OPERATIONAL,
    )
    session.add(service)
    session.flush()
    raw_key = f"pf_test_{uuid4().hex}{uuid4().hex}"
    api_key = ApiKey(
        organization_id=organization.id,
        service_id=service.id,
        name="Security key",
        key_hash=hash_api_key(raw_key),
        prefix=raw_key[:16],
        scopes=[] if state == "wrong-scope" else ["events:write"],
        expires_at=(
            datetime.now(timezone.utc) - timedelta(minutes=1)
            if state == "expired"
            else None
        ),
        revoked_at=datetime.now(timezone.utc) if state == "revoked" else None,
    )
    session.add(api_key)
    session.commit()
    return raw_key


@pytest.mark.parametrize(
    ("state", "expected_status", "expected_code"),
    [
        ("revoked", 401, "INVALID_API_KEY"),
        ("expired", 401, "INVALID_API_KEY"),
        ("wrong-scope", 403, "API_KEY_SCOPE_REQUIRED"),
        ("disabled", 403, "SERVICE_DISABLED"),
    ],
)
def test_invalid_api_key_states_are_rejected(
    security_client: tuple[TestClient, sessionmaker[Session]],
    state: str,
    expected_status: int,
    expected_code: str,
) -> None:
    client, session_factory = security_client
    with session_factory() as session:
        raw_key = seed_key(session, state=state)

    response = client.post(
        "/api/v1/events",
        headers={"Authorization": f"Bearer {raw_key}"},
        json={
            "event_id": f"security-{state}",
            "event_type": "SECURITY_TEST",
            "level": "ERROR",
            "message": "This request must be rejected",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {},
        },
    )

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
