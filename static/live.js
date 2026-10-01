export class LiveFleet {
  constructor(base, token, onEvent) {
    this.base = base;
    this.token = token;
    this.onEvent = onEvent;
    this.closed = false;
    this.socket = null;
    this.retry = null;
  }
  static async signIn(base, username, password, onEvent) {
    const parsed = new URL(base),
      local = ["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname);
    if (parsed.protocol !== "https:" && !(parsed.protocol === "http:" && local))
      throw new Error(
        "Use HTTPS for a remote API; HTTP is allowed only for localhost.",
      );
    if (
      parsed.username ||
      parsed.password ||
      parsed.search ||
      parsed.hash ||
      !["", "/"].includes(parsed.pathname)
    )
      throw new Error(
        "Enter only the backend origin, without credentials or an API path.",
      );
    const response = await fetch(parsed.origin + "/api/v1/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
      signal: AbortSignal.timeout(90000),
    });
    if (!response.ok) {
      let message = `Sign-in returned ${response.status}`;
      try {
        message = (await response.json()).error?.message || message;
      } catch {}
      throw new Error(message);
    }
    return new LiveFleet(
      parsed.origin,
      (await response.json()).access_token,
      onEvent,
    );
  }
  async api(path, options = {}) {
    const response = await fetch(this.base + "/api/v1" + path, {
      ...options,
      headers: {
        Authorization: "Bearer " + this.token,
        "Content-Type": "application/json",
      },
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) {
      let message = `API returned ${response.status}`;
      try {
        message = (await response.json()).error?.message || message;
      } catch {}
      if (response.status === 401) {
        this.disconnect();
        message =
          "Session expired. Stored trips remain in PostgreSQL; sign in again.";
        this.onEvent({ type: "connection", connected: false, note: message });
      }
      throw new Error(message);
    }
    return response.json();
  }
  listVehicles() {
    return this.api("/vehicles");
  }
  async listTrips() {
    const data = await this.api("/trips?limit=200");
    this.hasMoreTrips = data.has_more;
    return data.trips;
  }
  async snapshot() {
    const data = await this.api("/fleet/live");
    this.ttl = data.live_ttl_seconds;
    return data.positions;
  }
  register(body) {
    return this.api("/vehicles", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }
  start(vehicleId, body) {
    return this.api(`/vehicles/${vehicleId}/trips`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }
  finish(id) {
    return this.api(`/trips/${id}/finish`, { method: "POST" });
  }
  detail(id) {
    return this.api(`/trips/${id}`);
  }
  listen() {
    if (this.closed || !this.token) return;
    const socket = new WebSocket(this.base.replace(/^http/, "ws") + "/ws/live");
    this.socket = socket;
    socket.onopen = () =>
      socket.send(JSON.stringify({ type: "auth", token: this.token }));
    socket.onmessage = (event) => {
      if (this.closed) return;
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (["ready", "heartbeat", "status"].includes(message.type))
        this.onEvent({
          type: "connection",
          connected: message.data.realtime === "connected",
          note:
            message.data.realtime === "connected"
              ? "WebSocket connected · synthetic GPS"
              : "Redis unavailable · PostgreSQL reconciliation",
        });
      else this.onEvent(message);
    };
    socket.onerror = () => {
      if (!this.closed)
        this.onEvent({
          type: "connection",
          connected: false,
          note: "WebSocket unavailable · REST fallback",
        });
    };
    socket.onclose = (event) => {
      if (this.closed) return;
      const expired = event.code === 1008;
      this.onEvent({
        type: "connection",
        connected: false,
        note: expired
          ? "Sign in again · stored trips retained"
          : "Connection interrupted · retrying",
      });
      if (!expired) this.retry = setTimeout(() => this.listen(), 2500);
    };
  }
  disconnect() {
    this.closed = true;
    clearTimeout(this.retry);
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
    }
    this.token = null;
  }
}
