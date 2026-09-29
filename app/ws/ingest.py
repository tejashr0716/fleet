"""Streaming telemetry ingest endpoint over WebSockets."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.redis_client import get_redis_client
from app.schemas.position import PositionIngestSchema

router = APIRouter()


@router.websocket("/ingest")
async def ingest_websocket_endpoint(websocket: WebSocket) -> None:
    """Device and simulator streaming ingest endpoint over WebSockets.

    Validates incoming positions and appends them to Redis Streams without blocking on DB.
    """
    await websocket.accept()
    redis = get_redis_client()

    try:
        while True:
            data: dict[str, Any] = await websocket.receive_json()
            pos = PositionIngestSchema.model_validate(data)
            stream_payload = {
                "vehicle_id": str(pos.vehicle_id),
                "lat": str(pos.lat),
                "lon": str(pos.lon),
                "speed_kmh": str(pos.speed_kmh),
                "heading": str(pos.heading),
                "accuracy_m": str(pos.accuracy_m),
                "time": pos.time.isoformat(),
                "emitted_at": datetime.now(tz=UTC).isoformat(),
            }
            stream_id = await redis.xadd(settings.stream_name, stream_payload)
            await websocket.send_json({"status": "accepted", "stream_id": stream_id})
    except (WebSocketDisconnect, Exception):
        pass
