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
function StatcheckPaper({ paperId, onOpenPaper, active }) {
  const [meta, setMeta] = useState(null);          // { title, hasText } | null
  const [state, setState] = useState({ status: "idle" });  // idle | running | done | error
  const listRef = useRef(null);
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
  // inc-140 build-first: when this section is the OPEN one, auto-run the check so a (flagged) paper's per-test
  // rows show with no extra click — the experience-pass gap. Gated on `active` (sections are mount-but-hidden, so
  // a hidden section never runs); re-runs per paper (the meta-reset effect above puts status back to idle).
  useEffect(() => {
    if (active && meta && meta.hasText && state.status === "idle") run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, meta]);
  // inc 154: once a check finishes, scroll the FIRST inconsistent row into view + flash it — so the flagged-chip
  // path (inc 141) lands the citer on the specific result that doesn't recompute, not just the list of all tests.
  useEffect(() => {
    if (state.status !== "done" || !listRef.current) return;
    const row = listRef.current.querySelector(".statcheck-item.flagged-row");
    if (!row) return;
    row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    row.classList.add("flash");
    const t = setTimeout(() => row.classList.remove("flash"), 1400);
    return () => clearTimeout(t);
  }, [state.status]);
  const open = (r, idx) => {
    if (!onOpenPaper || !r || r.page == null) return;
    onOpenPaper(
      { id: paperId, title: meta ? meta.title : "" },
      {
        id: `statcheck:${paperId}:${idx}:${r.coordinate_precision || "region"}`,
        paperId,
        paperTitle: meta ? meta.title : "",
        page: r.page,
        pageEnd: r.page_end || r.page,
        section: r.section || null,
        precision: r.coordinate_precision || "region",
        bboxJson: r.bbox_json || null,
        status: r.consistency,
        quote: r.raw || "",
      },
    );
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
            <div className="statcheck-list" ref={listRef}>
              {d.results.map((r, i) => (
                <div key={i} className={"statcheck-item" + (r.consistency !== "consistent" ? " flagged-row" : "")}>
                  <button type="button" className="statcheck-item-main"
                    title={r.page != null
                      ? (r.coordinate_precision === "exact" ? "Open and highlight this reported test" : "Open page " + r.page + " — region precision")
                      : "No page recorded for this test"}
                    onClick={() => open(r, i)}>
                    <span className="statcheck-raw">{r.raw}</span>
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
                    caveat="statcheck recomputes inline APA-style tests only; a signal is a prompt to inspect, not a verdict." />
                </div>
              ))}
            </div>
            <div className="statcheck-caveat">
              statcheck reads only inline APA-style tests and recomputes each p — it can't see tables, Bayesian stats, or CIs, so a clean result isn't a clean bill. Inconsistencies are common and usually innocent (typos, rounding, one-tailed tests) — a prompt to look, not a verdict.
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
      <div className="method-credit-sub">Re-implemented in Python (the <i>statcheck</i> R package is by Nuijten &amp; Epskamp) — credited, not reused. Surfaced via D. Lakens' automated-review catalog.</div>
    </div>
  );
}

function StatcheckSection({ ctx }) {
  return (
    <div className="statcheck-section">
      <p className="eyebrow">Whole library</p>
      <StatcheckLibrary onShowFlagged={ctx.onShowStatcheckFlagged} onRan={ctx.onStatcheckRan} />
      <p className="eyebrow">This paper</p>
      <StatcheckPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper} active={ctx.methodsOpen === "statcheck"} />
      <StatcheckCredit />
    </div>
  );
}

registerPaneSection({
  id: "statcheck", label: "Statistics", paneId: "methods", order: 30, hideInReadOnly: true,
  render: (ctx) => <StatcheckSection ctx={ctx} />,
});
