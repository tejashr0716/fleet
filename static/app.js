// Application Bootstrap, Replay Controller, and Offline Demo Fallback
let isReplayMode = false;
let replayTimer = null;
let replayPoints = [];
let replayIndex = 0;
let replaySpeedMultiplier = 1;

async function bootstrapApp() {
  const offlineBanner = document.getElementById("offline-banner");
  try {
    const res = await fetch(`${window.__API_BASE__}/health`, {
      signal: AbortSignal.timeout(3000),
    });

    if (!res.ok) throw new Error("API unhealthy");

    // Live API reachable: Connect WebSocket live telemetry
    if (offlineBanner) offlineBanner.style.display = "none";
    connectWebSocket();
  } catch (err) {
    console.warn("Backend sleeping or unreachable. Initiating offline demo fallback...", err);
    if (offlineBanner) offlineBanner.style.display = "block";
    startOfflineDemoFallback();
  }
}

// Replay Mode Toggle
const btnToggleReplay = document.getElementById("btn-toggle-replay");
const replayBar = document.getElementById("replay-bar");
const replayPlayBtn = document.getElementById("replay-play");
const replaySlider = document.getElementById("replay-slider");
const replaySpeedSelect = document.getElementById("replay-speed");
const replayTimeLabel = document.getElementById("replay-time");

if (btnToggleReplay) {
  btnToggleReplay.addEventListener("click", async () => {
    isReplayMode = !isReplayMode;
    if (isReplayMode) {
      btnToggleReplay.innerText = "Exit Replay";
      btnToggleReplay.style.borderColor = "var(--accent)";
      if (replayBar) replayBar.style.display = "flex";
      await loadReplayData();
    } else {
      btnToggleReplay.innerText = "Replay Mode";
      btnToggleReplay.style.borderColor = "var(--border)";
      if (replayBar) replayBar.style.display = "none";
      stopReplay();
    }
  });
}

if (replaySpeedSelect) {
  replaySpeedSelect.addEventListener("change", (e) => {
    replaySpeedMultiplier = parseInt(e.target.value, 10) || 1;
    if (replayTimer) {
      startReplayLoop();
    }
  });
}

if (replayPlayBtn) {
  replayPlayBtn.addEventListener("click", () => {
    if (replayTimer) {
      stopReplay();
      replayPlayBtn.innerText = "Play";
    } else {
      startReplayLoop();
      replayPlayBtn.innerText = "Pause";
    }
  });
}

if (replaySlider) {
  replaySlider.addEventListener("input", (e) => {
    replayIndex = Math.floor((parseInt(e.target.value, 10) / 100) * (replayPoints.length - 1));
    if (replayPoints[replayIndex]) {
      updateVehicleMarker(replayPoints[replayIndex]);
      updateReplayLabel(replayPoints[replayIndex].ts);
    }
  });
}

async function loadReplayData() {
  try {
    const res = await fetch("./demo/replay.json");
    replayPoints = await res.json();
    replayIndex = 0;
  } catch (err) {
    console.error("Failed to load replay data:", err);
  }
}

function startReplayLoop() {
  if (replayTimer) clearInterval(replayTimer);
  const interval = Math.max(50, 1000 / replaySpeedMultiplier);

  replayTimer = setInterval(() => {
    if (!replayPoints || replayPoints.length === 0) return;
    const pt = replayPoints[replayIndex];
    updateVehicleMarker(pt);
    updateReplayLabel(pt.ts);

    if (replaySlider) {
      replaySlider.value = Math.floor((replayIndex / (replayPoints.length - 1)) * 100);
    }

    replayIndex = (replayIndex + 1) % replayPoints.length;
  }, interval);
}

function stopReplay() {
  if (replayTimer) {
    clearInterval(replayTimer);
    replayTimer = null;
  }
}

function updateReplayLabel(isoString) {
  if (replayTimeLabel && isoString) {
    replayTimeLabel.innerText = new Date(isoString).toLocaleTimeString();
  }
}

// Offline fallback mechanism: runs seamlessly from ./demo/replay.json
async function startOfflineDemoFallback() {
  const connDot = document.getElementById("conn-dot");
  const connText = document.getElementById("conn-text");
  if (connDot) connDot.className = "status-dot idle";
  if (connText) connText.innerText = "Demo Replay";

  await loadReplayData();
  startReplayLoop();
}

window.addEventListener("DOMContentLoaded", bootstrapApp);
