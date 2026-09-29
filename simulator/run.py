"""Deterministic telemetry simulator generating realistic multi-vehicle Bengaluru traces."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import websockets


def interpolate_segment(
    p1: list[float], p2: list[float], fraction: float
) -> tuple[float, float, int]:
    """Linearly interpolate coordinates along a route segment and calculate bearing."""
    lat = p1[0] + (p2[0] - p1[0]) * fraction
    lon = p1[1] + (p2[1] - p1[1]) * fraction
    dlat = p2[0] - p1[0]
    dlon = p2[1] - p1[1]
    heading = int((math.degrees(math.atan2(dlon, dlat)) + 360) % 360)
    return lat, lon, heading


class SimulatedVehicle:
    """Individual simulated vehicle moving along a fixed polyline route."""

    def __init__(self, vehicle_id: int, route: list[list[float]], seed: int) -> None:
        self.vehicle_id = vehicle_id
        self.route = route
        self.rng = random.Random(seed + vehicle_id)
        self.current_idx = self.rng.randint(0, max(0, len(route) - 2))
        self.fraction = self.rng.random()
        self.base_speed = self.rng.uniform(35.0, 75.0)

    def step(self, delta_sec: float) -> dict[str, Any] | None:
        """Advance vehicle state by delta_sec, returning telemetry or None on dropout."""
        # 0.5% chance of signal dropout to exercise signal_lost alerts
        if self.rng.random() < 0.005:
            return None

        # 5% chance of stopping at traffic signal
        speed = 0.0 if self.rng.random() < 0.05 else max(5.0, self.rng.gauss(self.base_speed, 8.0))

        step_dist_km = (speed / 3600.0) * delta_sec
        # Approximate 1 deg latitude as ~111 km
        step_fraction = (step_dist_km / 111.0) * 8.0
        self.fraction += step_fraction

        if self.fraction >= 1.0:
            self.fraction = 0.0
            self.current_idx = (self.current_idx + 1) % (len(self.route) - 1)

        p1 = self.route[self.current_idx]
        p2 = self.route[self.current_idx + 1]
        lat, lon, heading = interpolate_segment(p1, p2, self.fraction)

        return {
            "vehicle_id": self.vehicle_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "speed_kmh": round(speed, 1),
            "heading": heading,
            "accuracy_m": 4.5,
            "time": datetime.now(tz=UTC).isoformat(),
        }


async def run_simulator(
    vehicles_count: int,
    rate_multiplier: float,
    transport: str,
    target_url: str,
    seed: int,
) -> None:
    """Run the main simulation loop pushing telemetry batches."""
    routes_file = Path(__file__).resolve().parent / "routes.json"
    with open(routes_file, encoding="utf-8") as f:
        routes_data = json.load(f)

    vehicles = [
        SimulatedVehicle(
            vehicle_id=i,
            route=routes_data[i % len(routes_data)]["coordinates"],
            seed=seed,
        )
        for i in range(1, vehicles_count + 1)
    ]

    interval_sec = 5.0 / max(0.1, rate_multiplier)
    print(
        f"[Simulator] Initialized {vehicles_count} vehicles. Transport: {transport.upper()}, "
        f"Step interval: {interval_sec:.2f}s"
    )

    if transport == "http":
        async with httpx.AsyncClient(
            limits=httpx.Limits(max_connections=50), timeout=15.0
        ) as client:
            while True:
                start_loop = asyncio.get_event_loop().time()
                points: list[dict[str, Any]] = []

                for v in vehicles:
                    pt = v.step(interval_sec)
                    if pt:
                        points.append(pt)

                # Send in micro-batches of up to 500
                for i in range(0, len(points), 500):
                    batch = points[i : i + 500]
                    try:
                        resp = await client.post(target_url, json={"positions": batch})
                        if resp.status_code != 202:
                            print(f"[Simulator] Ingest returned status {resp.status_code}")
                    except Exception as exc:
                        print(f"[Simulator] Request error: {exc}")

                elapsed = asyncio.get_event_loop().time() - start_loop
                await asyncio.sleep(max(0.0, interval_sec - elapsed))

    elif transport == "ws":
        ws_url = target_url.replace("http://", "ws://").replace("https://", "wss://")
        if "/api/v1/positions/batch" in ws_url:
            ws_url = ws_url.replace("/api/v1/positions/batch", "/ws/ingest")

        while True:
            try:
                async with websockets.connect(ws_url) as ws:
                    print(f"[Simulator] Connected to WebSocket ingest at {ws_url}")
                    while True:
                        start_loop = asyncio.get_event_loop().time()
                        for v in vehicles:
                            pt = v.step(interval_sec)
                            if pt:
                                await ws.send(json.dumps(pt))
                                await ws.recv()
                        elapsed = asyncio.get_event_loop().time() - start_loop
                        await asyncio.sleep(max(0.0, interval_sec - elapsed))
            except Exception as exc:
                print(f"[Simulator] WebSocket disconnect: {exc}. Retrying in 3s...")
                await asyncio.sleep(3.0)


def main() -> None:
    """Entry point for running the telemetry simulator CLI."""
    parser = argparse.ArgumentParser(
        description="Deterministic Bengaluru Fleet Telemetry Simulator"
    )
    parser.add_argument(
        "--vehicles",
        type=int,
        default=1000,
        help="Number of concurrent vehicles to simulate",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=1.0,
        help="Rate speedup multiplier (1.0 = 5s ping baseline)",
    )
    parser.add_argument(
        "--transport",
        choices=["http", "ws"],
        default="http",
        help="Ingest transport protocol",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/api/v1/positions/batch",
        help="Target ingest API URL",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic pseudo-random seed",
    )

    args = parser.parse_args()
    asyncio.run(
        run_simulator(
            vehicles_count=args.vehicles,
            rate_multiplier=args.rate,
            transport=args.transport,
            target_url=args.url,
            seed=args.seed,
        )
    )


if __name__ == "__main__":
    main()
