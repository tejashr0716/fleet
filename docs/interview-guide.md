# Fleet interview guide

Use these as explanations to learn and verify, not as claims about work you have not understood. Open the referenced files and run each corresponding demo.

## A 60-second explanation

“Fleet is a vehicle-tracking backend and dashboard. A Python simulator supplies explicitly synthetic GPS points. FastAPI validates and authenticates batches, then commits positions and outbox events together in PostgreSQL. A worker retries delivery to Redis, which stores current coordinates and broadcasts them to authenticated WebSockets. The browser shows the latest positions and observed history, and reconciles after gaps. PostgreSQL is durable; Redis and Pub/Sub are disposable. I chose this small, understandable architecture rather than adding Kafka or a time-series extension before I had measured a need.”

## Why each library exists

| Choice | Specific job | Alternative and trade-off | Find it |
|---|---|---|---|
| FastAPI | Async HTTP/WebSockets, dependency-based auth, generated OpenAPI | Flask is simpler for synchronous apps; Django includes more batteries than this API needs | `app/main.py`, `app/routers/` |
| Pydantic | Lat/lon/speed bounds, timezone-aware input, consistent JSON schemas | Manual dict checks repeat validation and documentation | `app/schemas/position.py` |
| PostgreSQL | Durable history, uniqueness, transactions, outbox consistency | MySQL could work; PostgreSQL's conflict handling/JSONB/DISTINCT ON fit this implementation | `app/repositories/position_repo.py` |
| SQLAlchemy async + asyncpg | Parameterized queries, ORM models and async database I/O | Raw asyncpg is lighter; an ORM makes this demo's schema/service boundaries easier to maintain | `app/db.py`, `app/models/` |
| Alembic | Reviewable, repeatable schema creation | Runtime `create_all` is not a migration history | `migrations/` |
| Redis | Disposable latest-state cache, GEO lookup, Pub/Sub, rate-limit counters | PostgreSQL alone would be simpler, but would not demonstrate fan-out/cache failure behavior | `app/services/live_state.py` |
| PyJWT | HS256 signed tokens with expiry, issuer/audience and fixed algorithm | Server sessions permit easier revocation; JWT is not encrypted and revocation is not implemented here | `app/security.py` |
| pwdlib / Argon2 | Verify passwords with a slow password-hardening hash, not a fast/plain comparison | Fast hashes like SHA-256 are unsuitable for password hashing | `app/security.py` |
| WebSockets | Continuous events plus authentication/heartbeat control frames | SSE is a good simpler one-way alternative; polling is the implemented reconciliation fallback | `app/ws/` |
| Leaflet | Geographic map and observed trace overlays | A raw canvas would require implementing map projection/tiles | `static/map.js` |
| Chart.js | Actual speed samples, labeled units and exact-value table | An SVG chart is possible; the library avoids writing chart layout/hit-testing | `static/panels.js` |
| Docker Compose | Repeatable local service wiring | Manual setup works but creates more environment mismatch | `docker-compose.yml` |
| GitHub Actions | Lint and tests against real databases on commits/PRs | Local-only tests do not check a clean environment | `.github/workflows/ci.yml` |

React, Flask, Django, Node/Express, pandas and scikit-learn are not used merely to increase keyword density. The frontend intentionally uses plain JavaScript DOM manipulation; the project has no ML feature.

## Questions you should be able to answer

### Why is a 202 not “every viewer got the event”?

It means the database transaction committed and the outbox is queued. The worker/browser can lag or disconnect. This is an explicit durability boundary, not a marketing latency promise.

### What happens if Redis is down?

Accepted batches still commit to PostgreSQL. Worker delivery rolls back its delivery markers and retries. History still works. Nearest search returns `source_used: postgresql_scan`. Existing authenticated viewers can reconcile via REST. New logins fail closed because their rate limiter is unavailable. Run the outage demo to verify this.

### Are retries exactly once?

No. Database insertion is idempotent for the chosen unique key. Outbox handoff is at-least-once and can republish after a crash. Pub/Sub/WebSocket delivery is best effort. A database history query can recover stored observations; the live stream cannot guarantee every client saw every event.

