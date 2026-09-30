from fastapi import APIRouter, Depends, Query, Request

from app.repositories.position_repo import latest_rows, nearest_database, position_dict
from app.security import require_user
from app.services.live_state import nearest_cached

router = APIRouter(prefix="/fleet", tags=["Live fleet"], dependencies=[Depends(require_user)])


@router.get("/live")
async def snapshot(request: Request):
    async with request.app.state.db.sessions() as session:
        return {
            "positions": [position_dict(p) for p in await latest_rows(session)],
            "source_used": "postgresql",
            "live_ttl_seconds": request.app.state.settings.live_ttl_seconds,
        }


@router.get("/nearest")
async def nearest(
    request: Request,
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    limit: int = Query(5, ge=1, le=20),
):
    settings = request.app.state.settings
    cached = await nearest_cached(
        request.app.state.redis, lat, lon, limit, settings.live_ttl_seconds
    )
    if cached is not None:
        return {"positions": cached, "source_used": "redis_geo", "radius_m": 25000}
    async with request.app.state.db.sessions() as session:
        result = await nearest_database(session, lat, lon, limit, settings.live_ttl_seconds)
        return {"positions": result, "source_used": "postgresql_scan", "radius_m": 25000}
