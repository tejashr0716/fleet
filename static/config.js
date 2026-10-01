export const state = {
  mode: "preview",
  vehicles: [],
  trips: [],
  positions: new Map(),
  selected: 0,
  selectedTrip: 0,
  detail: null,
  query: "",
  showSamples: false,
  ttl: 30,
  token: null,
  apiBase: "",
  busy: false,
  connected: false,
};
export const el = (id) => document.getElementById(id);
export const clock = (value) =>
  value
    ? new Date(value).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—";
export const stamp = (value) =>
  value
    ? new Date(value).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
export const duration = (seconds) =>
  `${Math.floor(Math.max(0, seconds) / 60)}:${String(Math.floor(Math.max(0, seconds) % 60)).padStart(2, "0")}`;
export const visibleVehicles = () =>
  state.vehicles.filter((v) => state.showSamples || !v.is_sample);
export const activeTrip = () =>
  state.trips.find(
    (t) => t.vehicle_id === state.selected && t.status === "active",
  );
export const routeNames = {
  central: "Central Bengaluru loop",
  east: "East Bengaluru loop",
  west: "West Bengaluru loop",
};
export function toast(message) {
  clearTimeout(toast.timer);
  el("toast").textContent = message;
  el("toast").hidden = false;
  toast.timer = setTimeout(() => (el("toast").hidden = true), 6500);
}
export function distanceM(a, b) {
  const rad = (v) => (v * Math.PI) / 180,
    dlat = rad(b.lat - a.lat),
    dlon = rad(b.lon - a.lon);
  const h =
    Math.sin(dlat / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dlon / 2) ** 2;
  return 6371000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(Math.max(0, 1 - h)));
}
