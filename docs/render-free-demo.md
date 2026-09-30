# Temporary Render free-tier demo

This is an optional interview-demo deployment, not an always-on production promise. The normal Docker Compose deployment still uses separate API and outbox-worker services. Browser simulation remains explicitly separate from backend mode.

## Why a combined runner?

Render does not offer free background-worker instances. The `python -m app.cloud_demo` entrypoint runs migrations, idempotently seeds 12 demo vehicles, and starts a single Uvicorn process. With `CLOUD_DEMO_ENABLED=true`, the FastAPI lifespan starts the same outbox consumer as an asyncio task, using its own database and Redis connections. Shutdown cancels and joins the consumer and active GPS session before closing dependencies. Do not scale this demo runner beyond one web instance/one Uvicorn worker.

This compromise is about free-tier deployment, not about changing PostgreSQL durability or pretending the Redis pipeline exists. For durable hosting, use the normal separate-worker architecture.

## Three free-tier resources, same workspace and region

- Web service: Docker runtime, free compute, repository `tejashr0716/fleet`, Docker command `python -m app.cloud_demo`.
- PostgreSQL: free compute, PostgreSQL 16; use the private connection URL.
- Key Value: free compute, private connection URL, `noeviction` policy, no disk persistence.
- Suggested region for this India-based demonstration: Singapore.

Required runtime variables: `DATABASE_URL`, `REDIS_URL`, `ADMIN_USERNAME`, a strong `ADMIN_PASSWORD`, independently generated `JWT_SECRET` and `DEVICE_API_KEY`, and explicit `ALLOWED_ORIGINS` including `https://tejashr0716.github.io` and the actual backend origin. Secrets belong only in provider controls/private credential files, never GitHub or the public frontend. The entrypoint forces production validation, converts provider PostgreSQL URLs to the asyncpg scheme, and uses Render's assigned `PORT`.

## On-demand sample GPS

1. Connect the dashboard to the verified backend HTTPS origin using your private credentials.
2. Click **Start sample GPS (5 min)**. No GPS generator starts automatically at boot.
3. The existing Python simulator authenticates against the local HTTP API and submits synthetic positions. The real path is HTTP/Pydantic → PostgreSQL history and outbox → Redis latest/GEO/PubSub → authenticated WebSocket.
4. Inspect stored history, observed speed, geofence/speed alerts and Redis nearest-vehicle results.
5. Click **Stop sample GPS** or let the five-minute timer expire. Existing observations are not deleted.

Protected endpoints: `GET /api/v1/demo/status`, `POST /api/v1/demo/start` and `POST /api/v1/demo/stop`. They are disabled by default. Sessions last at most 600 seconds, use at most 12 seeded vehicles at three-second intervals, permit one active session and at most three starts per process/hour. The cumulative synthetic-position budget defaults to 50,000; this controls the built-in generator, not arbitrary external ingestion or the provider's storage guarantee. A large undelivered outbox prevents new sessions. Errors expose exception types, not private connection strings.

## Limitations to disclose

- Free web services sleep after 15 minutes without inbound traffic and can take about a minute to wake. Sign-in allows up to 90 seconds for that cold start. No bot pings or synthetic keepalive service is configured.
- Free PostgreSQL expires 30 days after creation and has 1 GB of storage. After the subsequent 14-day grace period, Render deletes it unless upgraded. Keep important work locally; this demo is disposable.
- Free Key Value loses its cache on restart. PostgreSQL remains the source of truth; empty/stale nearest caches fall back to PostgreSQL. WebSocket Pub/Sub is best effort, not durable exactly-once delivery.
- Free web-instance hours (750/month/workspace), bandwidth and build usage are shared with other projects. Free compute does not automatically prevent billable bandwidth/build overages when a payment method exists. Inspect billing controls before provisioning and never upgrade automatically.
- This mode does not prove throughput, high availability, physical GPS integration or production deployment skills.

Official references: [Render free-instance limits](https://render.com/docs/free), [compute plans](https://render.com/docs/compute-plans), [pricing](https://render.com/pricing).
