// My Publications Layer 4 (inc 386): grounded co-citation gaps. The dashboard reads a local snapshot; only the
// explicit Refresh button performs bounded OpenAlex metadata work. Every candidate expands to the shared
// reference anchors and confirmed own publications that caused it to surface.

function MyPubsCitationGaps({ domains, onSelectPaper, onLibraryChanged }) {
  const [state, setState] = useState({ status: "loading", candidates: [], coverage: null, computedAt: null });
  const [refresh, setRefresh] = useState({ status: "idle" });
  const [rowAction, setRowAction] = useState({});
  const [selectedDomainKeys, setSelectedDomainKeys] = useState(() => new Set());
  const availableDomains = (domains || []).filter(domain => domain.key);
  const availableKeyToken = availableDomains.map(domain => domain.key).sort().join("|");
  const selectedKeys = Array.from(selectedDomainKeys).sort();
  const scopeQuery = selectedKeys.map(key => `domain_key=${encodeURIComponent(key)}`).join("&");
  const listPath = `/my-publications/citation-gaps${scopeQuery ? `?${scopeQuery}` : ""}`;
  const selectedLabels = availableDomains
    .filter(domain => selectedDomainKeys.has(domain.key))
    .map(domain => domain.label);
  const scopeLabel = selectedLabels.length ? selectedLabels.join(" + ") : "all confirmed publications";

  const load = React.useCallback(() => {
    setState({ status: "loading", candidates: [], coverage: null, computedAt: null });
    api(listPath).then(r => {
      if (r.ok) {
        setState({
          status: "ready",
          candidates: r.data.candidates || [],
          coverage: r.data.coverage || null,
          computedAt: r.data.computed_at || null,
        });
      } else setState({ status: "error", error: r.error, candidates: [], coverage: null, computedAt: null });
    });
  }, [listPath]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const available = new Set(availableDomains.map(domain => domain.key));
    setSelectedDomainKeys(previous => {
      const next = new Set(Array.from(previous).filter(key => available.has(key)));
      return next.size === previous.size ? previous : next;
    });
  }, [availableKeyToken]);

  const runRefresh = async () => {
    setRefresh({ status: "running" });
    const started = await apiPost("/my-publications/citation-gaps/refresh", { domain_keys: selectedKeys });
    if (!started.ok) { setRefresh({ status: "error", error: started.error }); return; }
    const poll = (jobId) => api(`/my-publications/citation-gaps/refresh/${jobId}`).then(r => {
      if (!r.ok) { setRefresh({ status: "error", error: r.error }); return; }
      if (r.data.status === "done") {
        setRefresh({ status: "idle" });
        load();
      } else if (r.data.status === "error") {
        setRefresh({ status: "error", error: r.data.detail || "Citation-gap refresh failed." });
      } else setTimeout(() => poll(jobId), 1800);
    });
    poll(started.data.job_id);
  };

  const toggleDomain = (key) => {
    setRefresh({ status: "idle" });
    setRowAction({});
    setSelectedDomainKeys(previous => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const clearDomains = () => {
    setRefresh({ status: "idle" });
    setRowAction({});
    setSelectedDomainKeys(new Set());
  };

  const add = async (candidate) => {
    setRowAction(prev => ({ ...prev, [candidate.openalex_work_id]: "adding" }));
    const r = await apiPost("/gaps/add", {
      doi: candidate.doi,
      openalex_work_id: candidate.openalex_work_id,
      title: candidate.title,
    });
    if (r.ok) {
      if (onLibraryChanged) onLibraryChanged();
      load();
    } else {
      setRowAction(prev => ({ ...prev, [candidate.openalex_work_id]: r.error || "Add failed." }));
    }
  };

  const dismiss = async (candidate) => {
    setRowAction(prev => ({ ...prev, [candidate.openalex_work_id]: "dismissing" }));
    const r = await apiPost("/gaps/dismiss", {
      openalex_work_id: candidate.openalex_work_id,
      doi: candidate.doi,
    });
    if (r.ok) load();
    else setRowAction(prev => ({ ...prev, [candidate.openalex_work_id]: r.error || "Dismiss failed." }));
  };

  const coverage = state.coverage;
  const candidates = state.candidates || [];
  const running = refresh.status === "running";
  const refreshLabel = selectedKeys.length
    ? (state.computedAt ? "↻ Refresh scoped gaps" : "Find scoped gaps")
    : (state.computedAt ? "↻ Refresh gaps" : "Find citation gaps");
  return (
    <section className="mypubs-prospection" aria-labelledby="mypubs-citation-gaps-title">
      <div className="mypubs-summary-head">
        <span id="mypubs-citation-gaps-title">
          Citation gaps <span className="mypubs-grounded-tag">Grounded prospection</span>
        </span>
        <button className="btn btn-ghost" disabled={isDemoMode() || running} onClick={runRefresh}
          title={isDemoMode() ? "Refreshing citation gaps queries OpenAlex and requires local Callosum." : undefined}>
          {running ? "Scanning…" : refreshLabel}
        </button>
      </div>
      <p className="mypubs-prospection-intro">
        Works that share reference anchors with several of your publications, while none of the scanned
        publications cites the candidate. Every suggestion shows the exact OpenAlex graph evidence.
      </p>
      {isDemoMode() && <div className="settings-note">Saved citation-gap graph with inspectable reference anchors. Refreshing, adding, or dismissing candidates requires local Callosum.</div>}
      {availableDomains.length > 0 &&
        <div className="mypubs-gap-scope">
          <span className="mypubs-gap-scope-label">Scan scope</span>
          <div className="mypubs-gap-scope-options" aria-label="Citation-gap research-domain scope">
            <button type="button" className={"mypubs-gap-scope-chip" + (selectedKeys.length === 0 ? " on" : "")}
              aria-pressed={selectedKeys.length === 0} disabled={running}
              onClick={clearDomains}>
              All publications
            </button>
            {availableDomains.map(domain => (
              <button type="button" key={domain.key}
                className={"mypubs-gap-scope-chip" + (selectedDomainKeys.has(domain.key) ? " on" : "")}
                aria-pressed={selectedDomainKeys.has(domain.key)} disabled={running}
                onClick={() => toggleDomain(domain.key)}>
                {domain.label} <span>{domain.paper_count}p</span>
              </button>
            ))}
          </div>
          <span className="mypubs-gap-scope-hint">
            {selectedKeys.length
              ? `Scanning the union of ${selectedKeys.length} selected domain${selectedKeys.length === 1 ? "" : "s"}.`
              : "Select one or more domains to narrow the scan; each scope keeps its own local snapshot."}
          </span>
        </div>}

      {running && <ProgressBar label={`Tracing shared references for ${scopeLabel} through OpenAlex…`} managedBy="backend-job" />}
      {refresh.status === "error" && <div className="axis-err">{refresh.error}</div>}
      {state.status === "error" && <div className="axis-err">{state.error}</div>}
      {state.status === "loading" && <div className="axis-hint">Loading the local citation-gap snapshot…</div>}

      {state.computedAt && coverage &&
        <div className="mypubs-gap-coverage">
          Last refreshed {new Date(state.computedAt).toLocaleString()} · scanned {coverage.checked} of{" "}
          {coverage.total} confirmed publications in {scopeLabel}
          {coverage.total > coverage.with_doi ? ` (${coverage.total - coverage.with_doi} had no DOI)` : ""}
          {" "}· {coverage.shared_anchor_count} shared reference anchor
          {coverage.shared_anchor_count === 1 ? "" : "s"}.
          {coverage.publication_cap_reached && " The publication scan cap was reached."}
          <span>{coverage.note}</span>
        </div>}

      {!state.computedAt && state.status === "ready" &&
        <div className="axis-hint">
          No local snapshot for {scopeLabel}. Run an explicit scan when you want to query OpenAlex.
        </div>}
      {state.computedAt && !running && candidates.length === 0 &&
        <div className="axis-hint">
          No grounded citation gaps surfaced at the current shared-reference threshold. This does not certify
          that the citation neighborhood is complete.
        </div>}

      <div className="mypubs-gap-list">
        {candidates.map(candidate => {
          const action = rowAction[candidate.openalex_work_id];
          const busy = action === "adding" || action === "dismissing";
          return (
            <article className="mypubs-gap-card" key={candidate.openalex_work_id}>
              <div className="mypubs-gap-card-main">
                <div className="mypubs-gap-card-copy">
                  <a href={`https://openalex.org/${candidate.openalex_work_id}`} target="_blank"
                    rel="noopener noreferrer" className="mypubs-gap-title">
                    {candidate.title || candidate.doi || candidate.openalex_work_id} ↗
                  </a>
                  <div className="gap-row-meta">
                    <span className="gap-count">
                      {candidate.shared_reference_count} shared reference
                      {candidate.shared_reference_count === 1 ? "" : "s"} across{" "}
                      {candidate.source_publication_count} of your publications
                    </span>
                    {candidate.authors && candidate.authors.length > 0 &&
                      <> · {candidate.authors.slice(0, 3).join(", ")}{candidate.authors.length > 3 ? " et al." : ""}</>}
                    {candidate.year ? ` · ${candidate.year}` : ""}
                  </div>
                </div>
                <div className="gap-row-actions">
                  {candidate.doi &&
                    <button className="axis-link mypubs-gap-add" disabled={isDemoMode() || busy}
                      title={isDemoMode() ? "Adding this candidate requires the local Callosum database." : undefined}
                      onClick={() => add(candidate)}>
                      {action === "adding" ? "Adding…" : "Add"}
                    </button>}
                  <button className="axis-link" disabled={isDemoMode() || busy}
                    title={isDemoMode() ? "Dismissing this candidate requires the local Callosum database." : undefined}
                    onClick={() => dismiss(candidate)}>
                    {action === "dismissing" ? "Dismissing…" : "Dismiss"}
                  </button>
                </div>
              </div>
              {action && !busy && <div className="axis-err">{action}</div>}
              <details className="mypubs-gap-evidence">
                <summary>Why this surfaced</summary>
                {(candidate.evidence || []).map(item => (
                  <div className="mypubs-gap-anchor" key={item.reference_openalex_work_id}>
                    <a href={`https://openalex.org/${item.reference_openalex_work_id}`} target="_blank"
                      rel="noopener noreferrer">
                      {item.reference_title || item.reference_doi || item.reference_openalex_work_id} ↗
                    </a>
                    <span> is cited by </span>
                    {(item.source_papers || []).map((paper, index) => (
                      <React.Fragment key={paper.paper_id}>
                        {index > 0 && <span>, </span>}
                        <button className="axis-link" onClick={() =>
                          onSelectPaper && onSelectPaper(paper.paper_id)}>
                          {paper.title}
                        </button>
                      </React.Fragment>
                    ))}
                  </div>
                ))}
                <div className="mypubs-gap-caveat">
                  Shared references are a retrieval trail, not proof that this work belongs in your bibliography.
                </div>
              </details>
            </article>
          );
        })}
      </div>
    </section>
  );
}
