from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.repositories import managed_trip_repo
from app.schemas.trip import ManagedTripOut, StartTrip
from app.security import require_user
from app.services.trip_runner import ROUTE_NAMES

router = APIRouter(tags=["Trips"], dependencies=[Depends(require_user)])


@router.get("/trip-routes")
async def routes():
    return {
        "routes": [{"key": key, "name": name} for key, name in ROUTE_NAMES.items()],
        "definition": "Illustrative synthetic routes, not a navigation or road-routing service",
    }


@router.get("/trips")
async def trips(
    request: Request,
    vehicle_id: int | None = Query(None, gt=0),
    limit: int = Query(100, ge=1, le=200),
):
    async with request.app.state.db.sessions() as session:
        return await managed_trip_repo.list_trips(session, vehicle_id, limit)


@router.post("/vehicles/{vehicle_id}/trips", status_code=201, response_model=ManagedTripOut)
async def start_trip(vehicle_id: int, body: StartTrip, request: Request):
    app = request.app
    if app.state.demo and app.state.demo.status()["running"]:
        raise HTTPException(409, "Stop the legacy fleet-wide GPS session before starting a trip")
    if app.state.settings.cloud_demo_enabled:
        worker = app.state.cloud_worker
        if worker is None or worker.done():
            raise HTTPException(503, "Cloud demo worker is unavailable")
    return await app.state.trips.start(vehicle_id, body)


@router.get("/vehicles/{vehicle_id}/trips")
async def vehicle_trips(vehicle_id: int, request: Request, limit: int = Query(25, ge=1, le=200)):
    async with request.app.state.db.sessions() as session:
        return await managed_trip_repo.list_trips(session, vehicle_id, limit)


@router.get("/trips/{trip_id}")
async def trip_detail(trip_id: int, request: Request):
    async with request.app.state.db.sessions() as session:
        return await managed_trip_repo.detail(session, trip_id)


@router.post("/trips/{trip_id}/finish", response_model=ManagedTripOut)
async def finish_trip(trip_id: int, request: Request):
    return await request.app.state.trips.finish(trip_id)
