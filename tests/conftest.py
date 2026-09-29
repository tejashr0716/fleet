"""Pytest configuration, async client fixtures, and test dependencies."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from app.main import app
from app.redis_client import get_redis_client


@pytest.fixture(scope="session")
def event_loop() -> AsyncGenerator[asyncio.AbstractEventLoop, None]:
    """Create session-scoped event loop for asyncio test execution."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis() -> Any:
    """Mock Redis client for offline unit and integration tests."""
    mock = AsyncMock(spec=Redis)
    mock.xadd = AsyncMock(return_value="1700000000000-0")
    mock.xlen = AsyncMock(return_value=5)
    mock.ping = AsyncMock(return_value=True)

    # Pipeline mock
    pipe_mock = AsyncMock()
    pipe_mock.xadd = MagicMock()
    pipe_mock.execute = AsyncMock(return_value=["1700000000000-0", "1700000000000-1"])
    pipe_mock.hset = MagicMock()
    pipe_mock.geoadd = MagicMock()
    pipe_mock.publish = MagicMock()
    pipe_mock.xack = MagicMock()
    pipe_mock.hget = MagicMock()
    pipe_mock.hgetall = MagicMock()

    mock.pipeline = MagicMock(return_value=pipe_mock)
    mock.scan_iter = MagicMock()
    return mock


@pytest.fixture
async def client(mock_redis: Any) -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous HTTP test client bound to ASGI FastAPI app."""
    # Override Redis dependency with mock to guarantee zero network failure during test suite

    app.dependency_overrides[get_redis_client] = lambda: mock_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
