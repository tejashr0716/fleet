import argparse
import asyncio
import json
import time
from datetime import UTC, datetime

import httpx
import websockets

from app.config import Settings
from benchmark.common import login, save_report


async def run(args):
    settings = Settings()
    values = []
    errors = 0
    started = time.perf_counter()
    async with httpx.AsyncClient(base_url=args.url.rstrip("/"), timeout=10) as client:
        token = await login(client)
        response = await client.get(
            "/api/v1/vehicles", headers={"Authorization": "Bearer " + token}
        )
        response.raise_for_status()
        vehicles = response.json()
        if not vehicles:
            raise RuntimeError("Seed vehicles first")
        async with websockets.connect(
            args.url.rstrip("/").replace("http", "ws", 1) + "/ws/live"
        ) as socket:
            await socket.send(json.dumps({"type": "auth", "token": token}))
            await socket.recv()
            for _ in range(args.samples):
                stamp = datetime.now(UTC).isoformat()
                point = {
                    "vehicle_id": vehicles[0]["id"],
                    "recorded_at": stamp,
                    "lat": 12.9716,
                    "lon": 77.5946,
                    "speed_kmh": 40,
                    "heading": 90,
                }
                start = time.perf_counter()
                response = await client.post(
                    "/api/v1/positions/batch",
                    json={"positions": [point]},
                    headers={"X-API-Key": settings.device_api_key.get_secret_value()},
                )
                response.raise_for_status()

                async def matching_event(vehicle_id=point["vehicle_id"], expected_stamp=stamp):
                    while True:
                        event = json.loads(await socket.recv())
                        if (
                            event.get("type") == "position"
                            and event["data"]["vehicle_id"] == vehicle_id
                            and datetime.fromisoformat(event["data"]["recorded_at"])
                            == datetime.fromisoformat(expected_stamp)
                        ):
                            return

                try:
                    await asyncio.wait_for(matching_event(), timeout=5)
                    values.append((time.perf_counter() - start) * 1000)
                except TimeoutError:
                    errors += 1
    save_report(
        "websocket-e2e-smoke",
        values,
        time.perf_counter() - started,
        errors,
        {
            "websocket_clients": 1,
            "synthetic_samples_submitted": args.samples,
            "clock": "same-client monotonic; excludes browser rendering",
        },
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--samples", type=int, default=20)
    args = p.parse_args()
    if not 1 <= args.samples <= 10000:
        p.error("Use 1-10000 samples")
    asyncio.run(run(args))
