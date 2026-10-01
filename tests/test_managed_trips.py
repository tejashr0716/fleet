import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import Trip
from app.repositories.managed_trip_repo import trace_summary
from app.schemas.trip import StartTrip
from app.schemas.vehicle import VehicleCreate
from app.services.trip_runner import TripRunner, sample_for


def test_trip_input_is_strict_and_known_routes_only():
    for body in [
        {"duration_seconds": True},
        {"duration_seconds": 4},
        {"duration_seconds": 601},
        {"route_key": "unknown"},
        {"include_speeding": "false"},
        {"extra": 1},
    ]:
        with pytest.raises(ValueError):
            StartTrip(**body)
    assert StartTrip().duration_seconds == 180


def test_vehicle_registration_normalizes_without_blank_names():
    vehicle = VehicleCreate(name=" Delivery One ", registration=" ka-01 test ")
    assert vehicle.name == "Delivery One" and vehicle.registration == "KA-01 TEST"
    for name in [" ", "<script>"]:
        with pytest.raises(ValueError):
            VehicleCreate(name=name, registration="DEMO")


def test_sample_is_tagged_and_speeding_is_an_explicit_fixture():
    trip = SimpleNamespace(id=17, vehicle_id=3, route_key="central", include_speeding=True)
    point = sample_for(trip, 8)
    assert point["trip_id"] == 17 and point["vehicle_id"] == 3 and point["speed_kmh"] == 92
    trip.include_speeding = False
    assert sample_for(trip, 8)["speed_kmh"] < 80
    assert -90 <= point["lat"] <= 90 and -180 <= point["lon"] <= 180


def test_summary_uses_only_stored_samples_and_labels_partial_trace():
    now = datetime.now(UTC)
    trip = SimpleNamespace(started_at=now - timedelta(seconds=10), ended_at=now)
    points = [SimpleNamespace(lat=0, lon=0), SimpleNamespace(lat=0, lon=0.001)]
    summary = trace_summary(trip, points, 2, 92, 1)
    assert summary["duration_seconds"] == 10
    assert summary["distance_km"] == pytest.approx(0.111)
    assert summary["max_speed_kmh"] == 92 and summary["alert_count"] == 1
    assert trace_summary(trip, points, 3, 92, 1)["distance_km"] is None
    empty = trace_summary(trip, [], 0, None, 0)
    assert empty["distance_km"] is None and empty["max_speed_kmh"] is None


async def test_task_failure_sanitizes_logs_and_marks_interruption(caplog):
    records = []

    async def fail(trip, tick):
        raise RuntimeError("private credential must not appear")

    runner = TripRunner(None, None, emitter=fail)
    runner.interval = 0.001

    async def close(trip_id, status, reason):
        records.append((trip_id, status, reason))

    runner.close_record = close
    trip = SimpleNamespace(id=1, expires_at=datetime.now(UTC) + timedelta(seconds=5))
    await runner.run(trip)
    assert records == [(1, "interrupted", "simulator_error")]
    assert "private credential" not in caplog.text


async def start(system, vehicle_id=1, **body):
    return await system.client.post(
        f"/api/v1/vehicles/{vehicle_id}/trips",
        headers=system.headers,
        json={"duration_seconds": 30, **body},
    )


async def detail(system, trip_id):
    return await system.client.get(f"/api/v1/trips/{trip_id}", headers=system.headers)


async def test_trip_mutations_and_reads_require_auth(system):
    for method, path in [
        ("post", "/vehicles/1/trips"),
        ("get", "/trips"),
        ("get", "/trips/1"),
        ("post", "/trips/1/finish"),
    ]:
        result = await getattr(system.client, method)("/api/v1" + path)
        assert result.status_code == 401


async def test_register_start_finish_review_is_persisted(system):
    registered = await system.client.post(
        "/api/v1/vehicles",
        headers=system.headers,
        json={"name": "Interview Van", "registration": "ka-01-demo", "kind": "delivery"},
    )
    assert registered.status_code == 201 and not registered.json()["is_sample"]
    vehicle_id = registered.json()["id"]
    started = await start(system, vehicle_id)
    assert started.status_code == 201, started.text
    trip = started.json()
    assert trip["status"] == "active" and trip["source"] == "synthetic"
    observed = (await detail(system, trip["id"])).json()
    assert observed["summary"]["point_count"] >= 1 and observed["source_used"] == "postgresql"
    assert observed["points"][0]["trip_id"] == trip["id"]
    stopped = await system.client.post(f"/api/v1/trips/{trip['id']}/finish", headers=system.headers)
    assert stopped.status_code == 200 and stopped.json()["end_reason"] == "manual"
    again = await system.client.post(f"/api/v1/trips/{trip['id']}/finish", headers=system.headers)
    assert again.json()["ended_at"] == stopped.json()["ended_at"]
    saved = (
        await system.client.get(f"/api/v1/vehicles/{vehicle_id}/trips", headers=system.headers)
    ).json()
    assert saved["trips"][0]["status"] == "completed"
    reviewed = (await detail(system, trip["id"])).json()
    count = reviewed["summary"]["point_count"]
    await asyncio.sleep(0.05)
    assert (await detail(system, trip["id"])).json()["summary"]["point_count"] == count


async def test_simultaneous_start_requests_have_one_winner(system):
    first, second = await asyncio.gather(start(system), start(system))
    assert sorted([first.status_code, second.status_code]) == [201, 409]


