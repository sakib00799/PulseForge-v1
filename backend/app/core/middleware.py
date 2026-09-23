import re
from contextvars import ContextVar, Token
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
request_id_context: ContextVar[str] = ContextVar("request_id", default="unknown")


def generate_request_id() -> str:
    return f"req_{uuid4().hex}"


def validated_request_id(value: str | None) -> str:
    if value and REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return generate_request_id()


def get_request_id() -> str:
    return request_id_context.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = validated_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        token: Token[str] = request_id_context.set(request_id)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            request_id_context.reset(token)
