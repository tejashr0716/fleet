# Deploying the real backend

The Pages workflow replaces the public showcase, not the Python service. The old hard-coded Railway application URL is removed because it was not a verified running service during inspection.

## Infrastructure needed

- A Python 3.12+ application service for `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- A continuously running worker service from the same source: `python -m workers.position_consumer`.
- Persistent PostgreSQL 15+ and Redis 6.2+ with TLS/private networking appropriate to the host.
- A simulator process if the demo needs ongoing generated positions.
- HTTPS/WSS, including origin `https://tejashr0716.github.io` in `ALLOWED_ORIGINS`.

Some hosting tiers stop processes on inactivity and do not support a persistent worker. This project does not promise that a free plan is sufficient. Check service support/cost before provisioning.

## Configuration

Use the hosting platform's secrets controls, never committed files. Set `ENVIRONMENT=production`, unique `ADMIN_PASSWORD`, independent random `JWT_SECRET` / `DEVICE_API_KEY`, real `DATABASE_URL` / `REDIS_URL`, and explicit allowed origins. The database URL uses `postgresql+asyncpg://`; configure required TLS using the provider's supported asyncpg options, and use `rediss://` for TLS Redis when required.

Run `alembic upgrade head` once per release, then `python -m simulator.seed`. Keep a backup and migration rollback plan. The `fleet_v2` schema avoids dropping old public-schema prototype tables.

After provisioning, verify health, JWT login, ingestion, outbox delivery, a WebSocket event and stored history. Only then connect the public page using **Connect live API**. The origin is entered in the dialog; no backend credentials or device key are embedded in the public build.

## Current delivery boundary

The repository and Pages showcase can be published with the connected GitHub account. Hosting account access and any provisioning/billing approval are separate. Until the backend is hosted, use the local Docker demo for actual backend interviews; the public page remains an honestly labeled simulation.
