import asyncio
import json
import time
from datetime import datetime

import httpx
import pytest
from fastapi import HTTPException

from app.cloud_demo import main, prepare_environment
from app.models import Position
from app.services.demo import SampleGPS


async def wait_forever(args):
    await asyncio.Event().wait()


def cloud_env(**changes):
    return {
        "DATABASE_URL": "postgresql://fixture:placeholder@db/fleet?sslmode=require",
        "REDIS_URL": "redis://cache:6379/0",
        **changes,
    }


def test_provider_url_normalization():
    env = prepare_environment(cloud_env(ENVIRONMENT="development"))
    assert env["DATABASE_URL"].startswith("postgresql+asyncpg://")
    assert env["DATABASE_URL"].endswith("?ssl=require")
    assert env["ENVIRONMENT"] == "production"
    assert env["CLOUD_DEMO_ENABLED"] == "true"
    assert env["PORT"] == "10000"


@pytest.mark.parametrize("port", ["bad", "0", "65536", "18012"])
def test_rejects_invalid_port(port):
    with pytest.raises(ValueError):
        prepare_environment(cloud_env(PORT=port))


def test_rejects_non_postgres_or_redis_urls():
    with pytest.raises(ValueError):
        prepare_environment(cloud_env(DATABASE_URL="sqlite:///local.db"))
    with pytest.raises(ValueError):
        prepare_environment(cloud_env(REDIS_URL="https://not-redis.example"))


def test_launcher_rejects_weak_credentials_without_logging_them(monkeypatch, capsys):
    for key, value in cloud_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("CLOUD_DEMO_ENABLED", "false")
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("ADMIN_PASSWORD", "private-fixture-password")
    monkeypatch.setenv("JWT_SECRET", "short-fixture")
    monkeypatch.setenv("DEVICE_API_KEY", "short-fixture")
    assert main() == 2
    output = capsys.readouterr().err
    assert "configuration rejected" in output
    assert "private-fixture-password" not in output
    assert "placeholder" not in output


async def test_session_conflict_and_graceful_stop():
    demo = SampleGPS("http://127.0.0.1:10000", sampler=wait_forever)
    assert (await demo.start(300, 50_000))["running"]
    with pytest.raises(HTTPException) as exc:
        await demo.start(300, 50_000)
    assert exc.value.status_code == 409
    stopped = await demo.stop()
    assert not stopped["running"] and stopped["phase"] == "stopped"
    assert stopped["ended_at"]


async def test_session_duration_and_row_budget():
    captured = []

    async def sample(args):
        captured.append(args)
        await wait_forever(args)

    demo = SampleGPS("http://127.0.0.1:10000", sampler=sample)
    with pytest.raises(HTTPException):
        await demo.start(601, 50_000)
    with pytest.raises(HTTPException) as exc:
        await demo.start(300, 11)
    assert exc.value.status_code == 409
    await demo.start(600, 24)
    await asyncio.sleep(0.01)
    assert captured[0].ticks == 2
    assert captured[0].vehicles == 12 and captured[0].interval == 3
    await demo.stop()


async def test_session_automatically_expires():
    demo = SampleGPS("http://127.0.0.1:10000", sampler=wait_forever)
    await demo.start(1, 50_000)
    await demo.task
    assert demo.status()["phase"] == "completed"
    assert not demo.status()["running"]


async def test_session_start_throttle_and_window_expiry():
    async def finish(args):
        return None

    demo = SampleGPS("http://127.0.0.1:10000", sampler=finish)
    for _ in range(3):
        await demo.start(1, 50_000)
        await demo.task
    with pytest.raises(HTTPException) as exc:
        await demo.start(1, 50_000)
    assert exc.value.status_code == 429
    demo.starts.clear()
    demo.starts.extend([time.monotonic() - 3601] * 3)
    await demo.start(1, 50_000)
    await demo.task


async def test_session_error_is_sanitized():
    async def fail(args):
        raise RuntimeError("private connection details must not escape")

    demo = SampleGPS("http://127.0.0.1:10000", sampler=fail)
    await demo.start(1, 50_000)
    await demo.task
    result = demo.status()
    assert result["phase"] == "failed" and result["error_type"] == "RuntimeError"
    assert "private connection" not in json.dumps(result)


async def test_api_disabled_by_default(system):
    assert (await system.client.post("/api/v1/demo/start", json={})).status_code == 401
    result = await system.client.post("/api/v1/demo/start", json={}, headers=system.headers)
    assert result.status_code == 404


@pytest.mark.parametrize("system", [True], indirect=True)
async def test_api_cloud_auth_limits_and_stop(system):
    system.app.state.demo.sampler = wait_forever
    assert (await system.client.get("/api/v1/demo/status")).status_code == 401
    for value in [0, 601, True]:
        result = await system.client.post(
            "/api/v1/demo/start", json={"duration_seconds": value}, headers=system.headers
        )
        assert result.status_code == 422
    health = (await system.client.get("/api/v1/health")).json()
    assert health["cloud_demo"] and health["demo_worker_running"]
    result = await system.client.post("/api/v1/demo/start", json={}, headers=system.headers)
    assert result.status_code == 202 and result.json()["running"]
    duplicate = await system.client.post("/api/v1/demo/start", json={}, headers=system.headers)
    assert duplicate.status_code == 409
    stopped = await system.client.post("/api/v1/demo/stop", headers=system.headers)
    assert stopped.status_code == 200 and not stopped.json()["running"]


@pytest.mark.parametrize("system", [True], indirect=True)
async def test_api_cloud_row_budget(system):
    system.app.state.settings.cloud_demo_position_budget = 12
    async with system.app.state.db.sessions() as session:
        point = system.point()
        point["recorded_at"] = datetime.fromisoformat(point["recorded_at"])
        session.add(Position(**point))
        await session.commit()
    result = await system.client.post("/api/v1/demo/start", json={}, headers=system.headers)
    assert result.status_code == 409


@pytest.mark.parametrize("system", [True], indirect=True)
async def test_api_cloud_worker_guard(system):
    worker = system.app.state.cloud_worker
    worker.cancel()
    await asyncio.gather(worker, return_exceptions=True)
    result = await system.client.post("/api/v1/demo/start", json={}, headers=system.headers)
    assert result.status_code == 503
    assert (await system.client.get("/api/v1/health")).json()["status"] == "degraded"


@pytest.mark.parametrize("system", [True], indirect=True)
async def test_api_cloud_real_pipeline(system, monkeypatch):
    import simulator.run as simulator_module

    original_client = httpx.AsyncClient

    def local_client(*args, **kwargs):
        if kwargs.get("base_url") == system.app.state.demo.local_url:
            kwargs["transport"] = httpx.ASGITransport(app=system.app)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(simulator_module.httpx, "AsyncClient", local_client)
    started = await system.client.post(
        "/api/v1/demo/start", json={"duration_seconds": 5}, headers=system.headers
    )
    assert started.status_code == 202
    cached = None
    for _ in range(80):
        cached = await system.app.state.redis.get("fleet-v2:live:1")
        if cached:
            break
        await asyncio.sleep(0.05)
    assert cached, "Real outbox worker did not deliver the synthetic position to Redis"
    observed = await system.client.get("/api/v1/vehicles/1/positions", headers=system.headers)
    assert observed.status_code == 200 and observed.json()["points"]
    assert json.loads(cached)["vehicle_id"] == 1
    stopped = await system.client.post("/api/v1/demo/stop", headers=system.headers)
    assert stopped.status_code == 200 and not stopped.json()["running"]


def test_route_wraps_before_first_tick():
    from simulator.run import route_point

    point = route_point([[0, 0], [0, 1], [0, 0]], -1)
    assert point[0] == 0 and point[1] == pytest.approx(1 / 120)
