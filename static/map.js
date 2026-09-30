import {state, el, stale} from "./config.js";
let map, layer, fenceLayer, trace, markers = new Map();
export function initializeMap() {
  if (typeof window.L === "undefined") { el("map").textContent = "Map library unavailable. Use the vehicle list and coordinates."; return; }
  map = L.map("map", {scrollWheelZoom:false,zoomControl:true}).setView([12.975,77.596],13);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom:19, attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).on("tileerror", () => {el("tile-warning").hidden=false;}).addTo(map);
  layer = L.layerGroup().addTo(map); fenceLayer = L.layerGroup().addTo(map);
  el("fit-map").addEventListener("click",fitFleet);
  new ResizeObserver(() => map.invalidateSize()).observe(el("map"));
}
export function renderMap() {
  if (!map) return;
  const existing = new Set(state.vehicles.map(v => v.id));
  for (const [id,marker] of markers) if (!existing.has(id)) { layer.removeLayer(marker); markers.delete(id); }
  for (const vehicle of state.vehicles) {
    const point = state.positions.get(vehicle.id); if (!point) continue;
    const icon = L.divIcon({className:`vehicle-pin ${state.selected===vehicle.id?"selected":""} ${stale(point)?"stale":""}`,html:String(vehicle.id),iconSize:[28,28],iconAnchor:[14,14]});
    let marker=markers.get(vehicle.id);
    if (!marker) { marker=L.marker([point.lat,point.lon],{icon,keyboard:true}).addTo(layer); marker.on("click",()=>state.onSelect(vehicle.id)); markers.set(vehicle.id,marker); }
    marker.setLatLng([point.lat,point.lon]); marker.setIcon(icon);
    const label=document.createElement("span"); label.textContent=`${vehicle.name} · ${point.speed_kmh.toFixed(1)} km/h${stale(point)?" · stale signal":""}`;
    marker.unbindTooltip().bindTooltip(label); marker.options.title=vehicle.name;
  }
}
export function fitFleet() {
  if (!map || !state.positions.size) return;
  map.fitBounds(L.latLngBounds([...state.positions.values()].map(p=>[p.lat,p.lon])),{padding:[45,45],maxZoom:15,animate:!matchMedia("(prefers-reduced-motion: reduce)").matches});
}
export function showFences(fences) {
  if (!map) return; fenceLayer.clearLayers();
  for (const fence of fences) {
    const label=document.createElement("span");label.textContent=fence.name;
    L.circle([fence.lat,fence.lon],{radius:fence.radius_m,color:"#2165ba",weight:1.5,dashArray:"5 6",fillOpacity:.035}).bindTooltip(label).addTo(fenceLayer);
  }
}
export function showTrace(points) {
  if (!map) return; if(trace) map.removeLayer(trace);
  trace = L.polyline(points.map(p=>[p.lat,p.lon]),{color:"#2165ba",weight:3,opacity:.85}).addTo(map);
  if (points.length>1) map.fitBounds(trace.getBounds(),{padding:[40,40],maxZoom:16,animate:false});
}
export function clearTrace() { if(map&&trace){map.removeLayer(trace);trace=null;} }
