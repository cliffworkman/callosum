// Retrieval model: which embedding profile ranks Ask's evidence. Shows each profile's exact model + revision and its
// index coverage over this library's passages; a profile can be selected only once its index is complete. Citation
// verification always stays on the baseline (named here so a switch is never mistaken for a re-calibration).
function RetrievalProfileSettings() {
  const [state, setState] = useState(null);
  const [job, setJob] = useState(null);  // {job_id, status, progress, summary, detail}
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api("/embedding-profiles").then(r => {
    if (!r.ok) { setError(r.error || "Couldn't load retrieval models."); return; }
    setState(r.data);
    if (r.data.index_job_id && !job) poll(r.data.index_job_id);
  });
  useEffect(() => { load(); }, []);

  const poll = (jobId) => api(`/embedding-profiles/index/${jobId}`).then(r => {
    if (!r.ok) { setJob({ status: "error", detail: r.error }); return; }
    setJob(r.data);
    if (r.data.status === "done" || r.data.status === "error") load();
    else setTimeout(() => poll(jobId), 1500);
  });

  const build = async (key) => {
    setError("");
    const r = await apiPost(`/embedding-profiles/${key}/index`, {});
    if (!r.ok) { setError(r.error || "Couldn't start the index build."); return; }
    setJob(r.data); poll(r.data.job_id);
  };
  const cancel = () => job && apiPost(`/embedding-profiles/index/${job.job_id}/cancel`, {});
  const select = async (key) => {
    setBusy(true); setError("");
    const r = await apiPut("/embedding-profiles/active", { key });
    setBusy(false);
    if (r.ok) setState(r.data); else setError(r.error || "Couldn't switch the retrieval model.");
  };

  if (!state) return <div className="retrieval-profiles"><p className="eyebrow">Retrieval model</p>{error && <p role="alert" className="settings-sub">{error}</p>}</div>;
  const running = job && (job.status === "pending" || job.status === "running");
  return (
    <div className="retrieval-profiles">
      <p className="eyebrow">Retrieval model</p>
      <p className="settings-sub">Chooses which local embedding model ranks passages for Ask. Citation verification always uses {state.verification_model} and its calibrated thresholds, whichever model retrieves. Switching never changes your library.</p>
      {state.profiles.map(p => {
        const c = p.coverage;
        const active = state.active === p.key;
        return (
          <div key={p.key} className="settings-subsection">
            <label>
              <input type="radio" name="retrieval-profile" checked={active} disabled={busy || running || (!active && !c.complete && !p.is_baseline)}
                onChange={() => select(p.key)} />{" "}
              <b>{p.label}</b>{active ? " — active" : ""}
            </label>
            <span className="settings-sub"><code>{p.model_name}@{p.revision.slice(0, 12)}</code> · {p.qualification}</span>
            <span className="settings-sub">
              Index: {c.indexed_chunks.toLocaleString()} of {c.eligible_chunks.toLocaleString()} passages{c.complete ? " (complete)" : ""}
              {c.papers_without_passage_text > 0 ? ` · ${c.papers_without_passage_text} papers have no full text to index` : ""}
            </span>
            {!p.is_baseline && !c.complete && !running &&
              <button className="btn btn-ghost" onClick={() => build(p.key)}>{c.indexed_chunks > 0 ? "Resume index build" : "Build index"}</button>}
          </div>
        );
      })}
      {running && <>
        <ProgressBar label="Building retrieval index" progress={job.progress} managedBy="backend-job" />
        <button className="btn btn-ghost" onClick={cancel}>Stop after the current paper</button>
      </>}
      {job && job.status === "done" && job.summary &&
        <p role="status" className="settings-sub">{job.summary.cancelled ? "Stopped" : "Finished"}: indexed {job.summary.chunks_indexed.toLocaleString()} passages in {job.summary.papers_indexed} papers. Progress is kept; a later build resumes.</p>}
      {job && job.status === "error" && <p role="alert" className="settings-sub">Index build failed: {job.detail}</p>}
      {error && <p role="alert" className="settings-sub">{error}</p>}
      <NliProfileSettings />
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
      {state.profiles.map(p => (
        <div key={p.key}>
          <label>
            <input type="radio" name="nli-profile" checked={state.active === p.key} disabled={busy} onChange={() => select(p.key)} />{" "}
            <b>{p.label}</b>{state.active === p.key ? " — active" : ""}
          </label>
          <span className="settings-sub"><code>{p.model_name}@{p.revision.slice(0, 12)}</code> · {p.qualification}</span>
        </div>
      ))}
      {busy && <ProgressBar label="Verifying the model checkpoint…" managedBy="tracked-request" />}
      {error && <p role="alert" className="settings-sub">{error}</p>}
    </div>
  );
}
