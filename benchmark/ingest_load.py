import argparse
import asyncio
import time
from datetime import UTC, datetime

import httpx

from app.config import Settings
from benchmark.common import login, save_report


async def run(args):
    settings = Settings()
    values = []
    errors = 0
    started = time.perf_counter()
    async with httpx.AsyncClient(base_url=args.url.rstrip("/"), timeout=10) as client:
        token = await login(client)
        vehicle_response = await client.get(
            "/api/v1/vehicles", headers={"Authorization": "Bearer " + token}
        )
        vehicle_response.raise_for_status()
        vehicles = vehicle_response.json()[: args.batch_size]
        if not vehicles:
            raise RuntimeError("Seed vehicles first")
        for _ in range(args.requests):
            payload = {
                "positions": [
                    {
                        "vehicle_id": v["id"],
                        "recorded_at": datetime.now(UTC).isoformat(),
                        "lat": 12.9716,
                        "lon": 77.5946,
                        "speed_kmh": 40,
                        "heading": 90,
                    }
                    for v in vehicles
                ]
            }
            start = time.perf_counter()
            try:
                res = await client.post(
                    "/api/v1/positions/batch",
                    json=payload,
                    headers={"X-API-Key": settings.device_api_key.get_secret_value()},
                )
                res.raise_for_status()
                values.append((time.perf_counter() - start) * 1000)
            except httpx.HTTPError:
                errors += 1
    elapsed = time.perf_counter() - started
    save_report(
        "ingest-smoke",
        values,
        elapsed,
        errors,
        {
            "requests": args.requests,
            "positions_per_batch": len(vehicles),
            "concurrent_clients": 1,
            "accepted_positions": len(values) * len(vehicles),
        },
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--requests", type=int, default=30)
    p.add_argument("--batch-size", type=int, default=12)
    args = p.parse_args()
    if not 1 <= args.requests <= 10000 or not 1 <= args.batch_size <= 100:
        p.error("Use 1-10000 requests and batch size 1-100")
    asyncio.run(run(args))
