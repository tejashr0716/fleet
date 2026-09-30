from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app


async def test_protected_reads_and_writes(system):
    for path in ["/api/v1/vehicles", "/api/v1/fleet/live", "/api/v1/alerts"]:
        assert (await system.client.get(path)).status_code == 401
    res = await system.client.post(
        "/api/v1/positions/batch",
        json={"positions": [system.point()]},
        headers={"X-API-Key": "wrong"},
    )
    assert res.status_code == 401


async def test_wrong_password_and_login_limit(system):
    # Fixture already performed one login; nine more allowed, eleventh rejected.
    for _ in range(9):
        response = await system.client.post(
            "/api/v1/auth/token", json={"username": "admin", "password": "wrong"}
        )
        assert response.status_code == 401
    response = await system.client.post(
        "/api/v1/auth/token", json={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 429 and response.headers["retry-after"] == "60"


async def test_expired_or_wrong_algorithm_jwt(system):
    payload = {
        "sub": "admin",
        "iat": datetime.now(UTC) - timedelta(hours=1),
        "exp": datetime.now(UTC) - timedelta(minutes=1),
        "iss": "fleet",
        "aud": "fleet-dashboard",
    }
    token = jwt.encode(payload, system.settings.jwt_secret.get_secret_value(), algorithm="HS256")
    res = await system.client.get("/api/v1/vehicles", headers={"Authorization": "Bearer " + token})
    assert res.status_code == 401
    payload["exp"] = datetime.now(UTC) + timedelta(minutes=5)
    token = jwt.encode(payload, system.settings.jwt_secret.get_secret_value(), algorithm="HS384")
    res = await system.client.get("/api/v1/vehicles", headers={"Authorization": "Bearer " + token})
    assert res.status_code == 401


async def test_ws_auth_and_ping(system):
    with TestClient(create_app(system.settings)) as client:
        with client.websocket_connect(
            "/ws/live", headers={"origin": "http://localhost:8000"}
        ) as ws:
            ws.send_json({"type": "auth", "token": system.headers["Authorization"].split()[1]})
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"type": "ping"})
            for _ in range(5):
                if ws.receive_json()["type"] == "pong":
                    break
            else:
                pytest.fail("Pong not received")


async def test_ws_invalid_token_and_origin(system):
    with TestClient(create_app(system.settings)) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/live") as ws:
                ws.send_json({"type": "auth", "token": "invalid"})
                ws.receive_json()
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/ws/live", headers={"origin": "https://untrusted.invalid"}
            ):
                pass


async def test_ws_rejects_non_object_frame(system):
    with TestClient(create_app(system.settings)) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/live") as ws:
                ws.send_json([])
                ws.receive_json()
