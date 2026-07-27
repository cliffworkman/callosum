// Funding Discovery: latent funding prospects from observed funding behavior and funding lineage, with current
// opportunities resolved separately. Signal only: no recommendation language, probability, or match percentage.

function FundingSegmented({ mode, setMode }) {
  return (
    <div className="tags-srcfilter funding-mode" role="group" aria-label="Funding Discovery input mode">
      <button type="button" className={"tags-srcfilter-btn" + (mode === "paper" ? " on" : "")}
        onClick={() => setMode("paper")}>Selected paper</button>
      <button type="button" className={"tags-srcfilter-btn" + (mode === "manual" ? " on" : "")}
        onClick={() => setMode("manual")}>Describe research</button>
    </div>
  );
}

function FundingCoverage({ statuses }) {
  if (!statuses || !statuses.length) return null;
  const limits = fundingCoverageLimits(statuses);
  return (
    <div className="funding-coverage">
      <div className="funding-subhead">Source coverage</div>
      <div className="funding-coverage-grid">
        {statuses.map((s, i) => (
          <div key={i} className={"funding-provider " + (s.status || "unknown")}>
            <div className="funding-provider-head">
              <span>{fundingProviderDisplayName(s.provider_id)} · {(s.capability || "coverage").replaceAll("_", " ")}</span>
              <b className="funding-provider-status">{fundingProviderStatusLabel(s.status)}</b>
            </div>
            {s.result_count != null && <small>{s.result_count} record{s.result_count === 1 ? "" : "s"}</small>}
            {s.indexed_through && <small>indexed through {s.indexed_through}</small>}
            {s.warning && <small>{s.warning}</small>}
            {s.error_code && <small>Error: {s.error_code}</small>}
            <small className="funding-provider-note">{fundingCoverageMeaning(s)}</small>
          </div>
        ))}
      </div>
      <details className="funding-coverage-limits">
        <summary>What was not covered</summary>
        <div>
          {limits.map((note, i) => <small key={i}>{note}</small>)}
        </div>
      </details>
    </div>
  );
}

function FundingLlmStatus({ status }) {
  if (!status || status.status === "not_searched") return null;
  const ok = status.status === "success";
  return (
    <div className={"funding-llm-status " + (ok ? "success" : "partial")}>
      <b>LLM triage</b>
      <span>
        {ok
          ? `${status.annotated_count || 0} item${status.annotated_count === 1 ? "" : "s"} marked for the triage view.`
          : status.warning || "AI triage was unavailable; full deterministic results are still shown."}
      </span>
      {ok && status.warning && <small>{status.warning}</small>}
      <small>Model labels are review aids only; the full surfaced pool remains available.</small>
    </div>
  );
}

function FundingLlmTriageControls({ report, ready, running, onRun }) {
  if (!report) return null;
  return (
    <div className="funding-llm-controls">
      <button className="btn btn-ghost" type="button" disabled={running} onClick={onRun}>
        {ready ? "Re-evaluate apparent fit with AI" : "Evaluate apparent fit with AI"}
      </button>
      <small>Advisory labels only. This does not remove records, alter saved items, or create recommendations.</small>
    </div>
  );
}

const FUNDING_VIEW_PREFS_KEY = "callosum.fundingDiscovery.viewPrefs.v1";

