const { listen } = window.__TAURI__.event;
const { invoke } = window.__TAURI__.core;

const statusEl = document.getElementById("status");
const retryEl = document.getElementById("retry");

listen("backend-status", (event) => {
  const { state, detail } = event.payload;
  if (state === "starting") {
    statusEl.textContent = detail || "Starting…";
    retryEl.hidden = true;
  } else if (state === "failed") {
    statusEl.textContent = detail || "Callosum couldn't start.";
    retryEl.hidden = false;
  }
  // "ready" is not handled here — the shell closes this window and shows the main window itself.
});

retryEl.addEventListener("click", () => {
  retryEl.hidden = true;
  statusEl.textContent = "Retrying…";
  invoke("retry_backend").catch((err) => {
    statusEl.textContent = String(err);
    retryEl.hidden = false;
  });
});
