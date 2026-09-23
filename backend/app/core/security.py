import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, password_hash_value: str) -> bool:
    return password_hash.verify(password, password_hash_value)


def create_access_token(subject: str, session_id: str | None = None) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expires_at, "type": "access"}
    if session_id is not None:
        payload["sid"] = session_id
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def hash_refresh_token(token: str) -> str:
    """Create the irreversible value persisted in the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token() -> tuple[str, str, datetime]:
    """Return the raw token once, its database hash, and its expiry time."""
    settings = get_settings()
    raw_token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    return raw_token, hash_refresh_token(raw_token), expires_at


def hash_password_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_password_reset_token() -> tuple[str, str, datetime]:
    settings = get_settings()
    raw_token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_expire_minutes
    )
    return raw_token, hash_password_reset_token(raw_token), expires_at


def hash_api_key(api_key: str) -> str:
    """Create a deterministic keyed hash suitable for API-key lookup."""
    settings = get_settings()
    return hmac.new(
        settings.api_key_pepper.encode("utf-8"),
        api_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_api_key(*, production: bool) -> tuple[str, str, str]:
    """Return the raw key once, its display prefix, and its persisted hash."""
    environment_prefix = "pf_live_" if production else "pf_test_"
    raw_key = f"{environment_prefix}{secrets.token_urlsafe(32)}"
    display_prefix = raw_key[:16]
    return raw_key, display_prefix, hash_api_key(raw_key)
