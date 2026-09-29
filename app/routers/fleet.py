"""Fleet aggregation, last-known live state, and H3 heatmap router."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.redis_client import get_redis_client
from app.repositories.position_repo import PositionRepository
from app.services.live_state import LiveStateManager

router = APIRouter(tags=["Fleet"])


@router.get("/fleet/live")
async def get_fleet_live(
    redis: Annotated[Redis, Depends(get_redis_client)],
    min_lon: float | None = Query(default=None),
    min_lat: float | None = Query(default=None),
    max_lon: float | None = Query(default=None),
    max_lat: float | None = Query(default=None),
) -> list[dict[str, Any]]:
    """Retrieve last-known positions of all active vehicles, optionally bounded by bbox."""
    bbox = None
    if min_lon is not None and min_lat is not None and max_lon is not None and max_lat is not None:
        bbox = [min_lon, min_lat, max_lon, max_lat]
    return await LiveStateManager.get_all_live(redis, bbox=bbox)


@router.get("/fleet/stats")
async def get_fleet_stats(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Retrieve aggregate fleet statistics computed from the 1-minute continuous aggregate."""
    repo = PositionRepository(db)
    return await repo.get_fleet_stats()


@router.get("/h3/cells")
async def get_h3_cells(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    resolution: int = Query(default=8, ge=6, le=10),
) -> list[dict[str, Any]]:
    """Retrieve active H3 cell densities over the last 15 minutes for live heatmap rendering."""
    repo = PositionRepository(db)
    return await repo.get_h3_density(resolution=resolution)
