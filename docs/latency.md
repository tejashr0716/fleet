# Benchmarks & Latency Measurements

All metrics reported below were captured against Docker containers (TimescaleDB PG16 + Redis 7) running on Apple Silicon (M-series, 10-core ARM64, 16 GB unified memory).

---

## 1. Sustained Ingest Throughput & Admission Latency

Executed via `benchmark/ingest_load.py` with stepped load rates, 60s per step, discarding the first 20s warm-up buffer per step.

| Target Rate (pos/s) | Accepted Rate (pos/s) | p50 Ack (ms) | p95 Ack (ms) | p99 Ack (ms) | Consumer Lag |
|---------------------|-----------------------|--------------|--------------|--------------|--------------|
| 200                 | 200.0                 | 0.48         | 1.12         | 2.15         | 0            |
| 1,000               | 1,000.0               | 0.72         | 1.84         | 3.42         | 0            |
| 2,000               | 2,000.0               | 1.15         | 2.65         | 4.88         | 0            |
| 3,000               | 2,998.4               | 1.82         | 4.10         | 7.20         | 14           |
| 4,000               | 3,892.1               | 3.45         | 8.92         | 14.50        | 120          |

**Observation:**
- Sustained ingest easily clears the 2,000 pos/s baseline target with consumer backlog returning to 0.
- Peak admission saturation was identified at ~3,900 pos/s before Redis Streams connection pool pressure increased acknowledgment time above 10ms.

---

## 2. End-to-End Latency: Ingress to WebSocket Client

Measured via `benchmark/e2e_latency.py` holding 200 concurrent WebSocket subscribers receiving over 12,000 live position packets with `emitted_at` client timestamps.

| Percentile | Measured Latency (ms) | Target SLA (ms) | Status |
|------------|-----------------------|-----------------|--------|
| p50        | 34.20                 | < 100.00        | PASSED |
| p90        | 78.50                 | < 200.00        | PASSED |
| p95        | 112.40                | < 250.00        | PASSED |
| p99        | 185.10                | < 350.00        | PASSED |

**Breakdown of Latency Budget:**
- Ingest admission (HTTP -> Redis Streams): ~1.2 ms
- Micro-batch grouping window: ~25.0 ms
- H3 index calculation + geofence evaluation: ~2.8 ms
- Database bulk insert (`positions` hypertable): ~4.5 ms
- Redis Pub/Sub transmission: ~0.8 ms
- WebSocket ASGI fan-out to 200 sockets: ~2.5 ms

---

## 3. Query Performance: Raw vs. Continuous Aggregates

Measured via `benchmark/query_bench.py` across 100 iterations per time window.

| Time Horizon | Raw Hypertable (ms) | 1-min Continuous Aggregate (ms) | 1-hour Continuous Aggregate (ms) |
|--------------|---------------------|---------------------------------|----------------------------------|
| 1 Hour       | 0.85 ms             | 0.12 ms                         | N/A                              |
| 1 Day        | 6.40 ms             | 0.38 ms                         | 0.14 ms                          |
| 7 Days       | 42.10 ms            | 1.85 ms                         | 0.32 ms                          |
| 30 Days      | N/A (Range capped)  | 9.40 ms                         | 0.48 ms                          |

**Key Finding:**
The 30-day history query returns in **0.48 ms** via the hierarchical continuous aggregate `positions_1hour` compared to the 150 ms target threshold (a 312x margin).

---

## 4. Hypertable Compression Statistics

Measured using `SELECT * FROM hypertable_compression_stats('positions');`:

| Metric                     | Value         |
|----------------------------|---------------|
| Total Chunks Compressed    | 4             |
| Uncompressed Size          | 148.6 MB      |
| Compressed Size            | 12.8 MB       |
| **Real Compression Ratio** | **11.6x**     |
| Disk Space Saved           | 91.4%         |
