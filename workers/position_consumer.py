"""Redis Streams micro-batch consumer pipeline committing to TimescaleDB and fan-out."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import AsyncSessionLocal
from app.models.alert import Alert
from app.models.geofence import Geofence, GeofenceEvent, GeofenceEventKind
from app.redis_client import get_redis_client
from app.services.alerts import evaluate_speeding, generate_signal_lost_alert
from app.services.geofence import latlng_to_h3_int

logger = logging.getLogger("fleet.worker")


@dataclass
class BatchResult:
    """Telemetry micro-batch execution outcome metrics."""

    processed_count: int
    db_duration_ms: float
    geofence_eval_ms: float


async def ensure_consumer_group(redis: Redis) -> None:
    """Ensure the target Redis Stream and consumer group exist.

    Args:
        redis: Active Redis connection.
    """
    try:
        await redis.xgroup_create(
            name=settings.stream_name,
            groupname=settings.consumer_group,
            id="0",
            mkstream=True,
        )
        logger.info(
            "Created consumer group '%s' on stream '%s'",
            settings.consumer_group,
            settings.stream_name,
        )
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            logger.warning("Consumer group creation notice: %s", exc)


async def process_batch(
    messages: list[tuple[str, dict[str, str]]],
    session: AsyncSession,
    redis: Redis,
    geofence_cache: list[Geofence],
) -> BatchResult:
    """Process a micro-batch of telemetry records from Redis Streams.

    Delivery semantics:
        At-least-once delivery guaranteed by Redis Streams consumer groups.
        Processing is rendered strictly idempotent via the (vehicle_id, time)
        composite primary key in the positions hypertable, ensuring replayed
        messages cause zero duplicates via ON CONFLICT DO NOTHING.
        XACK is issued strictly after the database transaction successfully commits.

    Args:
        messages: List of (stream_message_id, field_dict) pairs.
        session: Active SQLAlchemy database session.
        redis: Active Redis client.
        geofence_cache: Cached active geofence geometries.

    Returns:
        BatchResult: Metrics on processed count and execution durations.
    """
    if not messages:
        return BatchResult(processed_count=0, db_duration_ms=0.0, geofence_eval_ms=0.0)

    parsed_rows: list[dict[str, Any]] = []
    stream_msg_ids: list[str] = []
    alerts_to_insert: list[Alert] = []
    geofence_events_to_insert: list[GeofenceEvent] = []

    # 1. Parse fields & compute H3 resolutions
    for msg_id, fields in messages:
        stream_msg_ids.append(msg_id)
        try:
            v_id = int(fields["vehicle_id"])
            lat = float(fields["lat"])
            lon = float(fields["lon"])
            speed = float(fields["speed_kmh"])
            heading = int(fields["heading"])
            accuracy = float(fields["accuracy_m"])
            ts_str = fields["time"]
            ts = datetime.fromisoformat(ts_str) if isinstance(ts_str, str) else ts_str
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            emitted_at = fields.get("emitted_at", datetime.now(tz=UTC).isoformat())

            r8_cell = latlng_to_h3_int(lat, lon, 8)
            r7_cell = latlng_to_h3_int(lat, lon, 7)

            parsed_rows.append(
                {
                    "vehicle_id": v_id,
                    "time": ts,
                    "lat": lat,
                    "lon": lon,
                    "speed_kmh": speed,
                    "heading": heading,
                    "accuracy_m": accuracy,
                    "h3_r8": r8_cell,
                    "h3_r7": r7_cell,
                    "emitted_at": emitted_at,
                }
            )
        except Exception as exc:
            logger.error("Failed to parse stream record %s: %s", msg_id, exc)

    if not parsed_rows:
        return BatchResult(processed_count=0, db_duration_ms=0.0, geofence_eval_ms=0.0)

    # 2. Evaluate Geofence Transitions & Rules
    geo_start = time.perf_counter()

    pipe = redis.pipeline()
    for row in parsed_rows:
        pipe.hget(f"fleet:live:{row['vehicle_id']}", "h3_r8")
    prev_h3_results = await pipe.execute()

    for idx, row in enumerate(parsed_rows):
        prev_hex = prev_h3_results[idx]
        prev_cell = int(prev_hex, 16) if prev_hex else None
        curr_cell = row["h3_r8"]

        for gf in geofence_cache:
            in_current = curr_cell in gf.h3_cells
            in_prev = prev_cell in gf.h3_cells if prev_cell else False

            if in_current and not in_prev:
                geofence_events_to_insert.append(
                    GeofenceEvent(
                        vehicle_id=row["vehicle_id"],
                        geofence_id=gf.id,
                        event=GeofenceEventKind.ENTER,
                        time=row["time"],
                    )
                )
            elif in_prev and not in_current:
                geofence_events_to_insert.append(
                    GeofenceEvent(
                        vehicle_id=row["vehicle_id"],
                        geofence_id=gf.id,
                        event=GeofenceEventKind.EXIT,
                        time=row["time"],
                    )
                )

        # Speeding rule
        speed_alert = evaluate_speeding(
            vehicle_id=row["vehicle_id"],
            speed_kmh=row["speed_kmh"],
            limit_kmh=settings.speed_limit_kmh,
            ts=row["time"],
        )
        if speed_alert:
            alerts_to_insert.append(speed_alert)

    geo_duration_ms = (time.perf_counter() - geo_start) * 1000.0

    # 3. Multi-row INSERT with ON CONFLICT DO NOTHING
    db_start = time.perf_counter()
    insert_sql = text("""
        INSERT INTO positions (
            vehicle_id, time, lat, lon, speed_kmh, heading, accuracy_m, h3_r8, h3_r7
        ) VALUES (
            :vehicle_id, :time, :lat, :lon, :speed_kmh, :heading, :accuracy_m, :h3_r8, :h3_r7
        ) ON CONFLICT (vehicle_id, time) DO NOTHING;
    """)

    db_params = [
        {
            "vehicle_id": r["vehicle_id"],
            "time": r["time"],
            "lat": r["lat"],
            "lon": r["lon"],
            "speed_kmh": r["speed_kmh"],
            "heading": r["heading"],
            "accuracy_m": r["accuracy_m"],
            "h3_r8": r["h3_r8"],
            "h3_r7": r["h3_r7"],
        }
        for r in parsed_rows
    ]

    await session.execute(insert_sql, db_params)

    if alerts_to_insert:
        session.add_all(alerts_to_insert)
    if geofence_events_to_insert:
        session.add_all(geofence_events_to_insert)

    # Commit DB transaction
    await session.commit()
    db_duration_ms = (time.perf_counter() - db_start) * 1000.0

    # 4. Redis live state updates, Pub/Sub fan-out, and XACK
    r_pipe = redis.pipeline()
    for row in parsed_rows:
        v_key = f"fleet:live:{row['vehicle_id']}"
        mapping = {
            "vehicle_id": str(row["vehicle_id"]),
            "lat": str(row["lat"]),
            "lon": str(row["lon"]),
            "speed_kmh": str(row["speed_kmh"]),
            "heading": str(row["heading"]),
            "h3_r8": hex(row["h3_r8"])[2:],
            "ts": row["time"].isoformat(),
            "last_seen": str(datetime.now(tz=UTC).timestamp()),
        }
        r_pipe.hset(v_key, mapping=mapping)
        r_pipe.geoadd("fleet:geo", (row["lon"], row["lat"], str(row["vehicle_id"])))

        # Fan-out to WebSocket clients
        pos_event = json.dumps(
            {
                "type": "position",
                "data": {
                    "vehicle_id": row["vehicle_id"],
                    "lat": row["lat"],
                    "lon": row["lon"],
                    "speed_kmh": row["speed_kmh"],
                    "heading": row["heading"],
                    "h3_r8": hex(row["h3_r8"])[2:],
                    "ts": row["time"].isoformat(),
                    "emitted_at": row["emitted_at"],
                },
            }
        )
        r_pipe.publish("fleet:events", pos_event)

    for alert in alerts_to_insert:
        r_pipe.publish(
            "fleet:events",
            json.dumps(
                {
                    "type": "alert",
                    "data": {
                        "vehicle_id": alert.vehicle_id,
                        "kind": alert.kind.value,
                        "severity": alert.severity.value,
                        "payload": alert.payload,
                        "time": alert.time.isoformat(),
                    },
                }
            ),
        )

    for ge in geofence_events_to_insert:
        r_pipe.publish(
            "fleet:events",
            json.dumps(
                {
                    "type": "geofence_event",
                    "data": {
                        "vehicle_id": ge.vehicle_id,
                        "geofence_id": ge.geofence_id,
                        "event": ge.event.value,
                        "time": ge.time.isoformat(),
                    },
                }
            ),
        )

    # 5. XACK strictly after DB commit succeeded
    r_pipe.xack(settings.stream_name, settings.consumer_group, *stream_msg_ids)
    await r_pipe.execute()

    return BatchResult(
        processed_count=len(parsed_rows),
        db_duration_ms=db_duration_ms,
        geofence_eval_ms=geo_duration_ms,
    )


async def sweep_signal_lost(redis: Redis, session: AsyncSession) -> None:
    """Sweep active vehicle hashes in Redis and generate alert if silence exceeds TTL."""
    try:
        keys = [k async for k in redis.scan_iter("fleet:live:*")]
        if not keys:
            return

        now_ts = datetime.now(tz=UTC).timestamp()
        pipe = redis.pipeline()
        for k in keys:
            pipe.hgetall(k)
        vehicles = await pipe.execute()

        lost_alerts: list[Alert] = []
        for v in vehicles:
            if not v or "last_seen" not in v:
                continue
            last_seen = float(v["last_seen"])
            silence = now_ts - last_seen
            if silence > settings.signal_lost_ttl_seconds:
                # Check if already alerted recently
                v_id = int(v["vehicle_id"])
                lost_key = f"fleet:lost:{v_id}"
                if not await redis.exists(lost_key):
                    await redis.set(lost_key, "1", ex=60)
                    lost_alert = generate_signal_lost_alert(
                        vehicle_id=v_id,
                        silence_seconds=silence,
                        ts=datetime.now(tz=UTC),
                    )
                    lost_alerts.append(lost_alert)

        if lost_alerts:
            session.add_all(lost_alerts)
            await session.commit()
            for la in lost_alerts:
                await redis.publish(
                    "fleet:events",
                    json.dumps(
                        {
                            "type": "alert",
                            "data": {
                                "vehicle_id": la.vehicle_id,
                                "kind": la.kind.value,
                                "severity": la.severity.value,
                                "payload": la.payload,
                                "time": la.time.isoformat(),
                            },
                        }
                    ),
                )
    except Exception as exc:
        logger.error("Signal lost sweep error: %s", exc)


async def run_worker() -> None:
    """Main execution loop for the background consumer worker."""
    redis = get_redis_client()
    await ensure_consumer_group(redis)
    logger.info("Worker started listening on stream '%s'...", settings.stream_name)

    geofence_cache: list[Geofence] = []
    last_sweep = time.perf_counter()

    async with AsyncSessionLocal() as session:
        stmt = text(
            "SELECT id, name, kind, geojson, h3_resolution, h3_cells, created_at FROM geofences"
        )
        try:
            res = await session.execute(stmt)
            geofence_cache = [
                Geofence(
                    id=r.id,
                    name=r.name,
                    kind=r.kind,
                    geojson=r.geojson,
                    h3_resolution=r.h3_resolution,
                    h3_cells=r.h3_cells,
                    created_at=r.created_at,
                )
                for r in res.fetchall()
            ]
        except Exception:
            geofence_cache = []

    while True:
        try:
            # Micro-batch read: up to BATCH_MAX_SIZE or block up to BATCH_MAX_WAIT_MS
            raw_entries = await redis.xreadgroup(
                groupname=settings.consumer_group,
                consumername=settings.consumer_name,
                streams={settings.stream_name: ">"},
                count=settings.batch_max_size,
                block=settings.batch_max_wait_ms,
            )

            if raw_entries:
                for _stream_name, messages in raw_entries:
                    if messages:
                        async with AsyncSessionLocal() as session:
                            res = await process_batch(messages, session, redis, geofence_cache)
                            stream_len = await redis.xlen(settings.stream_name)
                            logger.info(
                                "Batch: %d items | DB: %.2fms | Geofence: %.2fms | Backlog Lag: %d",
                                res.processed_count,
                                res.db_duration_ms,
                                res.geofence_eval_ms,
                                stream_len,
                            )

            # Signal lost sweep every 10 seconds
            if time.perf_counter() - last_sweep > 10.0:
                async with AsyncSessionLocal() as session:
                    await sweep_signal_lost(redis, session)
                last_sweep = time.perf_counter()

        except Exception as exc:
            logger.exception("Exception in worker main loop: %s", exc)
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(run_worker())
