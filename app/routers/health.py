"""Health router verifying DB, Redis connectivity and consumer stream lag."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db_session
from app.errors import ServiceUnavailableError
from app.redis_client import get_redis_client

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=dict[str, Any])
async def health_check(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> dict[str, Any]:
    """Perform health verification across database, Redis, and consumer stream backlog.

    Raises:
        ServiceUnavailableError: When Postgres/Redis is down or consumer backlog exceeds threshold.

    Returns:
        dict[str, Any]: System health status report.
    """
    # 1. Database check
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise ServiceUnavailableError("PostgreSQL unreachable", {"error": str(exc)}) from exc

    # 2. Redis check
    try:
        await redis.ping()
    except Exception as exc:
        raise ServiceUnavailableError("Redis unreachable", {"error": str(exc)}) from exc

    # 3. Stream lag check
    try:
        stream_len = await redis.xlen(settings.stream_name)
        if stream_len > settings.consumer_lag_unhealthy:
            raise ServiceUnavailableError(
                "Consumer lag exceeded threshold",
                {"stream_len": stream_len, "threshold": settings.consumer_lag_unhealthy},
            )
    except Exception as exc:
        if isinstance(exc, ServiceUnavailableError):
            raise
        stream_len = 0

    return {
        "status": "healthy",
        "database": "connected",
        "redis": "connected",
        "consumer_lag": stream_len,
    }
