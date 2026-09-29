// Real-Time WebSocket Client, Bounding Box Synchronization & Connection Lifecycle
let socket = null;
let reconnectAttempts = 0;
let positionCount = 0;
let lastRateTimestamp = Date.now();
const latencySamples = [];

function connectWebSocket() {
  const connDot = document.getElementById("conn-dot");
  const connText = document.getElementById("conn-text");

  connDot.className = "status-dot reconnecting";
  connText.innerText = "Connecting...";

  socket = new WebSocket(`${window.__WS_BASE__}/live`);

  socket.onopen = () => {
    connDot.className = "status-dot live";
    connText.innerText = "Live";
    reconnectAttempts = 0;
    sendBboxSubscription();
  };

  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "position") {
        positionCount++;
        updateVehicleMarker(msg.data);
        if (msg.data.emitted_at) {
          updateE2ELatency(msg.data.emitted_at);
        }
      } else if (msg.type === "alert") {
        if (window.addAlertRow) {
          window.addAlertRow(msg.data);
        }
      } else if (msg.type === "ping") {
        socket.send(JSON.stringify({ action: "ping" }));
      }
    } catch (err) {
      console.error("Malformed WebSocket payload:", err);
    }
  };

  socket.onclose = (e) => {
    connDot.className = "status-dot reconnecting";
    connText.innerText = "Reconnecting...";

    // Exponential backoff with random jitter, capped at 30 seconds
    const baseDelay = Math.min(30000, 1000 * Math.pow(1.5, reconnectAttempts));
    const jitter = Math.random() * 1000;
    const delay = Math.min(30000, baseDelay + jitter);
    reconnectAttempts++;

    setTimeout(connectWebSocket, delay);
  };

  socket.onerror = () => {
    socket.close();
  };
}

function sendBboxSubscription() {
  if (socket && socket.readyState === WebSocket.OPEN) {
    const bounds = map.getBounds();
    const bbox = [
      bounds.getWest(),
      bounds.getSouth(),
      bounds.getEast(),
      bounds.getNorth(),
    ];
    socket.send(
      JSON.stringify({
        action: "subscribe",
        bbox: bbox,
        vehicle_ids: [],
      })
    );
  }
}

function updateE2ELatency(emittedAt) {
  const emittedTime = new Date(emittedAt).getTime();
  const latency = Date.now() - emittedTime;

  if (latency >= 0) {
    latencySamples.push(latency);
    if (latencySamples.length > 50) latencySamples.shift();

    // Compute p95 latency
    const sorted = [...latencySamples].sort((a, b) => a - b);
    const p95Idx = Math.floor(sorted.length * 0.95);
    const p95 = sorted[p95Idx];
    document.getElementById("stat-latency").innerText = `${p95} ms`;
  }
}

// Positions per second and active vehicles rate monitor
setInterval(() => {
  const now = Date.now();
  const elapsedSec = (now - lastRateTimestamp) / 1000.0;
  const rate = Math.round(positionCount / elapsedSec);

  const rateElem = document.getElementById("stat-rate");
  const vehiclesElem = document.getElementById("stat-vehicles");
  if (rateElem) rateElem.innerText = rate;
  if (vehiclesElem) vehiclesElem.innerText = markers.size;

  positionCount = 0;
  lastRateTimestamp = now;
}, 1000);

// Debounced Map moveend bbox re-subscription (300ms)
let moveDebounceTimer = null;
map.on("moveend", () => {
  clearTimeout(moveDebounceTimer);
  moveDebounceTimer = setTimeout(sendBboxSubscription, 300);
});
