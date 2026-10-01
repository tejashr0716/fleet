import { state, el, toast, visibleVehicles, activeTrip } from "./config.js";
import { PreviewFleet } from "./preview.js";
import { LiveFleet } from "./live.js";
import { initializeMap, renderMap, fitMap } from "./map.js";
import { initializePanels, renderPanels } from "./panels.js";
let preview,
  service,
  timer,
  lastLiveSync = 0,
  refreshing = null;
function render() {
  renderPanels(selectVehicle, reviewTrip);
  const detail = state.detail,
    points = detail?.points || [],
    vehicleIds = new Set(visibleVehicles().map((v) => v.id));
  const positions =
    detail?.trip.status !== "active" && points.length
      ? [points.at(-1)]
      : [...state.positions.values()].filter((p) =>
          vehicleIds.has(p.vehicle_id),
        );
  renderMap(positions, state.selected, points);
}
function setConnection(connected, note) {
  state.connected = connected;
  el("mode-name").textContent =
    state.mode === "preview"
      ? "Browser preview"
      : connected
        ? "Live API connected"
        : "Live API · connection interrupted";
  el("mode-note").textContent = note;
  el("mode-dot").className =
    `dot ${state.mode === "preview" ? "attention" : connected ? "positive" : "attention"}`;
}
async function refresh(fit = false) {
  if (refreshing) {
    await refreshing;
    return refresh(fit);
  }
  const current = service;
  const work = (async () => {
    const [vehicles, trips, positions] = await Promise.all([
      current.listVehicles(),
      current.listTrips(),
      current.snapshot(),
    ]);
    if (current !== service) return;
    state.vehicles = vehicles;
    state.trips = trips;
    state.hasMoreTrips = !!current.hasMoreTrips;
    for (const p of positions) {
      const old = state.positions.get(p.vehicle_id);
      if (!old || Date.parse(p.recorded_at) > Date.parse(old.recorded_at))
        state.positions.set(p.vehicle_id, p);
    }
    if (current.ttl) state.ttl = current.ttl;
    if (!visibleVehicles().some((v) => v.id === state.selected)) {
      state.selected = visibleVehicles()[0]?.id || 0;
      state.selectedTrip = 0;
      state.detail = null;
    }
    if (!state.selectedTrip && state.selected)
      state.selectedTrip =
        state.trips.find((t) => t.vehicle_id === state.selected)?.id || 0;
    if (state.selectedTrip) {
      const id = state.selectedTrip;
      const d = await current.detail(id);
      if (current !== service || id !== state.selectedTrip) return;
      state.detail = d;
      const index = state.trips.findIndex((t) => t.id === d.trip.id);
      if (index >= 0) state.trips[index] = d.trip;
    }
    render();
    if (fit) fitMap();
  })();
  refreshing = work;
  try {
    await work;
  } finally {
    if (refreshing === work) refreshing = null;
  }
}
async function selectVehicle(id) {
  state.selected = id;
  state.selectedTrip =
    state.trips.find((t) => t.vehicle_id === id && t.status === "active")?.id ||
    state.trips.find((t) => t.vehicle_id === id)?.id ||
    0;
  state.detail = null;
  render();
  try {
    await refresh(true);
  } catch (error) {
    toast(error.message);
  }
}
async function reviewTrip(id) {
  state.selectedTrip = id;
  state.detail = null;
  render();
  const current = service;
  try {
    const detail = await current.detail(id);
    if (current !== service || state.selectedTrip !== id) return;
    state.detail = detail;
    render();
    fitMap();
  } catch (error) {
    toast(error.message);
  }
}
function openRegister() {
  el("register-form").reset();
  el("register-error").hidden = true;
  el("register-mode").textContent =
    state.mode === "live"
      ? "Saved to your PostgreSQL database after registration."
      : "Preview only: this vehicle exists in this tab until reload.";
  el("register-dialog").showModal();
}
async function usePreview() {
  service?.disconnect();
  service = preview;
  state.mode = "preview";
  state.token = null;
  state.selected = 0;
  state.selectedTrip = 0;
  state.detail = null;
  state.positions.clear();
  state.showSamples = false;
  el("show-samples").checked = false;
  el("use-preview").hidden = true;
  el("reset-preview").hidden = false;
  el("connect-button").textContent = "Connect live API";
  el("source-explanation").textContent =
    "Preview: register a vehicle and complete a simulated trip in this tab. Nothing here is saved to a server. Connect the API to use real PostgreSQL, Redis and WebSockets.";
  setConnection(false, "This tab only · synthetic GPS");
  await refresh(true);
}
function liveEvent(message) {
  if (state.mode !== "live") return;
  if (message.type === "connection") {
    setConnection(message.connected, message.note);
    return;
  }
  if (message.type === "position") {
    const p = message.data,
      old = state.positions.get(p.vehicle_id);
    if (!old || Date.parse(p.recorded_at) > Date.parse(old.recorded_at))
      state.positions.set(p.vehicle_id, p);
    if (
      state.detail?.trip.id === p.trip_id &&
      state.detail.trip.status === "active" &&
      !state.detail.points.some((x) => x.recorded_at === p.recorded_at)
    )
      state.detail.points.push(p);
    render();
  }
  if (["alert", "gap"].includes(message.type)) lastLiveSync = 0;
}
async function main() {
  initializeMap();
  initializePanels();
  for (const button of document.querySelectorAll('[data-action="register"]'))
    button.addEventListener("click", openRegister);
  for (const button of document.querySelectorAll("[data-close]"))
    button.addEventListener("click", () => el(button.dataset.close).close());
  el("vehicle-search").addEventListener("input", (event) => {
    state.query = event.target.value.toLowerCase();
    render();
  });
  el("show-samples").addEventListener("change", async (event) => {
    state.showSamples = event.target.checked;
    try {
      await refresh(true);
    } catch (error) {
      toast(error.message);
    }
  });
  el("fit-map").addEventListener("click", fitMap);
  el("register-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const current = service;
    const button = el("register-submit");
    button.disabled = true;
    el("register-error").hidden = true;
    try {
      const vehicle = await current.register({
        name: el("vehicle-name").value,
        registration: el("vehicle-registration").value,
        kind: el("vehicle-type").value,
      });
      if (current !== service) return;
      state.selected = vehicle.id;
      state.selectedTrip = 0;
      state.detail = null;
      await refresh();
      el("register-dialog").close();
      toast(`${vehicle.name} registered. Now start its simulated trip.`);
    } catch (error) {
      el("register-error").textContent = error.message;
      el("register-error").hidden = false;
    } finally {
      button.disabled = false;
    }
  });
  el("start-trip-button").addEventListener("click", () => {
    el("start-error").hidden = true;
    el("trip-vehicle-name").textContent =
      state.vehicles.find((v) => v.id === state.selected)?.name || "vehicle";
    el("start-mode").textContent =
      state.mode === "live"
        ? "The Python simulator will write samples to PostgreSQL and stream updates through Redis/WebSockets."
        : "The browser will generate samples for this tab only. Connect the API for saved trips.";
    el("start-dialog").showModal();
  });
  el("start-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const current = service;
    state.busy = true;
    el("start-submit").disabled = true;
    el("start-error").hidden = true;
    try {
      const trip = await current.start(state.selected, {
        route_key: el("trip-route").value,
        duration_seconds: Number(el("trip-duration-select").value),
        include_speeding: el("include-speeding").checked,
      });
      if (current !== service) return;
      state.selectedTrip = trip.id;
      await refresh(true);
      el("start-dialog").close();
      toast(
        "Trip started. GPS is simulated; use Finish trip when you’re ready to review.",
      );
    } catch (error) {
      el("start-error").textContent = error.message;
      el("start-error").hidden = false;
    } finally {
      state.busy = false;
      el("start-submit").disabled = false;
      render();
    }
  });
  el("finish-trip-button").addEventListener("click", () => {
    el("finish-error").hidden = true;
    el("finish-dialog").showModal();
  });
  el("confirm-finish").addEventListener("click", async () => {
    const current = service,
      id = activeTrip()?.id;
    if (!id) return;
    state.busy = true;
    el("confirm-finish").disabled = true;
    try {
      await current.finish(id);
      if (current !== service) return;
      state.selectedTrip = id;
      await refresh(true);
      el("finish-dialog").close();
      toast(
        state.mode === "live"
          ? "Trip finished and saved. Review its stored route and alerts below."
          : "Preview trip finished. Its route and alerts remain in this tab only.",
      );
    } catch (error) {
      el("finish-error").textContent = error.message;
      el("finish-error").hidden = false;
    } finally {
      state.busy = false;
      el("confirm-finish").disabled = false;
      render();
    }
  });
  el("view-active-button").addEventListener("click", () => {
    const active = activeTrip();
    if (active) reviewTrip(active.id);
  });
  el("connect-button").addEventListener("click", () => {
    el("api-origin").value =
      state.apiBase ||
      (location.pathname.startsWith("/static/")
        ? location.origin
        : "https://fleet-tejashr0716-demo.onrender.com");
    el("login-user").value = "admin";
    el("login-password").value = "";
    el("connect-error").hidden = true;
    el("connect-dialog").showModal();
  });
  el("connect-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    el("submit-connect").disabled = true;
    el("connect-error").hidden = true;
    let candidate;
    try {
      candidate = await LiveFleet.signIn(
        el("api-origin").value,
        el("login-user").value,
        el("login-password").value,
        liveEvent,
      );
      el("login-password").value = "";
      const [vehicles, trips, positions] = await Promise.all([
        candidate.listVehicles(),
        candidate.listTrips(),
        candidate.snapshot(),
      ]);
      service?.disconnect();
      preview.interrupt();
      service = candidate;
      state.mode = "live";
      state.apiBase = candidate.base;
      state.token = candidate.token;
      state.vehicles = vehicles;
      state.trips = trips;
      state.positions = new Map(positions.map((p) => [p.vehicle_id, p]));
      state.selected = vehicles.find((v) => !v.is_sample)?.id || 0;
      state.selectedTrip = 0;
      state.detail = null;
      state.showSamples = false;
      el("show-samples").checked = false;
      el("use-preview").hidden = false;
      el("reset-preview").hidden = true;
      el("connect-button").textContent = "Reconnect / sign in";
      el("source-explanation").textContent =
        "Live API: vehicles, trips, GPS history and alerts are saved in PostgreSQL. The Python GPS source is still synthetic—not real vehicle hardware. Redis/WebSocket delivery is real.";
      setConnection(true, "Connecting WebSocket · synthetic GPS");
      render();
      candidate.listen();
      lastLiveSync = Date.now();
      el("connect-dialog").close();
      await refresh(true);
      toast("Connected. Register your vehicle, then start its trip.");
    } catch (error) {
      if (candidate && candidate !== service) candidate.disconnect();
      el("connect-error").textContent =
        error instanceof TypeError
          ? "Connection failed. Check the API origin, server status and allowed origins. A free cloud instance may need about a minute to wake."
          : error.message;
      el("connect-error").hidden = false;
    } finally {
      el("submit-connect").disabled = false;
    }
  });
  el("use-preview").addEventListener("click", () =>
    usePreview().catch((error) => toast(error.message)),
  );
  el("reset-preview").addEventListener("click", () =>
    el("reset-dialog").showModal(),
  );
  el("confirm-reset").addEventListener("click", async () => {
    preview.reset();
    state.selected = 0;
    state.selectedTrip = 0;
    state.detail = null;
    state.positions.clear();
    el("reset-dialog").close();
    await refresh(true);
    toast("Preview reset. No server data was changed.");
  });
  try {
    const response = await fetch("demo/replay.json");
    if (!response.ok) throw new Error("Could not load sample routes.");
    preview = new PreviewFleet((await response.json()).routes);
    await usePreview();
  } catch (error) {
    el("source-explanation").textContent =
      error.message + " Serve this folder over HTTP, not file://.";
    toast(error.message);
    return;
  }
  timer = setInterval(async () => {
    if (document.hidden || refreshing || state.busy) return;
    try {
      if (state.mode === "preview") {
        preview.advance();
        await refresh();
      } else if (service.token && Date.now() - lastLiveSync >= 4000) {
        lastLiveSync = Date.now();
        await refresh();
      }
    } catch (error) {
      if (state.mode === "live") setConnection(false, error.message);
      toast(error.message);
    }
  }, 1000);
  addEventListener("pagehide", () => {
    clearInterval(timer);
    service?.disconnect();
    state.token = null;
  });
}
main();
