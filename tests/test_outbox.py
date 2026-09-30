import json
from datetime import UTC, datetime, timedelta

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import func, select

from app.models import OutboxEvent, Position
from workers.position_consumer import drain_once
from workers.reclaimer import cleanup


class BrokenRedis:
    async def eval(self, *args, **kwargs):
        raise RedisConnectionError("Intentional test outage")

    async def ping(self):
        raise RedisConnectionError("Intentional test outage")


async def test_cache_updates_only_after_worker_delivery(system):
    point = system.point()
    await system.client.post(
        "/api/v1/positions/batch", headers=system.key, json={"positions": [point]}
    )
    assert await system.app.state.redis.get("fleet-v2:live:1") is None
    assert await drain_once(system.app.state.db, system.app.state.redis) == 1
    value = json.loads(await system.app.state.redis.get("fleet-v2:live:1"))
    assert value["lat"] == point["lat"]
    assert await drain_once(system.app.state.db, system.app.state.redis) == 0


async def test_redis_outage_keeps_data_and_retriable_outbox(system):
    await system.client.post(
        "/api/v1/positions/batch", headers=system.key, json={"positions": [system.point()]}
    )
    with pytest.raises(RedisConnectionError):
        await drain_once(system.app.state.db, BrokenRedis())
    async with system.app.state.db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Position)) == 1
        assert (
            await session.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.delivered_at.is_(None))
            )
            == 1
        )
    assert await drain_once(system.app.state.db, system.app.state.redis) == 1


async def test_late_point_does_not_overwrite_latest_cache(system):
    now = datetime.now(UTC)
    await system.client.post(
        "/api/v1/positions/batch",
        headers=system.key,
        json={"positions": [system.point(recorded_at=now.isoformat(), lat=12.98)]},
    )
    await drain_once(system.app.state.db, system.app.state.redis)
    await system.client.post(
        "/api/v1/positions/batch",
        headers=system.key,
        json={
            "positions": [
                system.point(recorded_at=(now - timedelta(seconds=5)).isoformat(), lat=12.95)
            ]
        },
    )
    await drain_once(system.app.state.db, system.app.state.redis)
    assert json.loads(await system.app.state.redis.get("fleet-v2:live:1"))["lat"] == 12.98


async def test_cleanup_never_removes_pending_events(system):
    async with system.app.state.db.sessions() as session:
        old = datetime.now(UTC) - timedelta(days=9)
        session.add_all(
            [
                OutboxEvent(payload={}, created_at=old),
                OutboxEvent(payload={}, created_at=old, delivered_at=old),
            ]
        )
        await session.commit()
    assert await cleanup(system.app.state.db) == 1
    async with system.app.state.db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 1


async def test_nearest_redis_and_database_fallback(system):
    await system.client.post(
        "/api/v1/positions/batch", headers=system.key, json={"positions": [system.point()]}
    )
    await drain_once(system.app.state.db, system.app.state.redis)
    response = await system.client.get(
        "/api/v1/fleet/nearest?lat=12.97&lon=77.59", headers=system.headers
    )
    assert response.json()["source_used"] == "redis_geo"
    assert response.json()["positions"][0]["vehicle_id"] == 1
    real = system.app.state.redis
    system.app.state.redis = BrokenRedis()
    try:
        response = await system.client.get(
            "/api/v1/fleet/nearest?lat=12.97&lon=77.59", headers=system.headers
        )
        assert response.json()["source_used"] == "postgresql_scan"
        assert len(response.json()["positions"]) == 1
        response = await system.client.get("/api/v1/health")
        assert response.json()["status"] == "degraded"
    finally:
        system.app.state.redis = real


async def test_polar_point_removes_old_geo_member(system):
    now = datetime.now(UTC)
    await system.client.post(
        "/api/v1/positions/batch",
        headers=system.key,
        json={"positions": [system.point(recorded_at=(now - timedelta(seconds=1)).isoformat())]},
    )
    await drain_once(system.app.state.db, system.app.state.redis)
    await system.client.post(
        "/api/v1/positions/batch",
        headers=system.key,
        json={"positions": [system.point(lat=90, recorded_at=now.isoformat())]},
    )
    await drain_once(system.app.state.db, system.app.state.redis)
    assert json.loads(await system.app.state.redis.get("fleet-v2:live:1"))["lat"] == 90
    assert await system.app.state.redis.zscore("fleet-v2:geo", "1") is None
