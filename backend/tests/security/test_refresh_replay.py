from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.modules.users.models import RefreshToken


def test_rotated_refresh_token_replay_revokes_the_token_family(
    security_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = security_client
    credentials = {
        "email": "refresh-security@example.com",
        "password": "correct-horse-battery-staple",
    }
    assert client.post(
        "/api/v1/auth/register",
        json={**credentials, "full_name": "Refresh Security"},
    ).status_code == 201
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 200

    cookie_name = get_settings().refresh_cookie_name
    old_token = client.cookies.get(cookie_name)
    assert client.post("/api/v1/auth/refresh").status_code == 200
    client.cookies.clear()
    client.cookies.set(cookie_name, old_token, path="/api/v1/auth")

    replay = client.post("/api/v1/auth/refresh")

    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "INVALID_OR_EXPIRED_REFRESH_TOKEN"
    with session_factory() as session:
        assert not session.scalars(
            select(RefreshToken).where(RefreshToken.revoked_at.is_(None))
        ).all()
