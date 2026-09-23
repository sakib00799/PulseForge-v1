from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import hash_api_key
from app.db.session import get_db_session
from app.modules.api_keys.models import ApiKey
from app.modules.services.models import ServiceStatus
from app.modules.users.models import RefreshToken, User

bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[Session, Depends(get_db_session)]


def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)], session: DbSession) -> User:
    if credentials is None:
        raise AuthenticationError()
    unauthorized = AuthenticationError(
        "Invalid or expired access token",
        code="INVALID_OR_EXPIRED_ACCESS_TOKEN",
    )
    settings = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise unauthorized
        user_id = UUID(payload["sub"])
        session_id = UUID(payload["sid"]) if payload.get("sid") else None
    except (jwt.PyJWTError, KeyError, ValueError) as error:
        raise unauthorized from error
    user = session.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise unauthorized
    if session_id is not None:
        refresh_session = session.scalar(
            select(RefreshToken).where(
                RefreshToken.id == session_id,
                RefreshToken.user_id == user_id,
            )
        )
        if (
            refresh_session is None
            or refresh_session.revoked_at is not None
            or is_expired(refresh_session.expires_at, datetime.now(timezone.utc))
        ):
            raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def is_expired(expires_at: datetime | None, now: datetime) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now


def get_ingestion_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: DbSession,
) -> ApiKey:
    unauthorized = AuthenticationError(
        "Invalid, expired, or revoked API key",
        code="INVALID_API_KEY",
    )
    if credentials is None or not credentials.credentials.startswith(("pf_live_", "pf_test_")):
        raise unauthorized

    api_key = session.scalar(
        select(ApiKey)
        .options(selectinload(ApiKey.service))
        .where(ApiKey.key_hash == hash_api_key(credentials.credentials))
    )
    now = datetime.now(timezone.utc)
    if (
        api_key is None
        or api_key.revoked_at is not None
        or is_expired(api_key.expires_at, now)
    ):
        raise unauthorized
    if api_key.service.status == ServiceStatus.DISABLED:
        raise PermissionDeniedError(
            "This service is disabled",
            code="SERVICE_DISABLED",
        )
    if "events:write" not in api_key.scopes:
        raise PermissionDeniedError(
            "API key requires the events:write scope",
            code="API_KEY_SCOPE_REQUIRED",
        )
    return api_key


IngestionApiKey = Annotated[ApiKey, Depends(get_ingestion_api_key)]
