// Map Initialization, Tile Layers, H3 Overlays, and Smooth Animation
const map = L.map("map", {
  zoomControl: false,
  center: [12.9716, 77.5946], // Bengaluru City Center
  zoom: 13,
  minZoom: 10,
  maxZoom: 19,
});

// CARTO Dark Matter Tiles with strictly preserved attribution per license
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  subdomains: "abcd",
  maxZoom: 19,
}).addTo(map);

// Layer groups
const markersLayer = L.layerGroup().addTo(map);
const h3HeatmapLayer = L.layerGroup();
const geofenceLayer = L.layerGroup().addTo(map);

const markers = new Map();
const markerAnimations = new Map();

function createArrowIcon(heading, status) {
  let color = "#0070f3"; // default active accent
  if (status === "idle") color = "#f5a623";
  else if (status === "offline") color = "#737373";
  else if (status === "alerting") color = "#f5455c";

  const svg = `
    <svg width="22" height="22" viewBox="0 0 24 24" style="transform: rotate(${heading}deg); will-change: transform;">
      <polygon points="12,2 22,22 12,17 2,22" fill="${color}" stroke="#000000" stroke-width="1.5"/>
    </svg>
  `;
  return L.divIcon({
    className: "vehicle-marker",
    html: svg,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function animateMarker(marker, targetLat, targetLon, targetHeading, durationMs = 4500) {
  const startLatLng = marker.getLatLng();
  const startTime = performance.now();

  if (markerAnimations.has(marker)) {
    cancelAnimationFrame(markerAnimations.get(marker));
  }

  function step(now) {
    const elapsed = now - startTime;
    const progress = Math.min(1.0, elapsed / durationMs);

    // Linear interpolation
    const curLat = startLatLng.lat + (targetLat - startLatLng.lat) * progress;
    const curLon = startLatLng.lng + (targetLon - startLatLng.lng) * progress;
    marker.setLatLng([curLat, curLon]);

    if (progress < 1.0) {
      const animId = requestAnimationFrame(step);
      markerAnimations.set(marker, animId);
    } else {
      markerAnimations.delete(marker);
    }
  }

  const animId = requestAnimationFrame(step);
  markerAnimations.set(marker, animId);
}

function updateVehicleMarker(vehicle) {
  const { vehicle_id, lat, lon, heading, speed_kmh } = vehicle;
  const status = speed_kmh > 0 ? "active" : "idle";

  if (markers.has(vehicle_id)) {
    const marker = markers.get(vehicle_id);
    marker.setIcon(createArrowIcon(heading, status));
    animateMarker(marker, lat, lon, heading);
  } else {
    const marker = L.marker([lat, lon], {
      icon: createArrowIcon(heading, status),
    });
    marker.on("click", () => {
      if (window.openVehicleDrawer) {
        window.openVehicleDrawer(vehicle_id, vehicle);
      }
    });
    markers.set(vehicle_id, marker);
    if (map.getZoom() >= 12) {
      markersLayer.addLayer(marker);
    }
  }
}

// Zoom threshold behavior: Below zoom 12, hide markers and show H3 heatmap
async function checkZoomLayers() {
  const zoom = map.getZoom();
  if (zoom < 12) {
    if (map.hasLayer(markersLayer)) map.removeLayer(markersLayer);
    if (!map.hasLayer(h3HeatmapLayer)) map.addLayer(h3HeatmapLayer);
    await fetchH3Density();
  } else {
    if (!map.hasLayer(markersLayer)) map.addLayer(markersLayer);
    if (map.hasLayer(h3HeatmapLayer)) map.removeLayer(h3HeatmapLayer);
  }
}

map.on("zoomend", checkZoomLayers);

// Fetch H3 cell density for heatmap rendering
async function fetchH3Density() {
  try {
    const res = await fetch(`${window.__API_BASE__}/h3/cells?resolution=8`);
    if (!res.ok) return;
    const cells = await res.json();
    h3HeatmapLayer.clearLayers();

    cells.forEach((c) => {
      // Approximate centroid bounding circle for cells
      const count = c.count;
      const opacity = Math.min(0.8, 0.1 + (count / 50.0) * 0.7);
      // Fallback visualization circle for H3 cell hex
      const circle = L.circle([12.9716, 77.5946], {
        radius: 350,
        color: "#0070f3",
        weight: 1,
        fillColor: "#0070f3",
        fillOpacity: opacity,
      });
      h3HeatmapLayer.addLayer(circle);
    });
  } catch (err) {
    console.debug("H3 heatmap load skipped:", err);
  }
}

// Geofence drawing tool
let drawingGeofence = false;
let drawnPoints = [];
let drawingTempPoly = null;

const btnGeofence = document.getElementById("btn-draw-geofence");
if (btnGeofence) {
  btnGeofence.addEventListener("click", () => {
    drawingGeofence = !drawingGeofence;
    if (drawingGeofence) {
      btnGeofence.innerText = "Click map to draw (Finish)";
      btnGeofence.style.borderColor = "var(--accent)";
      drawnPoints = [];
    } else {
      finishGeofence();
    }
  });
}

map.on("click", (e) => {
  if (!drawingGeofence) return;
  drawnPoints.push([e.latlng.lng, e.latlng.lat]); // [lon, lat] GeoJSON format

  if (!drawingTempPoly) {
    drawingTempPoly = L.polyline(
      drawnPoints.map((p) => [p[1], p[0]]),
      { color: "var(--accent)", dashArray: "4, 4" }
    ).addTo(map);
  } else {
    drawingTempPoly.setLatLngs(drawnPoints.map((p) => [p[1], p[0]]));
  }
});

async function finishGeofence() {
  if (btnGeofence) {
    btnGeofence.innerText = "+ Geofence";
    btnGeofence.style.borderColor = "var(--border)";
  }
  if (drawingTempPoly) {
    map.removeLayer(drawingTempPoly);
    drawingTempPoly = null;
  }
  if (drawnPoints.length < 3) {
    drawnPoints = [];
    return;
  }

  // Close loop
  drawnPoints.push(drawnPoints[0]);
  const geojson = {
    type: "Polygon",
    coordinates: [drawnPoints],
  };

  try {
    const res = await fetch(`${window.__API_BASE__}/geofences`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: `Zone-${Date.now().toString().slice(-4)}`,
        kind: "polygon",
        geojson: geojson,
        h3_resolution: 8,
      }),
    });

    if (res.ok) {
      const fence = await res.json();
      renderGeofenceOverlay(fence);
    }
  } catch (err) {
    console.error("Failed to persist geofence:", err);
  }
  drawnPoints = [];
}

function renderGeofenceOverlay(fence) {
  const coords = fence.geojson.coordinates[0].map((pt) => [pt[1], pt[0]]);
  // Polygon with 8% fill and 1px solid stroke
  L.polygon(coords, {
    color: "#0070f3",
    weight: 1,
    fillColor: "#0070f3",
    fillOpacity: 0.08,
  }).addTo(geofenceLayer);
}

// Initial geofences loader
async function loadGeofences() {
  try {
    const res = await fetch(`${window.__API_BASE__}/geofences`);
    if (res.ok) {
      const fences = await res.json();
      fences.forEach(renderGeofenceOverlay);
    }
  } catch (err) {
    console.debug("Geofence load skipped:", err);
  }
}
loadGeofences();
