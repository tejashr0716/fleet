# What this project does

Fleet is a small vehicle-trip tracking application. It answers: **Which vehicle is on a trip, where was it observed, and what happened during that trip?**

The workflow is deliberately small:

1. **Register a vehicle** — give it a name, identifier and type.
2. **Start a simulated trip** — choose an illustrative Bengaluru route and a time limit.
3. **Watch updates** — see new GPS samples, the growing route and trip-specific alerts.
4. **Finish the trip** — stop the generator without deleting its history. The time limit also stops it automatically.
5. **Review the record** — reopen that trip and inspect its start/end times, stored coordinates, synthetic speed inputs and alerts.

This demonstrates the tracking part of a fleet-management system. It is **not** an order-dispatch platform, navigation engine or real hardware installation.

## An example

Register `Delivery Van 01` with the demo identifier `KA-01-DEMO-01`. Start a three-minute Central Bengaluru trip. Every two seconds the simulator generates another coordinate. If the speeding fixture is enabled, a 92 km/h input triggers the configured 80 km/h rule after about 16 seconds. Finish the trip, then click its **Review** row. The route and alert still belong to that completed trip; a second trip gets a different record and history.

## Two honest modes

- **Browser preview:** no login required; the same five actions work in this tab. Vehicles, trips and samples live only in memory and disappear on reload. This does not demonstrate a running database or Redis.
- **Live API:** sign in using your private owner credentials. Vehicle registration and trip records are stored in PostgreSQL. The Python simulator produces synthetic GPS, the transactional outbox sends committed events to Redis, and an authenticated WebSocket updates the browser. Reconnect to load saved trips.

Connecting the API does not turn synthetic coordinates into real GPS. The interface never silently falls back to preview after an API failure.

## Why these technologies are used

| Technology | Its actual job |
|---|---|
| Python | Generates test telemetry and runs backend logic. |
| FastAPI + Pydantic | Expose REST routes and validate vehicle, trip and GPS input. |
| SQLAlchemy + Alembic | Query PostgreSQL and apply a forward migration that preserves earlier data. |
| PostgreSQL | Persist vehicles, explicit trips, samples, alerts and outbox events. A partial unique index permits only one active trip per vehicle. |
| Redis | Maintain disposable latest-location/GEO state and fan out committed events; it is not the history database. |
| WebSockets | Deliver new positions without making the viewer fetch every sample individually. REST reconciliation handles reconnects. |
| JWT + Argon2 | Protect owner actions and check the owner password; device ingestion also supports an API key. |
| Leaflet | Display map tiles, coordinates and the observed trace. It does not calculate road routes. |
| Chart.js | Plot stored/generated synthetic speed values. The coordinate table provides exact values without relying on the chart. |

**Explain only what you have run and understood.** A simulated demonstration is not proof of real vehicle deployments, production scale, machine learning or a historical performance claim.
