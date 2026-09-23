from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import AppEnvironment, get_settings
from app.core.exceptions import AuthenticationError, ConflictError, ResourceNotFoundError
from app.core.rate_limit import (
    LOGIN_RATE_LIMIT,
    REFRESH_RATE_LIMIT,
    REGISTER_RATE_LIMIT,
    client_ip,
    private_rate_limit_key,
    rate_limiter,
)
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    hash_password,
    hash_password_reset_token,
    hash_refresh_token,
    verify_password,
)
from app.modules.audit_logs.service import AuditAction, record_audit_log
from app.modules.organizations.models import OrganizationMember
from app.modules.users.models import PasswordResetToken, RefreshToken, User
from app.modules.users.schemas import (
    AccessTokenResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    SessionResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

router = APIRouter(prefix="/auth")
REFRESH_COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def delete_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=REFRESH_COOKIE_PATH,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def request_metadata(request: Request) -> tuple[str | None, str | None]:
    ip_address = request.client.host[:45] if request.client and request.client.host else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent[:500] if user_agent else None


def issue_session(
    user: User,
    session: DbSession,
    request: Request,
    response: Response,
) -> AccessTokenResponse:
    raw_refresh_token, refresh_token_hash, expires_at = create_refresh_token()
    ip_address, user_agent = request_metadata(request)
    stored_token = RefreshToken(
        user_id=user.id,
        token_hash=refresh_token_hash,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(stored_token)
    session.flush()
    set_refresh_cookie(response, raw_refresh_token)
    return AccessTokenResponse(
        access_token=create_access_token(str(user.id), str(stored_token.id)),
    )


def invalid_refresh_token() -> AuthenticationError:
    return AuthenticationError(
        "Invalid or expired refresh token",
        code="INVALID_OR_EXPIRED_REFRESH_TOKEN",
    )


def revoke_user_sessions(session: DbSession, user_id: UUID, revoked_at: datetime) -> None:
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=revoked_at)
    )


