// inc 122: the "Statistics" METHODS section (labeled "Statistics check" until the 2026-07-21 pane regroup) —
// the first real module on the inc-121 pane registry.
// Consolidates statcheck's two surfaces, moved out of Settings (StatcheckSettings) and the Details pane
// (StatcheckRow): a library-wide batch run + a per-paper check. Local, deterministic, NO AI (no egress).
// Counts are a list to review, never a rank or verdict (Principles #2/#7 + the no-accusation A-A boundary).

// inc 180 (credit-the-lineage): the source paper for statcheck, one-click added to the library via the inc-93
// import path — matching the GRIM/p-curve credit blocks (now all on the shared .method-credit recipe).
const STATCHECK_CSL = {
  type: "article-journal",
  title: "The prevalence of statistical reporting errors in psychology (1985–2013)",
  author: [
    { family: "Nuijten", given: "Michèle B." },
    { family: "Hartgerink", given: "Chris H. J." },
    { family: "van Assen", given: "Marcel A. L. M." },
    { family: "Epskamp", given: "Sacha" },
    { family: "Wicherts", given: "Jelte M." },
  ],
  "container-title": "Behavior Research Methods",
  volume: "48",
  page: "1205-1226",
  issued: { "date-parts": [[2016]] },
  DOI: "10.3758/s13428-015-0664-2",
};

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
      <div className="settings-sub">Recompute reported APA-style p-values across your whole library (statcheck) — from running text and clearly headed table rows, local and without AI. It flags where a reported and recomputed p disagree; usually innocent (typos, rounding, one-tailed tests) — a list to review, not a verdict.</div>
      <div className="settings-actions">
        <button className="btn btn-primary" disabled={run.status === "running" || isDemoMode()} onClick={start}
          title={isDemoMode() ? "Library-wide computation is unavailable in the static online demo." : undefined}>
          {run.status === "running" ? "Checking…" : "Check all papers"}
        </button>
      </div>
      {isDemoMode() && <div className="settings-note">This saved library snapshot is fully inspectable. Running statcheck requires the local Callosum application.</div>}
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
// inc 400: shows the CACHED result on selection (no live recompute) with a permanent, explicit Rescan control and
// an "as of <date>" line — on the premise that a published paper's statistics rarely change. A content-fingerprint
// mismatch (the paper was reprocessed since) surfaces as a passive amber hint beside the still-shown old result;
// it never blocks display or auto-triggers a recompute.
function StatcheckPaper({ paperId, onOpenPaper }) {
  const [meta, setMeta] = useState(null);          // { title, hasText } | null
  const [state, setState] = useState({ status: "idle" });  // idle | loading | empty | cached | running | error
  const listRef = useRef(null);
  useEffect(() => {
    setState({ status: "idle" }); setMeta(null);
    if (paperId == null) return;
    let live = true;
    api(`/papers/${paperId}`).then(r => {
      if (!live || !r.ok) return;
      setMeta({ title: r.data.title, hasText: (r.data.chunk_count || 0) > 0 || (r.data.attachment_count || 0) > 0 });
    });
    return () => { live = false; };
  }, [paperId]);
  // Fetches the cached result on paper select -- never recomputes. Replaces the old inc-140 auto-run-on-open.
  useEffect(() => {
    if (paperId == null) return undefined;
    let live = true;
    setState({ status: "loading" });
    api(`/papers/${paperId}/statcheck/cached`).then(r => {
      if (!live) return;
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      setState(r.data.cached ? { status: "cached", data: r.data } : { status: "empty" });
    });
    return () => { live = false; };
  }, [paperId]);
  const rescan = async () => {
    setState(s => ({ ...s, status: "running" }));
    const r = await apiPost(`/papers/${paperId}/statcheck/rescan`, {});
    setState(r.ok ? { status: "cached", data: r.data } : { status: "error", error: r.error });
  };
  // inc 154: once a check finishes, scroll the FIRST inconsistent row into view + flash it — so the flagged-chip
  // path (inc 141) lands the citer on the specific result that doesn't recompute, not just the list of all tests.
  useEffect(() => {
    if (state.status !== "cached" || !listRef.current) return;
    const row = listRef.current.querySelector(".statcheck-item.flagged-row");
    if (!row) return;
    row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    row.classList.add("flash");
    const t = setTimeout(() => row.classList.remove("flash"), 1400);
    return () => clearTimeout(t);
  }, [state.status]);
  const open = (r, idx) => {
    if (!onOpenPaper) return;
    const title = meta ? meta.title : "";
    const target = methodEvidenceTarget(paperId, title, r, `statcheck:${paperId}:${idx}`);
    if (target) onOpenPaper({ id: paperId, title }, target);
  };
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
          ? <span className="tag-suggest-empty">Process a PDF or supported full-text document first — statcheck needs extracted evidence.</span>
          : (state.status === "empty" || state.status === "cached") &&
            <div className="statcheck-actions">
              <button className="btn-link" disabled={state.status === "running" || isDemoMode()}
                title={isDemoMode() ? "Rescanning is unavailable in the static online demo." : "Recompute reported p-values from prose and clearly headed table rows — local, no AI"}
                onClick={rescan}>
                {state.status === "running" ? "Checking…" : state.status === "cached" ? "Rescan" : "Check statistics"}
              </button>
              {state.status === "cached" && d.computed_at &&
                <span className="statcheck-asof" title={`Last checked ${d.computed_at}`}>as of {d.computed_at.slice(0, 10)}</span>}
              {state.status === "cached" && d.stale &&
                <span className="statcheck-stale-hint" title="This paper's extracted text or attachments changed since this check ran. Rescan to refresh — this cached result is unchanged until you do.">
                  may be stale — paper reprocessed since
                </span>}
            </div>}
      {state.status === "loading" && <span className="tag-suggest-empty">loading…</span>}
      {state.status === "running" && !state.data && <span className="tag-suggest-empty">checking…</span>}
      {state.status === "error" && <div className="axis-err">Couldn't check: {state.error}</div>}
      {state.status === "cached" && d && (d.checked === 0
        ? <div className="tag-suggest-empty">
            No eligible APA-format statistics were found in running text or clearly headed table rows.
            {d.coverage && <div className="statcheck-coverage">
              Scanned {d.coverage.prose_chunks} text block{d.coverage.prose_chunks === 1 ? "" : "s"}
              {" "}and {d.coverage.table_rows_scanned} row{d.coverage.table_rows_scanned === 1 ? "" : "s"} from{" "}
              {d.coverage.tables_scanned} detected table{d.coverage.tables_scanned === 1 ? "" : "s"}.
              {d.coverage.truncated && " A safety cap was reached; coverage is partial."}
            </div>}
          </div>
        : <div className="statcheck-result">
            <div className="statcheck-summary">
              {d.checked} checked · {d.inconsistent} inconsistent · {d.decision_errors} decision error{d.decision_errors === 1 ? "" : "s"}
              {d.coverage && d.coverage.table_results > 0 && ` · ${d.coverage.table_results} from tables`}
            </div>
            <div className="statcheck-list" ref={listRef}>
              {d.results.map((r, i) => (
                <div key={i} className={"statcheck-item" + (r.consistency !== "consistent" ? " flagged-row" : "")}>
                  <button type="button" className="statcheck-item-main"
                    title={r.page != null
                      ? (r.coordinate_precision === "exact" ? "Open and highlight this reported test" : "Open page " + r.page + " — region precision")
                      : "No page recorded for this test"}
                    onClick={() => open(r, i)}>
                    <span className="statcheck-raw">{r.raw}</span>
                    {r.source_kind === "table" &&
                      <span className="statcheck-source" title="Reconstructed only from this explicitly headed table row">
                        table {r.table_index}{r.table_row ? ` · row ${r.table_row}` : ""}
                      </span>}
                    {r.context && <EvidenceQuote text={r.context} match={r.raw} label="Context"
                      section={r.section}
                      precision={r.coordinate_precision} hasSourcePage={r.page != null}
                      className="statcheck-context" maxChars={340} />}
                    {r.page != null
                      ? <span className="statcheck-page" title={r.coordinate_precision === "exact" ? "Open exact source highlight" : "Open this page (region precision — the page, not an exact highlight)"}>{pageLabel({ page_start: r.page, page_end: r.page_end, section: r.section })}</span>
                      : <span className="statcheck-page statcheck-page-none" title="statcheck couldn't attribute this test to a page">p. —</span>}
                    <span className="statcheck-computed">computed p = {r.computed_p}</span>
                    <span className={"cite-status " + (r.consistency === "consistent" ? "verified" : "flagged")}>{label(r.consistency)}</span>
                  </button>
                  <EvidenceTrail detector="statcheck" matched={r.raw} precision={r.coordinate_precision}
                    hasSourcePage={r.page != null} page={r.page} section={r.section}
                    caveat={r.source_kind === "table"
                      ? "Reconstructed from the displayed table headers and row; ambiguous rows are skipped. A signal is a prompt to inspect, not a verdict."
                      : "Recomputed from an inline APA-style test; a signal is a prompt to inspect, not a verdict."} />
                </div>
              ))}
            </div>
            {d.coverage && <div className="statcheck-coverage">
              Table coverage: {d.coverage.tables_scanned} detected table{d.coverage.tables_scanned === 1 ? "" : "s"},{" "}
              {d.coverage.table_rows_scanned} row{d.coverage.table_rows_scanned === 1 ? "" : "s"} scanned across{" "}
              {d.coverage.attachments_scanned} attachment{d.coverage.attachments_scanned === 1 ? "" : "s"}.
              {d.coverage.attachments_skipped > 0 && ` ${d.coverage.attachments_skipped} attachment${d.coverage.attachments_skipped === 1 ? " was" : "s were"} skipped.`}
              {d.coverage.truncated && " A safety cap was reached; coverage is partial."}
            </div>}
            <div className="statcheck-caveat">
              statcheck reads inline APA-style tests plus table rows whose headers unambiguously identify the test, degrees of freedom, statistic, and p-value. Ambiguous/unlabeled tables, Bayesian statistics, and confidence-interval-only results remain invisible, so a clean result isn't a clean bill. Inconsistencies are common and usually innocent (typos, rounding, one-tailed tests) — a prompt to look, not a verdict.
            </div>
          </div>)}
    </div>
  );
}

