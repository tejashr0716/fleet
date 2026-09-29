// Public origins — not secrets. Falls back to local dev automatically.
const local = ["localhost", "127.0.0.1"].includes(window.location.hostname);
window.__API_BASE__ = local
  ? "http://localhost:8000/api/v1"
  : "https://fleet-production.up.railway.app/api/v1";
window.__WS_BASE__ = local
  ? "ws://localhost:8000/ws"
  : "wss://fleet-production.up.railway.app/ws";
