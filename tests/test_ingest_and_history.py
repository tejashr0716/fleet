from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import OutboxEvent, Position


async def test_durable_insert_and_retry(system):
    body = {"positions": [system.point()]}
    first = await system.client.post("/api/v1/positions/batch", json=body, headers=system.key)
    retry = await system.client.post("/api/v1/positions/batch", json=body, headers=system.key)
    assert first.status_code == 202 and first.json()["inserted"] == 1
    assert first.json()["durability"] == "postgresql_committed"
    assert retry.json()["inserted"] == 0 and retry.json()["duplicates"] == 1
    async with system.app.state.db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Position)) == 1
        assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 1


async def test_history_sorted_and_bounded(system):
    now = datetime.now(UTC)
    body = {
        "positions": [
            system.point(recorded_at=(now - timedelta(seconds=i)).isoformat()) for i in range(5)
        ]
    }
    await system.client.post("/api/v1/positions/batch", json=body, headers=system.key)
    res = await system.client.get("/api/v1/vehicles/1/positions?limit=3", headers=system.headers)
    points = res.json()["points"]
    assert len(points) == 3 and res.json()["has_more"] is True
    assert [p["recorded_at"] for p in points] == sorted(p["recorded_at"] for p in points)


async def test_entire_batch_rejected_for_unregistered_vehicle(system):
    response = await system.client.post(
        "/api/v1/positions/batch",
        headers=system.key,
        json={"positions": [system.point(), system.point(vehicle_id=999)]},
    )
    assert response.status_code == 422
    async with system.app.state.db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Position)) == 0


async def test_vehicle_uniqueness_and_api_docs(system):
    res = await system.client.post(
        "/api/v1/vehicles",
        headers=system.headers,
        json={"name": "Fleet 01", "registration": "DEMO-001"},
    )
    assert res.status_code == 409
    assert (await system.client.get("/openapi.json")).status_code == 200
    assert (await system.client.get("/api/v1/health")).json()["schema_version"] == "fleet_v2"
