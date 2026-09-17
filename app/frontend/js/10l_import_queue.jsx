// #61 provisional ingestion: the narrowest visible/readable Import Queue surface that proves the
// capture -> queue -> (promote | stay queued) -> delete lifecycle end to end. No candidate-picker,
// no thumbnail, no library-filter integration — those remain explicit future work (see #61/#96's
// design comments). Self-contained (own fetch, own state) so it does not entangle with the existing
// library filter state machine (librarySignalFilter, libraryNeedsReview, etc.). Styling reuses
// `.add-menu` / `.add-menu-pop` (10b_libmenus.jsx's header-dropdown recipe) rather than inventing a
// new popover pattern.

function ImportQueuePanel({ count, onChanged }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef(null);

  const load = useCallback(() => {
    setLoading(true);
    api("/library/import-queue").then(r => {
      setLoading(false);
      if (r.ok) setItems(r.data.items || []);
    });
  }, []);

  useEffect(() => {
    if (!open) return;
    load();
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open, load]);

  const remove = useCallback((artifactId) => {
    apiDelete(`/library/import-queue/${encodeURIComponent(artifactId)}`).then(r => {
      if (r.ok) { load(); if (onChanged) onChanged(); }
    });
  }, [load, onChanged]);

  return (
    <span className="add-menu lib-chip-group lib-chip-queue" ref={ref}
      title="Direct-PDF captures Callosum preserved but has not yet identified confidently — never lost, safe to review">
      <span className="lib-chip-group-label">Import Queue</span>
      <button className="trash-toggle findings-chip" onClick={() => setOpen(o => !o)}>🗂 Import Queue · {count}</button>
      {open &&
        <div className="add-menu-pop saved-search-pop" style={{ maxHeight: 360, overflowY: "auto" }}>
          {loading && <span className="saved-search-empty">Loading…</span>}
          {!loading && items.length === 0 && <span className="saved-search-empty">Nothing queued.</span>}
          {!loading && items.map(item => (
            <div key={item.artifact_id} className="saved-search-row" style={{ flexDirection: "column", alignItems: "stretch", padding: "7px 12px" }}>
              <strong style={{ fontSize: 12 }}>
                {item.identity_state === "resolved" ? "Matched, not yet attached" : "Identity not yet resolved"}
              </strong>
              {item.last_source_url && <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{item.last_source_url}</span>}
              {item.last_original_filename && <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{item.last_original_filename}</span>}
              {item.encounter_count > 1 && <span style={{ fontSize: 11, color: "var(--ink-3)" }}>Captured {item.encounter_count} times</span>}
              <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{item.promotion_state.replace(/_/g, " ")}</span>
              <button className="paper-restore danger" onClick={() => remove(item.artifact_id)}>Delete</button>
            </div>
          ))}
        </div>}
    </span>
  );
}
