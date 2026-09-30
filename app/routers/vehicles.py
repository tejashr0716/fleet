from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.repositories import position_repo, trip_repo, vehicle_repo
from app.schemas.trip import TripOut
from app.schemas.vehicle import VehicleCreate, VehicleOut
from app.security import require_user

router = APIRouter(prefix="/vehicles", tags=["Vehicles"], dependencies=[Depends(require_user)])


@router.get("", response_model=list[VehicleOut])
async def list_vehicles(request: Request):
    async with request.app.state.db.sessions() as session:
        return await vehicle_repo.list_vehicles(session)


@router.post("", status_code=201, response_model=VehicleOut)
async def create_vehicle(body: VehicleCreate, request: Request):
    async with request.app.state.db.sessions() as session:
        return await vehicle_repo.create_vehicle(session, body)


@router.get("/{vehicle_id}", response_model=VehicleOut)
async def vehicle(vehicle_id: int, request: Request):
    async with request.app.state.db.sessions() as session:
        return await vehicle_repo.get_vehicle(session, vehicle_id)


def window(from_time, to_time):
    now = datetime.now(UTC)
    start, stop = from_time or now - timedelta(hours=1), to_time or now
    if start.tzinfo is None or stop.tzinfo is None:
        raise HTTPException(422, "History timestamps require a timezone")
    if stop < start or stop - start > timedelta(days=90):
        raise HTTPException(422, "Use a non-reversed history window of at most 90 days")
    return start, stop


@router.get("/{vehicle_id}/positions")
async def positions(
    vehicle_id: int,
    request: Request,
    from_time: datetime | None = Query(None, alias="from"),
    to_time: datetime | None = Query(None, alias="to"),
    limit: int = Query(200, ge=1, le=5000),
):
    start, stop = window(from_time, to_time)
    async with request.app.state.db.sessions() as session:
        await vehicle_repo.get_vehicle(session, vehicle_id)
        points, more = await position_repo.history(session, vehicle_id, start, stop, limit)
        return {
            "points": [position_repo.position_dict(p) for p in points],
            "has_more": more,
            "source_used": "postgresql",
            "window": {"from": start, "to": stop},
        }


@router.get("/{vehicle_id}/trips")
async def trips(
    vehicle_id: int,
    request: Request,
    from_time: datetime | None = Query(None, alias="from"),
    to_time: datetime | None = Query(None, alias="to"),
):
    start, stop = window(from_time, to_time)
    async with request.app.state.db.sessions() as session:
        await vehicle_repo.get_vehicle(session, vehicle_id)
        rows, truncated = await trip_repo.trace_sessions(session, vehicle_id, start, stop)
        return {
            "sessions": [TripOut.model_validate(p) for p in rows],
            "truncated": truncated,
            "definition": "Observed GPS sessions split by a 5-minute silence gap",
        }
