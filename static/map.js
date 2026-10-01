import { el } from "./config.js?v=3";
let map,
  markerLayer,
  trace,
  startMarker,
  lastPoints = [],
  markers = new Map();
export function initializeMap() {
  if (!window.L) {
    el("map").textContent =
      "Map unavailable. Exact coordinates remain in the observations table.";
    return;
  }
  map = L.map("map", { scrollWheelZoom: false }).setView([12.976, 77.595], 13);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution:
      '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  })
    .on("tileerror", () => {
      el("tile-warning").hidden = false;
    })
    .addTo(map);
  markerLayer = L.layerGroup().addTo(map);
  const zone = L.circle([12.9716, 77.5946], {
    radius: 1200,
    color: "#2783de",
    weight: 1.5,
    dashArray: "5 6",
    fillOpacity: 0.025,
  }).addTo(map);
  zone.bindTooltip("Central Bengaluru demo geofence");
  new ResizeObserver(() => map.invalidateSize()).observe(el("map"));
}
export function renderMap(positions, selectedId, points) {
  if (!map) return;
  const wanted = new Set(positions.map((p) => p.vehicle_id));
  for (const [id, marker] of markers)
    if (!wanted.has(id)) {
      markerLayer.removeLayer(marker);
      markers.delete(id);
    }
  for (const p of positions) {
    const icon = L.divIcon({
      className: `vehicle-pin ${p.vehicle_id === selectedId ? "selected" : ""}`,
      html: String(p.vehicle_id),
      iconSize: [30, 30],
      iconAnchor: [15, 15],
    });
    let marker = markers.get(p.vehicle_id);
    if (!marker) {
      marker = L.marker([p.lat, p.lon], { icon, keyboard: true }).addTo(
        markerLayer,
      );
      markers.set(p.vehicle_id, marker);
    }
    marker.setLatLng([p.lat, p.lon]);
    marker.setIcon(icon);
    const label = document.createElement("span");
    label.textContent = `Vehicle ${p.vehicle_id} · ${p.speed_kmh.toFixed(1)} km/h · synthetic sample`;
    marker.unbindTooltip().bindTooltip(label);
  }
  lastPoints = points.length ? points : positions;
  if (points.length) {
    if (!trace)
      trace = L.polyline([], {
        color: "#2783de",
        weight: 3,
        opacity: 0.9,
      }).addTo(map);
    trace.setLatLngs(points.map((p) => [p.lat, p.lon]));
    if (!startMarker)
      startMarker = L.circleMarker([points[0].lat, points[0].lon], {
        radius: 5,
        color: "#287b50",
        fillOpacity: 1,
      }).addTo(map);
    startMarker.setLatLng([points[0].lat, points[0].lon]);
    startMarker.bindTooltip("First stored sample");
  } else {
    if (trace) {
      map.removeLayer(trace);
      trace = null;
    }
    if (startMarker) {
      map.removeLayer(startMarker);
      startMarker = null;
    }
  }
}
export function fitMap() {
  if (!map || !lastPoints.length) return;
  map.fitBounds(L.latLngBounds(lastPoints.map((p) => [p.lat, p.lon])), {
    padding: [36, 36],
    maxZoom: lastPoints.length > 1 ? 16 : 14,
    animate: false,
  });
}