### How do delayed GPS points avoid moving a car backward?

They are retained as historical observations. A timestamp-checked Lua update rejects an older latest-cache replacement. The client also rejects older/equal samples. Transition alerts only evaluate points newer than the last known position.

### Why lock vehicle rows in sorted order?

Two concurrent batches for the same vehicle must not both decide a threshold transition from the same previous state. Sorted locking provides consistent ordering and reduces deadlock risk. This serializes per-vehicle work; it is a correctness choice, not an unlimited-throughput claim.

### What does the index do?

The unique vehicle/time constraint creates a B-tree. A vehicle equality plus timestamp range can use that index; reverse scanning supplies recent history. It does not magically accelerate arbitrary spatial/history queries. Inspect the actual plan and row count before claiming an optimization.

### How do slow viewers behave?

The queue is capped at 64 events. Older queued frames are dropped, not accumulated forever. A gap notification triggers REST reconciliation. Keeping current state is the goal; preserving every live frame is not.

### How secure is the auth implementation?

JWT algorithms are allowlisted and exp/issuer/audience are checked. Password verification uses Argon2. HTTP credentials are sent only to localhost or a remote HTTPS origin in the UI. Tokens are in memory and use the first WebSocket frame. It is still a single-admin demo: no token revocation, independent device identity, RBAC or production secret manager is included.

### Is the geofence exact?

It is a circular Haversine threshold in meters, not a polygon/H3 index and not road matching. GPS uncertainty and boundary jitter can cause false transitions. Hysteresis and accuracy filtering are future improvements.

### Are the moving cars real?

No. Their GPS is generated. In the local full-stack mode, the processing pipeline is real. The public browser simulation does not touch PostgreSQL or Redis unless an API is explicitly connected.

### How many vehicles or requests can it handle?

The checked demo seeds 12 synthetic vehicles. Do not answer with a larger number without a reproducible load test, hardware details, duration, error rate and measured backlog/latency. The provided probes are smoke benchmarks, not saturation studies.

## Code ownership rehearsal

1. Add a new vehicle via the authenticated API.
2. Explain and change one validation bound.
3. Send the same telemetry twice and inspect the unique constraint.
4. Change the speed threshold and run its test.
5. Explain why PostgreSQL and Redis can disagree temporarily.
6. Run a Redis outage/recovery and show pending events drain.
7. Explain one deliberately omitted feature and what would justify it.

Do these yourself before claiming you can maintain the project in an interview.

## Why does the free cloud demo share API and worker compute?

Render's free tier cannot host a separate background worker. The optional demo mode starts the existing outbox consumer as a lifespan-managed task inside one Uvicorn process. It is explicitly an interview-demo compromise, not a production scaling design. Normal Docker mode still has separate services. The GPS control is authenticated, time-limited and off until requested; its synthetic samples travel through the same real HTTP, PostgreSQL, Redis and WebSocket path. Explain both the compromise and the free database's 30-day expiration.


## Presenting the temporary hosted version

1. Open the public showcase and explicitly distinguish browser simulation from the connected backend.
2. Connect using the private owner credentials; click Start sample GPS. Explain that Python generates coordinates, not physical GPS hardware.
3. Show changing positions, stored PostgreSQL history, observed speed and the Redis GEO source label. A deliberate 92 km/h fixture crosses the 80 km/h speeding rule after approximately 15 simulator ticks; it is not an ML prediction.
4. Explain the free-tier compromise: the same outbox consumer is an asyncio task in one web process because Render has no free background-worker plan. Normal Docker Compose retains a separate worker.
5. Stop GPS and return to browser simulation. Disclose cold starts, shared free quotas, volatile cache and the database expiry on 2026-10-30 at 18:12 UTC.

Evidence from one controlled hosted run: 20 checks passed, authenticated WebSocket position frames were observed for all 12 seeded vehicles, PostgreSQL history was retrieved, Redis GEO was used, and a speeding fixture was stored. This is functionality evidence, not throughput, latency, real-hardware, uptime or production-scale evidence. Do not turn these counts into invented resume performance claims.
