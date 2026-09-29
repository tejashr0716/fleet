"""Geofence management and event retrieval router."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.errors import NotFoundError
from app.models.geofence import Geofence
from app.repositories.geofence_repo import GeofenceRepository
from app.schemas.geofence import GeofenceCreate, GeofenceEventRead, GeofenceRead
from app.services.geofence import polyfill_geojson_to_h3

router = APIRouter(prefix="/geofences", tags=["Geofences"])


@router.get("", response_model=list[GeofenceRead])
async def list_geofences(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[GeofenceRead]:
    """List all registered geofences with pre-computed H3 cell sets."""
    repo = GeofenceRepository(db)
    fences = await repo.list_all()
    return [GeofenceRead.model_validate(f) for f in fences]


@router.post("", response_model=GeofenceRead, status_code=status.HTTP_201_CREATED)
async def create_geofence(
    payload: GeofenceCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GeofenceRead:
    """Create a new geofence, polyfilling its GeoJSON geometry into H3 cells upon creation."""
    cells = polyfill_geojson_to_h3(payload.geojson, resolution=payload.h3_resolution)
    fence = Geofence(
        name=payload.name,
        kind=payload.kind,
        geojson=payload.geojson,
        h3_resolution=payload.h3_resolution,
        h3_cells=cells,
    )
    repo = GeofenceRepository(db)
    created = await repo.create(fence)
    return GeofenceRead.model_validate(created)


@router.delete("/{geofence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_geofence(
    geofence_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete a geofence by ID."""
    repo = GeofenceRepository(db)
    fence = await repo.get_by_id(geofence_id)
    if not fence:
        raise NotFoundError("Geofence", geofence_id)
    await repo.delete(fence)


@router.get("/{geofence_id}/events", response_model=list[GeofenceEventRead])
async def get_geofence_events(
    geofence_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[GeofenceEventRead]:
    """Retrieve historical entry and exit events for a specific geofence."""
    repo = GeofenceRepository(db)
    events = await repo.get_events(geofence_id)
    return [GeofenceEventRead.model_validate(e) for e in events]
