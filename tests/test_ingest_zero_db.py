"""Verify architectural guarantee: Ingest path must execute zero DB queries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import event

from app.db import engine


@pytest.mark.asyncio
async def test_ingest_zero_database_queries(client: AsyncClient) -> None:
    """Verify that batch telemetry ingest executes zero SQL database queries."""
    query_count = 0

    def before_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        nonlocal query_count
        query_count += 1

    # Attach event listener to detect any database queries on the SQLAlchemy engine
    event.listen(engine.sync_engine, "before_cursor_execute", before_cursor_execute)

    payload = {
        "positions": [
            {
                "vehicle_id": 101,
                "lat": 12.9716,
                "lon": 77.5946,
                "speed_kmh": 50.0,
                "heading": 180,
                "accuracy_m": 5.0,
                "time": datetime.now(tz=UTC).isoformat(),
            },
            {
                "vehicle_id": 102,
                "lat": 12.9350,
                "lon": 77.6250,
                "speed_kmh": 40.0,
                "heading": 90,
                "accuracy_m": 4.0,
                "time": datetime.now(tz=UTC).isoformat(),
            },
        ]
    }

    try:
        response = await client.post("/api/v1/positions/batch", json=payload)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", before_cursor_execute)

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["count"] == 2
    assert query_count == 0, (
        f"Ingest path violated zero-DB architectural contract: executed {query_count} queries"
    )
