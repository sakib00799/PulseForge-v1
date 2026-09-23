from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_missing_access_token_uses_standard_error_contract(
    security_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = security_client
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["x-request-id"].startswith("req_")
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_expired_and_modified_jwt_are_rejected(
    security_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = security_client
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": str(uuid4()),
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    valid_shape = jwt.encode(
        {
            "sub": str(uuid4()),
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    modified = f"{valid_shape[:-1]}{'a' if valid_shape[-1] != 'a' else 'b'}"

    for token in (expired, modified):
        response = client.get("/api/v1/auth/me", headers=bearer(token))
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_OR_EXPIRED_ACCESS_TOKEN"
