// Literature discovery — the Discover > Search workspace tab (backlog #28, inc 184; backend inc 183).
// Query box → GET /discovery/search → a dense, keyboard-triage results list. AI augments, never filters:
// the complete deduped list is always shown (axis-relevance highlight is SP1b). Save is metadata-only
// (POST /discovery/save → imported_source="discovery-import"); no PDF fetch. Function declarations hoist
// in the shared IIFE, so LibraryFrame (30c) references this regardless of chunk order.
function DiscoverPane({ onSaved, active, onOpenWanted, onOpenGaps, onOpenOverlooked }) {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | ready | error
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [cursor, setCursor] = useState(-1);
  const [expanded, setExpanded] = useState(() => new Set());
  const [savingKey, setSavingKey] = useState(null);
  const [relevance, setRelevance] = useState({}); // dedup_key -> {axis_label, similarity} — a HINT, never a filter
  const [sources, setSources] = useState([]);
  const [source, setSource] = useState("");
  const inputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    api("/discovery/sources").then(r => { if (r.ok) setSources(r.data.sources || []); });
  }, []);

  const runSearch = useCallback(async () => {
    const query = q.trim();
    if (!query) return;
    setStatus("loading"); setError(""); setCursor(-1); setExpanded(new Set()); setRelevance({});
    const sourceParam = source ? `&source=${encodeURIComponent(source)}` : "";
    const r = await api(`/discovery/search?q=${encodeURIComponent(query)}&limit=25${sourceParam}`);
    if (r.ok) {
      const rows = (r.data.items || []).map(it => ({ ...it, saved: !!it.in_library }));
      setItems(rows); setStatus("ready"); setCursor(rows.length ? 0 : -1);
      // SP1b: highlight likely axis matches WITHIN the complete list (best-effort; failure → no badges, never
      // breaks the list). The list is never filtered/reordered by relevance.
      if (rows.length) {
        const rr = await apiPost("/discovery/relevance", {
          items: rows.map(it => ({ dedup_key: it.dedup_key, title: it.title || "", abstract: it.abstract || null })),
        });
        if (rr.ok && rr.data && rr.data.relevance) setRelevance(rr.data.relevance);
      }
    } else {
      setItems([]); setError(r.error || "Search failed."); setStatus("error");
    }
  }, [q, source]);

  const save = useCallback(async (it) => {
    if (!it || it.saved || savingKey) return;
    setSavingKey(it.dedup_key);
    const r = await apiPost("/discovery/save", {
      title: it.title, doi: it.doi || null, abstract: it.abstract || null,
      authors: it.authors || [], journal: it.journal || null,
      year: it.year || null, url: it.url || null,
    });
    setSavingKey(null);
    if (r.ok) {
      setItems(prev => prev.map(p => (p.dedup_key === it.dedup_key ? { ...p, saved: true } : p)));
      onSaved && onSaved();
    }
  }, [savingKey, onSaved]);

  const toggleExpand = useCallback((key) => {
    setExpanded(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n; });
  }, []);

  // Keyboard triage: Enter in the box searches; j/k move, s saves, Enter expands the abstract in the list.
  const onKeyDown = useCallback((e) => {
    if (e.target === inputRef.current) {
      if (e.key === "Enter") { e.preventDefault(); runSearch(); }
      return;
    }
    if (!items.length) return;
    if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); setCursor(c => Math.min(items.length - 1, c < 0 ? 0 : c + 1)); }
    else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); setCursor(c => Math.max(0, c < 0 ? 0 : c - 1)); }
    else if (e.key === "s") { e.preventDefault(); if (cursor >= 0) save(items[cursor]); }
    else if (e.key === "Enter") { e.preventDefault(); if (cursor >= 0) toggleExpand(items[cursor].dedup_key); }
  }, [items, cursor, runSearch, save, toggleExpand]);

  useEffect(() => {
    if (cursor < 0 || !listRef.current) return;
    const row = listRef.current.querySelector(`[data-row="${cursor}"]`);
    if (row && row.scrollIntoView) row.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  return (
    <div className="discover" onKeyDown={onKeyDown}>
      <div className="pane-head">
        <div className="searchbar">
          <input
            ref={inputRef} value={q} onChange={e => setQ(e.target.value)} autoFocus
            placeholder="Search the literature — title, author, keywords…"
          />
          <select className="lib-sort" value={source} onChange={e => setSource(e.target.value)} title="Search source">
            <option value="">All sources</option>
            {sources.map(s => <option key={s.kind} value={s.kind}>{s.label || s.kind}</option>)}
          </select>
          <button className="btn btn-primary" onClick={runSearch} disabled={status === "loading" || !q.trim()}>
            {status === "loading" ? "Searching…" : "Search"}
          </button>
          {onOpenWanted && <button className="btn btn-primary" onClick={onOpenWanted} title="Papers you want an OA copy of — re-check open-access sources">Wanted</button>}
          {onOpenGaps && <button className="btn btn-primary" onClick={onOpenGaps} title="Works related to several of your papers that you don't have yet — references you cite, or newer work citing you">Gaps</button>}
          {onOpenOverlooked && <button className="btn btn-primary" onClick={onOpenOverlooked} title="Per axis: works relevant to it but under-cited for their year — work the field may have overlooked">Overlooked</button>}
        </div>
        <div className="discover-hint">
          Public metadata search · source choice controls where to query; the complete returned list is shown (nothing AI-filtered) · <b>j/k</b> move · <b>s</b> save · <b>Enter</b> abstract
        </div>
      </div>
      <div className="pane-list-body" ref={listRef} tabIndex={0}>
        {status === "idle" &&
          <div className="discover-empty">Search journals + preprints, then save any result to your library — metadata only, no PDF.</div>}
        {status === "error" && <div className="discover-empty">{error}</div>}
        {status === "ready" && !items.length && <div className="discover-empty">No results. Try different terms.</div>}
        {items.map((it, i) => (
          <div
            key={it.dedup_key} data-row={i}
            className={"discover-item" + (i === cursor ? " cur" : "")}
            onClick={() => setCursor(i)}
          >
            <div className="discover-title">{it.title}</div>
            {relevance[it.dedup_key]
              ? <div className="discover-relevance" title="A likely match to one of your axes (a hint — the full list is never filtered).">
                  likely: {relevance[it.dedup_key].axis_label} · match {relevance[it.dedup_key].similarity.toFixed(2)}
                </div>
              : null}
            <div className="paper-meta">
              {it.authors && it.authors.length
                ? <span className="paper-authors">{it.authors.slice(0, 3).join("; ")}{it.authors.length > 3 ? " et al." : ""}</span>
                : null}
              {it.year ? <span className="mono">{it.year}</span> : null}
              {it.journal ? <span className="paper-venue">{it.journal}</span> : null}
            </div>
            <div className="discover-foot">
              {(it.sources || []).map(s => <span key={s} className="discover-source">{s}</span>)}
              {it.saved
                ? <span className="discover-inlib">✓ in library</span>
                : <button className="btn btn-link" disabled={savingKey === it.dedup_key}
                    onClick={(e) => { e.stopPropagation(); save(it); }}>
                    {savingKey === it.dedup_key ? "Saving…" : "Save"}
                  </button>}
              {it.abstract
                ? <button className="btn btn-link" onClick={(e) => { e.stopPropagation(); toggleExpand(it.dedup_key); }}>
                    {expanded.has(it.dedup_key) ? "Hide abstract" : "Abstract"}
                  </button>
                : null}
            </div>
            {expanded.has(it.dedup_key) && it.abstract
              ? <div className="discover-abstract">{it.abstract}</div>
              : null}
          </div>
        ))}
      </div>
    </div>
  );
}
