import logging
import math
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, ExceptionHandler, Message, Receive, Scope, Send

from src.api.error_messages import (
    DEFAULT_FIELD_MESSAGE,
    ERROR_MESSAGES,
    FIELD_MESSAGES,
    RATE_LIMIT_WITH_WAIT,
)
from src.db.config import DatabaseUnavailableError

logger = logging.getLogger(__name__)

# Errors FastAPI or Starlette raise themselves, mapped to our error codes.
HTTP_STATUS_ERRORS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    429: "rate_limit_exceeded",
    503: "service_unavailable",
}
DATABASE_DOWN_ERRORS = (DatabaseUnavailableError, OperationalError, PoolTimeoutError)


class ErrorResponse(BaseModel):
    """Body of every error response (requirements-addendum CHK084)."""

    error: str
    message: str
    details: dict[str, Any] | None = None
    suggestion: str | None = None


class AppError(Exception):
    """Base for errors services raise on purpose; subclasses set the defaults."""

    status_code: ClassVar[int] = 400
    error: ClassVar[str] = "bad_request"
    message: str = ERROR_MESSAGES["bad_request"]

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Mapping[str, Any] | None = None,
        suggestion: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.message = message or type(self).message
        self.details = dict(details) if details else None
        self.suggestion = suggestion
        self.headers = dict(headers) if headers else None
        super().__init__(self.message)


class FieldValidationError(AppError):
    """One invalid input, in the same shape as request validation errors."""

    error = "validation_error"
    message = ERROR_MESSAGES["validation_error"]

    def __init__(self, field: str, field_message: str) -> None:
        super().__init__(
            details={"fields": [{"field": field, "message": field_message}]}
        )


class UnauthorizedError(AppError):
    status_code = 401
    error = "unauthorized"
    message = ERROR_MESSAGES["unauthorized"]


class ForbiddenError(AppError):
    status_code = 403
    error = "forbidden"
    message = ERROR_MESSAGES["forbidden"]


class NotFoundError(AppError):
    status_code = 404
    error = "not_found"
    message = ERROR_MESSAGES["not_found"]


class ConflictError(AppError):
    status_code = 409
    error = "conflict"
    message = ERROR_MESSAGES["conflict"]


class RateLimitError(AppError):
    status_code = 429
    error = "rate_limit_exceeded"
    message = ERROR_MESSAGES["rate_limit_exceeded"]

    def __init__(self, retry_after: int, message: str | None = None) -> None:
        minutes = max(1, math.ceil(retry_after / 60))
        super().__init__(
            message or RATE_LIMIT_WITH_WAIT.format(minutes=minutes),
            details={"retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


def error_response(
    status_code: int,
    error: str,
    message: str | None = None,
    *,
    details: Mapping[str, Any] | None = None,
    suggestion: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=error,
        message=message or ERROR_MESSAGES[error],
        details=dict(details) if details else None,
        suggestion=suggestion,
    )
    return JSONResponse(
        body.model_dump(exclude_none=True), status_code=status_code, headers=headers
    )


async def _app_error(_: Request, exc: AppError) -> JSONResponse:
    return error_response(
        exc.status_code,
        exc.error,
        exc.message,
        details=exc.details,
        suggestion=exc.suggestion,
        headers=exc.headers,
    )


async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
    default = "internal_error" if exc.status_code >= 500 else "bad_request"
    error = HTTP_STATUS_ERRORS.get(exc.status_code, default)
    # exc.detail is English framework text, so the Korean message replaces it.
    return error_response(exc.status_code, error, headers=exc.headers)


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Only field names and messages: the rejected input may be a password.
    fields = [_field_error(item) for item in exc.errors()]
    return error_response(400, "validation_error", details={"fields": fields})


def _field_error(item: Mapping[str, Any]) -> dict[str, str]:
    error_type = item["type"]
    if error_type == "value_error":
        # A custom validator's ValueError text is already written for users.
        message = str(item["ctx"]["error"])
    else:
        template = FIELD_MESSAGES.get(error_type, DEFAULT_FIELD_MESSAGE)
        message = template.format(**item.get("ctx", {}))
    return {"field": _field_name(item["loc"], error_type), "message": message}


def _field_name(loc: Sequence[str | int], error_type: str) -> str:
    if error_type == "json_invalid":
        return "body"
    # FastAPI puts the request location first: ("body", "email") -> "email".
    return ".".join(str(part) for part in loc[1:]) or str(loc[0])


async def _database_down(_: Request, exc: Exception) -> JSONResponse:
    logger.warning("Database unavailable: %s", type(exc).__name__)
    return error_response(503, "service_unavailable")


def register_exception_handlers(app: FastAPI) -> None:
    # Starlette only calls a handler for its own exception class, but types
    # every handler as taking Exception; cast keeps the narrow signatures.
    app.add_exception_handler(AppError, cast(ExceptionHandler, _app_error))
    app.add_exception_handler(HTTPException, cast(ExceptionHandler, _http_error))
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, _validation_error)
    )
    for error_class in DATABASE_DOWN_ERRORS:
        app.add_exception_handler(error_class, _database_down)


class UnhandledErrorMiddleware:
    """Turns unexpected exceptions into the shared 500 JSON body.

    Starlette's own 500 handler runs outside every middleware, so its
    responses miss CORS headers and the browser reports a CORS error instead.
    Add this as the innermost middleware so CORS and security headers apply.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            logger.exception("Unhandled error on %s %s", scope["method"], scope["path"])
            if response_started:
                # Headers already went out; let the server close the connection.
                raise
            await error_response(500, "internal_error")(scope, receive, send)
