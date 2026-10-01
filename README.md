# Fleet — Real-Time Vehicle Tracking Platform

## Register → start → track → finish → review

[Try Fleet](https://tejashr0716.github.io/fleet/) · [What this project does](docs/project-idea.md) · [Step-by-step demo](docs/demo-walkthrough.md)

Fleet now has a concrete trip workflow, not just an automatically moving sample fleet:

1. Register a vehicle with a name, identifier and type.
2. Start its simulated trip on an illustrative route.
3. Watch GPS samples, the growing trace and trip-specific alerts.
4. Finish the trip, or let its time limit finish it.
5. Reopen the completed record to review its route and alerts.

The public page starts empty in **browser preview**; its records exist only in this tab. **Connect live API** uses the real backend and private owner credentials. Registration, explicit trip records, GPS history and alerts are persisted in PostgreSQL; Redis and authenticated WebSockets provide live updates. GPS remains synthetic in both modes.

**Verification:** [real PostgreSQL/Redis CI](https://github.com/tejashr0716/fleet/actions/runs/36822140038) passed, and [25 hosted workflow checks](reports/trip-workflow-hosted.json) verified the new lifecycle and preserved the previous history.

The temporary free backend is [here](https://fleet-tejashr0716-demo.onrender.com/static/index.html). Free instances may need about a minute to wake. Its disposable PostgreSQL database expires **2026-10-30 at 18:12 UTC (23:42 IST)**; no paid plan or always-on guarantee is implied. [Hosting limits](docs/render-free-demo.md).

**Python · FastAPI · PostgreSQL · Redis · REST APIs · JWT · HTML/CSS/JavaScript · Chart.js**

[![Fleet CI](https://github.com/tejashr0716/fleet/actions/workflows/ci.yml/badge.svg)](https://github.com/tejashr0716/fleet/actions/workflows/ci.yml)

[Public showcase](https://tejashr0716.github.io/fleet/) · [Architecture](docs/architecture.md) · [Interview guide](docs/interview-guide.md) · [Demo walkthrough](docs/demo-walkthrough.md)

## What is real, and what is simulated?

| Mode | GPS source | Backend services | What it demonstrates |
|---|---|---|---|
| Public GitHub Pages showcase | Clearly labeled browser fixtures | None until you explicitly connect an API | UI, map, observed sample history, threshold alerts |
| Local full-stack demo | Python-generated synthetic GPS | Real FastAPI, PostgreSQL, Redis and WebSockets | Validation, durable history, JWT auth, outbox retries, live delivery |
| Hosted full stack | Same synthetic simulator unless you add devices | Requires a separately deployed backend | Same real pipeline over HTTPS |

**GitHub Pages cannot host a Python API or a database.** An animated public map is not evidence that Redis or PostgreSQL is running. The dashboard never silently substitutes sample data after a live connection fails.

This rebuild uses conventional PostgreSQL, not TimescaleDB; circular geofences, not H3; a transactional outbox, not Redis Streams. No Kafka, Kubernetes, ML model, real vehicle deployment, production traffic, or unverified throughput claim is implied.

## Start locally

Prerequisites: Git, Python 3.12+ for the credential setup script, and Docker Desktop / Docker Engine with Compose. On Windows use Docker Desktop with its supported WSL2 setup. Linux and macOS use the same Compose commands.

```bash
git clone https://github.com/tejashr0716/fleet.git
cd fleet
python scripts/doctor.py
python scripts/setup.py
docker compose up --build -d
```

If your machine uses `python3`, use that instead of `python`.

1. Open **http://localhost:8000/static/index.html**.
2. Click **Connect live API**; origin `http://localhost:8000`, credentials from your local `.env`.
3. Register your vehicle, start a simulated trip, watch updates, finish, then review it.
4. Reload and sign in again to demonstrate durable completed-trip history.
5. Open **http://localhost:8000/docs** for the REST contract.

The per-vehicle Python generator starts only when you start a trip. The optional old `--profile demo` simulator and `/demo/*` endpoints remain for compatibility; do not run that fleet-wide simulator during the new trip workflow.

`setup.py` creates random credentials once and never overwrites an existing `.env`. Do not commit that file or paste its contents into chat. Defaults in `.env.example` are conspicuous local-demo placeholders, not production credentials.

```bash
docker compose logs -f api worker
docker compose down
```

Stopping preserves PostgreSQL and Redis volumes. **Do not add `-v` unless you deliberately want to delete your local demo data.** The rebuild stores its tables under `fleet_v2`; it does not drop old prototype tables in `public`.

### Without Docker

Run PostgreSQL 15+ and Redis 6.2+ yourself, create a database owned by your application role, and configure the real URLs in `.env`. Python 3.12/3.13 is supported.

```bash
python -m venv .venv
# Activate using your OS's normal venv command.
pip install -e '.[dev]'
alembic upgrade head
python -m simulator.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000
# Separate terminals, with the same environment:
python -m workers.position_consumer
# Start trips from the dashboard; no always-moving simulator is needed.
# Optional legacy fixture generator (not during managed trips):
# python -m simulator.run --trigger-alerts
```

## Preview without backend dependencies

```bash
python -m http.server 8080 --directory static
```

Open http://localhost:8080. This is explicitly browser-simulated data, not a backend test. Use the API-served dashboard at port 8000 for the local live connection; a custom frontend origin must be added to `ALLOWED_ORIGINS`.

## Safely replace an existing clone from this package

The supplied package is a complete replacement, not a patch. Old H3/Timescale migration/tests must not remain mixed with the new implementation. The optional helper verifies checksums and the original base revision, refuses dirty or unrelated repositories, and creates local backup/rebuild branches. It never pushes or force-pushes.

```bash
git clone https://github.com/tejashr0716/fleet.git fleet-existing
python /path/to/extracted/fleet/scripts/replace_existing.py --target fleet-existing
# Review the dry-run summary, then explicitly apply:
python /path/to/extracted/fleet/scripts/replace_existing.py --target fleet-existing --apply
```

Use your own OS path syntax. Review `git diff`, commit and publish the branch through GitHub Desktop or your normal Git credentials, then merge a pull request after checks pass. Never embed an access token in a Git URL. The `SOURCE_MANIFEST.json` base/checksums intentionally stop this helper if the repository has changed since packaging.

## Architecture in one sentence

**Validate/authenticate a GPS batch → atomically commit positions plus outbox events in PostgreSQL → retry Redis cache/GEO/PubSub handoff in a worker → fan out to authenticated WebSockets, with REST snapshot reconciliation.**

```text
Browser --JWT--> start/finish trip REST routes --> TripRunner (synthetic Python GPS)
                                                      |
External device --API key--> /positions/batch --> shared Pydantic/ingestion path
                                                      |
                                       PostgreSQL transaction
                                  positions + trip alerts + outbox
                                                      |
                                          Outbox worker (retry)
                                                      |
                                 Redis latest cache + GEO + Pub/Sub
                                                      |
                                      Authenticated WebSockets
                                                      |
                                  Browser map + trip review/chart
```

A `202` response means PostgreSQL committed and realtime handoff is queued. It does **not** promise that every browser already received the event.

## API surface

| Method / route | Purpose | Authentication |
|---|---|---|
| `POST /api/v1/auth/token` | Issue short-lived HS256 JWT | Username/password; rate limited |
| `GET /api/v1/vehicles` | Registered vehicles | Bearer JWT |
| `POST /api/v1/vehicles` | Register a vehicle | Bearer JWT |
| `POST /api/v1/positions/batch` | Validate and commit 1–100 GPS samples | Device API key or JWT |
| `GET /api/v1/fleet/live` | Current PostgreSQL snapshot | Bearer JWT |
| `GET /api/v1/fleet/nearest` | Fresh nearest vehicles within 25 km | Bearer JWT |
| `GET /api/v1/vehicles/{id}/positions` | Bounded, UTC history window | Bearer JWT |
| `POST /api/v1/vehicles/{id}/trips` | Start an explicit bounded simulated trip | Bearer JWT |
| `GET /api/v1/vehicles/{id}/trips` | Saved explicit trips for a vehicle | Bearer JWT |
| `GET /api/v1/trips` | Recent explicit trips | Bearer JWT |
| `GET /api/v1/trips/{id}` | Trip route, synthetic samples, alerts and summary | Bearer JWT |
| `POST /api/v1/trips/{id}/finish` | Stop generation and durably finish; idempotent | Bearer JWT |
| `GET /api/v1/vehicles/{id}/trace-sessions` | Legacy gap-derived sessions, separate from managed trips | Bearer JWT |
| `GET / POST /api/v1/geofences` | Circular geofences | Bearer JWT |
| `GET /api/v1/alerts` | Persisted speeding / geofence transitions | Bearer JWT |
| `GET /api/v1/health` | Dependency health and pending outbox count | Public; no vehicle data |
| `WS /ws/live` | Authenticated live events | JWT in the first frame, not a URL |

The browser keeps JWTs only in memory. Tokens expire after 30 minutes by default. The demo is one admin account, not a production multi-tenant identity system.

## Correctness and failure behavior

- Retry the same `(vehicle_id, recorded_at)` sample: first write wins; no duplicate position/outbox row.
- Delayed GPS: preserve history, but do not regress the latest cache or create a false live transition.
- Redis failure: PostgreSQL ingestion/history still work; outbox rows wait; nearest queries use an explicitly labeled database fallback. Login fails closed while its Redis rate limiter is unavailable.
- Worker crash after publishing but before its DB commit: an event may be published again. Event IDs and sample timestamps permit deduplication. This is **not exactly-once delivery**.
- WebSocket loss: the viewer retries and reconciles from PostgreSQL. Pub/Sub itself is not durable.
- Slow viewer: queue is capped at 64 events; old queued frames are dropped and a gap notice requests reconciliation.
- Geofence jitter, real device clock drift, advanced permissions, multi-tenant isolation, durable client replay, alert hysteresis and production monitoring are future work.

## Test and measure

CI uses real PostgreSQL 16 and Redis 7 service containers. For local tests create a **separate** database named `fleet_test` and use Redis DB 1. Tests refuse to reset any other database.

```bash
pip install -e '.[dev]'
# Set DATABASE_URL to .../fleet_test (never your actual demo database).
alembic upgrade head
pytest -q
ruff check .
ruff format --check .
```

Benchmarks are optional, reproducible probes—not capacity guarantees:

```bash
python -m benchmark.ingest_load --url http://localhost:8000 --requests 30
python -m benchmark.e2e_latency --url http://localhost:8000 --samples 20
python -m benchmark.query_bench --url http://localhost:8000 --requests 20
```

They read local credentials from `.env`, write hardware/context plus raw timings to `reports/`, and use synthetic data. See [measurement notes](docs/latency.md). The old prototype's Apple Silicon numbers are not carried forward as verified results.

## Deployment and honest project claims

The Pages workflow publishes `static/`. Backend deployment additionally needs a Python host, persistent PostgreSQL, Redis, and a continuously running worker/simulator. See [deployment checklist](docs/deployment.md). No paid service is provisioned automatically.

Use [resume evidence](docs/resume-evidence.md) only after running, reviewing and understanding the code yourself. Project dates must reflect actual work; rebuilding now does not prove an earlier date or a historical performance number. Git history is not backdated.

## Project map

- `app/`: API, validated schemas, SQL repositories, rules, authentication and WebSockets.
- `workers/`: outbox delivery and optional delivered-event housekeeping.
- `migrations/`: isolated `fleet_v2` schema.
- `simulator/`: explicitly synthetic Bengaluru fixtures and generator.
- `static/`: deployable showcase and live API connector; local pinned map/chart assets.
- `tests/`: real dependency integration plus pure-rule unit tests.
- `docs/`: architecture, interview answers, demo walkthrough, evidence and deployment limits.
- `reports/`: verification context; no invented performance data.

## Optional temporary free-tier cloud demo

Version 2.1 adds an optional one-service API/worker runner and an authenticated, time-limited **Start sample GPS** control. The normal Docker workflow is unchanged. This is a temporary demonstration, not always-on production hosting. See [the complete Render free-demo guide](docs/render-free-demo.md), including the 30-day database expiration and shared usage/billing limits. Resource provisioning and billing controls must be confirmed separately; a prepared configuration does not mean a live backend has been deployed.

## Explicit trip lifecycle and checks

The forward `fleet_v3_002` migration adds `trips`, nullable trip links on positions/alerts, and a sample-vehicle flag. It preserves earlier vehicles, GPS history, alerts and outbox events. A partial unique index enforces one active trip per vehicle. Vehicle locking coordinates ingestion and finish; restart recovery marks abandoned simulated trips interrupted.

Frontend checks:

```bash
npm ci
npm run test:preview
npx playwright install chromium
npm run test:ui
```

CI runs Python tests against real PostgreSQL/Redis, pure preview-store tests, and browser workflow/contract tests. Mocked UI checks are not evidence of a deployed backend. Earlier v2.1 reports are historical; see `reports/README.md` for the scope of each report.

The in-process trip generator supports one API process; persistent scheduling, real device assignment, multi-tenant accounts and road routing are outside this demo's scope.
