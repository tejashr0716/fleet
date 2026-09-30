import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("fleet")


def response(request, status, code, message, details=None, headers=None):
    return JSONResponse(
        status_code=status,
        headers=headers,
        content={
            "error": {"code": code, "message": message, "details": details},
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )


def install_errors(app):
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        codes = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
            503: "UNAVAILABLE",
        }
        return response(
            request,
            exc.status_code,
            codes.get(exc.status_code, "REQUEST_ERROR"),
            str(exc.detail),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Never echo input values (a login body can contain a password).
        details = [
            {"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()
        ]
        return response(request, 422, "VALIDATION_ERROR", "Invalid request", details)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error("Database request failed: %s", type(exc).__name__)
        return response(request, 503, "DATABASE_UNAVAILABLE", "Database temporarily unavailable")

    @app.exception_handler(RedisError)
    async def redis_error(request: Request, exc: RedisError):
        return response(
            request, 503, "REDIS_UNAVAILABLE", "Realtime service temporarily unavailable"
        )
