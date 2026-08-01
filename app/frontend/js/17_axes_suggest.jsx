// Suggest-optimal-axes modal (inc 52). Clusters the library, proposes a diverse set of candidate
// axes that complement the user's existing ones, and lets the user curate (rename + toggle terms)
// and create the ones they like. Async: POST /axes/suggest → poll GET /axes/suggest/{job_id}.

function SuggestCard({ suggestion, onCreated }) {
  const [label, setLabel] = useState(suggestion.label);
  const [terms, setTerms] = useState(() => (suggestion.terms || []).map(t => ({ term: t, selected: true })));
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState(null);

  const toggle = (i) => setTerms(ts => ts.map((t, j) => (j === i ? { ...t, selected: !t.selected } : t)));

  const create = async () => {
    const name = label.trim();
    if (!name) { setErr("Give the axis a name first."); return; }
    const chosen = terms.filter(t => t.selected).map(t => t.term);
    const description = chosen.length ? "Related: " + chosen.join(", ") : null;
    setSaving(true); setErr(null);
    const r = await apiPost("/axes", { label: name, description });
    setSaving(false);
    if (!r.ok) { setErr(r.error); return; }
    setDone(true);
    if (onCreated) onCreated();
  };

  const titles = (suggestion.paper_titles || []).slice(0, 3).join(" · ");
  return (
    <div className={"suggest-item" + (done ? " is-created" : "")}>
      <input className="axis-input suggest-label" value={label} disabled={done}
        onChange={e => setLabel(e.target.value)} placeholder="Axis name" />
      <div className="axis-chips">
        {terms.length === 0 && <span className="axis-hint">No terms — add some after creating.</span>}
        {terms.map((t, i) => (
          <button key={i} className={"term-chip" + (t.selected ? " on" : "")} disabled={done} onClick={() => toggle(i)}>{t.term}</button>
        ))}
      </div>
      <div className="suggest-papers">{suggestion.size} papers{titles ? " · e.g. " + titles : ""}</div>
      {err && <div className="axis-err">{err}</div>}
      <div className="suggest-item-actions">
        {done
          ? <span className="suggest-done">✓ created</span>
          : <button className="axis-btn" disabled={saving || !label.trim()} onClick={create}>{saving ? "Creating…" : "Create axis"}</button>}
      </div>
    </div>
  );
}

function SuggestAxesModal({ onClose }) {
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <SuggestAxesModalBody onClose={onClose} />
      </div>
    </div>
  );
}

// inc 416: bare body split out so the onboarding wizard can embed it without a nested overlay —
// SuggestAxesModal above is now a thin wrapper adding that chrome. Every hook/handler below is unchanged.
function SuggestAxesModalBody({ onClose }) {
  const [state, setState] = useState({ status: "loading", suggestions: [] });
  const [createdCount, setCreatedCount] = useState(0);

  useEffect(() => {
    let live = true;
    let timer = null;
    const poll = (jobId) => {
      api(`/axes/suggest/${jobId}`).then(r => {
        if (!live) return;
        if (!r.ok) { setState({ status: "error", error: r.error, suggestions: [] }); return; }
        const d = r.data;
        if (d.status === "done") setState({ status: "ready", suggestions: d.suggestions || [] });
        else if (d.status === "error") setState({ status: "error", error: d.detail || "Suggestion failed.", suggestions: [] });
        else timer = setTimeout(() => poll(jobId), 1200);
      });
    };
    apiPost("/axes/suggest", {}).then(r => {
      if (!live) return;
      if (!r.ok) { setState({ status: "error", error: r.error, suggestions: [] }); return; }
      poll(r.data.job_id);
    });
    return () => { live = false; if (timer) clearTimeout(timer); };
  }, []);

  return (
    <>
      <div className="axis-modal-head">
        <span>Suggested axes</span>
        <button className="axis-link" onClick={onClose}>×</button>
      </div>
      <div className="axis-modal-note">
        Themes discovered in your library that your current axes don't already cover. Curate the terms,
        rename, and create the ones you want.
      </div>

      {state.status === "loading" && <ProgressBar label="Analyzing your library…" managedBy="backend-job" />}
      {state.status === "error" && <div className="axis-err">Couldn't suggest axes: {state.error}</div>}
      {state.status === "ready" && state.suggestions.length === 0 &&
        <div className="axis-hint">No new themes found — your axes already cover the library, or there aren't enough papers yet.</div>}
      {state.status === "ready" && state.suggestions.map((s, i) => (
        <SuggestCard key={i} suggestion={s} onCreated={() => setCreatedCount(c => c + 1)} />
      ))}

      <div className="axis-form-actions">
        <button className="axis-link" onClick={onClose}>{createdCount ? "Done" : "Close"}</button>
      </div>
    </>
  );
}
