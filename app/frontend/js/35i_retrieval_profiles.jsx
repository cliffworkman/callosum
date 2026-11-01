// Retrieval model: which embedding profile ranks Ask's evidence. Shows each profile's exact model + revision and its
// index coverage over this library's passages; a profile can be selected only once its index is complete. Citation
// verification always stays on the baseline (named here so a switch is never mistaken for a re-calibration).
// inc 620: the refresh loop lives in LibraryModelsSection (35j), shared with the modernization panel, and keeps
// running through every ongoing index state -- including inc 616's waiting_disk (INDEX_RUN_ACTIVE_STATES, 04f).
function RetrievalProfileSettings({ state, error: loadError, onState, onReload }) {
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const error = actionError || loadError;
  const ACTIVE = INDEX_RUN_ACTIVE_STATES;

  const act = async (key, action) => {
    setActionError("");
    const r = action === "build" ? await apiPost(`/embedding-profiles/${key}/index`, {})
                                 : await apiPost(`/embedding-profiles/${key}/index/${action}`, {});
    if (!r.ok) setActionError(r.error || "Couldn't change the index build.");
    onReload();
  };
  const select = async (key) => {
    setBusy(true); setActionError("");
    const r = await apiPut("/embedding-profiles/active", { key });
    setBusy(false);
    if (r.ok) onState(r.data); else setActionError(r.error || "Couldn't switch the retrieval model.");
    onReload();
  };

  if (!state) return <div className="retrieval-profiles"><p className="eyebrow">Retrieval model</p>{error && <p role="alert" className="settings-sub">{error}</p>}</div>;
  return (
    <div className="retrieval-profiles">
      <p className="eyebrow">Retrieval model</p>
      <p className="settings-sub">Chooses which local embedding model ranks passages for Ask. Citation verification always uses {state.verification_model} and its calibrated thresholds, whichever model retrieves. Switching never changes your library.</p>
      {/* inc 618: Automatic uses Arctic S only while its index covers every passage, otherwise MiniLM. */}
      <label className="settings-subsection">
        <input type="radio" name="retrieval-profile" checked={state.preference === "automatic"} disabled={busy}
          onChange={() => select("automatic")} />{" "}
        <b>Automatic</b> <span className="settings-sub">Arctic S once its index is complete; MiniLM until then.</span>
      </label>
      <p role={state.ask_blocked ? "alert" : "status"} className="settings-sub">{state.explanation}</p>
      {state.profiles.map(p => {
        const c = p.coverage;
        const run = p.index_run;
        const chosen = state.preference === p.key;  // the user's explicit choice
        const active = state.active === p.key;  // what Ask uses right now
        const building = run && ACTIVE.includes(run.state);
        return (
          <div key={p.key} className="settings-subsection">
            <label>
              <input type="radio" name="retrieval-profile" checked={chosen} disabled={busy || building || (!chosen && !c.complete && !p.is_baseline)}
                onChange={() => select(p.key)} />{" "}
              <b>{p.label}</b>{active ? " — in use for Ask" : ""}
            </label>
            <span className="settings-sub"><code>{p.model_name}@{p.revision.slice(0, 12)}</code> · {p.qualification}</span>
            <span className="settings-sub">
              Index: {c.indexed_chunks.toLocaleString()} of {c.eligible_chunks.toLocaleString()} passages
              {c.eligible_chunks > 0 ? ` (${(100 * c.indexed_chunks / c.eligible_chunks).toFixed(1)}%)` : ""}{c.complete ? " · complete" : ""}
              {c.papers_without_passage_text > 0 ? ` · ${c.papers_without_passage_text} papers have no full text to index` : ""}
            </span>
            {!p.is_baseline && !c.complete && <span className="settings-sub">{p.label} is not yet available for Ask because indexing is incomplete.</span>}
            {run && <IndexRunStatus run={run} label={p.label} onAction={a => act(p.key, a)} />}
            {!p.is_baseline && !c.complete && !run &&
              <button className="btn btn-ghost" onClick={() => act(p.key, "build")}>{c.indexed_chunks > 0 ? "Resume index build" : "Build index"}</button>}
          </div>
        );
      })}
      {error && <p role="alert" className="settings-sub">{error}</p>}
      <NliProfileSettings />
    </div>
  );
}

