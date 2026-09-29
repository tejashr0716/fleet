"""End-to-end latency benchmark measuring emitted_at to WebSocket receipt across 200 subscribers."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

import numpy as np
import websockets

logger = logging.getLogger("bench.e2e")
LATENCIES_MS: list[float] = []


async def subscriber_client(
    client_id: int, uri: str, stop_event: asyncio.Event, target_samples: int
) -> None:
    """Hold a single WebSocket subscriber and record end-to-end event latencies."""
    try:
        async with websockets.connect(uri) as ws:
            # Subscribe to Bengaluru area bounding box
            await ws.send(
                json.dumps(
                    {
                        "action": "subscribe",
                        "bbox": [77.40, 12.75, 77.85, 13.15],
                        "vehicle_ids": [],
                    }
                )
            )

            while not stop_event.is_set():
                if len(LATENCIES_MS) >= target_samples:
                    stop_event.set()
                    break

                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    msg = json.loads(raw_msg)
                    if msg.get("type") == "position":
                        emitted = msg["data"].get("emitted_at")
                        if emitted:
                            emitted_dt = datetime.fromisoformat(emitted)
                            if emitted_dt.tzinfo is None:
                                emitted_dt = emitted_dt.replace(tzinfo=UTC)
                            received_dt = datetime.now(tz=UTC)
                            diff_ms = (received_dt - emitted_dt).total_seconds() * 1000.0
                            if diff_ms >= 0:
                                LATENCIES_MS.append(diff_ms)
                except TimeoutError:
                    continue
    except Exception as exc:
        logger.debug("Client %d disconnected: %s", client_id, exc)


async def main() -> None:
    """Run 200 concurrent WebSocket subscribers and calculate latency percentiles."""
    target_samples = 10000
    concurrent_clients = 200
    uri = "ws://localhost:8000/ws/live"

    print("================================================================================")
    print(f" FLEET E2E LATENCY BENCHMARK: Holding {concurrent_clients} WebSocket clients")
    print(f" Target sample count: {target_samples} events")
    print("================================================================================")

    stop_event = asyncio.Event()
    tasks = [
        asyncio.create_task(subscriber_client(i, uri, stop_event, target_samples=target_samples))
        for i in range(concurrent_clients)
    ]

    try:
        await asyncio.wait_for(stop_event.wait(), timeout=120.0)
    except TimeoutError:
        print("[Benchmark] Completed with available samples collected before timeout.")
    finally:
        stop_event.set()
        for t in tasks:
            t.cancel()

    if not LATENCIES_MS:
        print("No telemetry samples received. Ensure API and simulator/worker are active.")
        return

    sample_count = len(LATENCIES_MS)
    p50 = float(np.percentile(LATENCIES_MS, 50))
    p90 = float(np.percentile(LATENCIES_MS, 90))
    p95 = float(np.percentile(LATENCIES_MS, 95))
    p99 = float(np.percentile(LATENCIES_MS, 99))

    print(f"Collected {sample_count} samples across {concurrent_clients} concurrent sockets.")
    print("| Metric   | Value (ms) | Target (ms) |")
    print("|----------|------------|-------------|")
    print(f"| p50      | {p50:6.2f}     | < 100.00    |")
    print(f"| p90      | {p90:6.2f}     | < 200.00    |")
    print(f"| p95      | {p95:6.2f}     | < 250.00    |")
    print(f"| p99      | {p99:6.2f}     | < 350.00    |")


if __name__ == "__main__":
    asyncio.run(main())
