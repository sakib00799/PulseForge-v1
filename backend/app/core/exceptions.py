import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = dict(headers or {})


class AuthenticationError(AppError):
    def __init__(
        self,
        message: str = "Authentication is required",
        *,
        code: str = "AUTHENTICATION_REQUIRED",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=code,
            message=message,
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionDeniedError(AppError):
    def __init__(
        self,
        message: str = "You do not have permission to perform this action",
        *,
        code: str = "PERMISSION_DENIED",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code=code,
            message=message,
        )


class ResourceNotFoundError(AppError):
    def __init__(
        self,
        message: str = "The requested resource was not found",
        *,
        code: str = "RESOURCE_NOT_FOUND",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code=code,
            message=message,
        )


class ConflictError(AppError):
    def __init__(
        self,
        message: str = "The request conflicts with the current resource state",
        *,
        code: str = "RESOURCE_CONFLICT",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code=code,
            message=message,
        )


class RateLimitError(AppError):
    def __init__(
        self,
        retry_after: int,
        message: str = "Too many requests. Please try again later.",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMIT_EXCEEDED",
            message=message,
            details={"retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


HTTP_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "AUTHENTICATION_REQUIRED",
    403: "PERMISSION_DENIED",
    404: "RESOURCE_NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "RESOURCE_CONFLICT",
    413: "REQUEST_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    429: "RATE_LIMIT_EXCEEDED",
    503: "SERVICE_UNAVAILABLE",
}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        headers=dict(headers or {}),
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": _request_id(request),
                "details": details,
            }
        },
    )


async def app_error_handler(request: Request, error: AppError) -> JSONResponse:
    return error_response(
        request,
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        details=error.details,
        headers=error.headers,
    )


async def http_error_handler(
    request: Request, error: StarletteHTTPException
) -> JSONResponse:
    code = HTTP_ERROR_CODES.get(error.status_code, "HTTP_ERROR")
    message = error.detail if isinstance(error.detail, str) else "The request could not be completed"
    details = None if isinstance(error.detail, str) else error.detail
    return error_response(
        request,
        status_code=error.status_code,
        code=code,
        message=message,
        details=details,
        headers=error.headers,
    )


async def validation_error_handler(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(part) for part in issue["loc"]),
            "message": issue["msg"],
            "type": issue["type"],
        }
        for issue in error.errors()
    ]
    return error_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=details,
    )


async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
    logger.exception("Unhandled request error request_id=%s", _request_id(request), exc_info=error)
    return error_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
