# System Architecture & Delivery Semantics

## Architecture Overview

Fleet is an asynchronous, high-throughput real-time telemetry processing platform designed to track 1,000+ continuous moving assets with sub-250ms end-to-end fan-out latency.

```
                                  +-----------------------+
                                  | Telemetry Ingest      |
                                  | (HTTP /ws/ingest)     |
                                  +-----------+-----------+
                                              |
                                              | XADD (Non-blocking)
                                              v
                                  +-----------------------+
                                  | Redis 7 Streams       |
                                  | stream:positions      |
                                  +-----------+-----------+
                                              |
                                              | XREADGROUP (Consumer Group: cg:positions)
                                              v
                              +-------------------------------+
                              | Micro-batch Worker            |
                              | (Batch <= 500 or 200ms)       |
                              +---------------+---------------+
                                              |
               +------------------------------+-------------------------------+
               |                                                              |
               v                                                              v
+-------------------------------+                            +-------------------------------+
| TimescaleDB (PostgreSQL 16)   |                            | Redis In-Memory State         |
| - Hypertable 'positions'      |                            | - HSET fleet:live:{id}        |
| - 1-min & 1-hour Aggregates   |                            | - GEOADD fleet:geo            |
| - Chunk Compression & Pruning |                            | - PUBLISH fleet:events        |
+-------------------------------+                            +---------------+---------------+
               | (Commit Success)                                             |
               v                                                              v
      +-----------------+                                    +--------------------------------+
      | XACK Stream Msg |                                    | API Pub/Sub Listener Lifespan  |
      +-----------------+                                    +---------------+----------------+
                                                                             |
                                                                             | Spatial Bbox Filter
                                                                             v
                                                              +-------------------------------+
                                                              | WebSocket Broadcast (/ws/live)|
                                                              | Leaflet Browser Map Client    |
                                                              +-------------------------------+
```

## Delivery Semantics: At-Least-Once with Idempotency

### Why not Exactly-Once?
In distributed streaming pipelines (specifically network ingest via HTTP/WebSockets through Redis Streams to a relational database), true "exactly-once" delivery across independent distributed state boundaries is impossible without expensive two-phase commits (2PC) that destroy high-throughput real-time streaming SLAs.

### How At-Least-Once Delivery is Guaranteed
1. **Redis Streams Ingress**: Incoming telemetry is assigned an immutable, monotonically increasing millisecond sequence ID (e.g. `1700000000000-0`) upon `XADD`.
2. **Consumer Group Tracking**: The consumer worker reads messages via `XREADGROUP`. Messages remain in the Pending Entries List (PEL) until explicitly acknowledged.
3. **Commit-Before-Ack**: The worker executes database insert operations and flushes state **before** invoking `XACK`. If the worker crashes mid-batch, the unacknowledged messages are reclaimed by `workers/reclaimer.py` via `XAUTOCLAIM`.

### Achieving Pure Idempotency
Because re-delivery can occur if a worker crashes post-database-commit but prior to `XACK`, idempotency is enforced at the database storage engine:
```sql
ALTER TABLE positions ADD PRIMARY KEY (vehicle_id, time);

INSERT INTO positions (vehicle_id, time, lat, lon, speed_kmh, heading, accuracy_m, h3_r8, h3_r7)
VALUES (:vehicle_id, :time, :lat, :lon, :speed_kmh, :heading, :accuracy_m, :h3_r8, :h3_r7)
ON CONFLICT (vehicle_id, time) DO NOTHING;
```
If a batch or single message is processed multiple times:
- Database row count remains strictly invariant (`ON CONFLICT DO NOTHING`).
- Redis Hashes (`fleet:live:{id}`) update in-place with idempotent state replacements.
- Re-broadcasting over WebSocket triggers client coordinate overwrites with identical timestamps.

## Dead Letter Queue (DLQ) & Failure Recovery
- `workers/reclaimer.py` monitors messages pending for more than 60 seconds.
- Every claim increments a message-specific retry key: `fleet:retry:<msg_id>`.
- If a corrupted or poisoned message fails 5 consecutive times, it is permanently shifted to `stream:positions:dlq`, acknowledged, and deleted from the active pipeline to prevent stream starvation.
