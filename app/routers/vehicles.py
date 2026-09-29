"""Vehicles router handling asset lookups, telemetry history, and trips."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.errors import NotFoundError
from app.repositories.position_repo import PositionRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.position import PositionHistoryFilter, PositionHistoryResponse
from app.schemas.trip import TripRead
from app.schemas.vehicle import VehicleFilters, VehicleRead

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get("", response_model=list[VehicleRead])
async def list_vehicles(
    filters: Annotated[VehicleFilters, Depends()],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[VehicleRead]:
    """Retrieve filtered and paginated list of vehicles."""
    repo = VehicleRepository(db)
    vehicles = await repo.list_vehicles(filters)
    return [VehicleRead.model_validate(v) for v in vehicles]


@router.get("/{vehicle_id}", response_model=VehicleRead)
async def get_vehicle(
    vehicle_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> VehicleRead:
    """Retrieve details for a single vehicle by ID."""
    repo = VehicleRepository(db)
    vehicle = await repo.get_by_id(vehicle_id)
    if not vehicle:
        raise NotFoundError("Vehicle", vehicle_id)
    return VehicleRead.model_validate(vehicle)


@router.get("/{vehicle_id}/positions", response_model=PositionHistoryResponse)
async def get_vehicle_positions(
    vehicle_id: int,
    filters: Annotated[PositionHistoryFilter, Depends()],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PositionHistoryResponse:
    """Retrieve historical positions using raw hypertable or continuous aggregates."""
    repo = PositionRepository(db)
    source, points = await repo.get_history(
        vehicle_id=vehicle_id,
        from_time=filters.from_time,
        to_time=filters.to_time,
        mode=filters.downsample,
    )
    return PositionHistoryResponse(source_used=source, points=points)


@router.get("/{vehicle_id}/trips", response_model=list[TripRead])
async def get_vehicle_trips(
    vehicle_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[TripRead]:
    """Retrieve recent completed trip intervals for a vehicle."""
    repo = TripRepository(db)
    trips = await repo.list_by_vehicle(vehicle_id)
    return [TripRead.model_validate(t) for t in trips]
