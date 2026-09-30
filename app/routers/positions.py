from fastapi import APIRouter, Depends, Request

from app.repositories.position_repo import ingest
from app.schemas.position import PositionBatch
from app.security import require_ingest

router = APIRouter(prefix="/positions", tags=["Telemetry"])


@router.post("/batch", status_code=202, dependencies=[Depends(require_ingest)])
async def batch(body: PositionBatch, request: Request):
    async with request.app.state.db.sessions() as session:
        return await ingest(session, body, request.app.state.settings.speed_limit_kmh)
