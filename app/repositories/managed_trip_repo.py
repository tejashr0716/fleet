import math
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError

from app.models import Alert, OutboxEvent, Position, Trip, Vehicle
from app.repositories.position_repo import position_dict
from app.repositories.vehicle_repo import get_vehicle
from app.schemas.trip import ManagedTripOut
from app.services.geofence import distance_m

MAX_ACTIVE = 3
STARTS_PER_HOUR = 12


def trip_dict(trip):
    return ManagedTripOut.model_validate(trip).model_dump(mode="json")


async def get_trip(session, trip_id):
    trip = await session.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(404, "Trip not found")
    return trip


async def create_trip(session, vehicle_id, body, settings):
    # Serializes capacity checks across concurrent start requests, not just Python tasks.
    await session.execute(text("SELECT pg_advisory_xact_lock(32732)"))
    vehicle = await session.scalar(
        select(Vehicle).where(Vehicle.id == vehicle_id).with_for_update()
    )
    if vehicle is None:
        raise HTTPException(404, "Register the vehicle before starting a trip")
    now = datetime.now(UTC)
    active = list((await session.scalars(select(Trip).where(Trip.status == "active"))).all())
    if any(t.vehicle_id == vehicle_id for t in active):
        raise HTTPException(409, "This vehicle already has an active trip")
    if len(active) >= MAX_ACTIVE:
        raise HTTPException(
            409, "Finish a trip first; at most three simulated trips can run together"
        )
    starts = await session.scalar(
        select(func.count()).select_from(Trip).where(Trip.started_at >= now - timedelta(hours=1))
    )
    if starts >= STARTS_PER_HOUR:
        raise HTTPException(
            429, "At most 12 simulated trip starts per hour", headers={"Retry-After": "3600"}
        )
    pending = await session.scalar(
        select(func.count()).select_from(OutboxEvent).where(OutboxEvent.delivered_at.is_(None))
    )
    if pending >= 5000:
        raise HTTPException(503, "Outbox backlog is too large; wait for Redis recovery")
    if settings.cloud_demo_enabled:
        observed = await session.scalar(
            select(func.count())
            .select_from(Position)
            .join(Vehicle)
            .where(or_(Position.trip_id.is_not(None), Vehicle.is_sample.is_(True)))
        )
        # Conservatively reserve a complete run for each active trip; never erase history for quota.
        reserved = sum(math.ceil(t.duration_seconds / 2) for t in active)
        if (
            observed + reserved + math.ceil(body.duration_seconds / 2)
            > settings.cloud_demo_position_budget
        ):
            raise HTTPException(
                409, "Temporary synthetic sample budget reached; use the local setup"
            )
    trip = Trip(
        vehicle_id=vehicle_id,
        started_at=now,
        expires_at=now + timedelta(seconds=body.duration_seconds),
        **body.model_dump(),
    )
    session.add(trip)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "This vehicle already has an active trip") from exc
    return trip


async def finish_trip(session, trip_id, status="completed", reason="manual"):
    trip = await get_trip(session, trip_id)
    # Same vehicle lock as ingestion: finish cannot race a committed sample past completion.
    await session.scalar(select(Vehicle).where(Vehicle.id == trip.vehicle_id).with_for_update())
    await session.refresh(trip)
    if trip.status == "active":
        trip.status, trip.end_reason, trip.ended_at = status, reason, datetime.now(UTC)
        await session.commit()
    return trip


async def list_trips(session, vehicle_id=None, limit=100):
    statement = select(Trip)
    if vehicle_id is not None:
        await get_vehicle(session, vehicle_id)
        statement = statement.where(Trip.vehicle_id == vehicle_id)
    rows = list(
        (
            await session.scalars(
                statement.order_by(Trip.started_at.desc(), Trip.id.desc()).limit(limit + 1)
            )
        ).all()
    )
    return {
        "trips": [trip_dict(t) for t in rows[:limit]],
        "has_more": len(rows) > limit,
        "source_used": "postgresql",
    }


def trace_summary(trip, points, total_points, maximum_speed, total_alerts):
    complete_trace = len(points) == total_points
    return {
        "duration_seconds": round(
            max(0, ((trip.ended_at or datetime.now(UTC)) - trip.started_at).total_seconds()), 1
        ),
        "point_count": total_points,
        "displayed_point_count": len(points),
        "distance_km": round(
            sum(
                distance_m(a.lat, a.lon, b.lat, b.lon)
                for a, b in zip(points, points[1:], strict=False)
            )
            / 1000,
            3,
        )
        if complete_trace and points
        else None,
        "max_speed_kmh": round(maximum_speed, 1) if maximum_speed is not None else None,
        "alert_count": total_alerts,
        "distance_definition": "Straight-line sum between stored synthetic observations, not road distance",
    }


async def detail(session, trip_id):
    trip = await get_trip(session, trip_id)
    points = list(
        (
            await session.scalars(
                select(Position)
                .where(Position.trip_id == trip_id)
                .order_by(Position.recorded_at, Position.id)
                .limit(5000)
            )
        ).all()
    )
    total, maximum = (
        await session.execute(
            select(func.count(Position.id), func.max(Position.speed_kmh)).where(
                Position.trip_id == trip_id
            )
        )
    ).one()
    alert_count = await session.scalar(
        select(func.count()).select_from(Alert).where(Alert.trip_id == trip_id)
    )
    alerts = list(
        (
            await session.scalars(
                select(Alert)
                .where(Alert.trip_id == trip_id)
                .order_by(Alert.recorded_at.desc(), Alert.id.desc())
                .limit(200)
            )
        ).all()
    )
    return {
        "trip": trip_dict(trip),
        "points": [position_dict(p) for p in points],
        "alerts": [
            {
                "id": a.id,
                "trip_id": a.trip_id,
                "vehicle_id": a.vehicle_id,
                "kind": a.kind,
                "recorded_at": a.recorded_at.isoformat(),
                "details": a.details,
            }
            for a in alerts
        ],
        "summary": trace_summary(trip, points, total, maximum, alert_count),
        "has_more_points": total > len(points),
        "has_more_alerts": alert_count > len(alerts),
        "source_used": "postgresql",
        "sample_data": True,
    }
