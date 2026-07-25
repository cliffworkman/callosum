// My Publications Layer 4 (inc 386): grounded co-citation gaps. The dashboard reads a local snapshot; only the
// explicit Refresh button performs bounded OpenAlex metadata work. Every candidate expands to the shared
// reference anchors and confirmed own publications that caused it to surface.

function MyPubsCitationGaps({ onSelectPaper, onLibraryChanged }) {
  const [state, setState] = useState({ status: "loading", candidates: [], coverage: null, computedAt: null });
  const [refresh, setRefresh] = useState({ status: "idle" });
  const [rowAction, setRowAction] = useState({});

  const load = React.useCallback(() => {
    api("/my-publications/citation-gaps").then(r => {
      if (r.ok) {
        setState({
          status: "ready",
          candidates: r.data.candidates || [],
          coverage: r.data.coverage || null,
          computedAt: r.data.computed_at || null,
        });
      } else setState({ status: "error", error: r.error, candidates: [], coverage: null, computedAt: null });
    });
  }, []);

  useEffect(() => { load(); }, [load]);

  const runRefresh = async () => {
    setRefresh({ status: "running" });
    const started = await apiPost("/my-publications/citation-gaps/refresh", {});
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
  return (
    <section className="mypubs-prospection" aria-labelledby="mypubs-citation-gaps-title">
      <div className="mypubs-summary-head">
        <span id="mypubs-citation-gaps-title">
          Citation gaps <span className="mypubs-grounded-tag">Grounded prospection</span>
        </span>
        <button className="btn btn-ghost" disabled={running} onClick={runRefresh}>
          {running ? "Scanning…" : (state.computedAt ? "↻ Refresh gaps" : "Find citation gaps")}
        </button>
      </div>
      <p className="mypubs-prospection-intro">
        Works that share reference anchors with several of your publications, while none of the scanned
        publications cites the candidate. Every suggestion shows the exact OpenAlex graph evidence.
      </p>

      {running && <ProgressBar label="Tracing shared references through OpenAlex…" />}
      {refresh.status === "error" && <div className="axis-err">{refresh.error}</div>}
      {state.status === "error" && <div className="axis-err">{state.error}</div>}
      {state.status === "loading" && <div className="axis-hint">Loading the local citation-gap snapshot…</div>}

      {state.computedAt && coverage &&
        <div className="mypubs-gap-coverage">
          Last refreshed {new Date(state.computedAt).toLocaleString()} · scanned {coverage.checked} of{" "}
          {coverage.total} confirmed publications
          {coverage.total > coverage.with_doi ? ` (${coverage.total - coverage.with_doi} had no DOI)` : ""}
          {" "}· {coverage.shared_anchor_count} shared reference anchor
          {coverage.shared_anchor_count === 1 ? "" : "s"}.
          {coverage.publication_cap_reached && " The publication scan cap was reached."}
          <span>{coverage.note}</span>
        </div>}

      {!state.computedAt && state.status === "ready" &&
        <div className="axis-hint">Not computed yet. Run an explicit scan when you want to query OpenAlex.</div>}
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
                    <button className="axis-link mypubs-gap-add" disabled={busy} onClick={() => add(candidate)}>
                      {action === "adding" ? "Adding…" : "Add"}
                    </button>}
                  <button className="axis-link" disabled={busy} onClick={() => dismiss(candidate)}>
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
                          onSelectPaper && onSelectPaper({ id: paper.paper_id, title: paper.title })}>
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
