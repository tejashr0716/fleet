import argparse
import asyncio
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.config import Settings
from app.services.geofence import distance_m


def route_point(route, tick):
    segment = tick / 120
    a = route[int(segment) % (len(route) - 1)]
    b = route[(int(segment) % (len(route) - 1)) + 1]
    f = segment % 1
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]


async def run(args):
    settings = Settings()
    routes = json.loads((Path(__file__).parent / "routes.json").read_text())["routes"]
    async with httpx.AsyncClient(base_url=args.url.rstrip("/"), timeout=10) as client:
        res = await client.post(
            "/api/v1/auth/token",
            json={
                "username": settings.admin_username,
                "password": settings.admin_password.get_secret_value(),
            },
        )
        res.raise_for_status()
        vehicles_res = await client.get(
            "/api/v1/vehicles", headers={"Authorization": "Bearer " + res.json()["access_token"]}
        )
        vehicles_res.raise_for_status()
        vehicles = [v for v in vehicles_res.json() if v["registration"].startswith("DEMO-")][
            : args.vehicles
        ]
        if not vehicles:
            raise RuntimeError("No demo vehicles; run python -m simulator.seed first")
        tick = 0
        print(f"Generating SYNTHETIC telemetry for {len(vehicles)} vehicles; not real GPS data.")
        while args.ticks == 0 or tick < args.ticks:
            points = []
            for i, vehicle in enumerate(vehicles):
                step, route = tick + i * 37, routes[i % len(routes)]
                pos, prev = route_point(route, step), route_point(route, step - 1)
                speed = min(75, distance_m(*prev, *pos) * 3.6 / args.interval)
                if args.trigger_alerts and i == 0 and tick % 40 in [15, 16, 17]:
                    speed = 92  # Deliberate fixture to demonstrate a threshold alert, not a measurement.
                heading = math.degrees(math.atan2(pos[1] - prev[1], pos[0] - prev[0])) % 360
                points.append(
                    {
                        "vehicle_id": vehicle["id"],
                        "lat": pos[0],
                        "lon": pos[1],
                        "speed_kmh": round(speed, 1),
                        "heading": heading,
                        "recorded_at": datetime.now(UTC).isoformat(),
                    }
                )
            res = await client.post(
                "/api/v1/positions/batch",
                json={"positions": points},
                headers={"X-API-Key": settings.device_api_key.get_secret_value()},
            )
            res.raise_for_status()
            tick += 1
            if tick % 10 == 0:
                print(f"Submitted {tick * len(vehicles)} synthetic positions")
            await asyncio.sleep(args.interval)


def main():
    p = argparse.ArgumentParser(description="Synthetic GPS demo, 12 vehicles by default")
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--vehicles", type=int, default=12)
    p.add_argument("--interval", type=float, default=1)
    p.add_argument("--ticks", type=int, default=0, help="0 means keep running")
    p.add_argument("--trigger-alerts", action="store_true")
    args = p.parse_args()
    if not 1 <= args.vehicles <= 100 or args.interval <= 0 or args.ticks < 0:
        p.error("Use 1-100 vehicles, a positive interval and a nonnegative tick count")
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
