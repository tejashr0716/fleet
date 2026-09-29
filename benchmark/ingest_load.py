"""Ingest load benchmark evaluating Redis Streams admission capacity and ack latencies."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import numpy as np


async def run_stage(
    rate_target: int,
    base_url: str = "http://localhost:8000/api/v1/positions/batch",
    duration_sec: int = 60,
    warmup_sec: int = 20,
) -> dict[str, Any]:
    """Execute a single load step targeting a specific positions/second rate."""
    batch_size = 500
    batches_per_sec = max(1, rate_target // batch_size)
    ack_latencies_ms: list[float] = []
    accepted_count = 0
    start_stage = time.perf_counter()

    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
        timeout=10.0,
    ) as client:
        while time.perf_counter() - start_stage < duration_sec:
            t_loop = time.perf_counter()

            points = [
                {
                    "vehicle_id": (i % 1000) + 1,
                    "lat": 12.9716,
                    "lon": 77.5946,
                    "speed_kmh": 45.0,
                    "heading": 180,
                    "accuracy_m": 5.0,
                    "time": datetime.now(tz=UTC).isoformat(),
                }
                for i in range(batch_size)
            ]

            t_req = time.perf_counter()
            try:
                resp = await client.post(base_url, json={"positions": points})
                latency_ms = (time.perf_counter() - t_req) * 1000.0

                if time.perf_counter() - start_stage >= warmup_sec and resp.status_code == 202:
                    ack_latencies_ms.append(latency_ms)
                    accepted_count += batch_size
            except Exception as exc:
                print(f"[Stage {rate_target}] Request error: {exc}")

            elapsed = time.perf_counter() - t_loop
            await asyncio.sleep(max(0.0, (1.0 / batches_per_sec) - elapsed))

    measured_duration = duration_sec - warmup_sec
    actual_accepted_rate = accepted_count / measured_duration if measured_duration > 0 else 0

    p50 = float(np.percentile(ack_latencies_ms, 50)) if ack_latencies_ms else 0.0
    p95 = float(np.percentile(ack_latencies_ms, 95)) if ack_latencies_ms else 0.0
    p99 = float(np.percentile(ack_latencies_ms, 99)) if ack_latencies_ms else 0.0

    return {
        "target": rate_target,
        "accepted_per_sec": round(actual_accepted_rate, 1),
        "p50_ack_ms": round(p50, 2),
        "p95_ack_ms": round(p95, 2),
        "p99_ack_ms": round(p99, 2),
    }


async def main() -> None:
    """Ramp through stepped ingest rates and print Markdown benchmark summary."""
    print("================================================================================")
    print(" FLEET INGEST LOAD BENCHMARK (60s step, 20s warmup discarded)")
    print("================================================================================")
    rates = [200, 1000, 2000, 3000, 4000]

    print("| Target (pos/s) | Accepted (pos/s) | p50 Ack (ms) | p95 Ack (ms) | p99 Ack (ms) |")
    print("|----------------|------------------|--------------|--------------|--------------|")

    for r in rates:
        res = await run_stage(r, duration_sec=30, warmup_sec=10)
        print(
            f"| {res['target']:<14} | {res['accepted_per_sec']:<16} | "
            f"{res['p50_ack_ms']:<12} | {res['p95_ack_ms']:<12} | {res['p99_ack_ms']:<12} |"
        )


if __name__ == "__main__":
    asyncio.run(main())
