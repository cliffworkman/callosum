const { listen } = window.__TAURI__.event;
const { invoke } = window.__TAURI__.core;

const spinnerEl = document.getElementById("spinner");
const stageEl = document.getElementById("stage");
const detailEl = document.getElementById("detail");
const retryEl = document.getElementById("retry");
const progressWrapEl = document.getElementById("progress-wrap");
const progressEl = document.getElementById("progress");
const progressDetailEl = document.getElementById("progress-detail");
const elapsedEl = document.getElementById("elapsed");

// inc 594 (#39): the structured stage vocabulary. Keyed on the `state` string the shell records — NEVER parsed
// from `detail`. Only the real lifecycle stages the startup path can actually distinguish appear here; an
// unknown state falls back to the detail text (or a generic label) rather than inventing a phase.
const STAGE_LABELS = {
  idle: "Starting…",
  runtime_check: "Checking Callosum's local runtime…",
  runtime_manifest: "Checking Callosum's local runtime…",
  runtime_migration: "Reusing the runtime from your current install…",
  runtime_download: "Downloading Callosum's one-time runtime…",
  runtime_extract: "Verifying and preparing the runtime…",
  runtime_ready: "Runtime ready — starting Callosum…",
  starting: "Starting Callosum…",
  failed: "Callosum couldn't start.",
};

// A non-measurable phase (no byte total) that can legitimately take a while — show an honest elapsed timer so
// the splash never looks frozen. The download phase is measurable, so it shows the bar instead.
const SLOW_INDETERMINATE = new Set(["runtime_check", "runtime_manifest", "runtime_migration", "runtime_extract", "starting"]);

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "";
  // inc 594: include KB — the divisor steps by 1024, so a units list that skipped KB mislabelled every value
  // one unit too large (1 MB rendered as "1.0 GB"), a latent bug in the download byte readout.
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatElapsed(ms) {
  const s = Math.floor((Number(ms) || 0) / 1000);
  if (s < 60) return `${s}s elapsed`;
  return `${Math.floor(s / 60)}m ${s % 60}s elapsed`;
}

// The last snapshot + the wall-clock time it was rendered, so the elapsed timer can tick locally during a slow,
// event-quiet phase (e.g. the runtime hash) instead of freezing at the value from the last event.
let lastSnapshot = null;
let lastRenderedAt = 0;

// The single render function for a snapshot. Used for BOTH the seed (current_startup_state) and every live
// backend-status event, so a late-loading splash and one that caught every event render identically.
function render(snapshot) {
  if (!snapshot || typeof snapshot !== "object") return;
  lastSnapshot = snapshot;
  lastRenderedAt = Date.now();
  const state = typeof snapshot.state === "string" ? snapshot.state : "idle";
  const downloaded = snapshot.downloaded_bytes;
  const total = snapshot.total_bytes;
  const elapsedMs = snapshot.elapsed_ms;

  if (state === "failed") {
    spinnerEl.hidden = true;
    stageEl.textContent = STAGE_LABELS.failed;
    // `detail` is a sanitized shell-provided message (the full diagnostic is written to a log, never shown here).
    detailEl.textContent = snapshot.detail || "";
    progressWrapEl.hidden = true;
    elapsedEl.hidden = true;
    retryEl.hidden = false;
    return;
  }
  retryEl.hidden = true;
  spinnerEl.hidden = false;
  stageEl.textContent = STAGE_LABELS[state] || snapshot.detail || "Starting…";
  // The detail line repeats the shell's own copy only when it adds something beyond the stage label.
  detailEl.textContent = snapshot.detail && STAGE_LABELS[state] ? snapshot.detail : "";

  const measurable = Number.isFinite(downloaded) && Number.isFinite(total) && total > 0;
  progressWrapEl.hidden = !measurable;
  if (measurable) {
    const percent = Math.min(100, Math.max(0, (downloaded / total) * 100));
    progressEl.value = percent;
    progressDetailEl.textContent = `${Math.round(percent)}% · ${formatBytes(downloaded)} of ${formatBytes(total)}`;
    elapsedEl.hidden = true; // the bar itself communicates progress; no elapsed clutter
  } else if (SLOW_INDETERMINATE.has(state) && Number.isFinite(elapsedMs)) {
    // Non-measurable but potentially slow → an HONEST indeterminate indicator: elapsed only, no fake percentage.
    elapsedEl.hidden = false;
    elapsedEl.textContent = formatElapsed(elapsedMs);
  } else {
    elapsedEl.hidden = true;
  }
}

// #78 fix: SEED from the owned snapshot on load (an early backend-status event may have fired before this
// listener registered; Tauri never replays it). A live event below always wins over the seed.
invoke("current_startup_state")
  .then((snapshot) => { if (snapshot && snapshot.state && snapshot.state !== "idle") render(snapshot); })
  .catch(() => { /* pre-#594 shell or a transient error: fall back to listening only */ });

listen("backend-status", (event) => render(event.payload));

// Tick the elapsed timer locally once a second during a slow, non-measurable phase, so it advances even when no
// event arrives for a while (the runtime hash/verify can be quiet for tens of seconds). No fake percentage —
// only the honest wall-clock elapsed. Stops as soon as a measurable/terminal state renders.
setInterval(() => {
  if (!lastSnapshot || lastSnapshot.state === "failed") return;
  const total = lastSnapshot.total_bytes;
  const measurable = Number.isFinite(lastSnapshot.downloaded_bytes) && Number.isFinite(total) && total > 0;
  if (measurable || !SLOW_INDETERMINATE.has(lastSnapshot.state)) return;
  const base = Number.isFinite(lastSnapshot.elapsed_ms) ? lastSnapshot.elapsed_ms : 0;
  elapsedEl.hidden = false;
  elapsedEl.textContent = formatElapsed(base + (Date.now() - lastRenderedAt));
}, 1000);

retryEl.addEventListener("click", () => {
  retryEl.hidden = true;
  progressWrapEl.hidden = true;
  elapsedEl.hidden = true;
  spinnerEl.hidden = false;
  stageEl.textContent = "Retrying…";
  detailEl.textContent = "";
  invoke("retry_backend").catch((err) => {
    stageEl.textContent = "Callosum couldn't start.";
    detailEl.textContent = String(err);
    spinnerEl.hidden = true;
    retryEl.hidden = false;
  });
});
