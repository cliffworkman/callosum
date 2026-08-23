// Supplementary synthesis Overview: primary verified claims never wait for this display layer.
function OverviewBlock({ overview, status, onRetry, retrying }) {
  if ((!overview || overview.length === 0) && status === "not_requested") return null;
  if ((!overview || overview.length === 0) && (status === "pending" || status === "running")) {
    return (
      <section className="synth-overview" aria-live="polite">
        <p className="eyebrow">Overview</p>
        <div className="history-meta">Generating overview… Verified claims are ready below.</div>
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
