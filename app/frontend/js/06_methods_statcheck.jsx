// inc 122: the "Statistics check" METHODS section — the first real module on the inc-121 pane registry.
// Consolidates statcheck's two surfaces, moved out of Settings (StatcheckSettings) and the Details pane
// (StatcheckRow): a library-wide batch run + a per-paper check. Local, deterministic, NO AI (no egress).
// Counts are a list to review, never a rank or verdict (Principles #2/#7 + the no-accusation A-A boundary).

// Library-wide batch (moved verbatim from StatcheckSettings, inc 97). On completion it calls ctx.onStatcheckRan()
// so the App refreshes the header "N flagged" chip; ctx.onShowStatcheckFlagged jumps to the library filter.
function StatcheckLibrary({ onShowFlagged, onRan }) {
  const [run, setRun] = useState({ status: "idle" });  // idle | running | done | error
  const start = async () => {
    setRun({ status: "running" });
    const poll = (jobId) => api(`/methods/statcheck/run/${jobId}`).then(r => {
      if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setRun({ status: "done", summary: d.summary }); if (onRan) onRan(); }
      else if (d.status === "error") setRun({ status: "error", error: d.detail || "Check failed." });
      else setTimeout(() => poll(jobId), 1500);
    });
    const r = await apiPost("/methods/statcheck/run", {});
    if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  const s = run.summary;
  return (
    <div className="statcheck-lib">
      <div className="settings-sub">Recompute reported APA-style p-values across your whole library (statcheck) — local, no AI. It flags where a reported and recomputed p disagree; usually innocent (typos, rounding, one-tailed tests) — a list to review, not a verdict.</div>
      <div className="settings-actions">
        <button className="btn btn-primary" disabled={run.status === "running"} onClick={start}>
          {run.status === "running" ? "Checking…" : "Check all papers"}
        </button>
      </div>
      {run.status === "running" && <ProgressBar label="Recomputing statistics…" />}
      {run.status === "error" && <div className="settings-note settings-note-err">Check failed: {run.error}</div>}
      {run.status === "done" && s &&
        <div className="settings-note">
          {s.checked} paper{s.checked === 1 ? "" : "s"} with statistics checked · <b>{s.flagged}</b> with inconsistencies.
          {s.flagged > 0 && onShowFlagged && <> <button className="btn-link" onClick={onShowFlagged}>Show flagged papers</button></>}
        </div>}
    </div>
  );
}

// Per-paper check (moved from StatcheckRow in 25_detail.jsx, inc 95). The section gets only the paper id via ctx,
// so it self-fetches the paper's title + chunk_count (statcheck needs extracted text). Each row routes to its
// page at region precision (page-open, never a fake exact highlight — coordinate-honesty contract).
function StatcheckPaper({ paperId, onOpenPaper }) {
  const [meta, setMeta] = useState(null);          // { title, hasText } | null
  const [state, setState] = useState({ status: "idle" });  // idle | running | done | error
  useEffect(() => {
    setState({ status: "idle" }); setMeta(null);
    if (paperId == null) return;
    let live = true;
    api(`/papers/${paperId}`).then(r => {
      if (!live || !r.ok) return;
      setMeta({ title: r.data.title, hasText: (r.data.chunk_count || 0) > 0 });
    });
    return () => { live = false; };
  }, [paperId]);
  const run = async () => {
    setState({ status: "running" });
    const r = await api(`/papers/${paperId}/statcheck`);
    setState(r.ok ? { status: "done", data: r.data } : { status: "error", error: r.error });
  };
  const open = (page) => { if (onOpenPaper && page != null) onOpenPaper({ id: paperId, title: meta ? meta.title : "" }, { page, precision: "region" }); };
  const label = (c) => c === "consistent" ? "consistent" : c === "decision-error" ? "decision error" : "inconsistent";
  if (paperId == null) return <div className="tag-suggest-empty">Select a paper to check its statistical reporting.</div>;
  const hasText = meta ? meta.hasText : false;
  const d = state.data;
  return (
    <div className="detail-statcheck">
      <span className="detail-cite-label">{meta ? meta.title : "This paper"}</span>
      {!meta
        ? <span className="tag-suggest-empty">loading…</span>
        : !hasText
          ? <span className="tag-suggest-empty">Process a PDF first — statcheck reads the paper's extracted text.</span>
          : state.status === "idle"
            ? <button className="btn-link" title="Recompute reported p-values from this paper's text — local, no AI" onClick={run}>Check statistics</button>
            : null}
      {state.status === "running" && <span className="tag-suggest-empty">checking…</span>}
      {state.status === "error" && <div className="axis-err">Couldn't check: {state.error}</div>}
      {state.status === "done" && d && (d.checked === 0
        ? <div className="tag-suggest-empty">No APA-format statistics found in the extracted text.</div>
        : <div className="statcheck-result">
            <div className="statcheck-summary">{d.checked} checked · {d.inconsistent} inconsistent · {d.decision_errors} decision error{d.decision_errors === 1 ? "" : "s"}</div>
            <div className="statcheck-list">
              {d.results.map((r, i) => (
                <button key={i} className="statcheck-item" title={r.page != null ? "Open page " + r.page : ""} onClick={() => open(r.page)}>
                  <span className="statcheck-raw">{r.raw}</span>
                  <span className="statcheck-computed">computed p = {r.computed_p}</span>
                  <span className={"cite-status " + (r.consistency === "consistent" ? "verified" : "flagged")}>{label(r.consistency)}</span>
                </button>
              ))}
            </div>
            <div className="statcheck-caveat">
              statcheck reads only inline APA-style tests and recomputes each p — it can't see tables, Bayesian stats, or CIs, so a clean result isn't a clean bill. Inconsistencies are common and usually innocent (typos, rounding, one-tailed tests) — a prompt to look, not a verdict.
            </div>
          </div>)}
    </div>
  );
}

function StatcheckSection({ ctx }) {
  return (
    <div className="statcheck-section">
      <p className="eyebrow">Whole library</p>
      <StatcheckLibrary onShowFlagged={ctx.onShowStatcheckFlagged} onRan={ctx.onStatcheckRan} />
      <p className="eyebrow">This paper</p>
      <StatcheckPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper} />
    </div>
  );
}

registerPaneSection({
  id: "statcheck", label: "Statistics check", paneId: "methods", order: 30,
  render: (ctx) => <StatcheckSection ctx={ctx} />,
});
