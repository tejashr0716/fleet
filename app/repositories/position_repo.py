from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import Geofence, OutboxEvent, Position, Vehicle
from app.services.alerts import evaluate_alerts
from app.services.geofence import distance_m


def position_dict(point):
    return {
        "id": point.id,
        "vehicle_id": point.vehicle_id,
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
    inserted = 0
    for value in sorted(batch.positions, key=lambda p: (p.vehicle_id, p.recorded_at)):
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
        alerts = evaluate_alerts(point, latest.get(point.vehicle_id), fences, speed_limit)
        session.add_all(alerts)
        session.add(OutboxEvent(payload={"type": "position", "data": position_dict(point)}))
        for alert in alerts:
            session.add(
                OutboxEvent(
                    payload={
                        "type": "alert",
                        "data": {
                            "vehicle_id": alert.vehicle_id,
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