// inc 180: credit the statcheck method in-context + offer its source paper to the library (credit-the-lineage).
function StatcheckCredit() {
  return (
    <div className="method-credit">
      <b>Method:</b> statcheck — Nuijten, Hartgerink, van Assen, Epskamp &amp; Wicherts (2016), <i>Behavior Research Methods</i> 48:1205–1226.{" "}
      <MethodCreditButton items={[STATCHECK_CSL]} />
      <div className="method-credit-sub">Re-implemented in Python (the <i>statcheck</i> R package is by Nuijten &amp; Epskamp) — credited, not reused.</div>
      <LakensCredit />
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
      <StatcheckCredit />
    </div>
  );
}

// inc 402: a WIP manuscript has no papers.id, so ctx.selectedPaper is always null while one is active
// (40_app.jsx) -- branch on researchContext.kind exactly like the "Details" section (05_panes.jsx) does,
// delegating to the WIP-specific statcheck surface (10k_wip_checks.jsx) rather than a paper-shaped component.
registerPaneSection({
  id: "statcheck", label: "Statistics", paneId: "methods", order: 30, hideInReadOnly: true, demoInspectable: true,
  render: (ctx) => ctx.researchContext && ctx.researchContext.kind === "manuscript"
    ? <WipStatcheckSection manuscript={ctx.researchContext.entity} ctx={ctx} />
    : <StatcheckSection ctx={ctx} />,
});
