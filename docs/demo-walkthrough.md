# Demo walkthrough: register → start → track → finish → review

## Try it immediately — browser preview

Open [Fleet](https://tejashr0716.github.io/fleet/). You start with **zero vehicles**, not a fleet that moves automatically.

1. Click **Register vehicle**. Enter a name such as `Delivery Van 01`, a demo identifier such as `KA-01-DEMO-01`, and a vehicle type.
2. Click **Start simulated trip**. Choose a demo route and an automatic finish time. Keep **Include a 92 km/h speeding test event** checked if you want to demonstrate alerts.
3. Click **Start trip**. Samples appear about every two seconds. **Fit route** frames the observed trace. The speed chart and exact GPS table use generated observations, not a pre-drawn travel history.
4. After about 16 seconds the deliberate speeding input produces a trip-specific alert. These are threshold rules, not ML.
5. Click **Finish trip & review**, then confirm **Finish trip**. The trip changes to completed, its generator stops, and the record remains in the history list.
6. Select **Review** to inspect that trip's route, samples, start/end timestamps, trace distance and alerts. Start another trip to see separate histories.

Preview records disappear on reload. **Reset preview** only clears this tab; it never deletes backend data.

## Demonstrate the real backend

Start the local stack:

```bash
python scripts/setup.py
docker compose up --build -d
```

Do not start the legacy `demo` simulator profile for this workflow. The new per-vehicle generator starts only when you explicitly start a trip.

Open `http://localhost:8000/static/index.html`. Click **Connect live API**, use `http://localhost:8000` as the origin, and enter the username/password from your local `.env`. For the temporary hosted demo use `https://fleet-tejashr0716-demo.onrender.com` and your private hosted credentials. No password is included in this repository.

Repeat the five actions above. The interface now says **Stored in PostgreSQL**. Close/reload the page, sign in again, and reopen the completed trip. Its persisted route and alerts are returned by the API.

The twelve legacy seeded vehicles are preserved but hidden under **Show seeded samples**. Register your own demo vehicle for the clearest presentation.

## What to point to in an interview

- `POST /api/v1/vehicles` really registers a record.
- `POST /api/v1/vehicles/{id}/trips` creates an explicit active trip and starts bounded Python simulation.
- Samples carry `trip_id`; the shared validation/ingestion repository commits positions, alerts and outbox events together.
- The worker performs Redis cache/GEO/PubSub handoff; `/ws/live` requires a JWT in its first frame.
- `POST /api/v1/trips/{id}/finish` cancels generation and durably closes the trip. Repeating finish is idempotent.
- `GET /api/v1/trips/{id}` returns that trip's actual stored synthetic inputs and alerts. History is not guessed from an animation or a five-minute gap.
- A service restart marks an unfinished simulated trip **interrupted**; it never pretends a Python task continued across the restart.

Trace distance is the straight-line sum between stored coordinates, **not road distance**. The speeding event is a labeled fixture, not a measurement.

## Practical limits

- One active trip per vehicle; at most three simultaneous simulated trips and twelve starts per hour per single-owner application.
- Trip duration: API 5–600 seconds; UI 1, 3, 5 or 10 minutes; manual finish can end it earlier.
- Hosted synthetic storage budget: 50,000 samples by default. New runs are rejected when the budget/backlog guard is reached; existing history is not erased.
- Live list loads the most recent 200 trips. A direct trip detail remains available by ID. A detail response returns at most 5,000 points and 200 alerts, explicitly flags truncation, and does not invent a whole-trip distance from a partial trace.
- One API process is supported for in-process simulated trip tasks. The free deployment uses one process. A production multi-worker deployment would need a separate durable scheduler and per-user authorization.
- Temporary free hosting sleeps and has an expiring PostgreSQL database. It is not always-on production hosting. Stop/finish trips after presenting.

Finishing is explicit: closing the browser or returning to preview does not cancel a server-side trip. Finish it first, or let its bounded automatic time limit stop it. A running browser-preview trip is marked interrupted when you connect the API.
