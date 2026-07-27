// WIP deterministic checks (statcheck today; inc 403/404 add funding-discovery/journal-fit runs onto the same
// tool_runs/wip_tool_runs list). WipChecks itself is presentational (given data via props) so it can be mounted
// from two places: WipDetails' own "Checks" tab (10f_wip.jsx, the WIP tab's own home) and, as of inc 402, the
// Methods panel's "Statistics" section (self-fetching wrapper below) -- both read/write the same manuscript-scoped
// data, kept in sync via the shared wip.refresh counter (ctx.wipRefresh / externalRefresh).
function WipChecks({ manuscriptId, snapshots, checks, onReload }) {
  const [creating, setCreating] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const createCheckpoint = async () => {
    setCreating(true);
    setError("");
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/snapshots`, {});
    setCreating(false);
    if (result.ok) onReload();
    else setError(result.error || "Could not create checkpoint.");
  };
  const runStatcheck = async () => {
    setRunning(true);
    setError("");
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/checks/statcheck`, {});
    setRunning(false);
    if (result.ok) onReload();
    else setError(result.error || "Statcheck could not run.");
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
        <button className="axis-btn" disabled={running} onClick={runStatcheck}>
          {running ? "Running…" : "Run statcheck"}
        </button>
      </div>
    </div>
    {running && <ProgressBar />}
    {error && <div className="wip-root-error">{error}</div>}
    {(checks.runs || []).length === 0 ? <p className="axis-hint">
      No checks run yet. An empty history is not a clean manuscript.
    </p> : checks.runs.map(run => <div className="wip-tool-run" key={run.id}>
      <div className="wip-tool-run-head">
        <strong>{run.tool_id}</strong>
        <span className={`wip-identity-${run.validity}`}>{run.validity.replace(/-/g, " ")}</span>
        <time>{wipWhen(run.executed_at)}</time>
      </div>
      <p>{run.result_summary}</p>
      <small>v{run.tool_version} · snapshot {run.snapshot_id} · {run.coverage}</small>
      {(run.findings || []).map(finding => <div className="wip-finding-row" key={finding.id}>
        <div>
          <strong>Candidate</strong> <span>{finding.summary}</span>
          <button className="btn-link" onClick={async () => {
            const result = await apiPost(
              `/wip/manuscripts/${manuscriptId}/files/${finding.file_id}/open`, {},
            );
            if (!result.ok) setError(result.error || "Could not open the source file.");
          }}>Open source file</button>
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
