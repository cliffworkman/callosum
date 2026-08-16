// WIP deterministic checks (statcheck + transparency + LMM/Bayesian reporting; inc 403/404 add funding/journal receipts).
// WipChecks itself is presentational (given data via props) so it can be mounted
// from two places: WipDetails' own "Checks" tab (10f_wip.jsx, the WIP tab's own home) and, as of inc 402, the
// Methods panel's "Statistics" section (self-fetching wrapper below) -- both read/write the same manuscript-scoped
// data, kept in sync via the shared wip.refresh counter (ctx.wipRefresh / externalRefresh).
function WipChecks({ manuscriptId, snapshots, checks, onReload }) {
  const readOnly = React.useContext(AppReadOnly);
  const [creating, setCreating] = useState(false);
  const [runningTool, setRunningTool] = useState("");
  const [error, setError] = useState("");
  const running = runningTool !== "";
  const savedDemo = isDemoMode();
  const createCheckpoint = async () => {
    setCreating(true);
    setError("");
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/snapshots`, {});
    setCreating(false);
    if (result.ok) onReload();
    else setError(result.error || "Could not create checkpoint.");
  };
  const runCheck = async (toolId, failureMessage) => {
    setRunningTool(toolId);
    setError("");
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/checks/${toolId}`, {});
    setRunningTool("");
    if (result.ok) onReload();
    else setError(result.error || failureMessage);
  };
  const openSourceFile = async fileId => {
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/files/${fileId}/open`, {});
    if (!result.ok) setError(result.error || "Could not open the source file.");
  };
  return <section className="wip-work-view">
    <div className="wip-check-head">
      <div>
        <h3>Deterministic checks</h3>
        <p>Each run names its exact checkpoint, tool version, coverage, and reviewable findings.</p>
      </div>
      <div className="wip-check-actions">
        <button className="btn-ghost" disabled={creating || readOnly} onClick={createCheckpoint}
          title={savedDemo ? "Checkpoint creation requires the local app." : undefined}>
          {creating ? "Creating…" : "Create checkpoint"}
        </button>
        <button className="axis-btn" disabled={running || readOnly} title={savedDemo ? "Rerunning checks requires the local app." : undefined}
          onClick={() => runCheck("statcheck", "Statcheck could not run.")}>
          {runningTool === "statcheck" ? "Running…" : "Run statcheck"}
        </button>
        <button className="axis-btn" disabled={running || readOnly} title={savedDemo ? "Rerunning checks requires the local app." : undefined}
          onClick={() => runCheck("transparency", "Transparency check could not run.")}>
          {runningTool === "transparency" ? "Checking…" : "Check transparency"}
        </button>
        <button className="axis-btn" disabled={running || readOnly} title={savedDemo ? "Rerunning checks requires the local app." : undefined}
          onClick={() => runCheck("lmm", "Mixed-model reporting audit could not run.")}>
          {runningTool === "lmm" ? "Auditing…" : "Audit LMM reporting"}
        </button>
        <button className="axis-btn" disabled={running || readOnly} title={savedDemo ? "Rerunning checks requires the local app." : undefined}
          onClick={() => runCheck("bayes", "Bayesian reporting audit could not run.")}>
          {runningTool === "bayes" ? "Auditing…" : "Audit Bayesian reporting"}
        </button>
        <button className="axis-btn" disabled={running || readOnly} title={savedDemo ? "Rerunning checks requires the local app." : undefined}
          onClick={() => runCheck("meta-analysis", "Meta-analysis reporting audit could not run.")}>
          {runningTool === "meta-analysis" ? "Auditing…" : "Audit meta-analysis reporting"}
        </button>
      </div>
    </div>
    {running && <ProgressBar />}
    {error && <div className="wip-root-error">{error}</div>}
    {(checks.runs || []).length === 0 ? <p className="axis-hint">
      No checks run yet. An empty history is not a clean manuscript.
    </p> : checks.runs.map(run => <div className="wip-tool-run" key={run.id}>
      <div className="wip-tool-run-head">
        <strong>{wipToolLabel(run.tool_id)}</strong>
        <span className={`wip-identity-${run.validity}`}>{run.validity.replace(/-/g, " ")}</span>
        <time>{wipWhen(run.executed_at)}</time>
      </div>
      <p>{run.result_summary}</p>
      <small>v{run.tool_version} · snapshot {run.snapshot_id} · {run.coverage}</small>
      <div><button className="btn-link" disabled={readOnly}
        title={savedDemo ? "The synthetic manuscript file is local-app only; saved quotations and detector details remain below." : undefined}
        onClick={() => openSourceFile(run.file_id)}>Open source file</button></div>
      {run.tool_id === "transparency" && <WipTransparencyResult run={run}
        onOpenSource={() => openSourceFile(run.file_id)} />}
      {run.tool_id === "lmm" && <WipLmmResult run={run}
        onOpenSource={() => openSourceFile(run.file_id)} />}
      {run.tool_id === "bayes" && <WipBayesResult run={run}
        onOpenSource={() => openSourceFile(run.file_id)} />}
      {run.tool_id === "meta-analysis" && <WipMetaAnalysisResult run={run}
        onOpenSource={() => openSourceFile(run.file_id)} />}
      {(run.findings || []).filter(finding => finding.kind === "candidate").map(finding => <div className="wip-finding-row" key={finding.id}>
        <div>
          <strong>Candidate</strong> <span>{finding.summary}</span>
        </div>
        <select value={finding.disposition || "open"} disabled={readOnly} title={savedDemo ? "Review changes require the local app." : undefined} onChange={async event => {
          const result = await apiPatch(`/wip/findings/${finding.id}`, { disposition: event.target.value });
          if (result.ok) onReload();
          else setError(result.error || "Could not update the finding.");
        }}>
          {["open", "acknowledged", "resolved", "dismissed", "false-positive", "deferred", "superseded"]
            .map(value => <option key={value} value={value}>{value.replace(/-/g, " ")}</option>)}
        </select>
        {finding.quote && <blockquote>{finding.quote}</blockquote>}
        {finding.context && <p>{finding.context}</p>}
        {finding.finding_type.startsWith("statcheck-") &&
          <small>Reported {finding.details_json.reported_p}; recomputed p = {finding.details_json.computed_p}</small>}
      </div>)}
    </div>)}
    <div className="wip-checkpoint-heading">
      <h3>Content checkpoints</h3>
      <p>Exact local hashes and bounded context; never a copy of the manuscript file.</p>
    </div>
    {snapshots.length === 0 ? <p className="axis-hint">No content checkpoints yet.</p> :
      snapshots.map(snapshot => <div className="wip-checkpoint-row" key={snapshot.id}>
        <div>
          <strong>{snapshot.reason.replace(/-/g, " ")}</strong>
          {snapshot.reason_detail && <span>{snapshot.reason_detail}</span>}
          <small>{snapshot.extraction_provider} {snapshot.extraction_version} · {snapshot.extracted_char_count.toLocaleString()} extracted characters</small>
        </div>
        <div className="wip-checkpoint-state">
          <span className={`wip-identity-${snapshot.identity_status}`}>{snapshot.identity_status.replace(/-/g, " ")}</span>
          <time>{wipWhen(snapshot.created_at)}</time>
        </div>
        <p>{snapshot.status_detail}</p>
      </div>)}
    <p className="axis-hint">No tool result is implied by a content checkpoint. Deterministic checks will appear here after they run.</p>
  </section>;
}

function wipToolLabel(toolId) {
  if (toolId === "transparency") return "Transparency";
  if (toolId === "lmm") return "Mixed-model reporting";
  if (toolId === "bayes") return "Bayesian reporting";
  if (toolId === "meta-analysis") return "Meta-analysis reporting";
  return "Statcheck";
}

function WipTransparencyResult({ run, onOpenSource }) {
  const checks = (run.structured_result_json || {}).checks || [];
  if (!checks.length) return null;
  return <div className="wip-transparency-result">
    <TransparencyChecklist checks={checks} onOpen={onOpenSource} showRegistrationReferences={false} />
    <div className="statcheck-caveat">
      Detected rows are retained as evidence-backed facts. “Not detected” rows never become negative findings or
      claims about the manuscript.
    </div>
  </div>;
}

function WipLmmResult({ run, onOpenSource }) {
  const result = run.structured_result_json || {};
  if (!result.is_lmm) return <div className="statcheck-caveat">
    No linear mixed-model language was detected, so the seven-item reporting checklist was not applied. This does
    not prove the manuscript uses no mixed model.
  </div>;
  return <div className="wip-lmm-result">
    <LmmChecklist checks={result.checks || []} onOpen={onOpenSource} />
    <div className="statcheck-caveat">
      Each “not found” row is retained as a reviewable candidate, not a claim that reporting is absent. Review
      dispositions are available in the WIP Checks tab.
    </div>
  </div>;
}

function WipBayesResult({ run, onOpenSource }) {
  const result = run.structured_result_json || {};
  const completeness = result.completeness || {};
  if (!completeness.is_bayesian) return <div className="statcheck-caveat">
    Bayesian analysis language was not detected, so the reporting checklist was not applied and no review
    candidates were created. This does not prove the manuscript contains no Bayesian analysis.
  </div>;
  return <div className="wip-bayes-result">
    {result.checked === 0
      ? <div className="tag-suggest-empty">No supported inline Bayes factors were available to recompute.</div>
      : <>
          <div className="statcheck-summary">{result.checked} checked · {result.not_reproduced} couldn't reproduce under the default prior</div>
          <div className="statcheck-list">
            {(result.results || []).map((item, index) => <div key={index}
              className={"statcheck-item" + (item.consistency !== "reproduced" ? " flagged-row" : "")}>
              <button type="button" className="statcheck-item-main" onClick={onOpenSource}>
                <EvidenceQuote text={item.raw} match={item.raw} label="Reported result"
                  precision={item.coordinate_precision} hasSourcePage={item.page != null}
                  className="statcheck-context" maxChars={220} />
                <span className="statcheck-computed">reported BF₁₀ = {item.reported_bf10} · recomputed {reBfLabel(item)}</span>
                <span className={"cite-status " + (item.consistency === "reproduced" ? "verified" : "flagged")}>
                  {item.consistency === "reproduced" ? "reproduces" : "couldn't reproduce"}
                </span>
              </button>
            </div>)}
          </div>
        </>}
    <div className="statcheck-caveat">
      Recomputed only under the displayed default-prior assumptions. A mismatch commonly reflects a different
      prior or design interpretation and is a review prompt, never an error verdict.
    </div>
    <BayesChecklist items={completeness.items || []} onOpen={onOpenSource} />
    {(completeness.advisories || []).length > 0 &&
      <BayesAdvisories notes={completeness.advisories} onOpen={onOpenSource} />}
    <div className="statcheck-caveat">
      Mismatches, reporting gaps, coherence flags, and advisories are retained as reviewable <b>info</b> candidates.
      Their dispositions are available in the WIP Checks tab; none is a score, verdict, or accusation.
    </div>
  </div>;
}

function WipMetaAnalysisResult({ run, onOpenSource }) {
  const result = run.structured_result_json || {};
  if (!result.is_meta_analysis) return <div className="statcheck-caveat">
    Meta-analysis language was not detected, so the seven-item reporting checklist was not applied and no review
    candidates were created. This does not prove the manuscript contains no meta-analysis.
  </div>;
  return <div className="wip-meta-analysis-result">
    <MetaChecklist checks={result.checks || []} onOpen={onOpenSource} />
    <div className="statcheck-caveat">
      Each “not found” row is retained as a reviewable <b>info</b> candidate, never proof of omission or a claim that
      reporting is absent. Review dispositions are available in the WIP Checks tab; none is a score, verdict, or
      accusation.
    </div>
  </div>;
}

// Shared self-fetching shell for WIP checklist tools. It reads the same stored run as the manuscript's own Checks
// tab while keeping Library-wide paper batches and paper-only workflows out of manuscript context.
function WipChecklistSection({ manuscript, ctx, toolId, label, labels, emptyText, selectText, renderResult }) {
  const manuscriptId = manuscript ? manuscript.id : null;
  const [checks, setChecks] = useState({ tools: [], runs: [] });
  const [state, setState] = useState({ status: "idle" });
  useEffect(() => {
    setState({ status: "idle" });
    if (manuscriptId == null) { setChecks({ tools: [], runs: [] }); return undefined; }
    let live = true;
    api(`/wip/manuscripts/${manuscriptId}/checks`).then(result => {
      if (live && result.ok) setChecks(result.data || { tools: [], runs: [] });
    });
    return () => { live = false; };
  }, [manuscriptId, ctx.wipRefresh]);
  const start = async () => {
    setState({ status: "running" });
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/checks/${toolId}`, {});
    if (!result.ok) return setState({ status: "error", error: result.error });
    setChecks(current => ({ ...current, runs: [result.data, ...(current.runs || [])] }));
    setState({ status: "done" });
    if (ctx.onReloadWip) ctx.onReloadWip();
  };
  const openSource = async fileId => {
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/files/${fileId}/open`, {});
    if (!result.ok) setState({ status: "error", error: result.error || "Could not open the source file." });
  };
  if (manuscriptId == null) return <div className="axis-hint">{selectText}</div>;
  const latest = (checks.runs || []).find(run => run.tool_id === toolId);
  return <div className="detail-statcheck">
    <span className="detail-cite-label">{manuscript.display_title || manuscript.derived_title || "This manuscript"}</span>
    <div className="settings-actions">
      <button className="btn btn-primary" disabled={state.status === "running" || isDemoMode()} onClick={start}
        title={isDemoMode() ? "Rerunning checks requires the local app." : undefined}>
        {state.status === "running" ? labels.running : latest ? labels.again : labels.first}
      </button>
    </div>
    {state.status === "running" && <ProgressBar label={labels.progress} />}
    {state.status === "error" && <div className="axis-err">{labels.error}: {state.error}</div>}
    {!latest && state.status !== "running" && <p className="axis-hint">
      {emptyText}
    </p>}
    {latest && <div className="wip-tool-run">
      <div className="wip-tool-run-head">
        <strong>{label}</strong>
        <span className={`wip-identity-${latest.validity}`}>{latest.validity.replace(/-/g, " ")}</span>
        <time>{wipWhen(latest.executed_at)}</time>
      </div>
      <p>{latest.result_summary}</p>
      <small>v{latest.tool_version} · snapshot {latest.snapshot_id} · {latest.coverage}</small>
      <div><button className="btn-link" onClick={() => openSource(latest.file_id)}>Open source file</button></div>
      {renderResult(latest, () => openSource(latest.file_id))}
    </div>}
  </div>;
}

function WipTransparencySection({ manuscript, ctx }) {
  return <WipChecklistSection manuscript={manuscript} ctx={ctx} toolId="transparency" label="Transparency"
    labels={{ first: "Check disclosures", again: "Check disclosures again", running: "Checking…",
      progress: "Checking manuscript disclosures…", error: "Transparency check failed" }}
    emptyText="No transparency check run yet. An empty history is not a clean manuscript."
    selectText="Select a WIP manuscript to check its disclosures."
    renderResult={(run, openSource) => <WipTransparencyResult run={run} onOpenSource={openSource} />} />;
}

function WipLmmSection({ manuscript, ctx }) {
  return <WipChecklistSection manuscript={manuscript} ctx={ctx} toolId="lmm" label="Mixed-model reporting"
    labels={{ first: "Audit reporting", again: "Audit reporting again", running: "Auditing…",
      progress: "Auditing mixed-model reporting…", error: "Mixed-model reporting audit failed" }}
    emptyText="No mixed-model reporting audit yet. An empty history says nothing about the manuscript."
    selectText="Select a WIP manuscript to audit its mixed-model reporting."
    renderResult={(run, openSource) => <WipLmmResult run={run} onOpenSource={openSource} />} />;
}

function WipBayesSection({ manuscript, ctx }) {
  return <WipChecklistSection manuscript={manuscript} ctx={ctx} toolId="bayes" label="Bayesian reporting"
    labels={{ first: "Audit reporting", again: "Audit reporting again", running: "Auditing…",
      progress: "Auditing Bayesian reporting…", error: "Bayesian reporting audit failed" }}
    emptyText="No Bayesian reporting audit yet. An empty history says nothing about the manuscript."
    selectText="Select a WIP manuscript to audit its Bayesian reporting."
    renderResult={(run, openSource) => <WipBayesResult run={run} onOpenSource={openSource} />} />;
}

function WipMetaAnalysisSection({ manuscript, ctx }) {
  return <WipChecklistSection manuscript={manuscript} ctx={ctx} toolId="meta-analysis"
    label="Meta-analysis reporting"
    labels={{ first: "Audit reporting", again: "Audit reporting again", running: "Auditing…",
      progress: "Auditing meta-analysis reporting…", error: "Meta-analysis reporting audit failed" }}
    emptyText="No meta-analysis reporting audit yet. An empty history says nothing about the manuscript."
    selectText="Select a WIP manuscript to audit its meta-analysis reporting."
    renderResult={(run, openSource) => <WipMetaAnalysisResult run={run} onOpenSource={openSource} />} />;
}

// inc 402: the Methods panel's "Statistics" section, for a WIP manuscript instead of a Library paper. Self-fetches
// (mirroring StatcheckPaper's shape) rather than depending on WipDetails' own fetch orchestration, so the two
// mount points have independent, resilient data lifecycles; ctx.wipRefresh (the shared wip.refresh counter) keeps
// them in sync when a run/disposition change happens on either side.
function WipStatcheckSection({ manuscript, ctx }) {
  const manuscriptId = manuscript ? manuscript.id : null;
  const [snapshots, setSnapshots] = useState([]);
  const [checks, setChecks] = useState({ tools: [], runs: [] });
  useEffect(() => {
    if (manuscriptId == null) { setSnapshots([]); setChecks({ tools: [], runs: [] }); return undefined; }
    let live = true;
    Promise.all([
      api(`/wip/manuscripts/${manuscriptId}/snapshots`),
      api(`/wip/manuscripts/${manuscriptId}/checks`),
    ]).then(([snapshotResult, checkResult]) => {
      if (!live) return;
      if (snapshotResult.ok) setSnapshots(snapshotResult.data || []);
      if (checkResult.ok) setChecks(checkResult.data || { tools: [], runs: [] });
    });
    return () => { live = false; };
  }, [manuscriptId, ctx.wipRefresh]);
  if (manuscriptId == null) return <div className="axis-hint">Select a WIP manuscript to check its statistics.</div>;
  return <WipChecks manuscriptId={manuscriptId} snapshots={snapshots} checks={checks}
    onReload={() => { if (ctx.onReloadWip) ctx.onReloadWip(); }} />;
}
