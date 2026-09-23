import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import RateLimitError
from app.core.rate_limit import (
    EVENT_INGESTION_RATE_LIMIT,
    LOGIN_RATE_LIMIT,
    REFRESH_RATE_LIMIT,
    REGISTER_RATE_LIMIT,
    InMemoryRateLimiter,
)


@pytest.mark.parametrize(
    "policy",
    [
        LOGIN_RATE_LIMIT,
        REGISTER_RATE_LIMIT,
        REFRESH_RATE_LIMIT,
        EVENT_INGESTION_RATE_LIMIT,
    ],
)
def test_each_policy_rejects_after_its_limit(policy: object) -> None:
    now = 100.0
    limiter = InMemoryRateLimiter(clock=lambda: now)
    for _ in range(policy.limit):
        limiter.check("same-identity", policy)

    with pytest.raises(RateLimitError) as caught:
        limiter.check("same-identity", policy)
    assert caught.value.headers["Retry-After"] == str(policy.window_seconds)


def test_login_rate_limit_returns_429_header_and_standard_body(
    security_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = security_client
    payload = {"email": "limited@example.com", "password": "wrong-password"}
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json=payload).status_code == 401

    response = client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 429
    assert int(response.headers["retry-after"]) >= 1
    assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert response.json()["error"]["message"] == (
        "Too many requests. Please try again later."
    )
    assert response.json()["error"]["request_id"].startswith("req_")
