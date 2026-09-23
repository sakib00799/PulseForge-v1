from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.security import hash_password_reset_token
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.modules.audit_logs.models import AuditLog
from app.modules.organizations.models import Organization, OrganizationMember
from app.modules.users.models import PasswordResetToken, RefreshToken, User

TEST_PASSWORD = "correct-horse-battery-staple"
NEW_PASSWORD = "new-correct-horse-battery-staple"


@pytest.fixture
def auth_client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
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
            RefreshToken.__table__,
            PasswordResetToken.__table__,
            AuditLog.__table__,
        ],
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session() -> Generator[Session, None, None]:
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as client:
        yield client, testing_session
    app.dependency_overrides.pop(get_db_session, None)
    engine.dispose()


def register_user(client: TestClient) -> str:
    email = f"auth-{uuid4().hex}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": TEST_PASSWORD, "full_name": "Auth Test"},
    )
    assert response.status_code == 201
    return email


def login_user(client: TestClient, email: str, password: str = TEST_PASSWORD) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    assert "refresh_token" not in response.json()
    return response.json()["access_token"]


def bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_login_sets_http_only_refresh_cookie(
    auth_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_client
    email = register_user(client)

    access_token = login_user(client, email)
    cookie = client.cookies.get(get_settings().refresh_cookie_name)
    set_cookie = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
    ).headers["set-cookie"]

    assert access_token
    assert cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie


def test_wrong_password_and_expired_access_token_are_rejected(
    auth_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_client
    email = register_user(client)
    wrong_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    settings = get_settings()
    expired_token = jwt.encode(
        {
            "sub": str(uuid4()),
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    assert wrong_login.status_code == 401
    assert wrong_login.json()["error"]["code"] == "INVALID_CREDENTIALS"
    expired_response = client.get("/api/v1/auth/me", headers=bearer(expired_token))
    assert expired_response.status_code == 401
    assert expired_response.json()["error"]["code"] == "INVALID_OR_EXPIRED_ACCESS_TOKEN"


def test_refresh_rotates_cookie_and_replay_revokes_sessions(
    auth_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = auth_client
    email = register_user(client)
    old_access_token = login_user(client, email)
    cookie_name = get_settings().refresh_cookie_name
    old_refresh_token = client.cookies.get(cookie_name)

    refresh_response = client.post("/api/v1/auth/refresh")
    new_refresh_token = client.cookies.get(cookie_name)

    assert refresh_response.status_code == 200
    assert old_refresh_token != new_refresh_token
    assert client.get("/api/v1/auth/me", headers=bearer(old_access_token)).status_code == 401
    assert client.get(
        "/api/v1/auth/me", headers=bearer(refresh_response.json()["access_token"])
    ).status_code == 200
    client.cookies.clear()
    client.cookies.set(cookie_name, old_refresh_token, path="/api/v1/auth")
    replay_response = client.post("/api/v1/auth/refresh")
    assert replay_response.status_code == 401

    with testing_session() as session:
        active_count = len(
            session.scalars(select(RefreshToken).where(RefreshToken.revoked_at.is_(None))).all()
        )
    assert active_count == 0


def test_logout_revokes_cookie_session(
    auth_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_client
    email = register_user(client)
    access_token = login_user(client, email)

    logout_response = client.post("/api/v1/auth/logout")

    assert logout_response.status_code == 204
    assert client.cookies.get(get_settings().refresh_cookie_name) is None
    assert client.post("/api/v1/auth/refresh").status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(access_token)).status_code == 401


def test_sessions_can_be_listed_and_revoked(
    auth_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_client
    email = register_user(client)
    access_token = login_user(client, email)

    sessions = client.get("/api/v1/auth/sessions", headers=bearer(access_token))
    assert sessions.status_code == 200
    assert len(sessions.json()) == 1

    session_id = sessions.json()[0]["id"]
    revoked = client.delete(
        f"/api/v1/auth/sessions/{session_id}",
        headers=bearer(access_token),
    )
    assert revoked.status_code == 204
    assert client.post("/api/v1/auth/refresh").status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(access_token)).status_code == 401


def test_logout_all_revokes_every_session(
    auth_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = auth_client
    email = register_user(client)
    login_user(client, email)
    access_token = login_user(client, email)

    response = client.post("/api/v1/auth/logout-all", headers=bearer(access_token))

    assert response.status_code == 204
    assert client.get("/api/v1/auth/me", headers=bearer(access_token)).status_code == 401
    with testing_session() as session:
        assert not session.scalars(
            select(RefreshToken).where(RefreshToken.revoked_at.is_(None))
        ).all()


def test_change_password_revokes_sessions_and_changes_credentials(
    auth_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_client
    email = register_user(client)
    access_token = login_user(client, email)

    response = client.post(
        "/api/v1/auth/change-password",
        headers=bearer(access_token),
        json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 204
    assert client.get("/api/v1/auth/me", headers=bearer(access_token)).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": NEW_PASSWORD},
    ).status_code == 200


def test_password_reset_is_single_use_and_revokes_sessions(
    auth_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = auth_client
    email = register_user(client)
    login_user(client, email)
    forgot = client.post("/api/v1/auth/forgot-password", json={"email": email})
    reset_token = forgot.json()["development_reset_token"]

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": NEW_PASSWORD},
    )

    assert forgot.status_code == 202
    assert reset.status_code == 204
    assert client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": TEST_PASSWORD},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": NEW_PASSWORD},
    ).status_code == 200


def test_expired_password_reset_token_is_rejected(
    auth_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = auth_client
    email = register_user(client)
    forgot = client.post("/api/v1/auth/forgot-password", json={"email": email})
    reset_token = forgot.json()["development_reset_token"]
    with testing_session() as session:
        stored_token = session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == hash_password_reset_token(reset_token)
            )
        )
        assert stored_token is not None
        stored_token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()

    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_OR_EXPIRED_PASSWORD_RESET_TOKEN"
