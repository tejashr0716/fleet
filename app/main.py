"""Application factory, ASGI lifespan, middleware, and router mounts."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from app.config import settings
from app.errors import AppError, app_error_handler, request_id_ctx
from app.redis_client import close_redis, get_redis_client
from app.routers import (
    alerts_router,
    fleet_router,
    geofences_router,
    health_router,
    positions_router,
    vehicles_router,
)
from app.ws import ingest_router, live_router, ws_manager

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] [req:%(request_id)s] %(name)s: %(message)s",
)


class RequestIdFilter(logging.Filter):
    """Logging filter that injects the active request ID into record attributes."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


root_logger = logging.getLogger()
for handler in root_logger.handlers:
    handler.addFilter(RequestIdFilter())

logger = logging.getLogger("fleet.api")


async def redis_pubsub_fanout_task() -> None:
    """Lifespan background task subscribing to Redis Pub/Sub events for WebSocket broadcast."""
    redis: Redis = get_redis_client()
    pubsub = redis.pubsub()
    await pubsub.subscribe("fleet:events")
    logger.info("Subscribed to Redis Pub/Sub channel 'fleet:events' for WebSocket fan-out")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    payload = json.loads(message["data"])
                    event_type = payload.get("type", "position")
                    if event_type == "position":
                        await ws_manager.broadcast_position(payload["data"])
                    else:
                        await ws_manager.broadcast_event(event_type, payload["data"])
                except Exception as exc:
                    logger.error("Error broadcasting message over WebSocket: %s", exc)
    except asyncio.CancelledError:
        logger.info("Cancelling Redis Pub/Sub listener task...")
    finally:
        await pubsub.unsubscribe("fleet:events")
        await pubsub.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle with structured asyncio.TaskGroup."""
    logger.info("Initializing Fleet API runtime...")
    # Initialize redis client pool once during lifespan startup
    get_redis_client()

    async with asyncio.TaskGroup() as tg:
        fanout_task = tg.create_task(redis_pubsub_fanout_task())
        try:
            yield
        finally:
            fanout_task.cancel()
            await close_redis()
            logger.info("Closed Redis connection pool.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="Fleet Real-Time Telemetry Platform",
        version="1.0.0",
        description="Production-grade real-time vehicle tracking platform",
        lifespan=lifespan,
    )

    # Middleware: Request ID Context & Response Timing Header
    @app.middleware("http")
    async def trace_and_timing_middleware(
        request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(req_id)
        start_time = time.perf_counter()

        try:
            response: Response = await call_next(request)
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            request_id_ctx.reset(token)

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time-ms"] = f"{duration_ms:.2f}"
        return response

    # Global Exception Handling: ensure AppError and validation errors return standard envelope
    app.add_exception_handler(AppError, app_error_handler)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "The requested endpoint was not found",
                    "details": {"path": request.url.path},
                }
            },
        )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST Routers
    api_v1 = "/api/v1"
    app.include_router(health_router, prefix=api_v1)
    app.include_router(vehicles_router, prefix=api_v1)
    app.include_router(positions_router, prefix=api_v1)
    app.include_router(fleet_router, prefix=api_v1)
    app.include_router(geofences_router, prefix=api_v1)
    app.include_router(alerts_router, prefix=api_v1)

    # WebSocket Routers
    app.include_router(live_router, prefix="/ws")
    app.include_router(ingest_router, prefix="/ws")

    # Static assets mount (if directory exists)
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
