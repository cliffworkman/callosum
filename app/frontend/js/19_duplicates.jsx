// Duplicate-detection review modal (inc 56). Runs an async scan, lists likely-duplicate groups
// (layered: shared identifier / title+author+year / very similar text), and lets the user resolve each
// by trashing the redundant copy (reuses the soft-delete) or opening it to inspect. Flag-only — no merge
// (deferred). Clones SuggestAxesModal's poll lifecycle.

function _dupConfLabel(c) { return Math.round((c || 0) * 100) + "%"; }

function DuplicateGroupCard({ group, onOpenPaper, onChanged, onDismiss }) {
  const [papers, setPapers] = useState(group.papers);
  const [busy, setBusy] = useState(false);
  if (papers.length < 2) return null;  // resolved (a copy was trashed)

  const del = async (paper) => {
    if (!window.confirm(`Move “${paper.title || "this paper"}” to Trash? You can restore it from Trash.`)) return;
    setBusy(true);
    const r = await apiDelete(`/papers/${paper.id}`);
    setBusy(false);
    if (!r.ok) return;
    setPapers(ps => ps.filter(p => p.id !== paper.id));
    if (onChanged) onChanged();  // refresh the library list
  };

  return (
    <div className="dup-group">
      <div className="dup-group-head">
        <span className="dup-conf">{_dupConfLabel(group.confidence)}</span>
        <span className="dup-reason">{group.reason}</span>
        <button className="axis-link" onClick={onDismiss} title="Not a duplicate — won't be flagged again">dismiss</button>
      </div>
      {papers.map(p => (
        <div key={p.id} className="dup-paper">
          <div className="dup-paper-info">
            <div className="dup-paper-title">{p.title || "Untitled"}</div>
            <div className="dup-paper-meta">
              {fmtAuthors(p.authors) || "—"}{p.year ? " · " + p.year : ""}{p.venue ? " · " + p.venue : ""}
            </div>
          </div>
          <button className="axis-link" onClick={() => onOpenPaper && onOpenPaper(p)}>open</button>
          <button className="axis-link axis-danger" disabled={busy} onClick={() => del(p)}>delete</button>
        </div>
      ))}
    </div>
  );
}

function DuplicatesModal({ onClose, onOpenPaper, onChanged }) {
  const [state, setState] = useState({ status: "loading", groups: [] });
  const [dismissed, setDismissed] = useState(() => new Set());  // session-only hide for the current scan
  const [dismissedPairs, setDismissedPairs] = useState([]);     // persisted dismissals, for un-dismiss (inc 67)
  const [showDismissed, setShowDismissed] = useState(false);
  const refreshDismissed = () =>
    api("/papers/duplicates/dismissed").then(r => { if (r.ok) setDismissedPairs(r.data.pairs || []); });

  useEffect(() => { refreshDismissed(); }, []);

  useEffect(() => {
    let live = true;
    let timer = null;
    const poll = (jobId) => {
      api(`/papers/duplicates/${jobId}`).then(r => {
        if (!live) return;
        if (!r.ok) { setState({ status: "error", error: r.error, groups: [] }); return; }
        const d = r.data;
        if (d.status === "done") setState({ status: "ready", groups: d.groups || [] });
        else if (d.status === "error") setState({ status: "error", error: d.detail || "Scan failed.", groups: [] });
        else timer = setTimeout(() => poll(jobId), 1200);
      });
    };
    apiPost("/papers/duplicates", {}).then(r => {
      if (!live) return;
      if (!r.ok) { setState({ status: "error", error: r.error, groups: [] }); return; }
      poll(r.data.job_id);
    });
    return () => { live = false; if (timer) clearTimeout(timer); };
  }, []);

  const remaining = state.status === "ready" ? state.groups.filter((_, i) => !dismissed.has(i)).length : 0;
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Possible duplicates</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Likely-duplicate groups, ranked by confidence. Review each and delete the redundant copy — it goes
          to Trash (restorable). Nothing is merged or removed automatically.
        </div>

        {state.status === "loading" && <ProgressBar label="Scanning your library…" />}
        {state.status === "error" && <div className="axis-err">Couldn't scan: {state.error}</div>}
        {state.status === "ready" && remaining === 0 && <div className="axis-hint">No likely duplicates found.</div>}
        {state.status === "ready" && state.groups.map((g, i) => (
          dismissed.has(i) ? null :
            <DuplicateGroupCard key={i} group={g} onOpenPaper={onOpenPaper} onChanged={onChanged}
              onDismiss={() => {
                setDismissed(s => new Set(s).add(i));                                   // hide now (this session)
                apiPost("/papers/duplicates/dismiss", { paper_ids: g.papers.map(p => p.id) })  // persist (inc 64)
                  .then(r => { if (r.ok) refreshDismissed(); });                          // surface under "previously dismissed"
              }} />
        ))}

        {dismissedPairs.length > 0 &&
          <div className="dup-dismissed">
            <button className="dup-dismissed-toggle" onClick={() => setShowDismissed(s => !s)}>
              {showDismissed ? "▾" : "▸"} Previously dismissed ({dismissedPairs.length})
            </button>
            {showDismissed && dismissedPairs.map((pair, i) => (
              <div key={i} className="dup-dismissed-row">
                <span className="dup-dismissed-titles">
                  {pair.low.title} <span className="dup-dismissed-sep">↔</span> {pair.high.title}
                </span>
                <button className="axis-link" title="Flag this pair as a possible duplicate again"
                  onClick={() => apiPost("/papers/duplicates/undismiss", { paper_ids: [pair.low.id, pair.high.id] })
                    .then(r => { if (r.ok) refreshDismissed(); })}>un-dismiss</button>
              </div>
            ))}
          </div>}

        <div className="axis-form-actions">
          <button className="axis-link" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
