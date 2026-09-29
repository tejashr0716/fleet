"""Browser WebSocket subscriber endpoint for live telemetry updates."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws.manager import ws_manager

router = APIRouter()


@router.websocket("/live")
async def live_websocket_endpoint(websocket: WebSocket) -> None:
    """Browser WebSocket subscriber endpoint.

    Accepts spatial subscriptions, sends periodic pings, and filters
    out clients exceeding thresholds or failing heartbeats.
    """
    await ws_manager.connect(websocket)
    last_received = datetime.now(tz=UTC).timestamp()

    async def heartbeat_monitor() -> None:
        try:
            while True:
                await asyncio.sleep(20)
                # Check for client timeout (> 60s silence)
                if datetime.now(tz=UTC).timestamp() - last_received > 60:
                    await websocket.close(code=1000, reason="Heartbeat timeout")
                    break
                await websocket.send_json({"type": "ping"})
        except (asyncio.CancelledError, Exception):
            pass

    heartbeat_task = asyncio.create_task(heartbeat_monitor())

    try:
        while True:
            message: dict[str, Any] = await websocket.receive_json()
            last_received = datetime.now(tz=UTC).timestamp()
            action = message.get("action")

            if action == "ping":
                await websocket.send_json({"type": "pong"})

            elif action == "subscribe":
                bbox = message.get("bbox")
                vehicle_ids = message.get("vehicle_ids", [])

                # Reject global bounding boxes spanning the entire world
                if (
                    bbox
                    and len(bbox) == 4
                    and bbox[0] <= -170
                    and bbox[2] >= 170
                    and bbox[1] <= -80
                    and bbox[3] >= 80
                    and not vehicle_ids
                ):
                    await websocket.close(
                        code=1008,
                        reason="Global bbox without vehicle filter rejected",
                    )
                    return

                if len(vehicle_ids) > 5000:
                    await websocket.close(
                        code=1008,
                        reason="Subscription exceeds 5000 vehicle cap",
                    )
                    return

                ws_manager.update_subscription(websocket, bbox, vehicle_ids)

            elif action == "unsubscribe":
                ws_manager.update_subscription(websocket, None, None)

    except (WebSocketDisconnect, Exception):
        pass
    finally:
        heartbeat_task.cancel()
        ws_manager.disconnect(websocket)
