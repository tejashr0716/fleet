"""WebSocket ConnectionManager tracking subscriber bbox filters and broadcasting events."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("fleet.ws")


class ConnectionManager:
    """Central registry of live WebSocket subscribers with Bounding Box filters."""

    def __init__(self) -> None:
        self.active_connections: dict[WebSocket, dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        """Register a newly accepted WebSocket connection.

        Args:
            websocket: Incoming WebSocket instance.
        """
        await websocket.accept()
        self.active_connections[websocket] = {
            "bbox": None,  # [minLon, minLat, maxLon, maxLat]
            "vehicle_ids": set(),
        }

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the registry.

        Args:
            websocket: Disconnected WebSocket.
        """
        self.active_connections.pop(websocket, None)

    def update_subscription(
        self,
        websocket: WebSocket,
        bbox: list[float] | None,
        vehicle_ids: list[int] | None,
    ) -> None:
        """Update the spatial bounding box or vehicle ID filter for a connection.

        Args:
            websocket: Target connection.
            bbox: Bounding box [minLon, minLat, maxLon, maxLat] or None.
            vehicle_ids: Specific vehicle IDs filter or None.
        """
        if websocket in self.active_connections:
            self.active_connections[websocket] = {
                "bbox": bbox,
                "vehicle_ids": set(vehicle_ids) if vehicle_ids else set(),
            }

    @staticmethod
    def is_in_bbox(lat: float, lon: float, bbox: list[float]) -> bool:
        """Check whether a coordinate falls inside a bounding box.

        Args:
            lat: Latitude.
            lon: Longitude.
            bbox: [minLon, minLat, maxLon, maxLat].

        Returns:
            bool: True if coordinate is within bbox boundaries.
        """
        min_lon, min_lat, max_lon, max_lat = bbox
        return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

    async def broadcast_position(self, event_data: dict[str, Any]) -> None:
        """Deliver live position event to eligible filtered subscribers.

        Args:
            event_data: Enriched vehicle telemetry record.
        """
        lat = event_data.get("lat")
        lon = event_data.get("lon")
        vehicle_id = event_data.get("vehicle_id")
        payload = {"type": "position", "data": event_data}

        dead_connections: list[WebSocket] = []

        for ws, sub in list(self.active_connections.items()):
            try:
                # 1. Filter by explicit vehicle ID if configured
                if sub["vehicle_ids"] and vehicle_id not in sub["vehicle_ids"]:
                    continue

                # 2. Filter by spatial bounding box if configured
                if (
                    sub["bbox"]
                    and lat is not None
                    and lon is not None
                    and not self.is_in_bbox(lat, lon, sub["bbox"])
                ):
                    continue

                await ws.send_json(payload)
            except Exception:
                dead_connections.append(ws)

        for ws in dead_connections:
            self.disconnect(ws)

    async def broadcast_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Deliver non-position events (alerts, geofence crossings) to all subscribers.

        Args:
            event_type: Event category (alert, geofence_event).
            data: Payload details.
        """
        payload = {"type": event_type, "data": data}
        dead_connections: list[WebSocket] = []

        for ws in list(self.active_connections.keys()):
            try:
                await ws.send_json(payload)
            except Exception:
                dead_connections.append(ws)

        for ws in dead_connections:
            self.disconnect(ws)


ws_manager = ConnectionManager()
