// Persistent, dismissible beyond-library suggestion queue (backlog #30's last open piece, inc 465).
// A "Save for later" click on a beyond-library suggestion card (37_cite.jsx) lands here — a flat review queue,
// no direction/axis/Refresh controls (unlike gap-finder, there's nothing to recompute: every row is a specific
// suggestion someone explicitly flagged). Add imports metadata-only into the library (the PDF stays the
// separate OA-acquire lane); Dismiss hides it for good. Clones the GapsModal shell (36_gaps.jsx).

function BeyondLibrarySavedModal({ onClose, onChanged }) {
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | loading | ready | error
  const [busyKey, setBusyKey] = useState(null);

  const load = React.useCallback(() => {
    setStatus("loading");
    api("/citations/beyond-library/saved").then(r => {
      if (r.ok) { setRows(r.data.items || []); setStatus("ready"); } else setStatus("error");
    });
  }, []);

  useEffect(() => { load(); }, [load]);

  const add = async (row) => {
    setBusyKey(row.dedup_key);
    const r = await apiPost("/citations/beyond-library/add", { dedup_key: row.dedup_key });
    setBusyKey(null);
    if (r.ok) { load(); if (onChanged) onChanged(); }  // re-GET: read-time filter drops the now-in-library row
  };
  const dismiss = async (row) => {
    setBusyKey(row.dedup_key);
    const r = await apiPost("/citations/beyond-library/dismiss", { dedup_key: row.dedup_key });
    setBusyKey(null);
    if (r.ok) load();
  };

  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Saved for later</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Beyond-library suggestions you flagged with <b>Save for later</b> while writing, kept here until you
          decide. <b>Add</b> imports the metadata; <b>Dismiss</b> removes it from this list.
        </div>

        {status === "loading" && rows.length === 0 && <div className="axis-hint">Loading…</div>}
        {status === "error" && <div className="axis-err">Couldn't load your saved suggestions.</div>}
        {status === "ready" && rows.length === 0 &&
          <div className="axis-hint">Nothing saved yet — use "Save for later" on a beyond-library suggestion in Work → Cite.</div>}

        {rows.map(row => (
          <div key={row.dedup_key} className="gap-row">
            <div className="gap-row-info">
              <div className="gap-row-title">{row.title || row.doi}</div>
              <div className="gap-row-meta">
                {row.authors && row.authors.length > 0 && <>{row.authors.slice(0, 3).join(", ")}{row.authors.length > 3 ? " et al." : ""}</>}
                {row.year ? ` · ${row.year}` : ""}
                {row.journal ? ` · ${row.journal}` : ""}
              </div>
              {(row.relationship_label || row.reason) &&
                <div className="gap-row-meta">{row.relationship_label || row.reason}</div>}
              {row.source_query &&
                <div className="gap-row-meta" title="The draft sentence that surfaced this suggestion">
                  from: “{row.source_query.length > 140 ? row.source_query.slice(0, 140) + "…" : row.source_query}”
                </div>}
            </div>
            <div className="gap-row-actions">
              <button className="axis-link" disabled={busyKey === row.dedup_key} onClick={() => add(row)}>Add</button>
              <button className="axis-link" disabled={busyKey === row.dedup_key} onClick={() => dismiss(row)}>Dismiss</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
