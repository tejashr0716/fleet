# Resume claims and their evidence

The current supplied project entry names **Python, FastAPI, PostgreSQL, Redis and RESTful APIs**. No quantitative Fleet bullets were supplied. This build does not invent any.

| Defensible capability after running/reviewing it | Code/evidence | Demo |
|---|---|---|
| FastAPI endpoints with Pydantic validation and JWT authentication | `app/routers/`, `app/security.py`, validation/auth tests | Swagger plus invalid input and unauthorized requests |
| PostgreSQL GPS history with retry-safe inserts | schema unique key; ingestion/history tests | Repeat an identical timestamped sample |
| Redis-backed latest state, proximity lookup and live fan-out | `live_state.py`, outbox tests | Nearest query plus actual WebSocket packets |
| Transactional outbox and dependency failure handling | worker and outage/retry tests | Stop and restart Redis |
| JavaScript map and Chart.js observed-speed dashboard | `static/` | Connect live API, select vehicle and show stored route |
| Docker setup and GitHub Actions checks | Compose/CI files | Fresh environment and passing workflow |

## Optional wording, after you understand and reproduce it

- Built a FastAPI vehicle-tracking backend that stores GPS history in PostgreSQL and distributes current positions through Redis and authenticated WebSockets.
- Added validated REST endpoints, JWT authentication, retry-safe telemetry insertion and a transactional outbox to recover Redis handoff after failures.
- Created a JavaScript/Leaflet dashboard with Chart.js speed history, circular geofence alerts and a synthetic GPS simulator for reproducible demonstrations.

These are qualitative capability statements, not fabricated production outcomes. “Real-time” describes the processing path, not a guarantee of a particular latency. Do not claim real fleet operators, thousands of vehicles, a compression ratio, p95 latency or a specific throughput without evidence measured under a documented workload.

This rebuild is current work. Preserve Jan–May 2026 dates only if they accurately describe your original project work; do not backdate code or use this rebuild as evidence of when something was first implemented. No resume file is changed by the rebuild.
