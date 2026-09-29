"""Telemetry position ingest router streaming to Redis Streams."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from redis.asyncio import Redis

from app.config import settings
from app.redis_client import get_redis_client
from app.schemas.position import PositionBatchIngestSchema, PositionIngestSchema

router = APIRouter(prefix="/positions", tags=["Positions Ingest"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_single_position(
    payload: PositionIngestSchema,
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> dict[str, Any]:
    """Ingest a single telemetry event into Redis Streams.

    Enforces zero database queries in the HTTP path for microsecond ingress performance.
    """
    stream_payload = {
        "vehicle_id": str(payload.vehicle_id),
        "lat": str(payload.lat),
        "lon": str(payload.lon),
        "speed_kmh": str(payload.speed_kmh),
        "heading": str(payload.heading),
        "accuracy_m": str(payload.accuracy_m),
        "time": payload.time.isoformat(),
        "emitted_at": datetime.now(tz=UTC).isoformat(),
    }
    stream_id = await redis.xadd(settings.stream_name, stream_payload)
    return {"status": "accepted", "stream_id": stream_id}


@router.post("/batch", status_code=status.HTTP_202_ACCEPTED)
async def ingest_position_batch(
    payload: PositionBatchIngestSchema,
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> dict[str, Any]:
    """Ingest a batch of up to 500 telemetry points via a non-blocking Redis pipeline."""
    pipe = redis.pipeline()
    now_iso = datetime.now(tz=UTC).isoformat()

    for pos in payload.positions:
        stream_payload = {
            "vehicle_id": str(pos.vehicle_id),
            "lat": str(pos.lat),
            "lon": str(pos.lon),
            "speed_kmh": str(pos.speed_kmh),
            "heading": str(pos.heading),
            "accuracy_m": str(pos.accuracy_m),
            "time": pos.time.isoformat(),
            "emitted_at": now_iso,
        }
        pipe.xadd(settings.stream_name, stream_payload)

    stream_ids = await pipe.execute()
    return {"status": "accepted", "count": len(stream_ids), "stream_ids": stream_ids}
