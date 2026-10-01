import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { PreviewFleet } from "../static/preview.js";
const routes = JSON.parse(
  fs.readFileSync(new URL("../static/demo/replay.json", import.meta.url)),
).routes;
const body = {
  route_key: "central",
  duration_seconds: 60,
  include_speeding: true,
};
test("registration starts empty, normalizes and rejects duplicates", async () => {
  const p = new PreviewFleet(routes);
  assert.equal((await p.listVehicles()).length, 0);
  const v = await p.register({
    name: " Van ",
    registration: "ka-01-demo",
    kind: "delivery",
  });
  assert.equal(v.registration, "KA-01-DEMO");
  await assert.rejects(
    p.register({ name: "Other", registration: "ka-01-demo", kind: "cab" }),
  );
  await assert.rejects(
    p.register({ name: " ", registration: "X", kind: "cab" }),
  );
});
test("only explicitly started trips generate samples; finish preserves the record", async () => {
  const p = new PreviewFleet(routes),
    v = await p.register({
      name: "Van",
      registration: "VAN",
      kind: "delivery",
    });
  p.advance();
  assert.equal((await p.snapshot()).length, 0);
  const t = await p.start(v.id, body);
  assert.equal((await p.detail(t.id)).summary.point_count, 1);
  p.advance(Date.parse(t.started_at) + 2100);
  assert.equal((await p.detail(t.id)).summary.point_count, 2);
  await p.finish(t.id);
  p.advance(Date.parse(t.started_at) + 4100);
  const d = await p.detail(t.id);
  assert.equal(d.trip.status, "completed");
  assert.equal(d.summary.point_count, 2);
});
test("a speeding fixture is attached to its trip and persists in review", async () => {
  const p = new PreviewFleet(routes),
    v = await p.register({
      name: "Van",
      registration: "VAN",
      kind: "delivery",
    }),
    t = await p.start(v.id, body);
  for (let i = 1; i <= 12; i++) p.advance(Date.parse(t.started_at) + i * 2100);
  await p.finish(t.id);
  const d = await p.detail(t.id);
  assert.equal(d.alerts.filter((a) => a.kind === "speeding").length, 1);
  assert.equal(d.alerts.find((a) => a.kind === "speeding").trip_id, t.id);
  assert.equal(d.summary.max_speed_kmh, 92);
});
test("timeout and switching to API stop preview without fabricating backend persistence", async () => {
  const p = new PreviewFleet(routes),
    v = await p.register({
      name: "Van",
      registration: "VAN",
      kind: "delivery",
    }),
    t = await p.start(v.id, body);
  p.advance(Date.parse(t.expires_at));
  assert.equal((await p.detail(t.id)).trip.end_reason, "time_limit");
  const second = await p.start(v.id, body);
  p.interrupt();
  assert.equal((await p.detail(second.id)).trip.status, "interrupted");
  assert.equal((await p.detail(t.id)).source_used, "browser_memory");
  p.reset();
  assert.equal((await p.listTrips()).length, 0);
});
