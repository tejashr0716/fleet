import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.db import Database
from app.errors import install_errors
from app.redis_client import make_redis
from app.routers import alerts, fleet, geofences, health, positions, vehicles
from app.security import Auth, Login
from app.ws.live import router as ws_router
from app.ws.manager import Hub

logger = logging.getLogger("fleet")
LOGIN_LIMIT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], 60) end
return count
"""


def create_app(settings=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.settings = settings
        app.state.db = Database(settings.database_url)
        app.state.redis = make_redis(settings.redis_url)
        app.state.auth = Auth(settings)
        app.state.hub = Hub()
        listener = asyncio.create_task(app.state.hub.listen(app.state.redis))
        if settings.environment == "development":
            logger.warning(
                "Development mode: local demo credentials; do not expose this setup publicly"
            )
        try:
            yield
        finally:
            listener.cancel()
            await asyncio.gather(listener, return_exceptions=True)
            await app.state.redis.aclose()
            await app.state.db.close()

    app = FastAPI(
        title="Fleet Vehicle Tracking",
        version="2.0.0",
        lifespan=lifespan,
        description="Synthetic GPS demo. PostgreSQL durability, Redis fan-out, JWT-protected reads.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    @app.middleware("http")
    async def trace_request(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    install_errors(app)

    @app.post("/api/v1/auth/token", tags=["Authentication"])
    async def login(body: Login, request: Request):
        key = f"fleet-v2:login:{request.client.host if request.client else 'unknown'}"
        attempts = await request.app.state.redis.eval(LOGIN_LIMIT, 1, key)
        if attempts > 10:
            raise HTTPException(
                429, "At most 10 login attempts per minute", headers={"Retry-After": "60"}
            )
        valid = await asyncio.to_thread(
            request.app.state.auth.verify_password, body.username, body.password
        )
        if not valid:
            raise HTTPException(401, "Invalid username or password")
        return {
            "access_token": request.app.state.auth.issue(),
            "token_type": "bearer",
            "expires_in": settings.token_ttl_minutes * 60,
        }

    for router in [
        vehicles.router,
        positions.router,
        fleet.router,
        geofences.router,
        alerts.router,
        health.router,
    ]:
        app.include_router(router, prefix="/api/v1")
    app.include_router(ws_router)

    @app.get("/", include_in_schema=False)
    async def home():
        return RedirectResponse("/static/index.html")

    static = Path(__file__).resolve().parents[1] / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")
    return app


app = create_app()
