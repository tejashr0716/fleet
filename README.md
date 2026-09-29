# Fleet — Real-Time Telemetry & Geospatial Tracking Platform

[![Fleet CI](https://github.com/tejashr0716/fleet/actions/workflows/ci.yml/badge.svg)](https://github.com/tejashr0716/fleet/actions/workflows/ci.yml)
[![Deploy Frontend](https://github.com/tejashr0716/fleet/actions/workflows/pages.yml/badge.svg)](https://github.com/tejashr0716/fleet/actions/workflows/pages.yml)

> **Live Demo:** [https://tejashr0716.github.io/fleet/](https://tejashr0716.github.io/fleet/)  
> **Source Repository:** [https://github.com/tejashr0716/fleet](https://github.com/tejashr0716/fleet)

---

## Why This Is Interesting

Most real-time tracking architectures either collapse under write pressure because every telemetry ping executes a synchronous database write, or they introduce excessive infrastructure bloat (Kafka, Kubernetes, Celery, Spark) that no engineer can realistically defend or tune single-handedly. **Fleet** solves both problems cleanly: HTTP/WebSocket ingress writes directly to **Redis Streams** in sub-millisecond memory without touching the database. An asynchronous micro-batch worker then pulls batches of up to 500 points, computes **Uber H3 spatial cells (r7 and r8)**, evaluates complex geofences via constant-time array/set membership, persists multi-row records into a **TimescaleDB hypertable** using idempotent upserts, and fans out live coordinates via Redis Pub/Sub to WebSockets filtered by each browser client's active bounding box.

The entire system sustains over **2,000 positions/second** with an end-to-end **p95 latency under 120 ms**, compresses time-series chunks by **11.6x**, and prunes historical hypertable partitions so a 30-day vehicle history query returns in **under 1 ms**.

---

## Architecture

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

---

## Key Performance Numbers

> *Note: Benchmark numbers are measured against local Docker containers running TimescaleDB and Redis 7 on Apple Silicon. The free hosting tier sleeps on inactivity.*

| Metric | Target | Measured Result | Benchmark Script |
|---|---|---|---|
| **Concurrent Vehicles** | 1,000 active | **1,000 sustained (10 min)** | `simulator/run.py --vehicles 1000` |
| **Sustained Ingest** | ≥ 2,000 pos/s | **3,892 pos/s ceiling** | `benchmark/ingest_load.py` |
| **End-to-End Latency (p95)** | < 250 ms | **112.4 ms** | `benchmark/e2e_latency.py` (200 WS sockets) |
| **Concurrent WebSockets** | 200 sockets | **200 held concurrently** | `benchmark/e2e_latency.py` |
| **Geofence Evaluation** | < 5 ms / pos | **1.8 ms p95 per batch** | Worker instrumentation |
| **30-Day History Query** | < 150 ms | **0.48 ms** | `benchmark/query_bench.py` (1-hour agg) |
| **Hypertable Compression** | > 5x | **11.6x (91.4% space saved)** | `hypertable_compression_stats()` |

---

## Local Setup in 5 Commands

```bash
# 1. Clone repository
git clone https://github.com/tejashr0716/fleet.git && cd fleet

# 2. Boot TimescaleDB, Redis, API, and Worker services
make up

# 3. Run database migrations
make migrate

# 4. Seed 1,000 vehicles into the database
make seed

# 5. Launch Bengaluru traffic simulator (1,000 vehicles)
make sim
```

Open your browser to `http://localhost:8000/static/index.html` to see 1,000 vehicles moving smoothly across Bengaluru with live speed sparklines and H3 heatmap density.

---

## Environment Variables (`.env`)

All configurations are handled via `pydantic-settings` in `app/config.py`:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/fleet` | Async SQLAlchemy database URI |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 7 connection URI |
| `CORS_ORIGINS` | `https://tejashr0716.github.io` | Comma-separated allowed HTTP origins |
| `WS_ALLOWED_ORIGINS`| `https://tejashr0716.github.io` | Comma-separated allowed WebSocket origins |
| `STREAM_NAME` | `stream:positions` | Key name for the ingest stream |
| `CONSUMER_GROUP` | `cg:positions` | Redis Streams consumer group |
| `BATCH_MAX_SIZE` | `500` | Maximum messages per micro-batch |
| `BATCH_MAX_WAIT_MS`| `200` | Maximum millisecond wait before batch dispatch |
| `H3_RESOLUTION` | `8` | Spatial indexing resolution (~460m edge length) |
| `SPEED_LIMIT_KMH` | `80.0` | Threshold triggering automated speeding alerts |
| `SIGNAL_LOST_TTL_SECONDS` | `30` | Silence duration before marking signal lost |
| `MAX_WS_CONNECTIONS`| `5000` | Max concurrent WebSocket connections allowed |
| `CONSUMER_LAG_UNHEALTHY` | `10000` | Backlog threshold causing `/health` to return 503 |
| `POSITION_RETENTION_DAYS` | `30` | Retention window for raw telemetry chunks |

---

## REST API Reference

Every failure response returns the standard envelope:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Vehicle '9999' was not found",
    "details": {"resource": "Vehicle", "identifier": "9999"}
  }
}
```

### 1. Ingest Batch Telemetry
`POST /api/v1/positions/batch` (Status: 202 Accepted)
```bash
curl -X POST http://localhost:8000/api/v1/positions/batch \
  -H "Content-Type: application/json" \
  -d '{
    "positions": [
      {
        "vehicle_id": 1,
        "lat": 12.9716,
        "lon": 77.5946,
        "speed_kmh": 45.2,
        "heading": 180,
        "accuracy_m": 4.5,
        "time": "2026-09-30T08:00:00Z"
      }
    ]
  }'
```
Response:
```json
{
  "status": "accepted",
  "count": 1,
  "stream_ids": ["1759190400000-0"]
}
```

### 2. Vehicle History Query (Auto Downsampling)
`GET /api/v1/vehicles/1/positions?from=2026-09-01T00:00:00Z&to=2026-09-30T00:00:00Z&downsample=auto`
```bash
curl "http://localhost:8000/api/v1/vehicles/1/positions?from=2026-09-01T00:00:00Z&to=2026-09-30T00:00:00Z&downsample=auto"
```
Response:
```json
{
  "source_used": "positions_1hour (hierarchical continuous aggregate)",
  "points": [
    {
      "vehicle_id": 1,
      "time": "2026-09-01T00:00:00Z",
      "lat": 12.9172,
      "lon": 77.6228,
      "speed_kmh": 42.5,
      "point_count": 720
    }
  ]
}
```

### 3. Create Geofence (Polyfilled to H3)
`POST /api/v1/geofences` (Status: 201 Created)
```bash
curl -X POST http://localhost:8000/api/v1/geofences \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Koramangala Commercial Hub",
    "kind": "polygon",
    "geojson": {
      "type": "Polygon",
      "coordinates": [[[77.61, 12.93], [77.63, 12.93], [77.63, 12.95], [77.61, 12.95], [77.61, 12.93]]]
    },
    "h3_resolution": 8
  }'
```
Response:
```json
{
  "id": 1,
  "name": "Koramangala Commercial Hub",
  "kind": "polygon",
  "h3_resolution": 8,
  "h3_cells": [613941295947775999, 613941295947776000],
  "created_at": "2026-09-30T08:00:00Z"
}
```

### 4. Health Check with Consumer Lag
`GET /api/v1/health`
```bash
curl http://localhost:8000/api/v1/health
```
Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "consumer_lag": 0
}
```

---

## WebSocket Protocol (`/ws/live`)

### Client → Server Frames
```json
// Bounding box subscription (lon_min, lat_min, lon_max, lat_max)
{"action": "subscribe", "bbox": [77.50, 12.85, 77.75, 13.05], "vehicle_ids": []}

// Heartbeat ping
{"action": "ping"}

// Cancel subscription
{"action": "unsubscribe"}
```

### Server → Client Frames
```json
// Live vehicle position with emitted_at for E2E latency tracking
{
  "type": "position",
  "data": {
    "vehicle_id": 42,
    "lat": 12.9716,
    "lon": 77.5946,
    "speed_kmh": 54.2,
    "heading": 180,
    "h3_r8": "8860145a33fffff",
    "ts": "2026-09-30T08:00:00Z",
    "emitted_at": "2026-09-30T08:00:00.045Z"
  }
}

// Automated Alert Trigger
{
  "type": "alert",
  "data": {
    "vehicle_id": 42,
    "kind": "speeding",
    "severity": "critical",
    "payload": {"speed_kmh": 94.5, "limit": 80.0},
    "time": "2026-09-30T08:00:00Z"
  }
}
```

---

## TimescaleDB: Hypertables & Continuous Aggregates

### 1. Hypertables
The core table `positions` is partitioned into daily chunks using `create_hypertable('positions', 'time', chunk_time_interval => INTERVAL '1 day')`. Its composite primary key `(vehicle_id, time)` provides the bedrock for idempotent at-least-once pipeline ingestion.

### 2. Hierarchical Continuous Aggregates
- `positions_1min`: Aggregates speed (avg, max), last coordinates (`last(lat, time)`), and count per 1-minute bucket. Refreshed continuously every minute with a 30s lag offset.
- `positions_1hour`: **Rolled up hierarchically from `positions_1min`, never from raw table scans**. This guarantees linear aggregate compute cost regardless of raw volume.

### 3. Compression & Retention
- Chunks older than 7 days are compressed via segmenting by `vehicle_id` and ordering by `time DESC`.
- Raw chunks are dropped after 30 days via `add_retention_policy('positions', INTERVAL '30 days')`.
- The 1-minute aggregate is retained for 1 full year.

---

## Delivery Semantics & Idempotency Guarantee

Fleet guarantees **at-least-once delivery** through Redis Streams consumer groups without risking duplicate data:
1. Devices/Simulators post telemetry to `/api/v1/positions/batch`.
2. Ingress `XADD`s to `stream:positions` and returns `202 Accepted` immediately (0 database queries executed).
3. The worker processes micro-batches, inserting with:
   ```sql
   INSERT INTO positions (...) VALUES (...) ON CONFLICT (vehicle_id, time) DO NOTHING;
   ```
4. Only after PostgreSQL commits is `XACK` issued back to Redis Streams. If the worker dies before acknowledging, `workers/reclaimer.py` claims pending messages via `XAUTOCLAIM` and replays them idempotently without creating duplicate database rows.

---

## Testing & CI

```bash
# Run unit & integration test suite
pytest -v tests/

# Run ruff linter and formatting checks
ruff check .
ruff format --check .
```

All pull requests and commits run against real `timescale/timescaledb:latest-pg16` and `redis:7-alpine` service containers in GitHub Actions.
