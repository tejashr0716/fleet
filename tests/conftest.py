import os
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import pytest_asyncio
from sqlalchemy import text

from app.config import Settings
from app.main import create_app


@dataclass
class System:
    app: object
    client: httpx.AsyncClient
    settings: Settings
    headers: dict
    key: dict

    def point(self, **changes):
        return {
            "vehicle_id": 1,
            "lat": 12.9716,
            "lon": 77.5946,
            "speed_kmh": 40,
            "heading": 90,
            "recorded_at": datetime.now(UTC).isoformat(),
            **changes,
        }


@pytest_asyncio.fixture
async def system(request):
    url = os.getenv(
        "TEST_DATABASE_URL",
        os.getenv("DATABASE_URL", "postgresql+asyncpg://fleet:fleet@localhost:5432/fleet_test"),
    )
    redis_url = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")
    if not url.split("?")[0].endswith("/fleet_test") or not redis_url.endswith("/1"):
        raise RuntimeError("Tests refuse to reset any database except fleet_test and Redis DB 1")
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=url,
        redis_url=redis_url,
        cloud_demo_enabled=getattr(request, "param", False),
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with app.state.db.engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE fleet_v2.trips, fleet_v2.outbox, fleet_v2.alerts, fleet_v2.positions, fleet_v2.geofences, fleet_v2.vehicles RESTART IDENTITY CASCADE"
                )
            )
        await app.state.redis.flushdb()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            token = await client.post(
                "/api/v1/auth/token",
                json={
                    "username": settings.admin_username,
                    "password": settings.admin_password.get_secret_value(),
                },
            )
            assert token.status_code == 200
            auth = {"Authorization": "Bearer " + token.json()["access_token"]}
            result = await client.post(
                "/api/v1/vehicles",
                headers=auth,
                json={"name": "Fleet 01", "registration": "DEMO-001"},
            )
            assert result.status_code == 201
            yield System(
                app,
                client,
                settings,
                auth,
                {"X-API-Key": settings.device_api_key.get_secret_value()},
            )
