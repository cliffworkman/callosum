// Supplementary synthesis Overview: primary verified claims never wait for this display layer.

// A pending/running state can otherwise sit unresolvable forever (the app quit mid-generation, or the
// gap between the primary commit and the Overview call actually starting) with no way for the user to
// ever trigger a retry — the backend already reclaims a stale `running` row after 5 minutes and already
// accepts `pending` as retryable at any age (overview_lifecycle.py's acquire_overview), so a click here
// that lands too early simply 409s harmlessly (see the retry() handling below) rather than double-firing
// real in-flight work. This threshold is deliberately well short of that 5-minute backend window — just
// long enough that ordinary, healthy generation (seconds, not minutes) never shows it.
const OVERVIEW_STUCK_AFTER_SECONDS = 60;

// overview_updated_at is a naive-UTC ISO datetime string from the backend's _naive_utc() (no trailing
// Z/offset) — Date.parse() would otherwise misread it as local time, the same fix 30e_feed.jsx already
// applies to last_polled_at.
function _overviewAgeSeconds(updatedAt) {
  if (!updatedAt) return null;
  const iso = /[Z+]/.test(updatedAt) ? updatedAt : updatedAt + "Z";
  const parsed = Date.parse(iso);
  return Number.isFinite(parsed) ? Math.max(0, (Date.now() - parsed) / 1000) : null;
}

function OverviewBlock({ overview, status, updatedAt, onRetry, retrying }) {
  if ((!overview || overview.length === 0) && status === "not_requested") return null;
  if ((!overview || overview.length === 0) && (status === "pending" || status === "running")) {
    const age = _overviewAgeSeconds(updatedAt);
    const stuck = age != null && age >= OVERVIEW_STUCK_AFTER_SECONDS;
    return (
      <section className="synth-overview" aria-live="polite">
        <p className="eyebrow">Overview</p>
        <div className="history-meta">
          {stuck
            ? "Still generating the overview — this is taking longer than usual. Verified claims are ready below."
            : "Generating overview… Verified claims are ready below."}
        </div>
        {stuck && onRetry && <button className="btn btn-link" disabled={retrying} onClick={onRetry}>
          {retrying ? "Retrying overview…" : "Retry overview"}
        </button>}
      </section>
    );
  }
  if ((!overview || overview.length === 0) && status === "failed") {
    return (
      <section className="synth-overview" aria-live="polite">
        <p className="eyebrow">Overview unavailable</p>
        <div className="history-meta">The verified synthesis is complete; only its supplementary overview failed.</div>
        {onRetry && <button className="btn btn-link" disabled={retrying} onClick={onRetry}>
          {retrying ? "Retrying overview…" : "Retry overview"}
        </button>}
      </section>
    );
  }
  if (!overview || overview.length === 0) return null;
  return (
    <section className="synth-overview">
      <p className="eyebrow">Overview — synthesized from the verified claims below</p>
      {overview.map((item, i) => (
        <button key={i} className="overview-line" title="Show the verified claim(s) this restates"
          onClick={() => flashClaims(item.claim_ordinals)}>
          {item.text}
          <span className="overview-trace">
            {(item.claim_ordinals || []).map(o => "[" + (o + 1) + "]").join(" ")}
          </span>
        </button>
      ))}
    </section>
  );
}

function useSynthesisOverview(state, setState) {
  const [retrying, setRetrying] = useState(false);
  const summaryId = state.result && state.result.summary_id;
  const needsRefresh = !!(state.result && ["pending", "running"].includes(state.result.overview_status));

  // Bounded authoritative rereads: fast while the common overview is finishing, then backed off.
  // Reload remains sufficient after the ~65-second observer budget or a lost process-local signal.
  useEffect(() => {
    if (!summaryId || !needsRefresh) return;
    let active = true;
    let timer = null;
    let controller = null;
    let attempt = 0;
    const refresh = async () => {
      controller = new AbortController();
      const response = await api(`/summaries/${summaryId}`, { signal: controller.signal });
      controller = null;
      if (!active) return;
      if (response.ok) {
        const next = response.data;
        setState(current => current.result && current.result.summary_id === summaryId
          ? { ...current, result: next }
          : current);
        if (!["pending", "running"].includes(next.overview_status)) return;
      }
      attempt += 1;
      if (attempt >= 40) return;
      timer = window.setTimeout(refresh, attempt < 10 ? 500 : 2000);
    };
    timer = window.setTimeout(refresh, 250);
    return () => {
      active = false;
      if (timer != null) window.clearTimeout(timer);
      if (controller) controller.abort();
    };
  }, [summaryId, needsRefresh]);

  const retry = useCallback(() => {
    if (!summaryId || retrying) return;
    setRetrying(true);
    apiPost(`/summaries/${summaryId}/overview/retry`, {}).then(async response => {
      setRetrying(false);
      if (!response.ok && response.status !== 409) return;
      const refreshed = await api(`/summaries/${summaryId}`);
      if (refreshed.ok) setState(current => ({ ...current, result: refreshed.data }));
    });
  }, [summaryId, retrying]);

  return { retry, retrying };
}
