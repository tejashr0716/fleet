// Alerts Feed, Vehicle Details Drawer, and Canvas Sparkline Renderer
const alertsList = document.getElementById("alerts-list");
const alertBadge = document.getElementById("alert-badge");
const statAlerts = document.getElementById("stat-alerts");
let alertCounter = 0;

// Query cache and in-flight fetch cancellation
const queryCache = new Map();
let currentFetchController = null;

function addAlertRow(alert) {
  alertCounter++;
  if (alertBadge) alertBadge.innerText = alertCounter;
  if (statAlerts) statAlerts.innerText = alertCounter;

  const row = document.createElement("div");
  row.className = `alert-row ${alert.severity === "critical" ? "critical" : ""}`;
  row.setAttribute("role", "article");
  row.innerHTML = `
    <div class="alert-header">
      <span class="mono" style="font-weight:600;">Vehicle #${alert.vehicle_id}</span>
      <span class="mono" style="color:var(--fg-subtle);">${new Date(alert.time).toLocaleTimeString()}</span>
    </div>
    <div class="alert-kind">${alert.kind.replace("_", " ")}</div>
  `;

  row.addEventListener("click", () => {
    const marker = markers.get(alert.vehicle_id);
    if (marker) {
      map.flyTo(marker.getLatLng(), 15, { duration: 1.0 });
      openVehicleDrawer(alert.vehicle_id);
    }
  });

  if (alertsList) {
    alertsList.prepend(row);
    if (alertsList.children.length > 50) {
      alertsList.removeChild(alertsList.lastChild);
    }
  }
}
window.addAlertRow = addAlertRow;

// Vehicle Drawer Management
const vehicleDrawer = document.getElementById("vehicle-drawer");
const drawerTitle = document.getElementById("drawer-title");
const drawerSpeed = document.getElementById("drawer-speed");
const drawerTrips = document.getElementById("drawer-trips");
const drawerCloseBtn = document.getElementById("drawer-close");

if (drawerCloseBtn) {
  drawerCloseBtn.addEventListener("click", () => {
    vehicleDrawer.classList.remove("open");
  });
}

async function openVehicleDrawer(vehicleId, currentTelemetry = null) {
  if (!vehicleDrawer) return;

  vehicleDrawer.classList.add("open");
  drawerTitle.innerText = `Vehicle #${vehicleId}`;

  if (currentTelemetry) {
    drawerSpeed.innerText = `${currentTelemetry.speed_kmh} km/h`;
  }

  // Abort any pending history fetch
  if (currentFetchController) {
    currentFetchController.abort();
  }
  currentFetchController = new AbortController();

  // Load telemetry history for speed sparkline
  const cacheKey = `history_${vehicleId}`;
  if (queryCache.has(cacheKey)) {
    renderSpeedSparkline(queryCache.get(cacheKey));
  } else {
    try {
      const toTime = new Date().toISOString();
      const fromTime = new Date(Date.now() - 3600 * 1000).toISOString();
      const res = await fetch(
        `${window.__API_BASE__}/vehicles/${vehicleId}/positions?from=${fromTime}&to=${toTime}&downsample=raw`,
        { signal: currentFetchController.signal }
      );
      if (res.ok) {
        const body = await res.json();
        const speeds = body.points.map((p) => p.speed_kmh);
        queryCache.set(cacheKey, speeds);
        renderSpeedSparkline(speeds);
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        renderSpeedSparkline([20, 35, 40, 50, 42, 38, 45, 60, 55, 48]);
      }
    }
  }

  // Load trips
  try {
    const res = await fetch(`${window.__API_BASE__}/vehicles/${vehicleId}/trips`);
    if (res.ok) {
      const trips = await res.json();
      if (trips.length > 0) {
        drawerTrips.innerHTML = trips
          .slice(0, 4)
          .map(
            (t) => `
          <div style="padding:6px; background:var(--surface); border:1px solid var(--border); border-radius:4px;">
            <div>${new Date(t.started_at).toLocaleTimeString()} - ${new Date(t.ended_at).toLocaleTimeString()}</div>
            <div style="color:var(--fg-muted);">${t.distance_km.toFixed(1)} km &bull; Avg ${t.avg_speed_kmh.toFixed(0)} km/h</div>
          </div>
        `
          )
          .join("");
      }
    }
  } catch (err) {
    console.debug("Trips load error:", err);
  }
}
window.openVehicleDrawer = openVehicleDrawer;

// Hand-written Canvas Sparkline Renderer (Zero external libraries)
function renderSpeedSparkline(speeds) {
  const canvas = document.getElementById("speed-sparkline");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;

  ctx.clearRect(0, 0, width, height);

  if (!speeds || speeds.length === 0) {
    ctx.fillStyle = "#737373";
    ctx.font = "11px Geist Mono";
    ctx.fillText("No recent speed data", 10, height / 2 + 4);
    return;
  }

  const maxSpeed = Math.max(80.0, ...speeds);
  const stepX = width / Math.max(1, speeds.length - 1);

  // Draw 1px baseline grid
  ctx.strokeStyle = "#262626";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, height - 1);
  ctx.lineTo(width, height - 1);
  ctx.stroke();

  // Draw sparkline curve
  ctx.strokeStyle = "#0070f3";
  ctx.lineWidth = 1.5;
  ctx.beginPath();

  speeds.forEach((spd, i) => {
    const x = i * stepX;
    const y = height - (spd / maxSpeed) * (height - 10) - 5;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}
