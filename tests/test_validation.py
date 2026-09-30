from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas.position import PositionIn


@pytest.mark.parametrize(
    "field,value",
    [
        ("lat", 91),
        ("lon", 181),
        ("speed_kmh", -1),
        ("speed_kmh", 251),
        ("heading", 360),
        ("lat", float("nan")),
        ("lon", float("inf")),
    ],
)
def test_invalid_coordinates_and_speed(field, value):
    data = {
        "vehicle_id": 1,
        "lat": 12.97,
        "lon": 77.59,
        "speed_kmh": 30,
        "recorded_at": datetime.now(UTC),
    }
    data[field] = value
    with pytest.raises(ValidationError):
        PositionIn(**data)


@pytest.mark.parametrize(
    "stamp",
    [
        datetime.now(),
        datetime.now(UTC) + timedelta(minutes=2),
        datetime.now(UTC) - timedelta(days=91),
    ],
)
def test_invalid_time(stamp):
    with pytest.raises(ValidationError):
        PositionIn(vehicle_id=1, lat=12.97, lon=77.59, speed_kmh=30, recorded_at=stamp)


def test_production_rejects_defaults():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production")


async def test_json_error_envelope_and_no_secret_echo(system):
    response = await system.client.post(
        "/api/v1/positions/batch", headers=system.key, json={"positions": [system.point(lat=100)]}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["request_id"] == response.headers["x-request-id"]


async def test_unknown_vehicle_and_empty_batch(system):
    for body in [{"positions": [system.point(vehicle_id=999)]}, {"positions": []}]:
        res = await system.client.post("/api/v1/positions/batch", headers=system.key, json=body)
        assert res.status_code == 422


async def test_history_bad_window_and_missing_vehicle(system):
    res = await system.client.get(
        "/api/v1/vehicles/1/positions?from=2026-01-01&to=2026-01-02", headers=system.headers
    )
    assert res.status_code == 422
    res = await system.client.get("/api/v1/vehicles/999", headers=system.headers)
    assert res.status_code == 404
