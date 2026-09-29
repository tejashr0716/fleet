"""Test suite for strict input validation, HTTP 422 errors, and timing headers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_invalid_telemetry_lat_rejection(client: AsyncClient) -> None:
    """Verify latitude outside [-90, 90] returns 422."""
    payload = {
        "positions": [
            {
                "vehicle_id": 1,
                "lat": 91.0,  # Invalid latitude
                "lon": 77.5946,
                "speed_kmh": 40.0,
                "heading": 180,
                "accuracy_m": 5.0,
                "time": datetime.now(tz=UTC).isoformat(),
            }
        ]
    }
    resp = await client.post("/api/v1/positions/batch", json=payload)
    assert resp.status_code == 422
    assert "X-Request-ID" in resp.headers
    assert "X-Response-Time-ms" in resp.headers


@pytest.mark.asyncio
async def test_invalid_speed_rejection(client: AsyncClient) -> None:
    """Verify speed > 300 km/h returns 422."""
    payload = {
        "positions": [
            {
                "vehicle_id": 1,
                "lat": 12.9716,
                "lon": 77.5946,
                "speed_kmh": 400.0,  # Invalid speed
                "heading": 180,
                "accuracy_m": 5.0,
                "time": datetime.now(tz=UTC).isoformat(),
            }
        ]
    }
    resp = await client.post("/api/v1/positions/batch", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_size_limit_rejection(client: AsyncClient) -> None:
    """Verify batch over 500 items returns 422."""
    payload = {
        "positions": [
            {
                "vehicle_id": i,
                "lat": 12.9716,
                "lon": 77.5946,
                "speed_kmh": 40.0,
                "heading": 180,
                "accuracy_m": 5.0,
                "time": datetime.now(tz=UTC).isoformat(),
            }
            for i in range(501)  # 501 exceeds 500 cap
        ]
    }
    resp = await client.post("/api/v1/positions/batch", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_date_range_inverted_rejection(client: AsyncClient) -> None:
    """Verify 'from' > 'to' returns 422."""
    now = datetime.now(tz=UTC)
    params = {
        "from": now.isoformat(),
        "to": (now.replace(year=now.year - 1)).isoformat(),  # Inverted range
    }
    resp = await client.get("/api/v1/vehicles/1/positions", params=params)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_request_headers_present(client: AsyncClient) -> None:
    """Verify X-Request-ID and X-Response-Time-ms are attached to all responses."""
    resp = await client.get("/static/index.html")
    assert "X-Request-ID" in resp.headers
    assert "X-Response-Time-ms" in resp.headers
