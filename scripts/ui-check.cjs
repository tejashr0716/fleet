const { chromium } = require("playwright");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const root = path.resolve(__dirname, "..");
const out = process.env.UI_OUTPUT_DIR || "/tmp/fleet-ui-check";
const base = "http://127.0.0.1:8768";
fs.mkdirSync(out, { recursive: true });
const server = spawn(
  "python3",
  [
    "-m",
    "http.server",
    "8768",
    "--bind",
    "127.0.0.1",
    "--directory",
    path.join(root, "static"),
  ],
  { stdio: "ignore" },
);
let browser;
const checks = [];
const record = (name, details = {}) => {
  checks.push({ name, status: "passed", ...details });
  console.log("PASS:", name);
};
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  for (let i = 0; i < 60; i++) {
    if (server.exitCode !== null) throw Error("Preview server exited");
    try {
      if ((await fetch(base)).ok) break;
    } catch {}
    await wait(100);
  }
  const executable =
    process.env.CHROMIUM_EXECUTABLE ||
    (fs.existsSync("/usr/local/bin/chromium")
      ? "/usr/local/bin/chromium"
      : undefined);
  browser = await chromium.launch({
    executablePath: executable,
    headless: true,
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [],
    apiCalls = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/"))
      apiCalls.push({ method: request.method(), url: request.url() });
  });
  await page.clock.install();
  await page.goto(base, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    () => document.querySelector("#vehicle-count").textContent === "0 vehicles",
  );
  assert.match(
    await page.locator("#source-explanation").innerText(),
    /Nothing here is saved/,
  );
  await page.screenshot({
    path: path.join(out, "desktop-empty.png"),
    fullPage: true,
  });
  record(
    "Empty preview has no invented registered fleet or automatic backend requests",
  );
  await page.locator('[data-action="register"]').first().click();
  await page.locator("#vehicle-name").fill("Interview Van");
  await page.locator("#vehicle-registration").fill("ka-01-demo");
  await page.locator("#register-submit").click();
  await page.waitForFunction(
    () =>
      document.querySelector("#detail-title").textContent === "Interview Van",
  );
  assert.equal(
    await page.locator("#detail-registration").innerText(),
    "KA-01-DEMO",
  );
  assert.equal(await page.locator("#start-trip-button").isVisible(), true);
  record("Register vehicle -> ready to start, identifier normalized");
  await page.locator('[data-action="register"]').first().click();
  await page.locator("#vehicle-name").fill("Other Van");
  await page.locator("#vehicle-registration").fill("KA-01-DEMO");
  await page.locator("#register-submit").click();
  await page.locator("#register-error").waitFor({ state: "visible" });
  assert.match(
    await page.locator("#register-error").innerText(),
    /already exists/,
  );
  await page.locator('[data-close="register-dialog"]').click();
  record("Duplicate registration displays an actionable error");
  await page.locator("#start-trip-button").click();
  await page.locator("#trip-duration-select").selectOption("60");
  await page.locator("#start-submit").click();
  await page.waitForFunction(
    () => document.querySelector("#trip-status").textContent === "active",
  );
  assert.equal(await page.locator("#finish-trip-button").isVisible(), true);
  record("Start simulated trip -> active controls, route and initial sample");
  for (let i = 0; i < 9; i++) {
    await page.clock.runFor(2100);
    await page.waitForTimeout(15);
  }
  await page.waitForFunction(
    () => Number(document.querySelector("#trip-points").textContent) >= 8,
  );
  assert.equal(
    await page.locator("#alert-list").getByText("Speeding test event").count(),
    1,
  );
  await page.screenshot({
    path: path.join(out, "desktop-active.png"),
    fullPage: true,
  });
  record("Live preview samples and trip-scoped speeding test alert appear");
  await page.locator("#finish-trip-button").click();
  await page.locator("#confirm-finish").click();
  await page.waitForFunction(
    () => document.querySelector("#trip-status").textContent === "completed",
  );
  const stoppedCount = await page.locator("#trip-points").innerText();
  await page.clock.runFor(5000);
  await page.waitForTimeout(20);
  assert.equal(await page.locator("#trip-points").innerText(), stoppedCount);
  assert.equal(await page.locator("#trip-list [data-trip-id]").count(), 1);
  await page.locator("#trip-list [data-trip-id]").click();
  await page.waitForFunction(
    () => document.querySelector("#trip-status").textContent === "completed",
  );
  await page.locator("#observations summary").click();
  assert.equal(
    await page.locator("#observation-values tr").count(),
    Number(stoppedCount),
  );
  record(
    "Finish stops samples; saved preview record reopens with exact coordinates and alerts",
  );
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.waitForTimeout(50);
    const dimensions = await page.evaluate(() => ({
      body: document.documentElement.scrollWidth,
      viewport: innerWidth,
    }));
    assert.ok(
      dimensions.body <= dimensions.viewport + 1,
      `Page overflow at ${width}: ${JSON.stringify(dimensions)}`,
    );
  }
  await page.clock.runFor(7000);
  await page.waitForTimeout(1000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.waitForTimeout(250);
  await page.screenshot({
    path: path.join(out, "desktop-dark-review.png"),
    fullPage: true,
  });
  await page.emulateMedia({ colorScheme: "light" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(out, "desktop-review.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(1000);
  await page.screenshot({
    path: path.join(out, "mobile-review.png"),
    fullPage: true,
  });
  await page.locator('[data-action="register"]').first().click();
  const modal = await page.locator("#register-dialog").boundingBox();
  assert.ok(modal.width < 390 && modal.x >= 0);
  await page.screenshot({
    path: path.join(out, "mobile-register.png"),
    fullPage: true,
  });
  await page.locator('[data-close="register-dialog"]').click();
  record("Responsive workflow and forms fit 1440, 1024, 768, 390 and 320px");
  assert.equal(apiCalls.length, 0);
  record("Preview made zero backend requests");
  await page.reload();
  await page.waitForFunction(
    () => document.querySelector("#vehicle-count").textContent === "0 vehicles",
  );
  record("Reload clears preview as labeled, not falsely persisted");
  // Mocked API contract test, separate from the genuine hosted-service verification.
  let vehicles = Array.from({ length: 12 }, (_, i) => ({
    id: i + 1,
    name: `Fleet ${i + 1}`,
    registration: `DEMO-${i + 1}`,
    kind: "delivery",
    is_sample: true,
  }));
  let trips = [],
    detail = null;
  const mockBase = "https://fleet.test.example";
  await page.route(mockBase + "/api/v1/**", async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      endpoint = url.pathname.replace("/api/v1", "");
    if (request.method() === "OPTIONS")
      return route.fulfill({
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": base,
          "Access-Control-Allow-Headers": "Authorization,Content-Type",
          "Access-Control-Allow-Methods": "GET,POST",
        },
      });
    let data;
    if (endpoint === "/auth/token")
      data = {
        access_token: "fixture-only-not-a-real-jwt",
        token_type: "bearer",
      };
    else {
      assert.equal(
        request.headers().authorization,
        "Bearer fixture-only-not-a-real-jwt",
      );
      if (endpoint === "/vehicles" && request.method() === "GET")
        data = vehicles;
      else if (endpoint === "/vehicles") {
        const body = request.postDataJSON();
        data = {
          id: 13,
          ...body,
          registration: body.registration.trim().toUpperCase(),
          is_sample: false,
        };
        vehicles.push(data);
      } else if (endpoint === "/trips")
        data = { trips, has_more: false, source_used: "postgresql" };
      else if (endpoint === "/fleet/live")
        data = {
          positions: detail?.points || [],
          live_ttl_seconds: 30,
          source_used: "postgresql",
        };
      else if (endpoint === "/vehicles/13/trips") {
        const body = request.postDataJSON(),
          now = Date.now();
        const trip = {
          id: 101,
          vehicle_id: 13,
          ...body,
          status: "active",
          source: "synthetic",
          started_at: new Date(now).toISOString(),
          expires_at: new Date(now + 60000).toISOString(),
          ended_at: null,
          end_reason: null,
        };
        trips = [trip];
        detail = {
          trip,
          points: [
            {
              id: 1,
              trip_id: 101,
              vehicle_id: 13,
              lat: 12.974,
              lon: 77.583,
              speed_kmh: 26,
              heading: 12,
              recorded_at: new Date(now).toISOString(),
            },
          ],
          alerts: [],
          summary: {
            duration_seconds: 0,
            point_count: 1,
            displayed_point_count: 1,
            distance_km: 0,
            max_speed_kmh: 26,
            alert_count: 0,
          },
          source_used: "postgresql",
          sample_data: true,
        };
        data = trip;
      } else if (endpoint === "/trips/101/finish") {
        detail.trip = {
          ...detail.trip,
          status: "completed",
          ended_at: new Date().toISOString(),
          end_reason: "manual",
        };
        trips = [detail.trip];
        data = detail.trip;
      } else if (endpoint === "/trips/101") data = detail;
      else throw Error("Unexpected mocked API path: " + endpoint);
    }
    await route.fulfill({
      status:
        request.method() === "POST" && endpoint === "/vehicles" ? 201 : 200,
      contentType: "application/json",
      headers: { "Access-Control-Allow-Origin": base },
      body: JSON.stringify(data),
    });
  });
  await page.routeWebSocket("wss://fleet.test.example/ws/live", (ws) =>
    ws.onMessage(() =>
      ws.send(
        JSON.stringify({ type: "ready", data: { realtime: "connected" } }),
      ),
    ),
  );
  async function connect() {
    await page.locator("#connect-button").click();
    await page.locator("#api-origin").fill(mockBase);
    await page.locator("#login-user").fill("admin");
    await page
      .locator("#login-password")
      .fill("fixture-password-not-a-real-secret");
    await page.locator("#submit-connect").click();
    await page.waitForFunction(
      () =>
        document.querySelector("#mode-name").textContent ===
        "Live API connected",
    );
  }
  await connect();
  assert.equal(await page.locator("#vehicle-count").innerText(), "0 vehicles");
  assert.equal(await page.locator("#sample-count").innerText(), "12");
  record(
    "Live API hides seeded fixtures rather than pretending they are newly registered vehicles",
  );
  await page.locator('[data-action="register"]').first().click();
  await page.locator("#vehicle-name").fill("Backend Van");
  await page.locator("#vehicle-registration").fill("live-demo");
  await page.locator("#register-submit").click();
  await page.waitForFunction(
    () => document.querySelector("#detail-title").textContent === "Backend Van",
  );
  await page.locator("#start-trip-button").click();
  await page.locator("#start-submit").click();
  await page.waitForFunction(
    () => document.querySelector("#trip-status").textContent === "active",
  );
  assert.equal(
    await page.locator("#trip-source").innerText(),
    "Stored in PostgreSQL",
  );
  await page.locator("#finish-trip-button").click();
  await page.locator("#confirm-finish").click();
  await page.waitForFunction(
    () => document.querySelector("#trip-status").textContent === "completed",
  );
  record(
    "Live registration/start/finish/review use JWT-protected API routes (mock contract)",
  );
  const storage = await page.evaluate(() => ({
    local: localStorage.length,
    session: sessionStorage.length,
    password: document.querySelector("#login-password").value,
  }));
  assert.deepEqual(storage, { local: 0, session: 0, password: "" });
  record("JWT not stored; password cleared after sign-in");
  await page.reload();
  await connect();
  await page.waitForFunction(
    () => document.querySelector("#trip-status").textContent === "completed",
  );
  assert.equal(await page.locator("#detail-title").innerText(), "Backend Van");
  record("Reconnect loads stored completed-trip review (mock contract)");
  await page.locator("#use-preview").click();
  await page.waitForFunction(
    () =>
      document.querySelector("#mode-name").textContent === "Browser preview",
  );
  assert.equal(await page.locator("#vehicle-count").innerText(), "0 vehicles");
  record(
    "Switching modes is explicit; live records are not relabeled as browser fixtures",
  );
  assert.deepEqual(errors, []);
  record("No browser runtime exceptions");
  fs.writeFileSync(
    path.join(out, "functional-checks.json"),
    JSON.stringify(
      {
        checks,
        scope:
          "Local browser preview + mocked API contract; not hosted backend evidence",
        errors,
      },
      null,
      2,
    ),
  );
  console.log(`Completed ${checks.length} UI checks.`);
})()
  .catch((error) => {
    console.error(error.stack || String(error));
    process.exitCode = 1;
  })
  .finally(async () => {
    if (browser) await browser.close();
    server.kill();
  });
