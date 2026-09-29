"""Test suite for position_consumer worker processing and idempotency."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.geofence import Geofence, GeofenceKind
from workers.position_consumer import BatchResult, process_batch


@pytest.mark.asyncio
async def test_worker_process_batch_flow() -> None:
    """Verify process_batch parses records, invokes DB commit, and issues XACK."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add_all = MagicMock()

    mock_redis = AsyncMock()
    pipe_mock = AsyncMock()
    pipe_mock.execute = AsyncMock(return_value=["1001", "1002"])
    pipe_mock.hget = MagicMock()
    pipe_mock.hset = MagicMock()
    pipe_mock.geoadd = MagicMock()
    pipe_mock.publish = MagicMock()
    pipe_mock.xack = MagicMock()
    mock_redis.pipeline = MagicMock(return_value=pipe_mock)

    test_messages = [
        (
            "1700000000000-0",
            {
                "vehicle_id": "1",
                "lat": "12.9716",
                "lon": "77.5946",
                "speed_kmh": "45.0",
                "heading": "180",
                "accuracy_m": "4.5",
                "time": datetime.now(tz=UTC).isoformat(),
            },
        ),
        (
            "1700000000000-1",
            {
                "vehicle_id": "2",
                "lat": "12.9350",
                "lon": "77.6250",
                "speed_kmh": "55.0",
                "heading": "90",
                "accuracy_m": "3.5",
                "time": datetime.now(tz=UTC).isoformat(),
            },
        ),
    ]

    geofence_cache: list[Geofence] = [
        Geofence(
            id=1,
            name="Zone A",
            kind=GeofenceKind.POLYGON,
            geojson={},
            h3_resolution=8,
            h3_cells=[1001, 1002],
        )
    ]

    result: BatchResult = await process_batch(
        messages=test_messages,
        session=mock_session,
        redis=mock_redis,
        geofence_cache=geofence_cache,
    )

    assert result.processed_count == 2
    assert mock_session.commit.call_count == 1
    # Verify XACK was called for both message IDs
    pipe_mock.xack.assert_called_once()
