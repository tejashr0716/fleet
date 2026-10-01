from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import Geofence, OutboxEvent, Position, Trip, Vehicle
from app.services.alerts import evaluate_alerts
from app.services.geofence import distance_m


def position_dict(point):
    return {
        "id": point.id,
        "vehicle_id": point.vehicle_id,
        "trip_id": point.trip_id,
        "recorded_at": point.recorded_at.isoformat(),
        "lat": point.lat,
        "lon": point.lon,
        "speed_kmh": point.speed_kmh,
        "heading": point.heading,
    }


async def latest_rows(session):
    statement = (
        select(Position)
        .distinct(Position.vehicle_id)
        .order_by(Position.vehicle_id, Position.recorded_at.desc())
    )
    return list((await session.scalars(statement)).all())


async def ingest(session, batch, speed_limit):
    ids = sorted({p.vehicle_id for p in batch.positions})
    # Serialize batches touching the same vehicle so alert transitions are consistent.
    vehicles = list(
        (
            await session.scalars(
                select(Vehicle).where(Vehicle.id.in_(ids)).order_by(Vehicle.id).with_for_update()
            )
        ).all()
    )
    if {v.id for v in vehicles} != set(ids):
        raise HTTPException(422, "Every vehicle must be registered before ingestion")
    latest = {
        p.vehicle_id: p
        for p in (
            await session.scalars(
                select(Position)
                .where(Position.vehicle_id.in_(ids))
                .distinct(Position.vehicle_id)
                .order_by(Position.vehicle_id, Position.recorded_at.desc())
            )
        ).all()
    }
    fences = list((await session.scalars(select(Geofence))).all())
    trip_ids = {p.trip_id for p in batch.positions if p.trip_id is not None}
    trips = {
        t.id: t for t in (await session.scalars(select(Trip).where(Trip.id.in_(trip_ids)))).all()
    }
    active = {
        t.vehicle_id: t
        for t in (
            await session.scalars(
                select(Trip).where(Trip.vehicle_id.in_(ids), Trip.status == "active")
            )
        ).all()
    }
    inserted = 0
    for value in sorted(batch.positions, key=lambda p: (p.vehicle_id, p.recorded_at)):
        trip = trips.get(value.trip_id) if value.trip_id is not None else None
        if value.trip_id is not None and (trip is None or trip.vehicle_id != value.vehicle_id):
            raise HTTPException(422, "Trip must belong to the telemetry vehicle")
        if trip and value.recorded_at < trip.started_at:
            raise HTTPException(422, "Trip sample cannot precede its start")
        if trip and value.recorded_at > trip.expires_at:
            raise HTTPException(422, "Trip sample cannot exceed its scheduled end")
        closed_trip = trip is not None and trip.status != "active"
        untagged_active = trip is None and value.vehicle_id in active
        if closed_trip or untagged_active:
            # Exact historical retries remain first-write-wins even after a trip has finished.
            duplicate = await session.scalar(
                select(Position.id).where(
                    Position.vehicle_id == value.vehicle_id,
                    Position.recorded_at == value.recorded_at,
                )
            )
            if duplicate is not None:
                continue
            raise HTTPException(
                409,
                "Trip is finished"
                if closed_trip
                else "An active simulated trip requires its trip_id",
            )
        # Duplicate key means exact retries are harmless; different data at the same timestamp is first-write-wins.
        statement = (
            insert(Position)
            .values(**value.model_dump())
            .on_conflict_do_nothing(constraint="uq_vehicle_time")
            .returning(Position)
        )
        point = (await session.execute(statement)).scalar_one_or_none()
        if point is None:
            continue
        inserted += 1
        previous = latest.get(point.vehicle_id)
        if trip and (previous is None or previous.trip_id != trip.id):
            previous = None
        alerts = evaluate_alerts(point, previous, fences, speed_limit)
        for alert in alerts:
            alert.trip_id = point.trip_id
        session.add_all(alerts)
        session.add(OutboxEvent(payload={"type": "position", "data": position_dict(point)}))
        for alert in alerts:
            session.add(
                OutboxEvent(
                    payload={
                        "type": "alert",
                        "data": {
                            "vehicle_id": alert.vehicle_id,
                            "trip_id": alert.trip_id,
                            "kind": alert.kind,
                            "recorded_at": alert.recorded_at.isoformat(),
                            "details": alert.details,
                        },
                    }
                )
            )
        previous = latest.get(point.vehicle_id)
        if previous is None or point.recorded_at > previous.recorded_at:
            latest[point.vehicle_id] = point
    await session.commit()  # Both historical data and outbox event commit atomically.
    return {
        "received": len(batch.positions),
        "inserted": inserted,
        "duplicates": len(batch.positions) - inserted,
        "durability": "postgresql_committed",
        "realtime_delivery": "queued_in_outbox",
    }


async def history(session, vehicle_id, from_time, to_time, limit):
    statement = (
        select(Position)
        .where(
            Position.vehicle_id == vehicle_id,
            Position.recorded_at >= from_time,
            Position.recorded_at <= to_time,
        )
        .order_by(Position.recorded_at.desc())
        .limit(limit + 1)
    )
    result = list((await session.scalars(statement)).all())
    return list(reversed(result[:limit])), len(result) > limit


async def nearest_database(session, lat, lon, limit, ttl):
    now = datetime.now(UTC)
    rows = [
        dict(position_dict(p), distance_m=round(distance_m(lat, lon, p.lat, p.lon), 1))
        for p in await latest_rows(session)
        if (now - p.recorded_at).total_seconds() <= ttl
        and distance_m(lat, lon, p.lat, p.lon) <= 25000
    ]
    return sorted(rows, key=lambda p: p["distance_m"])[:limit]
