import { distanceM } from "./config.js?v=3";
export class PreviewFleet {
  constructor(routes) {
    this.routes = routes;
    this.reset();
  }
  reset() {
    this.vehicles = [];
    this.trips = [];
    this.points = new Map();
    this.alerts = new Map();
    this.nextVehicle = 1;
    this.nextTrip = 1;
  }
  async listVehicles() {
    return this.vehicles.map((v) => ({ ...v }));
  }
  async listTrips() {
    return this.trips.map(({ tick, ...t }) => ({ ...t })).reverse();
  }
  async snapshot() {
    return [...this.points.values()].map((p) => p.at(-1)).filter(Boolean);
  }
  async register(body) {
    const name = body.name.trim(),
      registration = body.registration.trim().toUpperCase();
    if (
      !/^[\p{L}\p{N}_ -]{1,60}$/u.test(name) ||
      !/^[A-Z0-9 -]{1,30}$/.test(registration)
    )
      throw new Error(
        "Use letters, numbers, spaces or hyphens; neither field can be blank.",
      );
    if (
      this.vehicles.some(
        (v) => v.name === name || v.registration === registration,
      )
    )
      throw new Error("Vehicle name or registration already exists.");
    const vehicle = {
      id: this.nextVehicle++,
      name,
      registration,
      kind: body.kind,
      is_sample: false,
    };
    this.vehicles.push(vehicle);
    return { ...vehicle };
  }
  async start(vehicleId, body) {
    if (
      this.trips.some(
        (t) => t.vehicle_id === vehicleId && t.status === "active",
      )
    )
      throw new Error("This vehicle already has an active trip.");
    if (this.trips.filter((t) => t.status === "active").length >= 3)
      throw new Error(
        "Finish a trip first; at most three simulated trips can run together.",
      );
    const now = Date.now(),
      trip = {
        id: this.nextTrip++,
        vehicle_id: vehicleId,
        ...body,
        status: "active",
        source: "synthetic",
        started_at: new Date(now).toISOString(),
        expires_at: new Date(now + body.duration_seconds * 1000).toISOString(),
        ended_at: null,
        end_reason: null,
        tick: 0,
      };
    this.trips.push(trip);
    this.points.set(trip.id, []);
    this.alerts.set(trip.id, []);
    this.emit(trip, now);
    return { ...trip };
  }
  emit(trip, now) {
    const route = this.routes[{ central: 0, east: 1, west: 2 }[trip.route_key]],
      step = trip.tick / 30,
      index = Math.floor(step) % (route.length - 1),
      frac = step % 1;
    const lat =
        route[index][0] + (route[index + 1][0] - route[index][0]) * frac,
      lon = route[index][1] + (route[index + 1][1] - route[index][1]) * frac;
    const points = this.points.get(trip.id),
      prior = points.at(-1);
    let speed = prior
      ? Math.min(75, (distanceM(prior, { lat, lon }) * 3.6) / 2)
      : 0;
    if (trip.include_speeding && [8, 9, 10].includes(trip.tick % 40))
      speed = 92;
    const point = {
      id: points.length + 1,
      trip_id: trip.id,
      vehicle_id: trip.vehicle_id,
      lat,
      lon,
      speed_kmh: Math.round(speed * 10) / 10,
      heading:
        ((Math.atan2(
          route[index + 1][1] - route[index][1],
          route[index + 1][0] - route[index][0],
        ) *
          180) /
          Math.PI +
          360) %
        360,
      recorded_at: new Date(now).toISOString(),
    };
    points.push(point);
    const alerts = this.alerts.get(trip.id);
    if (point.speed_kmh > 80 && (!prior || prior.speed_kmh <= 80))
      alerts.unshift({
        trip_id: trip.id,
        vehicle_id: trip.vehicle_id,
        kind: "speeding",
        recorded_at: point.recorded_at,
        details: { speed_kmh: point.speed_kmh, limit_kmh: 80 },
      });
    if (prior) {
      const center = { lat: 12.9716, lon: 77.5946 };
      const before = distanceM(prior, center) <= 1200,
        after = distanceM(point, center) <= 1200;
      if (before !== after)
        alerts.unshift({
          trip_id: trip.id,
          vehicle_id: trip.vehicle_id,
          kind: after ? "geofence_enter" : "geofence_exit",
          recorded_at: point.recorded_at,
          details: { geofence_name: "Central Bengaluru demo zone" },
        });
    }
    trip.tick++;
  }
  advance(now = Date.now()) {
    for (const t of this.trips.filter((t) => t.status === "active")) {
      if (now >= Date.parse(t.expires_at)) {
        t.status = "completed";
        t.end_reason = "time_limit";
        t.ended_at = t.expires_at;
      } else if (
        now - Date.parse(this.points.get(t.id).at(-1).recorded_at) >=
        2000
      )
        this.emit(t, now);
    }
  }
  async finish(id) {
    const t = this.trips.find((t) => t.id === id);
    if (!t) throw new Error("Trip not found.");
    if (t.status === "active") {
      t.status = "completed";
      t.end_reason = "manual";
      t.ended_at = new Date().toISOString();
    }
    return { ...t };
  }
  async detail(id) {
    const trip = this.trips.find((t) => t.id === id);
    if (!trip) throw new Error("Trip not found.");
    const points = this.points.get(id),
      alerts = this.alerts.get(id),
      { tick, ...copy } = trip;
    return {
      trip: { ...copy },
      points: points.map((p) => ({ ...p })),
      alerts: alerts.map((a) => ({ ...a })),
      source_used: "browser_memory",
      sample_data: true,
      summary: {
        duration_seconds: Math.max(
          0,
          ((trip.ended_at ? Date.parse(trip.ended_at) : Date.now()) -
            Date.parse(trip.started_at)) /
            1000,
        ),
        point_count: points.length,
        displayed_point_count: points.length,
        distance_km: points.length
          ? points
              .slice(1)
              .reduce((sum, p, i) => sum + distanceM(points[i], p), 0) / 1000
          : null,
        max_speed_kmh: points.length
          ? Math.max(...points.map((p) => p.speed_kmh))
          : null,
        alert_count: alerts.length,
      },
      has_more_points: false,
      has_more_alerts: false,
    };
  }
  interrupt() {
    for (const t of this.trips.filter((t) => t.status === "active")) {
      t.status = "interrupted";
      t.end_reason = "preview_switched";
      t.ended_at = new Date().toISOString();
    }
  }
  disconnect() {}
}
