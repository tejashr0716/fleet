"""Redis live state service maintaining current positions and spatial indices."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis


class LiveStateManager:
    """Manages Redis Hashes for last-known vehicle positions and Geospatial indices."""

    @staticmethod
    async def update_state(
        redis: Redis,
        vehicle_id: int,
        lat: float,
        lon: float,
        speed_kmh: float,
        heading: int,
        h3_r8: int,
        ts: datetime,
    ) -> None:
        """Persist last-known position in Redis Hashes and update GEOADD index.

        Args:
            redis: Redis async client.
            vehicle_id: Vehicle ID.
            lat: Current latitude.
            lon: Current longitude.
            speed_kmh: Current speed in km/h.
            heading: Compass heading degrees.
            h3_r8: H3 resolution 8 cell identifier.
            ts: Event timestamp.
        """
        key = f"fleet:live:{vehicle_id}"
        iso_ts = ts.isoformat()
        payload = {
            "vehicle_id": str(vehicle_id),
            "lat": str(lat),
            "lon": str(lon),
            "speed_kmh": str(speed_kmh),
            "heading": str(heading),
            "h3_r8": hex(h3_r8)[2:],
            "ts": iso_ts,
            "last_seen": str(datetime.now(tz=UTC).timestamp()),
        }
        pipe = redis.pipeline()
        pipe.hset(key, mapping=payload)
        pipe.geoadd("fleet:geo", (lon, lat, str(vehicle_id)))
        await pipe.execute()

    @staticmethod
    async def get_all_live(redis: Redis, bbox: list[float] | None = None) -> list[dict[str, Any]]:
        """Retrieve all currently active vehicle telemetry positions from Redis.

        Args:
            redis: Redis async client.
            bbox: Optional bounding box [minLon, minLat, maxLon, maxLat].

        Returns:
            list[dict[str, Any]]: Vehicle snapshots with position and status metadata.
        """
        keys = [k async for k in redis.scan_iter("fleet:live:*")]
        if not keys:
            return []

        pipe = redis.pipeline()
        for k in keys:
            pipe.hgetall(k)
        results = await pipe.execute()

        vehicles: list[dict[str, Any]] = []
        for r in results:
            if not r or "vehicle_id" not in r:
                continue
            lat = float(r["lat"])
            lon = float(r["lon"])

            if bbox and len(bbox) == 4:
                min_lon, min_lat, max_lon, max_lat = bbox
                if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                    continue

            vehicles.append(
                {
                    "vehicle_id": int(r["vehicle_id"]),
                    "lat": lat,
                    "lon": lon,
                    "speed_kmh": float(r["speed_kmh"]),
                    "heading": int(r["heading"]),
                    "h3_r8": r.get("h3_r8", ""),
                    "ts": r.get("ts", ""),
                }
            )
        return vehicles
