// Capture commits wake a held GET immediately; timeout is a connection lifetime, not a polling delay.
// Uses api() so the existing auth-fetch shim applies. No credential is placed in a URL.
function observeCaptureUpdates(refresh) {
  let active = true, revision = "", controller = null, retry = null;
  const retrySoon = () => { retry = window.setTimeout(() => { retry = null; request(); }, JOB_STATUS_FALLBACK_RETRY_MS); };
  const request = async () => {
    controller = new AbortController();
    const response = await api(`/library/capture-updates?after=${revision}&wait_seconds=20`, { signal: controller.signal });
    controller = null;
    if (!active) return;
    if (!response.ok) {
      const retryable = response.status == null || response.status >= 500 || [408, 429].includes(response.status);
      if (retryable) retrySoon();
      return;
    }
    if (response.data.revision !== revision) {
      const refreshed = await refresh(true); // Fetch authoritative queue + invalidate Library through its existing callback.
      if (!active) return;
      if (refreshed === false) { retrySoon(); return; }
      revision = response.data.revision;
    }
    request(); // A capture during the fetch is detected atomically by the next held GET.
  };
  request();
  return () => {
    active = false;
    if (controller) controller.abort();
    if (retry != null) window.clearTimeout(retry);
  };
}

function useCaptureUpdates(refresh, healthLoaded) {
  useEffect(() => {
    if (!healthLoaded) return;
    if (isDemoMode()) { refresh(); return; }
    let stop = observeCaptureUpdates(refresh);
    // A suspended/disconnected window rechecks immediately when the user returns.
    const onFocus = () => { stop(); stop = observeCaptureUpdates(refresh); };
    window.addEventListener("focus", onFocus);
    return () => { window.removeEventListener("focus", onFocus); stop(); };
  }, [refresh, healthLoaded]);
}
