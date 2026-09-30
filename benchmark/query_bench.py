import argparse
import asyncio
import time

import httpx

from benchmark.common import login, save_report


async def run(args):
    values = []
    errors = 0
    started = time.perf_counter()
    rows = 0
    async with httpx.AsyncClient(base_url=args.url.rstrip("/"), timeout=10) as client:
        token = await login(client)
        headers = {"Authorization": "Bearer " + token}
        vehicles = await client.get("/api/v1/vehicles", headers=headers)
        vehicles.raise_for_status()
        registered = vehicles.json()
        if not registered:
            raise RuntimeError("Seed vehicles first")
        for _ in range(args.requests):
            start = time.perf_counter()
            try:
                response = await client.get(
                    f"/api/v1/vehicles/{registered[0]['id']}/positions?limit=200", headers=headers
                )
                response.raise_for_status()
                rows = len(response.json()["points"])
                values.append((time.perf_counter() - start) * 1000)
            except httpx.HTTPError:
                errors += 1
    save_report(
        "history-http-smoke",
        values,
        time.perf_counter() - started,
        errors,
        {
            "requests": args.requests,
            "returned_rows_last_request": rows,
            "query_window": "last hour, at most 200 observations",
            "measurement": "client HTTP RTT, not raw SQL time",
        },
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--requests", type=int, default=20)
    args = p.parse_args()
    if not 1 <= args.requests <= 10000:
        p.error("Use 1-10000 requests")
    asyncio.run(run(args))
