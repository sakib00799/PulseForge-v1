import re

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
GENERATED_REQUEST_ID = re.compile(r"^req_[0-9a-f]{32}$")


def test_missing_authentication_has_standard_error_and_request_id() -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    request_id = response.headers["x-request-id"]
    assert GENERATED_REQUEST_ID.fullmatch(request_id)
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "AUTHENTICATION_REQUIRED",
            "message": "Authentication is required",
            "request_id": request_id,
            "details": None,
        }
    }


def test_safe_client_request_id_is_reused() -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "client-request_123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "client-request_123"


def test_invalid_client_request_id_is_replaced() -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "bad request\nvalue"})

    assert response.status_code == 200
    assert GENERATED_REQUEST_ID.fullmatch(response.headers["x-request-id"])


def test_validation_error_does_not_echo_sensitive_input() -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "do-not-echo-this-password"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["request_id"] == response.headers["x-request-id"]
    assert body["error"]["details"][0]["field"] == "body.email"
    assert "do-not-echo-this-password" not in response.text


def test_unknown_route_uses_standard_error_format() -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
