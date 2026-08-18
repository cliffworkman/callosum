// 08n_methods_analytic_flexibility.jsx — Analytic-flexibility surfacing (backlog #37): the 5th Checklists-family
// panel, and the first that's LLM-assisted rather than deterministic/local (see 08h/08f/08d/08g for the other
// four). The model only PROPOSES a decomposed, quote-only {category, quote} candidate from a paper's methods
// section (backend/analytic_flexibility.py); it never asserts a location or confidence. A local, deterministic
// locator (pdf_processing/quote_matching.py) independently decides each quote's exact/region/unanchored anchor
// before anything is persisted, honoring the coordinate-honesty contract (invariant #2). Every candidate is
// reviewable via the shared FindingCard (08x_methods_critical.jsx, unmodified) — AI funnel, human filter. No
// count, index, tally, or aggregate score appears anywhere in this panel, by design.
//
// AnalyticFlexibilityPaper (below) is the Library-paper path: a WIP manuscript has no `papers.id`, so the
// per-paper endpoints it calls don't apply to one. The WIP counterpart is `WipAnalyticFlexibilitySection`
// (10k_wip_checks.jsx), called from this file's own manuscript branch — the shared-IIFE cross-chunk hoist
// pattern (inc-208/222) the sibling checklist panels (08f/08d/08g/08h) already use for their own WIP branches.

function AnalyticFlexibilityPaper({ paperId, onOpenPaper, onFindingsChanged, findingsRefresh }) {
  const [findings, setFindings] = useState([]);
  const [aiReady, setAiReady] = useState(false);
  const [state, setState] = useState({ status: "idle" }); // idle | running | done | error

  const load = useCallback(() => {
    if (paperId == null) { setFindings([]); return; }
    api(`/papers/${paperId}/findings?source=analytic-flexibility`).then(r => {
      if (r.ok) setFindings(r.data.candidates || []);
    });
  }, [paperId]);

  useEffect(() => { load(); }, [load, findingsRefresh]);
  useEffect(() => { setState({ status: "idle" }); }, [paperId]);
  useEffect(() => { api("/settings").then(r => { if (r.ok) setAiReady(Boolean(r.data.data_egress_enabled)); }); }, []);

  const run = async () => {
    setState({ status: "running" });
    const r = await apiPost(`/papers/${paperId}/analytic-flexibility`, {});
    if (!r.ok) { setState({ status: "error", error: r.error }); return; }
    setState({ status: "done", result: r.data });
    load();
    if (onFindingsChanged) onFindingsChanged();
  };

  if (paperId == null) return <div className="tag-suggest-empty">Select a paper to surface analytic decision points.</div>;

  return (
    <div className="detail-statcheck">
      <div className="statcheck-caveat">
        Proposes specific, disclosed analytic decision points from this paper's methods section — exclusion
        criteria, covariate/control choices, statistical test or model selection, outcome/measure choices, and
        other reported branch points — each a reviewable <b>candidate</b> you confirm or dismiss, never a
        flexibility count or score. The model only proposes a quote; a local, deterministic check independently
        decides where (or whether) it anchors in the source PDF.
      </div>
      {isDemoMode()
        ? <div className="tag-suggest-empty">Surfacing analytic decision points requires the local Callosum application; no paper text is sent anywhere from this saved demo.</div>
        : !aiReady
        ? <div className="tag-suggest-empty">Enable AI features in Settings (data-egress consent) to surface analytic-flexibility candidates.</div>
        : <div className="settings-actions">
            <button className="btn btn-primary" disabled={state.status === "running"} onClick={run}
              title="Proposes candidate analytic decision points from this paper's methods section — opt-in AI, each candidate reviewable against its quoted source text">
              {state.status === "running" ? "Surfacing…" : findings.length ? "Surface again" : "Surface decision points"}
            </button>
          </div>}
      {state.status === "running" && <ProgressBar label="Surfacing analytic decision points…" managedBy="tracked-request" />}
      {state.status === "error" && <div className="axis-err">Couldn't surface decision points: {state.error}</div>}
      {state.status === "done" && state.result && state.result.methods_text_found === false
        ? <div className="tag-suggest-empty">
            No methods-section text was found to check — process a PDF first, or this paper's methods section
            wasn't detected. That is not a claim the design has no analytic flexibility.
          </div>
        : findings.length === 0 && state.status !== "running" &&
          <div className="tag-suggest-empty">
            No candidates surfaced yet. An empty list isn't a claim the design had no analytic flexibility — only
            that nothing was proposed (or everything proposed has since been reviewed away) here.
          </div>}
      {findings.map(f => <FindingCard key={f.id} finding={f} onReviewed={load} onOpenPaper={onOpenPaper} />)}
    </div>
  );
}

function AnalyticFlexibilitySection({ ctx }) {
  if (ctx.researchContext.kind === "manuscript") return (
    <div className="statcheck-section">
      <div className="settings-sub">
        Surface specific, disclosed <b>analytic decision points</b> the current manuscript's methods section
        reports, against its exact primary-file checkpoint. LLM-assisted (opt-in, egress-gated); every candidate
        is a reviewable suggestion you confirm against its quoted source text — never a verdict about the
        design's rigor or a "researcher degrees of freedom" score. An empty result is not a claim the design had
        no analytic flexibility.
      </div>
      <p className="eyebrow">This manuscript</p>
      <WipAnalyticFlexibilitySection manuscript={ctx.researchContext.entity} ctx={ctx} />
    </div>
  );
  return (
    <div className="statcheck-section">
      <div className="settings-sub">
        Surface specific, disclosed <b>analytic decision points</b> a paper's methods section reports — places
        where a different reasonable choice could have changed the result. LLM-assisted (opt-in, egress-gated);
        every candidate is a reviewable suggestion you confirm against its quoted, page-anchored source text —
        never a verdict about the paper's rigor or a "researcher degrees of freedom" score.
      </div>
      <AnalyticFlexibilityPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper}
        onFindingsChanged={ctx.onFindingsChanged} findingsRefresh={ctx.findingsRefresh} />
    </div>
  );
}

registerPaneTab(
  { id: "checklists", label: "Checklists", paneId: "methods", order: 40 },
  {
    id: "analytic-flexibility", label: "Analytic flexibility", order: 50, hideInReadOnly: true, demoInspectable: true,
    render: (ctx, active) => <AnalyticFlexibilitySection ctx={ctx} />,
  },
);
