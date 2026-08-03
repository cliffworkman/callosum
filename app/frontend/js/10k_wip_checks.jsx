// WIP deterministic checks (statcheck + transparency; inc 403/404 add funding-discovery/journal-fit receipts).
// WipChecks itself is presentational (given data via props) so it can be mounted
// from two places: WipDetails' own "Checks" tab (10f_wip.jsx, the WIP tab's own home) and, as of inc 402, the
// Methods panel's "Statistics" section (self-fetching wrapper below) -- both read/write the same manuscript-scoped
// data, kept in sync via the shared wip.refresh counter (ctx.wipRefresh / externalRefresh).
function WipChecks({ manuscriptId, snapshots, checks, onReload }) {
  const [creating, setCreating] = useState(false);
  const [runningTool, setRunningTool] = useState("");
  const [error, setError] = useState("");
  const running = runningTool !== "";
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
        <button className="btn-ghost" disabled={creating} onClick={createCheckpoint}>
          {creating ? "Creating…" : "Create checkpoint"}
        </button>
        <button className="axis-btn" disabled={running}
          onClick={() => runCheck("statcheck", "Statcheck could not run.")}>
          {runningTool === "statcheck" ? "Running…" : "Run statcheck"}
        </button>
        <button className="axis-btn" disabled={running}
          onClick={() => runCheck("transparency", "Transparency check could not run.")}>
          {runningTool === "transparency" ? "Checking…" : "Check transparency"}
        </button>
      </div>
    </div>
    {running && <ProgressBar />}
    {error && <div className="wip-root-error">{error}</div>}
    {(checks.runs || []).length === 0 ? <p className="axis-hint">
      No checks run yet. An empty history is not a clean manuscript.
    </p> : checks.runs.map(run => <div className="wip-tool-run" key={run.id}>
      <div className="wip-tool-run-head">
        <strong>{run.tool_id === "transparency" ? "Transparency" : "Statcheck"}</strong>
        <span className={`wip-identity-${run.validity}`}>{run.validity.replace(/-/g, " ")}</span>
        <time>{wipWhen(run.executed_at)}</time>
      </div>
      <p>{run.result_summary}</p>
      <small>v{run.tool_version} · snapshot {run.snapshot_id} · {run.coverage}</small>
      <div><button className="btn-link" onClick={() => openSourceFile(run.file_id)}>Open source file</button></div>
      {run.tool_id === "transparency" && <WipTransparencyResult run={run}
        onOpenSource={() => openSourceFile(run.file_id)} />}
      {(run.findings || []).filter(finding => finding.kind === "candidate").map(finding => <div className="wip-finding-row" key={finding.id}>
        <div>
          <strong>Candidate</strong> <span>{finding.summary}</span>
        </div>
        <select value={finding.disposition || "open"} onChange={async event => {
          const result = await apiPatch(`/wip/findings/${finding.id}`, { disposition: event.target.value });
          if (result.ok) onReload();
          else setError(result.error || "Could not update the finding.");
        }}>
          {["open", "acknowledged", "resolved", "dismissed", "false-positive", "deferred", "superseded"]
            .map(value => <option key={value} value={value}>{value.replace(/-/g, " ")}</option>)}
        </select>
        <blockquote>{finding.quote}</blockquote>
        <p>{finding.context}</p>
        <small>Reported {finding.details_json.reported_p}; recomputed p = {finding.details_json.computed_p}</small>
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

// The Checklists → Transparency surface for a WIP manuscript. It reads the same stored run as the manuscript's own
// Checks tab, while keeping Library-wide paper checks and registration workflows out of manuscript context.
function WipTransparencySection({ manuscript, ctx }) {
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
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/checks/transparency`, {});
    if (!result.ok) return setState({ status: "error", error: result.error });
    setChecks(current => ({ ...current, runs: [result.data, ...(current.runs || [])] }));
    setState({ status: "done" });
    if (ctx.onReloadWip) ctx.onReloadWip();
  };
  const openSource = async fileId => {
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/files/${fileId}/open`, {});
    if (!result.ok) setState({ status: "error", error: result.error || "Could not open the source file." });
  };
  if (manuscriptId == null) return <div className="axis-hint">Select a WIP manuscript to check its disclosures.</div>;
  const latest = (checks.runs || []).find(run => run.tool_id === "transparency");
  return <div className="detail-statcheck">
    <span className="detail-cite-label">{manuscript.display_title || manuscript.derived_title || "This manuscript"}</span>
    <div className="settings-actions">
      <button className="btn btn-primary" disabled={state.status === "running"} onClick={start}>
        {state.status === "running" ? "Checking…" : latest ? "Check disclosures again" : "Check disclosures"}
      </button>
    </div>
    {state.status === "running" && <ProgressBar label="Checking manuscript disclosures…" />}
    {state.status === "error" && <div className="axis-err">Transparency check failed: {state.error}</div>}
    {!latest && state.status !== "running" && <p className="axis-hint">
      No transparency check run yet. An empty history is not a clean manuscript.
    </p>}
    {latest && <div className="wip-tool-run">
      <div className="wip-tool-run-head">
        <strong>Transparency</strong>
        <span className={`wip-identity-${latest.validity}`}>{latest.validity.replace(/-/g, " ")}</span>
        <time>{wipWhen(latest.executed_at)}</time>
      </div>
      <p>{latest.result_summary}</p>
      <small>v{latest.tool_version} · snapshot {latest.snapshot_id} · {latest.coverage}</small>
      <div><button className="btn-link" onClick={() => openSource(latest.file_id)}>Open source file</button></div>
      <WipTransparencyResult run={latest} onOpenSource={() => openSource(latest.file_id)} />
    </div>}
  </div>;
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
