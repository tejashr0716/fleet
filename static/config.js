export const state = { mode: "simulation", paused: false, vehicles: [], positions: new Map(), histories: new Map(), alerts: [], selected: 1, filter: "all", query: "", ttl: 30, speedLimit: 80, token: null, apiBase: "", onSelect: null, sourceNote: "Browser fixtures" };
export const el = id => document.getElementById(id);
export const clock = value => new Date(value).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"});
export const stale = p => !p || Date.now()-Date.parse(p.recorded_at) > state.ttl*1000;
export const listeners = new Set();
export function changed() { for (const listener of listeners) listener(); }
export function acceptPosition(point) {
  if (!Number.isFinite(point.lat) || !Number.isFinite(point.lon) || !Number.isFinite(point.speed_kmh) || !Number.isFinite(Date.parse(point.recorded_at))) return;
  const previous = state.positions.get(point.vehicle_id);
  if (previous && Date.parse(point.recorded_at) <= Date.parse(previous.recorded_at)) return;
  state.positions.set(point.vehicle_id, point);
  const observations = state.histories.get(point.vehicle_id) || [];
  observations.push(point); state.histories.set(point.vehicle_id, observations.slice(-120));
}
export function addAlert(alert) {
  const key = `${alert.vehicle_id}:${alert.kind}:${alert.recorded_at}`;
  if (state.alerts.some(a => a.key === key)) return;
  state.alerts.unshift({...alert,key}); state.alerts = state.alerts.slice(0,30);
}
let toastTimer;
export function toast(message) {
  clearTimeout(toastTimer); el("toast").textContent = message; el("toast").hidden = false;
  toastTimer = setTimeout(() => { el("toast").hidden = true; }, 6500);
}