async def test_trip_vehicle_association_and_untagged_ingestion_guard(system):
    trip = (await start(system)).json()
    registered = await system.client.post(
        "/api/v1/vehicles", headers=system.headers, json={"name": "Other", "registration": "OTHER"}
    )
    for point, expected in [
        (system.point(), 409),
        (system.point(trip_id=trip["id"], vehicle_id=registered.json()["id"]), 422),
        (system.point(trip_id=999), 422),
        (
            system.point(
                trip_id=trip["id"],
                recorded_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            ),
            422,
        ),
    ]:
        result = await system.client.post(
            "/api/v1/positions/batch", headers=system.key, json={"positions": [point]}
        )
        assert result.status_code == expected, result.text


async def test_trip_specific_alerts_and_closed_trip_retry(system):
    trip = (await start(system)).json()
    point = system.point(trip_id=trip["id"], speed_kmh=92)
    response = await system.client.post(
        "/api/v1/positions/batch", headers=system.key, json={"positions": [point]}
    )
    assert response.status_code == 202
    await system.client.post(f"/api/v1/trips/{trip['id']}/finish", headers=system.headers)
    review = (await detail(system, trip["id"])).json()
    assert review["summary"]["alert_count"] == 1
    assert review["alerts"][0]["trip_id"] == trip["id"]
    retry = await system.client.post(
        "/api/v1/positions/batch", headers=system.key, json={"positions": [point]}
    )
    assert retry.status_code == 202 and retry.json()["duplicates"] == 1
    new_point = system.point(trip_id=trip["id"])
    rejected = await system.client.post(
        "/api/v1/positions/batch", headers=system.key, json={"positions": [new_point]}
    )
    assert rejected.status_code == 409
    assert (await detail(system, trip["id"])).json()["summary"] == review["summary"]


async def test_new_trip_has_its_own_history_and_alert_transitions(system):
    first = (await start(system)).json()
    await system.client.post(
        "/api/v1/positions/batch",
        headers=system.key,
        json={"positions": [system.point(trip_id=first["id"], speed_kmh=92)]},
    )
    await system.client.post(f"/api/v1/trips/{first['id']}/finish", headers=system.headers)
    second = (await start(system)).json()
    result = (await detail(system, second["id"])).json()
    assert second["id"] != first["id"]
    assert result["summary"]["point_count"] == 1 and result["alerts"] == []
    assert all(p["trip_id"] == second["id"] for p in result["points"])


async def test_automatic_finish_and_startup_recovery_keep_records(system):
    trip = (await start(system, duration_seconds=5)).json()
    task = system.app.state.trips.tasks[trip["id"]]
    await asyncio.wait_for(asyncio.shield(task), timeout=8)
    finished = (await detail(system, trip["id"])).json()
    assert (
        finished["trip"]["status"] == "completed" and finished["trip"]["end_reason"] == "time_limit"
    )
    assert finished["summary"]["point_count"] >= 2
    now = datetime.now(UTC)
    async with system.app.state.db.sessions() as session:
        abandoned = Trip(
            vehicle_id=1,
            route_key="east",
            status="active",
            source="synthetic",
            started_at=now,
            expires_at=now + timedelta(seconds=30),
            duration_seconds=30,
            include_speeding=False,
        )
        session.add(abandoned)
        await session.commit()
        abandoned_id = abandoned.id
    await system.app.state.trips.reconcile()
    record = (await detail(system, abandoned_id)).json()
    assert (
        record["trip"]["status"] == "interrupted"
        and record["trip"]["end_reason"] == "server_restart"
    )
    assert record["summary"]["point_count"] == 0


async def test_shutdown_cancels_tasks_without_deleting_history(system):
    trip = (await start(system)).json()
    await system.app.state.trips.shutdown()
    review = (await detail(system, trip["id"])).json()
    assert review["trip"]["end_reason"] == "service_shutdown"
    assert review["summary"]["point_count"] == 1
    assert not system.app.state.trips.tasks


async def test_active_trip_capacity_and_missing_entities(system):
    assert (await start(system, 999)).status_code == 404
    assert (await detail(system, 999)).status_code == 404
    for i in range(4):
        if i:
            await system.client.post(
                "/api/v1/vehicles",
                headers=system.headers,
                json={"name": f"Car {i}", "registration": f"CAR-{i}"},
            )
        result = await start(system, i + 1)
        assert result.status_code == (201 if i < 3 else 409)


@pytest.mark.parametrize("system", [True], indirect=True)
async def test_cloud_trip_uses_real_outbox_and_redis_and_quota(system):
    trip = (await start(system)).json()
    cached = None
    for _ in range(80):
        cached = await system.app.state.redis.get("fleet-v2:live:1")
        if cached:
            break
        await asyncio.sleep(0.05)
    assert cached and json.loads(cached)["trip_id"] == trip["id"]
    await system.client.post(f"/api/v1/trips/{trip['id']}/finish", headers=system.headers)
    system.app.state.settings.cloud_demo_position_budget = 12
    result = await start(system)
    assert result.status_code == 409


async def test_hourly_quota_is_persistent_not_process_only(system):
    now = datetime.now(UTC)
    async with system.app.state.db.sessions() as session:
        session.add_all(
            [
                Trip(
                    vehicle_id=1,
                    route_key="central",
                    status="completed",
                    source="synthetic",
                    started_at=now - timedelta(seconds=20),
                    expires_at=now,
                    ended_at=now,
                    duration_seconds=20,
                    include_speeding=False,
                    end_reason="manual",
                )
                for _ in range(12)
            ]
        )
        await session.commit()
    assert (await start(system)).status_code == 429
    async with system.app.state.db.sessions() as session:
        assert len((await session.scalars(select(Trip))).all()) == 12