// One build's durable state: what is happening, whether recovery is scheduled, and the actions that apply now.
// Technical diagnostics stay behind a disclosure; the message never carries an exception or a path.
function IndexRunStatus({ run, label, onAction }) {
  const working = INDEX_RUN_ACTIVE_STATES.includes(run.state);
  const names = { pause: "Pause", resume: "Resume", cancel: "Cancel" };
  return (
    <div className="index-run">
      {working && <ProgressBar label={`Building ${label} index`} managedBy="backend-job"
        progress={{ current: run.indexed_chunks, total: Math.max(1, run.eligible_chunks), label: run.message }} />}
      <p role={run.state === "failed" ? "alert" : "status"} className="settings-sub">{run.message}</p>
      {(run.attempts > 1 || run.failures_without_progress > 0) &&
        <p className="settings-sub">Attempts: {run.attempts}{run.failures_without_progress > 0 ? ` · ${run.failures_without_progress} without progress` : ""}{run.auto_retry_scheduled ? " · automatic retry scheduled" : ""}</p>}
      {run.actions.map(a => <button key={a} className="btn btn-ghost" onClick={() => onAction(a)}>{names[a]}</button>)}
      {run.diagnostic && <details className="settings-sub"><summary>Technical details</summary><code>{run.diagnostic}</code></details>}
    </div>
  );
}

// Verification NLI model: which local cross-encoder scores synthesis citation support. Selecting a non-baseline model
// verifies its pinned checkpoint first; thresholds are never re-tuned per model, and the copy says so.
function NliProfileSettings() {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api("/verification-nli-profiles").then(r => r.ok ? setState(r.data) : setError(r.error || "Couldn't load verification models.")); }, []);
  const select = async (key) => {
    setBusy(true); setError("");
    // Loading + verifying a checkpoint is local model work: one Status row, named as Local AI (invariant #5).
    const statusId = _startClientStatus({ label: "Verifying NLI model checkpoint", nav: { workspace: "settings" }, computeKind: "Local AI" });
    const r = await apiPut("/verification-nli-profiles/active", { key });
    _finishClientStatus(statusId, r.ok, r.ok ? null : r.error);
    setBusy(false);
    if (r.ok) setState(r.data); else setError(r.error || "Couldn't switch the verification model.");
  };
  if (!state) return error ? <p role="alert" className="settings-sub">{error}</p> : null;
  return (
    <div className="settings-subsection">
      <p className="eyebrow">Verification model (NLI)</p>
      <p className="settings-sub">Scores whether each cited passage supports or contradicts a synthesis claim. The support and contradiction thresholds were calibrated on {state.thresholds_calibrated_on} and are used unchanged for every model. Other stance features keep the baseline.</p>
      {/* inc 619: Automatic uses DeBERTa when it is enabled, verified and fits in memory; otherwise MiniLM2. */}
      <label>
        <input type="radio" name="nli-profile" checked={state.preference === "automatic"} disabled={busy} onChange={() => select("automatic")} />{" "}
        <b>Automatic</b> <span className="settings-sub">DeBERTa when it is ready and fits in memory; MiniLM2 otherwise.</span>
      </label>
      <p role={state.synthesis_blocked ? "alert" : "status"} className="settings-sub">{state.explanation}</p>
      {state.profiles.map(p => (
        <div key={p.key}>
          <label>
            <input type="radio" name="nli-profile" checked={state.preference === p.key} disabled={busy} onChange={() => select(p.key)} />{" "}
            <b>{p.label}</b>{state.active === p.key ? " — used for the next synthesis" : ""}
          </label>
          <span className="settings-sub"><code>{p.model_name}@{p.revision.slice(0, 12)}</code> · {p.qualification}</span>
        </div>
      ))}
      {busy && <ProgressBar label="Verifying the model checkpoint…" managedBy="tracked-request" />}
      {error && <p role="alert" className="settings-sub">{error}</p>}
    </div>
  );
}