def has_expired(expires_at: datetime, now: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now


def audit_password_change(
    session: DbSession,
    *,
    user_id: UUID,
    request: Request,
) -> None:
    organization_ids = list(
        session.scalars(
            select(OrganizationMember.organization_id).where(
                OrganizationMember.user_id == user_id
            )
        ).all()
    )
    for organization_id in organization_ids or [None]:
        record_audit_log(
            session,
            action=AuditAction.PASSWORD_CHANGED,
            organization_id=organization_id,
            actor_user_id=user_id,
            resource_type="user",
            resource_id=user_id,
            request=request,
        )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, request: Request, session: DbSession) -> User:
    rate_limiter.check(
        private_rate_limit_key("register", client_ip(request)),
        REGISTER_RATE_LIMIT,
    )
    user = User(
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError(
            "Email is already registered",
            code="EMAIL_ALREADY_REGISTERED",
        ) from error
    session.refresh(user)
    return user


@router.post("/login", response_model=AccessTokenResponse)
def login(
    payload: UserLogin,
    request: Request,
    response: Response,
    session: DbSession,
) -> AccessTokenResponse:
    rate_limiter.check(
        private_rate_limit_key(
            "login",
            client_ip(request),
            str(payload.email).lower(),
        ),
        LOGIN_RATE_LIMIT,
    )
    user = session.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        record_audit_log(
            session,
            action=AuditAction.LOGIN_FAILED,
            actor_user_id=None,
            resource_type="authentication",
            request=request,
            metadata={"reason": "invalid_credentials"},
        )
        session.commit()
        raise AuthenticationError(
            "Email or password is incorrect",
            code="INVALID_CREDENTIALS",
        )
    access_token = issue_session(user, session, request, response)
    session.commit()
    return access_token


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh_access_token(
    request: Request,
    response: Response,
    session: DbSession,
) -> AccessTokenResponse:
    settings = get_settings()
    raw_refresh_token = request.cookies.get(settings.refresh_cookie_name)
    rate_limiter.check(
        private_rate_limit_key(
            "refresh",
            hash_refresh_token(raw_refresh_token) if raw_refresh_token else client_ip(request),
        ),
        REFRESH_RATE_LIMIT,
    )
    if not raw_refresh_token:
        raise invalid_refresh_token()

    stored_token = session.scalar(
        select(RefreshToken)
        .options(selectinload(RefreshToken.user))
        .where(RefreshToken.token_hash == hash_refresh_token(raw_refresh_token))
        .with_for_update()
    )
    now = datetime.now(timezone.utc)
    if stored_token is None:
        session.rollback()
        raise invalid_refresh_token()
    if stored_token.revoked_at is not None:
        revoke_user_sessions(session, stored_token.user_id, now)
        session.commit()
        raise invalid_refresh_token()
    if has_expired(stored_token.expires_at, now) or not stored_token.user.is_active:
        stored_token.revoked_at = now
        session.commit()
        raise invalid_refresh_token()

    stored_token.last_used_at = now
    stored_token.revoked_at = now
    access_token = issue_session(stored_token.user, session, request, response)
    session.commit()
    return access_token


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, session: DbSession) -> Response:
    settings = get_settings()
    raw_refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if raw_refresh_token:
        stored_token = session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(raw_refresh_token))
            .with_for_update()
        )
        if stored_token is not None and stored_token.revoked_at is None:
            stored_token.revoked_at = datetime.now(timezone.utc)
            session.commit()
        else:
            session.rollback()
    delete_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    session: DbSession,
    current_user: CurrentUser,
) -> Response:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise AuthenticationError(
            "Current password is incorrect",
            code="CURRENT_PASSWORD_INCORRECT",
        )
    if verify_password(payload.new_password, current_user.password_hash):
        raise ConflictError(
            "New password must be different from the current password",
            code="PASSWORD_UNCHANGED",
        )
    now = datetime.now(timezone.utc)
    current_user.password_hash = hash_password(payload.new_password)
    revoke_user_sessions(session, current_user.id, now)
    audit_password_change(session, user_id=current_user.id, request=request)
    session.commit()
    delete_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_202_ACCEPTED,
)
def forgot_password(payload: ForgotPasswordRequest, session: DbSession) -> ForgotPasswordResponse:
    generic_message = "If an active account exists, password reset instructions have been created"
    user = session.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not user.is_active:
        return ForgotPasswordResponse(message=generic_message)

    now = datetime.now(timezone.utc)
    session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw_token, token_hash, expires_at = create_password_reset_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    session.commit()

    environment = get_settings().environment
    development_token = (
        raw_token
        if environment in {AppEnvironment.DEVELOPMENT, AppEnvironment.TEST}
        else None
    )
    return ForgotPasswordResponse(
        message=generic_message,
        development_reset_token=development_token,
    )


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    response: Response,
    session: DbSession,
) -> Response:
    stored_token = session.scalar(
        select(PasswordResetToken)
        .options(selectinload(PasswordResetToken.user))
        .where(PasswordResetToken.token_hash == hash_password_reset_token(payload.token))
        .with_for_update()
    )
    now = datetime.now(timezone.utc)
    if (
        stored_token is None
        or stored_token.used_at is not None
        or has_expired(stored_token.expires_at, now)
        or not stored_token.user.is_active
    ):
        session.rollback()
        raise AuthenticationError(
            "Invalid or expired password reset token",
            code="INVALID_OR_EXPIRED_PASSWORD_RESET_TOKEN",
        )

    stored_token.user.password_hash = hash_password(payload.new_password)
    stored_token.used_at = now
    revoke_user_sessions(session, stored_token.user_id, now)
    audit_password_change(session, user_id=stored_token.user_id, request=request)
    session.commit()
    delete_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    response: Response,
    session: DbSession,
    current_user: CurrentUser,
) -> Response:
    revoke_user_sessions(session, current_user.id, datetime.now(timezone.utc))
    session.commit()
    delete_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(session: DbSession, current_user: CurrentUser) -> list[RefreshToken]:
    now = datetime.now(timezone.utc)
    return list(
        session.scalars(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == current_user.id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
            .order_by(RefreshToken.created_at.desc())
        ).all()
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: UUID,
    response: Response,
    session: DbSession,
    current_user: CurrentUser,
) -> Response:
    stored_token = session.scalar(
        select(RefreshToken).where(
            RefreshToken.id == session_id,
            RefreshToken.user_id == current_user.id,
        )
    )
    if stored_token is None:
        raise ResourceNotFoundError(
            "Session not found",
            code="SESSION_NOT_FOUND",
        )
    if stored_token.revoked_at is None:
        stored_token.revoked_at = datetime.now(timezone.utc)
        session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
def get_me(current_user: CurrentUser) -> User:
    return current_user
