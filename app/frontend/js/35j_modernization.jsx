// Inc 620: Settings → Library behavior → Library modernization, plus the one refresh loop shared with the retrieval
// panel. GET /modernization and GET /embedding-profiles are read together on each tick; modernizationPollDelay
// (04f) picks the next tick from the stored states, so waits (disk, memory, network) keep refreshing. Settled states
// keep a slow idle tick (inc 621) that reads only GET /modernization and does the full read when it sees a change, so a
// mounted panel notices an import or another window. Nothing here loads a model or starts work: Pause and
// Resume call the existing durable endpoints and never change a retrieval or verifier choice.
function LibraryModelsSection() {
  const [modernization, setModernization] = useState(null);
  const [profiles, setProfiles] = useState(null);
  const [error, setError] = useState("");
  const timer = useRef(null);
  const alive = useRef(true);

  const seen = useRef(null);

  const load = useCallback(async (idle) => {
    const m = await api("/modernization");
    if (!alive.current) return;
    const signature = m.ok ? modernizationSignature(m.data) : null;
    let delay = MODERNIZATION_IDLE_MS;  // an idle tick that saw no change: the full read below is not needed
    if (idle !== true || signature === null || signature !== seen.current) {
      const p = await api("/embedding-profiles");
      if (!alive.current) return;
      seen.current = signature;
      if (m.ok) setModernization(m.data);
      if (p.ok) setProfiles(p.data); else setError(p.error || "Couldn't load retrieval models.");
      delay = modernizationPollDelay(m.ok ? m.data : null, p.ok ? p.data : null);
    }
    clearTimeout(timer.current);
    if (delay != null) timer.current = setTimeout(() => load(delay === MODERNIZATION_IDLE_MS), delay);
  }, []);
  useEffect(() => {
    alive.current = true;
    load();
    return () => { alive.current = false; clearTimeout(timer.current); };
  }, [load]);

  return (
    <React.Fragment>
      <div className="settings-section" id="modernization">
        <ModernizationPanel state={modernization} profiles={profiles} onChanged={setModernization} onReload={load} />
      </div>
      <div className="settings-section" id="retrieval-model">
        <RetrievalProfileSettings state={profiles} error={error} onState={setProfiles} onReload={load} />
      </div>
    </React.Fragment>
  );
}

function ModernizationPanel({ state, profiles, onChanged, onReload }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!state || !state.summary) return <div><p className="eyebrow">Library modernization</p></div>;
  const s = state.summary;
  const labelOf = (key) => ((profiles && profiles.profiles) || []).find(p => p.key === key)?.label || key;
  const toggle = async (action) => {
    if (busy) return;  // one request at a time; the endpoints are idempotent anyway
    setBusy(true); setError("");
    const r = await apiPost(`/modernization/${action}`, {});
    setBusy(false);
    if (r.ok) onChanged(r.data); else setError(r.error || "Couldn't change background modernization.");
    onReload();
  };
  const retrieval = state.effective_retrieval;
  const verifier = state.verifier;
  return (
    <div>
      <p className="eyebrow">Library modernization</p>
      <p className="settings-sub">
        Callosum is upgrading local search for this library in the background: it classifies the scientific sources
        behind your existing passages and builds an Arctic S retrieval index. Your PDFs are not re-extracted or
        re-chunked, and the library stays usable. Completed work is saved as it goes and resumes in later sessions.
      </p>
      <p role={s.state === "action_required" ? "alert" : "status"} className="settings-sub"><b>{s.headline}</b></p>
      {s.progress && s.state === "working" &&
        <ProgressBar label={s.headline} progress={{ ...s.progress, eta_seconds: null }} managedBy="status-popover" />}
      {s.attention.map(text => <p key={text} role="alert" className="settings-sub">{text}</p>)}
      {["model", "classification", "indexing"].filter(k => !s.attention.includes(s.notes[k])).map(k =>
        <p key={k} className="settings-sub">{s.notes[k]}</p>)}
      {retrieval &&
        <p role={retrieval.ask_blocked ? "alert" : "status"} className="settings-sub">
          Ask retrieval right now: <b>{labelOf(retrieval.profile)}</b>. {retrieval.explanation}
        </p>}
      {verifier &&
        <p className="settings-sub">Citation verification right now: <b>{verifier.effective_label}</b>. {verifier.explanation}</p>}
      {state.enabled && (state.intent === "paused"
        ? <button className="btn btn-ghost" disabled={busy} onClick={() => toggle("resume")}>Resume modernization</button>
        : <button className="btn btn-ghost" disabled={busy} onClick={() => toggle("pause")}>Pause modernization</button>)}
      {state.enabled &&
        <p className="settings-sub">Pausing stops background work only. It does not change the retrieval or verification model you have chosen.</p>}
      {error && <p role="alert" className="settings-sub">{error}</p>}
    </div>
  );
}
