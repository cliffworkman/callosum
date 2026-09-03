const { listen } = window.__TAURI__.event;
const { invoke } = window.__TAURI__.core;

const statusEl = document.getElementById("status");
const retryEl = document.getElementById("retry");
const progressWrapEl = document.getElementById("progress-wrap");
const progressEl = document.getElementById("progress");
const progressDetailEl = document.getElementById("progress-detail");

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "";
  const units = ["B", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

listen("backend-status", (event) => {
  const { state, detail, downloaded_bytes: downloaded, total_bytes: total } = event.payload;
  if (state === "starting" || state.startsWith("runtime_")) {
    statusEl.textContent = detail || "Starting…";
    retryEl.hidden = true;
    const measurable = Number.isFinite(downloaded) && Number.isFinite(total) && total > 0;
    progressWrapEl.hidden = !measurable;
    if (measurable) {
      const percent = Math.min(100, Math.max(0, (downloaded / total) * 100));
      progressEl.value = percent;
      progressDetailEl.textContent = `${Math.round(percent)}% · ${formatBytes(downloaded)} of ${formatBytes(total)}`;
    }
  } else if (state === "failed") {
    statusEl.textContent = detail || "Callosum couldn't start.";
    retryEl.hidden = false;
    progressWrapEl.hidden = true;
  }
  // "ready" is not handled here — the shell closes this window and shows the main window itself.
});

retryEl.addEventListener("click", () => {
  retryEl.hidden = true;
  progressWrapEl.hidden = true;
  statusEl.textContent = "Retrying…";
  invoke("retry_backend").catch((err) => {
    statusEl.textContent = String(err);
    retryEl.hidden = false;
  });
});
