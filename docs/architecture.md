# Architecture and design decisions

## Scope

A demonstrable, single-fleet backend project built around Python, FastAPI, PostgreSQL, Redis and REST APIs. The source of GPS data is a synthetic simulator. The server runs actual database transactions, actual Redis operations and actual WebSocket fan-out. The public static page is a separate, clearly labeled browser simulation until explicitly connected.

## Durable ingestion, not an optimistic animation

`app/repositories/position_repo.py` locks the affected vehicle rows in sorted ID order, validates registration, sorts each batch by timestamp, inserts positions with `ON CONFLICT DO NOTHING`, evaluates transition rules, and inserts outbox events in the same transaction. Only after commit does the API return 202.

The unique `(vehicle_id, recorded_at)` key defines a retry. A conflicting payload at that key is not a replacement: first-write-wins. Device identity beyond a shared demo API key is intentionally out of scope. A real deployment should give each device revocable, independently scoped credentials.

## Outbox vs a Redis-first queue

The database is the source of truth. A Redis-only ingress acknowledgment could lose accepted telemetry after Redis failure unless persistence/replication guarantees were specified. The small demo chooses a database transaction and an outbox instead. The cost is synchronous database latency per accepted batch; this is not the fastest possible architecture and no high-ingestion-rate claim is made.

The worker selects pending events with `FOR UPDATE SKIP LOCKED`. Handoff is retried after errors. Publishing and the database delivery marker cannot share a distributed transaction; therefore a crash can produce a duplicate publication. The event ID identifies a delivery attempt's logical event. The client ignores older/equal position timestamps and deduplicates alert identities. Pub/Sub can miss a viewer entirely; REST history remains available.

## Redis roles

1. Latest-position keys have a TTL.
2. GEOADD/GEOSEARCH supply fresh nearest-vehicle queries for the demo region.
3. Pub/Sub distributes events across independently running API instances.
4. Atomic Lua protects latest-position freshness and login rate-limit counters.

GEO members are cross-checked against TTL keys; stale members never become a fresh vehicle. Nearest search is intentionally bounded to 1,000 geo candidates within 25 km. This is sufficient for a 12-vehicle demo, not evidence of arbitrary fleet-scale correctness. Polar-coordinate queries use the database fallback because Redis GEO uses a Mercator latitude limit.

## History and SQL

Ordinary PostgreSQL tables hold historical samples. The unique vehicle/time key also supplies the B-tree used for per-vehicle time windows. `DISTINCT ON (vehicle_id)` selects the latest sample per vehicle. A bounded request returns the most recent N matching observations in ascending time order, with `has_more` explicitly indicating truncation.

This avoids adding TimescaleDB before the dataset needs it. A future larger history workload should measure plans and row counts before choosing partitioning or time-series extensions.

## Rules, not ML

Speeding alerts trigger only when crossing above the configured limit. Circular geofence alerts compare Haversine membership of the previous latest and new latest points. Late history does not invent live transitions. GPS jitter can cause boundary chatter: hysteresis/accuracy handling is explicitly not implemented. Trace sessions split at a five-minute silence gap; their straight-line point-to-point distance is not road-network map matching.

## Viewer delivery

JWT in the first WebSocket frame avoids placing secrets in query strings/logs. Allowed origins are checked. Each viewer has one bounded 64-event queue and one writer task. Old queued frames can be dropped; a gap message requests a database snapshot. Tokens have expiry, and the viewer must sign in again when expired.

The dashboard makes a five-second snapshot reconciliation request because realtime Pub/Sub is best effort. Reconnecting never silently switches to browser fixtures. If the backend becomes unavailable, the UI retains last observations and shows a connection interruption.

## Deployment boundaries

A static Pages publication is not a backend deployment. Real services require separate persistent infrastructure and HTTPS. The included Compose setup binds application/database/cache ports to loopback by default. Production mode rejects conspicuous demo secrets, but the project is not a complete production security posture: single account, no token revocation, no multi-tenancy, no device-level rotation or audit system.


## v3: explicit vehicle trips

`app/routers/trips.py` exposes start/list/detail/finish. `app/models/trip.py` stores explicit lifecycle records; `managed_trip_repo.py` handles capacity checks, database locking and observed summaries. `TripRunner` creates Pydantic-validated synthetic batches through the same ingestion repository used by `/positions/batch`. It does not need to make loopback HTTP requests or keep an owner password in the browser.

Trip and alert samples carry `trip_id`. `positions/batch` validates the vehicle association, rejects new samples for a finished trip, and still accepts first-write-wins retries of already stored timestamps. Finishing waits for the generator to stop, takes the same vehicle lock as ingestion, and then commits the lifecycle update. Delayed outbox delivery can still contain earlier committed samples; it does not mean generation continued after completion.

Only one active trip per vehicle is enforced by a PostgreSQL partial unique index. Start-capacity checks use a PostgreSQL advisory transaction lock; the hourly quota is counted from persisted trip records, not reset by a Python restart. On startup, previously active simulated tasks are marked interrupted. There is no claim of durable task execution or multi-process scheduling.

Browser preview implements the workflow in isolated memory. It makes no backend requests and is explicitly reset by reload. Switching to live mode marks a running preview interrupted. A live API failure retains the observed data and connection warning; it never switches to fixtures silently.

Trip detail metrics are computed from the stored inputs: lifecycle duration, sample count, maximum synthetic input speed, alert count and straight-line trace distance. Truncated traces do not receive an invented full distance. Leaflet displays observations; it does not perform navigation, map matching or road-route optimization.
