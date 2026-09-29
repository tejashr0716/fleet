"""Single pooled Redis client with typed dependency injection."""

from __future__ import annotations

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config import settings

_redis_pool: Redis | None = None


def get_redis_client() -> Redis:
    """Return the global Redis client singleton instance.

    Returns:
        Redis: Active asynchronous Redis connection client.
    """
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )
    return _redis_pool


async def close_redis() -> None:
    """Gracefully close the global Redis connection pool."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
