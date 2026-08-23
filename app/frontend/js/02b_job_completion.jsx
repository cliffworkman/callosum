// Shared model-backed job completion observer.
//
// Status/result endpoints remain authoritative.  The optional wait_seconds
// query merely asks the in-process JobStore to hold the GET until state
// changes (or a bounded timeout); after every wake the full status response is
// fetched and rendered normally.  A failed held request falls back to the old
// immediate-GET + 1.2 s retry behavior, so notification failure cannot strand
// the UI.  One AbortController owns each request and cleanup aborts it on
// unmount/navigation.
const JOB_STATUS_WAIT_SECONDS = 20;
const JOB_STATUS_FALLBACK_RETRY_MS = 1200;

function jobStatusUrl(path, waitSeconds) {
  const join = path.includes("?") ? "&" : "?";
  return `${path}${join}wait_seconds=${waitSeconds}`;
}

function rememberActiveJob(key, jobId) {
  try {
    if (jobId) window.sessionStorage.setItem(key, jobId);
    else window.sessionStorage.removeItem(key);
  } catch (_) {
    // Restricted storage must never prevent the authoritative status request.
  }
}

function recalledActiveJob(key) {
  try { return window.sessionStorage.getItem(key); } catch (_) { return null; }
}

function observeJobUntilTerminal(path, handlers) {
  let active = true;
  let controller = null;
  let retryTimer = null;

  const stop = () => {
    if (!active) return;
    active = false;
    if (retryTimer != null) window.clearTimeout(retryTimer);
    retryTimer = null;
    if (controller) controller.abort();
    controller = null;
  };

  const requestStatus = async (waitSeconds) => {
    if (!active) return;
    controller = new AbortController();
    const response = await api(jobStatusUrl(path, waitSeconds), { signal: controller.signal });
    controller = null;
    if (!active) return;

    if (!response.ok) {
      const retryable = response.status == null || response.status >= 500
        || response.status === 408 || response.status === 429;
      if (!retryable) {
        active = false;
        if (handlers.onError) handlers.onError(response.error);
        return;
      }
      // A proxy/network may reject a held request even though ordinary status
      // GETs work.  Retry without waiting, at the previous robust cadence;
      // once it succeeds the next request returns to long polling.
      retryTimer = window.setTimeout(() => {
        retryTimer = null;
        requestStatus(0);
      }, JOB_STATUS_FALLBACK_RETRY_MS);
      return;
    }

    const data = response.data;
    if (data.status === "done") {
      active = false;
      if (handlers.onDone) handlers.onDone(data);
      return;
    }
    if (data.status === "error") {
      active = false;
      if (handlers.onError) handlers.onError(data.detail || "Job failed.", data);
      return;
    }
    if (handlers.onProgress) handlers.onProgress(data);
    // No timer: the next request waits efficiently and wakes at the next
    // progress/completion transition.  Terminal state is rechecked atomically
    // while the backend registers the waiter, so the handoff cannot miss it.
    requestStatus(JOB_STATUS_WAIT_SECONDS);
  };

  // Initial/reload discovery is immediate.  Only a known non-terminal state
  // starts a held request.
  requestStatus(0);
  return stop;
}
