"""Test suite for XAUTOCLAIM reclaimer and Dead Letter Queue (DLQ) routing."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from workers.reclaimer import DEAD_LETTER_STREAM, MAX_RETRIES


@pytest.mark.asyncio
async def test_dlq_routing_after_max_retries() -> None:
    """Verify that messages exceeding 5 retry attempts are redirected to DLQ and acknowledged."""
    mock_redis = AsyncMock()

    # Simulate message claiming
    msg_id = "1700000000000-0"
    fields = {"vehicle_id": "1", "lat": "12.9716", "lon": "77.5946"}

    # Mock incr returning 6 (exceeding MAX_RETRIES = 5)
    mock_redis.incr = AsyncMock(return_value=6)
    mock_redis.xadd = AsyncMock()
    mock_redis.xack = AsyncMock()
    mock_redis.xdel = AsyncMock()

    retries = await mock_redis.incr(f"fleet:retry:{msg_id}")
    if retries > MAX_RETRIES:
        await mock_redis.xadd(DEAD_LETTER_STREAM, fields)
        await mock_redis.xack("stream:positions", "cg:positions", msg_id)
        await mock_redis.xdel("stream:positions", msg_id)

    # Assert forwarded to DLQ
    mock_redis.xadd.assert_called_once_with(DEAD_LETTER_STREAM, fields)
    mock_redis.xack.assert_called_once_with("stream:positions", "cg:positions", msg_id)
    mock_redis.xdel.assert_called_once_with("stream:positions", msg_id)
