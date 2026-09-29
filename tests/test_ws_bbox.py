"""Test suite for WebSocket ConnectionManager and spatial bbox filtering."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.ws.manager import ConnectionManager


@pytest.mark.asyncio
async def test_bbox_spatial_filtering() -> None:
    """Verify subscriber receives positions within its bounding box and ignores outside points."""
    mgr = ConnectionManager()

    mock_ws = AsyncMock()
    mock_ws.send_json = AsyncMock()

    # Connect client
    await mgr.connect(mock_ws)

    # Subscribe to Bengaluru Central bbox [minLon, minLat, maxLon, maxLat]
    mgr.update_subscription(
        websocket=mock_ws,
        bbox=[77.55, 12.95, 77.65, 13.05],
        vehicle_ids=[],
    )

    # 1. Point INSIDE bbox (MG Road: 12.975, 77.609)
    inside_point = {
        "vehicle_id": 1,
        "lat": 12.9750,
        "lon": 77.6090,
        "speed_kmh": 40.0,
        "heading": 90,
    }
    await mgr.broadcast_position(inside_point)
    assert mock_ws.send_json.call_count == 1

    # 2. Point OUTSIDE bbox (Whitefield: 12.969, 77.749)
    mock_ws.send_json.reset_mock()
    outside_point = {
        "vehicle_id": 2,
        "lat": 12.9698,
        "lon": 77.7499,
        "speed_kmh": 50.0,
        "heading": 180,
    }
    await mgr.broadcast_position(outside_point)
    assert mock_ws.send_json.call_count == 0, "Out-of-bbox point must not be delivered"


@pytest.mark.asyncio
async def test_disconnect_cleanup() -> None:
    """Verify that abrupt client disconnection removes socket without leaking state."""
    mgr = ConnectionManager()
    mock_ws = AsyncMock()
    mock_ws.send_json = AsyncMock(side_effect=RuntimeError("Client closed socket"))

    await mgr.connect(mock_ws)
    assert mock_ws in mgr.active_connections

    # Broadcasting position when socket is closed triggers cleanup
    await mgr.broadcast_position({"vehicle_id": 1, "lat": 12.9, "lon": 77.6})
    assert mock_ws not in mgr.active_connections
