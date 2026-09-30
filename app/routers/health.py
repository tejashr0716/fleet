from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text

from app.models import OutboxEvent

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health(request: Request):
    database, redis, backlog = False, False, None
    try:
        async with request.app.state.db.sessions() as session:
            await session.execute(text("SELECT 1"))
            backlog = await session.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.delivered_at.is_(None))
            )
            database = True
    except Exception:
        pass
    try:
        redis = bool(await request.app.state.redis.ping())
    except Exception:
        pass
    demo_enabled = request.app.state.settings.cloud_demo_enabled
    worker = request.app.state.cloud_worker
    worker_running = worker is not None and not worker.done()
    healthy = database and redis and (not demo_enabled or worker_running)
    state = "healthy" if healthy else ("degraded" if database else "unavailable")
    return JSONResponse(
        status_code=200 if database else 503,
        content={
            "status": state,
            "database": "connected" if database else "unavailable",
            "redis": "connected" if redis else "unavailable",
            "outbox_pending": backlog,
            "websocket_clients": len(request.app.state.hub.clients),
            "pubsub_connected": request.app.state.hub.connected,
            "sample_data": True,
            "schema_version": "fleet_v2",
            "speed_limit_kmh": request.app.state.settings.speed_limit_kmh,
            "cloud_demo": demo_enabled,
            "demo_worker_running": worker_running,
        },
    )
