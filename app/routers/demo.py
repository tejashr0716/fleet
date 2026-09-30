from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.models import OutboxEvent, Position, Vehicle
from app.security import require_user

router = APIRouter(tags=["Optional cloud demo"], dependencies=[Depends(require_user)])


class StartSample(BaseModel):
    duration_seconds: int = Field(default=300, ge=1, le=600, strict=True)


def enabled(request):
    if not request.app.state.settings.cloud_demo_enabled:
        raise HTTPException(404, "Cloud demo controls are disabled")
    return request.app.state.demo


@router.get("/demo/status")
async def status(request: Request):
    return enabled(request).status()


@router.post("/demo/start", status_code=202)
async def start(body: StartSample, request: Request):
    controller = enabled(request)
    worker = request.app.state.cloud_worker
    if worker is None or worker.done():
        raise HTTPException(503, "Cloud demo worker is unavailable")
    async with request.app.state.db.sessions() as session:
        observed = await session.scalar(
            select(func.count())
            .select_from(Position)
            .join(Vehicle, Position.vehicle_id == Vehicle.id)
            .where(Vehicle.registration.startswith("DEMO-"))
        )
        pending = await session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.delivered_at.is_(None))
        )
    if pending >= 5000:
        raise HTTPException(503, "Outbox backlog is too large; wait for Redis recovery")
    remaining = request.app.state.settings.cloud_demo_position_budget - observed
    return await controller.start(body.duration_seconds, remaining)


@router.post("/demo/stop")
async def stop(request: Request):
    return await enabled(request).stop()
