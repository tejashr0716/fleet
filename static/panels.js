import {
  state,
  el,
  clock,
  stamp,
  duration,
  visibleVehicles,
  activeTrip,
  routeNames,
} from "./config.js";
let chart;
const text = (id, value) => (el(id).textContent = value);
const make = (tag, className, value) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
};
export function initializePanels() {
  if (!window.Chart) return;
  const colors = getComputedStyle(document.documentElement),
    purple = colors.getPropertyValue("--purple").trim(),
    muted = colors.getPropertyValue("--muted").trim();
  chart = new Chart(el("speed-chart"), {
    type: "line",
    data: {
      datasets: [
        {
          label: "Synthetic input speed",
          data: [],
          borderColor: purple,
          backgroundColor: purple,
          pointRadius: 2,
          borderWidth: 2,
          tension: 0,
          fill: false,
          clip: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      parsing: false,
      normalized: true,
      interaction: { mode: "index", intersect: false, axis: "x" },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) =>
              items.length ? new Date(items[0].parsed.x).toLocaleString() : "",
            label: (item) => `${item.parsed.y.toFixed(1)} km/h`,
          },
        },
      },
      scales: {
        x: {
          type: "linear",
          grid: { display: false },
          ticks: {
            maxTicksLimit: 3,
            maxRotation: 0,
            color: muted,
            font: { size: 12 },
            callback: (value) => clock(value),
          },
        },
        y: {
          min: 0,
          max: 120,
          ticks: { stepSize: 30, color: muted, font: { size: 12 } },
          grid: { color: colors.getPropertyValue("--grid").trim() },
        },
      },
    },
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener(
    "change",
    updateChartTheme,
  );
}
function updateChartTheme() {
  if (!chart) return;
  const colors = getComputedStyle(document.documentElement);
  const purple = colors.getPropertyValue("--purple").trim();
  chart.data.datasets[0].borderColor = purple;
  chart.data.datasets[0].backgroundColor = purple;
  for (const axis of ["x", "y"])
    chart.options.scales[axis].ticks.color = colors
      .getPropertyValue("--muted")
      .trim();
  chart.options.scales.y.grid.color = colors.getPropertyValue("--grid").trim();
  chart.update("none");
}
export function renderPanels(onSelect, onReview) {
  const vehicles = visibleVehicles(),
    vehicle = state.vehicles.find((v) => v.id === state.selected),
    detail = state.detail,
    trip = detail?.trip,
    active = activeTrip();
  text(
    "vehicle-count",
    `${vehicles.length} vehicle${vehicles.length === 1 ? "" : "s"}`,
  );
  text(
    "active-count",
    `${state.trips.filter((t) => t.status === "active").length} running`,
  );
  el("show-samples-wrap").hidden = !state.vehicles.some((v) => v.is_sample);
  text("sample-count", state.vehicles.filter((v) => v.is_sample).length);
  const filtered = vehicles.filter((v) =>
    `${v.name} ${v.registration}`.toLowerCase().includes(state.query),
  );
  const list = el("vehicle-list"),
    scroll = list.scrollTop,
    focused =
      document.activeElement?.closest(".vehicle-row")?.dataset.vehicleId;
  list.replaceChildren();
  if (!filtered.length)
    list.append(
      make(
        "p",
        "empty",
        vehicles.length
          ? "No matching vehicle. Try a different name or registration."
          : "No vehicles yet. Register one to start your first trip.",
      ),
    );
  for (const v of filtered) {
    const button = make(
      "button",
      `vehicle-row ${v.id === state.selected ? "selected" : ""}`,
    );
    button.type = "button";
    button.dataset.vehicleId = v.id;
    button.setAttribute("aria-pressed", String(v.id === state.selected));
    const running = state.trips.some(
      (t) => t.vehicle_id === v.id && t.status === "active",
    );
    const icon = make("span", "vehicle-avatar", String(v.id).padStart(2, "0")),
      copy = make("span", "vehicle-copy");
    copy.append(make("strong", "", v.name), make("span", "", v.registration));
    button.append(
      icon,
      copy,
      make(
        "span",
        `tag ${running ? "positive" : ""}`,
        running ? "Active" : "Ready",
      ),
    );
    button.addEventListener("click", () => onSelect(v.id));
    list.append(button);
  }
  list.scrollTop = scroll;
  if (focused)
    list
      .querySelector(`[data-vehicle-id="${focused}"]`)
      ?.focus({ preventScroll: true });
  el("vehicle-empty").hidden = !!vehicle;
  el("vehicle-controls").hidden = !vehicle;
  text("detail-title", vehicle?.name || "Choose a vehicle");
  text(
    "detail-registration",
    vehicle?.registration || "Register a vehicle to begin",
  );
  text(
    "vehicle-kind",
    vehicle
      ? vehicle.kind.charAt(0).toUpperCase() + vehicle.kind.slice(1)
      : "—",
  );
  el("start-trip-button").hidden = !!active;
  el("start-trip-button").disabled = state.busy;
  el("finish-trip-button").hidden = !active || trip?.id !== active.id;
  el("finish-trip-button").disabled = state.busy;
  el("view-active-button").hidden = !active || trip?.id === active.id;
  el("trip-record").hidden = !trip;
  el("no-trip-message").hidden = !!trip;
  const running = trip?.status === "active",
    points = detail?.points || [],
    last = points.at(-1);
  text("trip-status", trip?.status || "Not started");
  el("trip-status").className =
    `tag ${running ? "positive" : trip?.status === "interrupted" ? "attention" : ""}`;
  text("trip-id", trip ? `Trip #${trip.id}` : "Trip controls");
  text("route-name", trip ? routeNames[trip.route_key] : "—");
  text(
    "trip-source",
    state.mode === "live" ? "Stored in PostgreSQL" : "Preview · this tab only",
  );
  text("trip-started", stamp(trip?.started_at));
  text(
    "trip-ended",
    running
      ? `Auto-finishes at ${clock(trip.expires_at)}`
      : stamp(trip?.ended_at),
  );
  text(
    "end-reason",
    trip?.end_reason
      ? {
          manual: "Finished by you",
          time_limit: "Automatic time limit",
          server_restart: "Server restarted",
          service_shutdown: "Service stopped",
          simulator_error: "Simulator interrupted",
          preview_switched: "Preview stopped when API connected",
        }[trip.end_reason] || trip.end_reason
      : "Simulated trip in progress",
  );
  const summary = detail?.summary;
  text("trip-duration", summary ? duration(summary.duration_seconds) : "—");
  text("trip-points", summary?.point_count ?? "—");
  text(
    "trip-distance",
    summary?.distance_km == null ? "—" : `${summary.distance_km.toFixed(2)} km`,
  );
  text(
    "trip-max-speed",
    summary?.max_speed_kmh == null
      ? "—"
      : `${summary.max_speed_kmh.toFixed(1)} km/h`,
  );
  text(
    "map-title",
    trip
      ? running
        ? "Live trip tracking"
        : "Trip route review"
      : "Your trip map",
  );
  text(
    "map-context",
    trip
      ? `${routeNames[trip.route_key]} · ${points.length} ${state.mode === "live" ? "stored" : "preview"} samples${detail.has_more_points ? " · first 5,000 shown" : ""}`
      : "Start a trip to see GPS positions and its observed trace",
  );
  el("map-empty").hidden = points.length > 0;
  el("fit-map").disabled = !points.length;
  text(
    "map-empty-title",
    !vehicle
      ? "Your first trip starts here"
      : !trip
        ? "Ready when you are"
        : "No recorded positions",
  );
  text(
    "map-empty-copy",
    !vehicle
      ? "Register a vehicle, choose a demo route, then start tracking."
      : !trip
        ? `Start a simulated trip for ${vehicle.name}.`
        : "This trip has no stored samples. Its interruption details remain in the record.",
  );
  text("position-speed", last ? `${last.speed_kmh.toFixed(1)} km/h` : "—");
  text("position-time", last ? clock(last.recorded_at) : "No GPS samples yet");
  text(
    "position-label",
    running ? "Latest synthetic speed" : "Last synthetic speed",
  );
  text(
    "position-status",
    running
      ? last && Date.now() - Date.parse(last.recorded_at) > state.ttl * 1000
        ? "Signal stale"
        : "Trip active"
      : trip
        ? "Trip finished"
        : "Waiting for a trip",
  );
  const hlist = el("trip-list"),
    tripFocus = document.activeElement?.closest(".trip-row")?.dataset.tripId;
  hlist.replaceChildren();
  const history = state.trips.filter((t) => t.vehicle_id === state.selected);
  text("history-title", vehicle ? `Trips for ${vehicle.name}` : "Trip history");
  text(
    "history-count",
    `${history.length}${state.hasMoreTrips ? " recent" : ""} trip${history.length === 1 ? "" : "s"}`,
  );
  if (!history.length)
    hlist.append(
      make(
        "p",
        "empty",
        vehicle
          ? "No trips yet. Start a simulated trip; finish it to review its route and alerts here."
          : "Choose or register a vehicle to see its trips.",
      ),
    );
  for (const t of history) {
    const button = make(
      "button",
      `trip-row ${t.id === state.selectedTrip ? "selected" : ""}`,
    );
    button.type = "button";
    button.dataset.tripId = t.id;
    button.setAttribute("aria-pressed", String(t.id === state.selectedTrip));
    const copy = make("span", "trip-copy");
    copy.append(
      make("strong", "", `Trip #${t.id} · ${routeNames[t.route_key]}`),
      make(
        "span",
        "muted",
        `${stamp(t.started_at)} · ${t.status === "active" ? "Running" : t.status === "interrupted" ? "Interrupted" : "Finished"}`,
      ),
    );
    button.append(
      copy,
      make(
        "span",
        "trip-review",
        t.status === "active" ? "View live →" : "Review →",
      ),
    );
    button.addEventListener("click", () => onReview(t.id));
    hlist.append(button);
  }
  if (tripFocus)
    hlist
      .querySelector(`[data-trip-id="${tripFocus}"]`)
      ?.focus({ preventScroll: true });
  text(
    "history-source",
    state.mode === "live"
      ? "Saved trips remain after refresh and reconnect. Most recent 200 trips are loaded."
      : "Preview records are in this tab’s memory. Reloading clears them; connect the API for saved records.",
  );
  renderObservations(points, trip);
  renderAlerts(detail);
  const step = !vehicle ? 1 : !trip ? 2 : running ? 3 : 5;
  for (const node of document.querySelectorAll(".workflow-step")) {
    const number = Number(node.dataset.step);
    node.classList.toggle("current", number === step);
    node.classList.toggle("done", number < step);
    if (number === step) node.setAttribute("aria-current", "step");
    else node.removeAttribute("aria-current");
  }
}
function renderObservations(points, trip) {
  const chartPoints = points.slice(-60);
  el("chart-empty").hidden = Boolean(chart && chartPoints.length >= 2);
  text(
    "chart-empty",
    chart
      ? "Waiting for two GPS samples…"
      : "Chart unavailable. Exact values are listed below.",
  );
  if (chart) {
    chart.data.datasets[0].data = chartPoints.map((p) => ({
      x: Date.parse(p.recorded_at),
      y: p.speed_kmh,
    }));
    chart.options.scales.y.max =
      Math.ceil(Math.max(120, ...chartPoints.map((p) => p.speed_kmh)) / 30) *
      30;
    chart.update("none");
  }
  const caption = chartPoints.length
    ? `${chartPoints.length} synthetic speed inputs, from ${clock(chartPoints[0].recorded_at)} to ${clock(chartPoints.at(-1).recorded_at)}; latest ${chartPoints.at(-1).speed_kmh.toFixed(1)} km/h.`
    : "No synthetic speed samples.";
  text("chart-summary", caption);
  el("speed-chart").setAttribute("aria-label", caption);
  text(
    "chart-coverage",
    `Last ${chartPoints.length} ${state.mode === "live" ? "stored" : "preview"} samples · km/h`,
  );
  const table = el("observation-values");
  table.replaceChildren();
  for (const p of points) {
    const row = make("tr");
    row.append(
      make("td", "", clock(p.recorded_at)),
      make("td", "", p.lat.toFixed(5)),
      make("td", "", p.lon.toFixed(5)),
      make("td", "", p.speed_kmh.toFixed(1)),
    );
    table.append(row);
  }
  el("observations").hidden = !trip;
}
function renderAlerts(detail) {
  const alerts = detail?.alerts || [];
  text(
    "alert-count",
    `${detail?.summary.alert_count || 0} alert${detail?.summary.alert_count === 1 ? "" : "s"}`,
  );
  const list = el("alert-list");
  list.replaceChildren();
  if (!alerts.length)
    list.append(
      make(
        "p",
        "empty",
        detail
          ? "No alert events for this trip. If enabled, the simulator injects a 92 km/h test event after about 16 seconds."
          : "Trip alerts appear here after you start tracking.",
      ),
    );
  for (const a of alerts) {
    const row = make("div", "alert-row"),
      icon = make("span", "alert-icon", a.kind === "speeding" ? "!" : "↔"),
      body = make("div", "alert-body");
    body.append(
      make(
        "strong",
        "",
        a.kind === "speeding"
          ? "Speeding test event"
          : a.kind === "geofence_enter"
            ? "Entered demo geofence"
            : "Exited demo geofence",
      ),
      make(
        "p",
        "muted",
        a.kind === "speeding"
          ? `${Number(a.details.speed_kmh).toFixed(1)} km/h · limit ${a.details.limit_kmh} km/h`
          : a.details.geofence_name,
      ),
    );
    row.append(icon, body, make("time", "muted", clock(a.recorded_at)));
    list.append(row);
  }
  text(
    "alert-source",
    detail?.has_more_alerts
      ? "Most recent 200 trip alerts shown. Rules are thresholds, not ML."
      : "Only this trip’s alerts. Speeding and circular geofence rules; no machine learning.",
  );
}
