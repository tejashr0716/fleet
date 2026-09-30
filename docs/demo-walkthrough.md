# Five-minute demonstration

## Before the interview

- Run `python scripts/doctor.py` on your own computer; it does not read credentials.
- Start the Compose demo and sign in to the live API. Keep `.env` out of screen shares.
- Open the dashboard, API `/docs`, architecture guide and tests in separate tabs.
- Verify dependency health and a drained outbox. Have local setup ready even if a hosted service is asleep/unavailable.
- Say up front: “GPS samples are simulated; backend storage and event delivery are real.”

## 1. Explain the screen (30 seconds)

Select a vehicle. Identify its actual last observed timestamp, coordinates, speed, freshness status and speed observations. Public Pages mode is explicitly simulation-only, so it is not the backend proof.

## 2. Show the real data path (60 seconds)

Connect to localhost with your local credentials. Show API health and worker/simulator logs. Open a stored history request in Swagger, using a JWT from `/auth/token`. Never paste the device key or token into a URL.

## 3. Prove a retry is safe (45 seconds)

Use the same JSON GPS sample and the same `recorded_at` twice in `/positions/batch`. First: `inserted: 1`. Retry: `duplicates: 1`. Show the history contains one row. If you change the timestamp, that is a new observation, not a retry.

## 4. Trigger a rule (45 seconds)

The `--trigger-alerts` simulator intentionally supplies a speeding fixture at ticks 15–17. This is a scripted demo input, not a measured sensor event. Show one threshold-crossing alert and explain why a repeated speeding sample does not create another crossing.

## 5. Pause Redis and recover (60 seconds)

```bash
docker compose stop redis
# Keep the API and worker running. Health becomes degraded.
# History and authenticated ingestion still work; nearest uses database fallback.
docker compose start redis
# Worker resumes and pending outbox events drain.
```

Do this after signing in: new login attempts fail closed while Redis is unavailable. Redis-down requests can take a few seconds because network operations must time out.

## 6. Explain one trade-off (30 seconds)

Database-first writes favor correctness over maximum admission throughput. Redis Pub/Sub is transient, so the browser reconciles from durable PostgreSQL. This demo does not promise exactly-once streaming or production scale.

## Closing

Point to a relevant test and an architecture decision. Show that you can change and rerun a rule. Be precise about what you implemented/reviewed and what remains a limitation.
