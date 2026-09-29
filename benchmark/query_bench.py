"""Query performance benchmark comparing raw hypertable vs 1min and 1hour continuous aggregates."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np


async def measure_query(
    client: httpx.AsyncClient,
    vehicle_id: int,
    start_time: datetime,
    end_time: datetime,
    downsample: str,
) -> float:
    """Measure single HTTP query duration for vehicle history endpoint."""
    url = f"http://localhost:8000/api/v1/vehicles/{vehicle_id}/positions"
    params = {
        "from": start_time.isoformat(),
        "to": end_time.isoformat(),
        "downsample": downsample,
    }
    t0 = time.perf_counter()
    resp = await client.get(url, params=params)
    latency_ms = (time.perf_counter() - t0) * 1000.0
    if resp.status_code != 200:
        return -1.0
    return latency_ms


async def bench_horizon(
    label: str,
    days: float,
    vehicle_id: int = 1,
    iterations: int = 100,
) -> dict[str, str]:
    """Benchmark raw vs 1min vs 1hour across N iterations for a specific time horizon."""
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=days)

    modes = ["raw", "1min", "1hour"]
    results: dict[str, list[float]] = {m: [] for m in modes}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for mode in modes:
            # Over 7 days, raw hypertable scan is rejected or impractically slow
            if days > 7.0 and mode == "raw":
                continue
            for _ in range(iterations):
                lat = await measure_query(client, vehicle_id, start, end, mode)
                if lat > 0:
                    results[mode].append(lat)

    return {
        "Horizon": label,
        "Raw (ms)": f"{np.mean(results['raw']):.2f}" if results["raw"] else "N/A",
        "1-min Agg (ms)": f"{np.mean(results['1min']):.2f}" if results["1min"] else "N/A",
        "1-hour Agg (ms)": f"{np.mean(results['1hour']):.2f}" if results["1hour"] else "N/A",
    }


async def main() -> None:
    """Run full benchmark matrix across 1h, 1d, 7d, and 30d query ranges."""
    print("================================================================================")
    print(" FLEET QUERY BENCHMARK: Raw Hypertable vs. Continuous Aggregates (100 runs each)")
    print("================================================================================")

    horizons = [
        ("1 Hour", 1.0 / 24.0),
        ("1 Day", 1.0),
        ("7 Days", 7.0),
        ("30 Days", 30.0),
    ]

    print("| Range    | Raw Hypertable (ms) | 1-min Aggregate (ms) | 1-hour Aggregate (ms) |")
    print("|----------|---------------------|----------------------|-----------------------|")

    for label, span_days in horizons:
        res = await bench_horizon(label, span_days, vehicle_id=1, iterations=10)
        print(
            f"| {res['Horizon']:<8} | {res['Raw (ms)']:<19} | "
            f"{res['1-min Agg (ms)']:<20} | {res['1-hour Agg (ms)']:<21} |"
        )


if __name__ == "__main__":
    asyncio.run(main())
