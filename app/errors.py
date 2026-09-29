"""Standard application exception types and single-envelope error serialization."""

from __future__ import annotations

import contextvars
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

# Context variable preserving the current request ID across async tasks for structured logging
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id_ctx", default="system"
)


class AppError(Exception):
    """Base application exception for standardized error envelopes."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    """Raised when a requested resource is absent in the database."""

    def __init__(self, resource: str, identifier: Any) -> None:
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} '{identifier}' was not found",
            status_code=404,
            details={"resource": resource, "identifier": str(identifier)},
        )


class ValidationError(AppError):
    """Raised when payload or filter validation criteria fail."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=422,
            details=details,
        )


class ServiceUnavailableError(AppError):
    """Raised when an infrastructure dependency is degraded or uncontactable."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="SERVICE_UNHEALTHY",
            message=message,
            status_code=503,
            details=details,
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Serialize AppError subclasses into the canonical single-envelope shape.

    Args:
        request: The incoming FastAPI request.
        exc: The raised AppError instance.

    Returns:
        JSONResponse: Standardized error envelope with appropriate status code.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )
