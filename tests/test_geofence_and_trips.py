from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.geofence import distance_m
from app.services.trips import segment_trace


@pytest.mark.parametrize("a,b,expected", [((0, 0), (0, 0), 0), ((0, 0), (0, 1), 111195)])
def test_haversine(a, b, expected):
    assert distance_m(*a, *b) == pytest.approx(expected, abs=1)


async def test_speeding_transition_and_geofence_events(system):
    await system.client.post(
        "/api/v1/geofences",
        headers=system.headers,
        json={"name": "Demo zone", "lat": 12.9716, "lon": 77.5946, "radius_m": 500},
    )
    now = datetime.now(UTC)
    points = [
        system.point(lat=12.95, recorded_at=(now - timedelta(seconds=3)).isoformat()),
        system.point(speed_kmh=92, recorded_at=(now - timedelta(seconds=2)).isoformat()),
        system.point(speed_kmh=93, recorded_at=(now - timedelta(seconds=1)).isoformat()),
    ]
    res = await system.client.post(
        "/api/v1/positions/batch", headers=system.key, json={"positions": points}
    )
    assert res.status_code == 202
    alerts = (await system.client.get("/api/v1/alerts", headers=system.headers)).json()
    assert [a["kind"] for a in alerts].count("speeding") == 1
    assert [a["kind"] for a in alerts].count("geofence_enter") == 1


async def test_late_history_does_not_create_live_alert(system):
    now = datetime.now(UTC)
    for p in [
        system.point(recorded_at=now.isoformat()),
        system.point(speed_kmh=92, recorded_at=(now - timedelta(seconds=5)).isoformat()),
    ]:
        await system.client.post(
            "/api/v1/positions/batch", headers=system.key, json={"positions": [p]}
        )
    assert (await system.client.get("/api/v1/alerts", headers=system.headers)).json() == []


def test_trace_sessions_split_on_gap():
    now = datetime.now(UTC)
    points = [
        SimpleNamespace(vehicle_id=1, recorded_at=now + timedelta(seconds=t), lat=12.97, lon=77.59)
        for t in [0, 10, 400, 410]
    ]
    groups = segment_trace(points)
    assert len(groups) == 2 and [g.point_count for g in groups] == [2, 2]