function fundingLoadViewPrefs() {
  const fallback = { triageOnly: false, showLowerProspects: false, resultFilter: "all", resultSort: "default" };
  try {
    const raw = localStorage.getItem(FUNDING_VIEW_PREFS_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    const validFilters = new Set(FUNDING_RESULT_FILTERS.map(f => f.key));
    const validSorts = new Set(FUNDING_RESULT_SORTS.map(s => s.key));
    return {
      triageOnly: parsed.triageOnly === true,
      showLowerProspects: parsed.showLowerProspects === true,
      resultFilter: validFilters.has(parsed.resultFilter) ? parsed.resultFilter : "all",
      resultSort: validSorts.has(parsed.resultSort) ? parsed.resultSort : "default",
    };
  } catch (_err) {
    return fallback;
  }
}

function fundingSaveViewPrefs(prefs) {
  try {
    localStorage.setItem(FUNDING_VIEW_PREFS_KEY, JSON.stringify(prefs));
  } catch (_err) {
    // Local display preferences are optional; storage failures must not affect evidence rendering.
  }
}

function FundingDiscoveryPanel({ ctx }) {
  const initialViewPrefs = fundingLoadViewPrefs();
  // inc 403: a WIP manuscript has no papers.id, so ctx.selectedPaper stays null while one is active -- mode
  // already falls through to "manual" for free; this just also seeds the manual fields from the manuscript.
  const manuscript = ctx.researchContext && ctx.researchContext.kind === "manuscript" ? ctx.researchContext.entity : null;
  const [mode, setMode] = useState(ctx.selectedPaper != null ? "paper" : "manual");
  const [description, setDescription] = useState("");
  const [field, setField] = useState("");
  const [llmTriage, setLlmTriage] = useState(false);
  const [triageOnly, setTriageOnly] = useState(initialViewPrefs.triageOnly);
  const [showLowerProspects, setShowLowerProspects] = useState(initialViewPrefs.showLowerProspects);
  const [resultFilter, setResultFilter] = useState(initialViewPrefs.resultFilter);
  const [resultSort, setResultSort] = useState(initialViewPrefs.resultSort);
  const [meta, setMeta] = useState(null);
  const [state, setState] = useState({ status: "idle" });
  const [triageState, setTriageState] = useState({ status: "idle" });
  const [savedItems, setSavedItems] = useState([]);
  const [recentRuns, setRecentRuns] = useState([]);
  const [runLoadState, setRunLoadState] = useState({ status: "idle" });

  const refreshSaved = () => api("/funding-discovery/saved").then(r => {
    if (r.ok) setSavedItems(r.data.items || []);
  });
  const refreshRuns = () => api("/funding-discovery/runs?limit=8").then(r => {
    if (r.ok) setRecentRuns(r.data.runs || []);
  });

  useEffect(() => {
    let live = true;
    api("/funding-discovery/saved").then(r => { if (live && r.ok) setSavedItems(r.data.items || []); });
    return () => { live = false; };
  }, []);
  useEffect(() => {
    let live = true;
    api("/funding-discovery/runs?limit=8").then(r => { if (live && r.ok) setRecentRuns(r.data.runs || []); });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    setMeta(null);
    if (ctx.selectedPaper == null) return;
    let live = true;
    api(`/papers/${ctx.selectedPaper}`).then(r => { if (live && r.ok) setMeta({ title: r.data.title }); });
    return () => { live = false; };
  }, [ctx.selectedPaper]);
  // Corrects a stale "paper" mode left from an earlier paper selection once no paper is selected anymore (e.g.
  // a WIP manuscript became active instead), so mode never dead-ends on an unusable "Select a paper" empty state.
  useEffect(() => {
    if (mode === "paper" && ctx.selectedPaper == null) setMode("manual");
  }, [ctx.selectedPaper]);

  useEffect(() => {
    fundingSaveViewPrefs({ triageOnly, showLowerProspects, resultFilter, resultSort });
  }, [triageOnly, showLowerProspects, resultFilter, resultSort]);

  // Seed (never clobber) the manual fields from the active manuscript -- a convenience starter, freely editable.
  useEffect(() => {
    if (!manuscript) return;
    setDescription(prev => prev.trim() ? prev : [manuscript.display_title, manuscript.notes].filter(Boolean).join("\n\n"));
    setField(prev => prev.trim() ? prev : (manuscript.target_journal || ""));
  }, [manuscript && manuscript.id]);

  const run = async () => {
    const body = mode === "paper"
      ? { paper_id: ctx.selectedPaper, llm_triage: llmTriage }
      : manuscript
      ? { description: description, field: field, llm_triage: llmTriage, manuscript_id: manuscript.id }
      : { description: description, field: field, llm_triage: llmTriage };
    setState({ status: "running", progress: null });
    setTriageState({ status: "idle" });
    const start = await apiPost("/funding-discovery/run", body);
    if (!start.ok) { setState({ status: "error", error: start.error }); return; }
    const poll = (jid) => api(`/funding-discovery/run/${jid}`).then(r => {
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") {
        setState({ status: "done", report: d.report });
        refreshRuns();
        // Let the manuscript's own WIP tab (Checks) pick up this run without a manual reload.
        if (manuscript && ctx.onReloadWip) ctx.onReloadWip();
      }
      else if (d.status === "error") setState({ status: "error", error: d.detail || "Funding Discovery failed." });
      else { setState({ status: "running", progress: d.progress }); setTimeout(() => poll(jid), 1400); }
    });
    poll(start.data.job_id);
  };

  const loadRun = async (runId) => {
    setRunLoadState({ status: "running", runId });
    const r = await api(`/funding-discovery/runs/${runId}`);
    if (!r.ok) { setRunLoadState({ status: "error", error: r.error }); return; }
    setState({ status: "done", report: r.data.report });
    setTriageOnly(r.data.report.llm_triage_status && r.data.report.llm_triage_status.status === "success");
    setRunLoadState({ status: "done", runId });
  };

  const runTriage = async () => {
    if (!state.report) return;
    const body = mode === "paper"
      ? { report: state.report, paper_id: ctx.selectedPaper }
      : { report: state.report, description: description, field: field };
    setTriageState({ status: "running" });
    const result = await apiPost("/funding-discovery/llm-triage", body);
    if (!result.ok) {
      setTriageState({ status: "error", error: result.error });
      return;
    }
    setState(current => ({ ...current, report: result.data.report }));
    if (result.data.llm_triage_status && result.data.llm_triage_status.status === "success") setTriageOnly(true);
    setTriageState({ status: "done" });
  };

  const report = state.report;
  const canRun = mode === "paper" ? ctx.selectedPaper != null : description.trim();
  const triageReady = report && report.llm_triage_status && report.llm_triage_status.status === "success";
  const effectiveTriageOnly = triageOnly && triageReady;
  const baseOpportunities = fundingGroupedItems(fundingTriageItems(report && report.open_opportunities, effectiveTriageOnly), "opportunity");
  const baseSchemes = fundingGroupedItems(fundingTriageItems(report && report.recurring_schemes, effectiveTriageOnly), "scheme");
  const allProspects = fundingGroupedItems(fundingTriageItems(report && report.funding_prospects, effectiveTriageOnly), "prospect");
  const hiddenProspects = allProspects.filter(item => fundingIsLowerSignalProspect(item, report && report.application_surfaces)).length;
  const baseProspects = showLowerProspects ? allProspects : allProspects.filter(item => !fundingIsLowerSignalProspect(item, report && report.application_surfaces));
  const surfacedResultItems = [
    ...baseOpportunities.map((item, i) => fundingTagItem(item, "opportunity", i)),
    ...baseSchemes.map((item, i) => fundingTagItem(item, "scheme", i)),
    ...allProspects.map((item, i) => fundingTagItem(item, "prospect", i)),
  ];
  const baseResultItems = [
    ...baseOpportunities.map((item, i) => fundingTagItem(item, "opportunity", i)),
    ...baseSchemes.map((item, i) => fundingTagItem(item, "scheme", i)),
    ...baseProspects.map((item, i) => fundingTagItem(item, "prospect", i)),
  ];
  const resultFilterCounts = fundingResultFilterCounts(baseResultItems, report && report.application_surfaces, savedItems);
  const filteredResultItems = fundingFilterResults(baseResultItems, resultFilter, report && report.application_surfaces, savedItems);
  const sortedResultItems = fundingSortResults(filteredResultItems, resultSort, report && report.application_surfaces, savedItems);
  const filteredHiddenCount = Math.max(0, baseResultItems.length - filteredResultItems.length);
  const opportunities = sortedResultItems.filter(item => item._fundingKind === "opportunity");
  const schemes = sortedResultItems.filter(item => item._fundingKind === "scheme");
  const prospects = sortedResultItems.filter(item => item._fundingKind === "prospect");
  const filteredEmpty = resultFilter !== "all";
  const hiddenLowerCount = Math.max(0, surfacedResultItems.length - baseResultItems.length);

  return (
    <div className="funding-panel ws-pad">
      <div className="funding-intro">
        Discovers plausible funding prospects from funding behavior and funding lineage, then separately checks for a
        current application surface. Absence of a surfaced record is not evidence that no mechanism exists.
      </div>
      <FundingSegmented mode={mode} setMode={setMode} />
      {mode === "paper"
        ? ctx.selectedPaper == null
          ? <div className="tag-suggest-empty">Select a paper in the library, or describe the research instead.</div>
          : <div className="pub-input-note">Building a funding profile from <b>{meta ? meta.title : "the selected paper"}</b>. Full PDFs are not sent to providers.</div>
        : <div className="pub-input">
            {manuscript && <div className="pub-input-note">Pre-filled from <b>{manuscript.display_title}</b> — edit freely; a search doesn't require your manuscript text.</div>}
            <textarea className="settings-input" rows={4} placeholder="Paste an abstract or describe the research…" value={description} onChange={e => setDescription(e.target.value)} />
            <input className="settings-input" placeholder="Short field / discipline context" value={field} onChange={e => setField(e.target.value)} />
            <div className="settings-sub">Provider queries use minimized structured facets, not full manuscript text.</div>
          </div>}
      <label className="funding-ai-toggle">
        <input type="checkbox" checked={llmTriage} onChange={e => setLlmTriage(e.target.checked)} />
        <span>Ask AI to triage apparent fit after discovery</span>
        <small>Sends the bounded abstract/description and surfaced funding-card summaries to the configured model.</small>
      </label>
      {state.status !== "running" &&
        <button className="btn btn-primary" disabled={!canRun} onClick={run}>
          {state.status === "done" ? "Search again" : "Discover funding"}
        </button>}
      {state.status === "running" && <ProgressBar progress={state.progress} label="Discovering funding prospects…" />}
      {state.status === "error" && <div className="axis-err">Funding Discovery failed: {state.error}</div>}
      <SavedFundingItems items={savedItems} onChanged={refreshSaved} />
      <FundingRunHistory runs={recentRuns} currentRunId={report && report.run_id} loadState={runLoadState}
        onReload={loadRun} onRefresh={refreshRuns} />
      {runLoadState.status === "error" && <div className="axis-err">Funding run reload failed: {runLoadState.error}</div>}
      <FundingRunActions report={report} />
      <FundingLlmTriageControls report={report} ready={triageReady}
        running={triageState.status === "running"} onRun={runTriage} />
      {triageState.status === "running" && <ProgressBar label="Evaluating apparent funding fit…" />}
      {triageState.status === "error" && <div className="axis-err">AI fit triage failed: {triageState.error}</div>}
      {report && <FundingLlmStatus status={report.llm_triage_status} />}
      <FundingViewToggle triageOnly={effectiveTriageOnly} setTriageOnly={setTriageOnly} enabled={triageReady} />
      {report && <FundingResultFilters filter={resultFilter} setFilter={setResultFilter}
        counts={resultFilterCounts} hiddenCount={filteredHiddenCount} />}
      {report && <FundingResultSort sort={resultSort} setSort={setResultSort} />}
      {report && <FundingResultSummary visible={sortedResultItems.length} displayPool={baseResultItems.length}
        surfacedTotal={surfacedResultItems.length} hiddenLower={hiddenLowerCount}
        filter={resultFilter} sort={resultSort} />}
      {report && <FundingCoverage statuses={report.provider_statuses} />}
      {report &&
        <div className="funding-results">
          <FundingSection title={`Open Opportunities (${opportunities.length})`} items={opportunities}
            empty={filteredEmpty
              ? "No open opportunities match the current display filter."
              : effectiveTriageOnly
              ? "No open opportunities were marked for the LLM-triaged view."
              : "No current opportunity records were surfaced from the sources searched."}
            render={item => <FundingOpportunityCard key={item.id} item={item}
              surfaces={fundingSurfacesFor(item, report.application_surfaces)}
              savedItem={fundingSavedItemFor("opportunity", item.id, savedItems)} onSaved={refreshSaved} />} />
          <FundingSection title={`Recurring Schemes (${schemes.length})`} items={schemes}
            empty={filteredEmpty
              ? "No recurring schemes match the current display filter."
              : effectiveTriageOnly
              ? "No recurring schemes were marked for the LLM-triaged view."
              : "No recurring scheme evidence was surfaced from the available historical records."}
            render={item => <FundingSchemeCard key={item.id} item={item}
              surfaces={fundingSurfacesFor(item, report.application_surfaces)}
              savedItem={fundingSavedItemFor("scheme", item.id, savedItems)} onSaved={refreshSaved} />} />
          {hiddenProspects > 0 &&
            <label className="funding-low-toggle">
              <input type="checkbox" checked={showLowerProspects} onChange={e => setShowLowerProspects(e.target.checked)} />
              <span>Show lower-signal prospects</span>
              <small>{hiddenProspects} lower-signal prospect{hiddenProspects === 1 ? "" : "s"} {showLowerProspects ? "shown" : "hidden"} by a display-only signal filter.</small>
            </label>}
          <FundingSection title={`Funding Prospects (${prospects.length})`} items={prospects}
            empty={filteredEmpty
              ? "No funding prospects match the current display filter."
              : effectiveTriageOnly
              ? "No funding prospects were marked for the LLM-triaged view."
              : "No matching historical records were surfaced from the sources searched."}
            render={item => <FundingProspectCard key={item.id} item={item}
              surfaces={fundingSurfacesFor(item, report.application_surfaces)}
              savedItem={fundingSavedItemFor("prospect", item.id, savedItems)} onSaved={refreshSaved} />} />
        </div>}
    </div>
  );
}

// inc 280 (stage 2): THEORY → the Discover workspace as the "Funding" tab (outward discovery — finding grants to
// pursue, alongside Search/Feed/Journals). Render unchanged (reads ctx.selectedPaper).
registerWorkspaceTab(
  { id: "discover" },
  { id: "funding", label: "Funding", order: 40, hideInReadOnly: true, render: (ctx) => <FundingDiscoveryPanel ctx={ctx} /> },
);
