"""User-started, bounded per-vehicle GPS simulation through the shared ingestion path."""

import asyncio
import json
import logging
import math
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Trip
from app.repositories.managed_trip_repo import create_trip, finish_trip, trip_dict
from app.repositories.position_repo import ingest
from app.schemas.position import PositionBatch
from app.services.geofence import distance_m
from simulator.run import route_point

logger = logging.getLogger("fleet.trips")
ROUTES = {
    key: route
    for key, route in zip(
        ["central", "east", "west"],
        json.loads((Path(__file__).resolve().parents[2] / "simulator/routes.json").read_text())[
            "routes"
        ],
        strict=True,
    )
}
ROUTE_NAMES = {
    "central": "Central Bengaluru loop",
    "east": "East Bengaluru loop",
    "west": "West Bengaluru loop",
}


def sample_for(trip, tick, recorded_at=None):
    # All coordinates and speeds here are test inputs, never physical GPS measurements.
    route = ROUTES[trip.route_key]
    pos, prior = route_point(route, tick * 4), route_point(route, (tick - 1) * 4)
    speed = min(75, distance_m(*prior, *pos) * 3.6 / 2)
    if trip.include_speeding and tick % 40 in [8, 9, 10]:
        speed = 92  # Deliberate speeding fixture; also documented in the UI.
    return {
        "vehicle_id": trip.vehicle_id,
        "trip_id": trip.id,
        "lat": pos[0],
        "lon": pos[1],
        "speed_kmh": round(speed, 1),
        "heading": math.degrees(math.atan2(pos[1] - prior[1], pos[0] - prior[0])) % 360,
        "recorded_at": (recorded_at or datetime.now(UTC)).isoformat(),
    }


class TripRunner:
    def __init__(self, db, settings, emitter=None):
        self.db, self.settings = db, settings
        self.tasks = {}
        self.lock = asyncio.Lock()
        self.interval = 2
        self.emitter = emitter or self.emit

    async def reconcile(self):
        # Tasks cannot survive a process restart. Keep the records, mark that fact honestly.
        async with self.db.sessions() as session:
            ids = list(
                (await session.scalars(select(Trip.id).where(Trip.status == "active"))).all()
            )
        for trip_id in ids:
            await self.close_record(trip_id, "interrupted", "server_restart")

    async def emit(self, trip, tick):
        body = PositionBatch(positions=[sample_for(trip, tick)])
        async with self.db.sessions() as session:
            return await ingest(session, body, self.settings.speed_limit_kmh)

    async def close_record(self, trip_id, status="completed", reason="manual"):
        async with self.db.sessions() as session:
            return await finish_trip(session, trip_id, status, reason)

    async def start(self, vehicle_id, body):
        async with self.lock:
            async with self.db.sessions() as session:
                trip = await create_trip(session, vehicle_id, body, self.settings)
            try:
                await self.emitter(trip, 0)
            except Exception as exc:
                await self.close_record(trip.id, "interrupted", "simulator_error")
                raise HTTPException(
                    503, "Could not start synthetic GPS; the trip was marked interrupted"
                ) from exc
            task = asyncio.create_task(self.run(trip))
            self.tasks[trip.id] = task
            return trip_dict(trip)

    async def run(self, trip):
        status, reason, cancelled = "completed", "time_limit", False
        tick = 1
        try:
            while (remaining := (trip.expires_at - datetime.now(UTC)).total_seconds()) > 0:
                await asyncio.sleep(min(self.interval, remaining))
                if datetime.now(UTC) >= trip.expires_at:
                    break
                await self.emitter(trip, tick)
                tick += 1
        except asyncio.CancelledError:
            cancelled = True
        except Exception as exc:
            status, reason = "interrupted", "simulator_error"
            logger.warning("Synthetic trip %s interrupted: %s", trip.id, type(exc).__name__)
        finally:
            if not cancelled:
                try:
                    await self.close_record(trip.id, status, reason)
                except Exception as exc:
                    logger.warning(
                        "Trip finalization deferred to startup recovery: %s", type(exc).__name__
                    )
            self.tasks.pop(trip.id, None)

    async def finish(self, trip_id):
        async with self.lock:
            task = self.tasks.get(trip_id)
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            return trip_dict(await self.close_record(trip_id))

    async def shutdown(self):
        async with self.lock:
            ids = list(self.tasks)
            tasks = list(self.tasks.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for trip_id in ids:
                try:
                    await self.close_record(trip_id, "interrupted", "service_shutdown")
                except Exception as exc:
                    logger.warning("Trip shutdown record unavailable: %s", type(exc).__name__)
