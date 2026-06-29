// Literature Feed — the Feed center tab (backlog #28 SP2b, inc 188; backend SP2a inc 187).
// Follow bioRxiv categories (pull-only, opt-in) → Refresh polls them → triage the items (read / star / save).
// AI never filters: the complete polled list is shown; read/starred are the user's own state. Save is metadata-only
// (reuses /discovery/save; no PDF). Function declarations hoist in the IIFE, so 30c_frame references this.

function FeedPane({ onSaved }) {
  const [subs, setSubs] = useState([]);
  const [sourceMeta, setSourceMeta] = useState([]); // [{kind,label,placeholder,suggestions}] — drives the Follow picker
  const [selKind, setSelKind] = useState("");
  const [cat, setCat] = useState("");
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [filter, setFilter] = useState("all"); // all | unread | starred
  const [refreshing, setRefreshing] = useState(false);
  const [savingKey, setSavingKey] = useState(null);
  const [expanded, setExpanded] = useState(() => new Set());

  const loadSubs = useCallback(async () => {
    const r = await api("/feed/subscriptions");
    if (r.ok) {
      setSubs(r.data.subscriptions || []);
      const meta = r.data.source_meta || [];
      setSourceMeta(meta);
      setSelKind(k => k || (meta[0] ? meta[0].kind : ""));
    }
  }, []);

  const loadItems = useCallback(async () => {
    const qs = filter === "unread" ? "?unread=true" : filter === "starred" ? "?starred=true" : "";
    const r = await api(`/feed${qs}`);
    if (r.ok) { setItems(r.data.items || []); setUnread(r.data.unread_count || 0); }
  }, [filter]);

  useEffect(() => { loadSubs(); }, [loadSubs]);
  useEffect(() => { loadItems(); }, [loadItems]);

  const follow = useCallback(async () => {
    // bioRxiv categories are lowercase in the API; PubMed queries keep the user's casing.
    const value = selKind === "biorxiv_category" ? cat.trim().toLowerCase() : cat.trim();
    if (!value || !selKind) return;
    const r = await apiPost("/feed/subscriptions", { kind: selKind, value, label: value });
    if (r.ok) { setCat(""); loadSubs(); }
  }, [cat, selKind, loadSubs]);

  const unfollow = useCallback(async (id) => {
    await apiDelete(`/feed/subscriptions/${id}`);
    loadSubs(); loadItems();
  }, [loadSubs, loadItems]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    const r = await apiPost("/feed/refresh", {});
    if (r.ok && r.data.job_id) {
      const jid = r.data.job_id;
      for (let i = 0; i < 40; i++) {
        const s = await api(`/feed/refresh/${jid}`);
        if (s.ok && (s.data.status === "done" || s.data.status === "error")) break;
        await new Promise(res => setTimeout(res, 700));
      }
    }
    setRefreshing(false);
    loadSubs(); loadItems();
  }, [loadSubs, loadItems]);

  const setRead = useCallback(async (item, isRead) => {
    if (item.is_read === isRead) return;
    setItems(prev => prev.map(p => p.id === item.id ? { ...p, is_read: isRead } : p));
    setUnread(u => Math.max(0, u + (isRead ? -1 : 1)));
    await apiPost(`/feed/items/${item.id}/state`, { is_read: isRead });
  }, []);

  const toggleStar = useCallback(async (item) => {
    const next = !item.is_starred;
    setItems(prev => prev.map(p => p.id === item.id ? { ...p, is_starred: next } : p));
    await apiPost(`/feed/items/${item.id}/state`, { is_starred: next });
    if (filter === "starred" && !next) loadItems();
  }, [filter, loadItems]);

  const markAllRead = useCallback(async () => {
    await apiPost("/feed/mark-read", {});
    loadItems();
  }, [loadItems]);

  const save = useCallback(async (item) => {
    if (item.in_library || savingKey) return;
    setSavingKey(item.id);
    const r = await apiPost("/discovery/save", {
      title: item.title, doi: item.doi || null, abstract: item.abstract || null,
      authors: item.authors || [], journal: item.journal || null, year: item.year || null, url: item.url || null,
    });
    setSavingKey(null);
    if (r.ok) {
      setItems(prev => prev.map(p => p.id === item.id ? { ...p, in_library: true } : p));
      onSaved && onSaved();
    }
  }, [savingKey, onSaved]);

  const toggleExpand = useCallback((id) => {
    setExpanded(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }, []);

  return (
    <div className="discover feed">
      <div className="pane-head">
        <div className="feed-subs">
          {subs.map(s => {
            const meta = sourceMeta.find(m => m.kind === s.kind);
            const tag = (meta ? meta.label : s.kind).split(" ")[0];
            return (
              <span key={s.id} className="feed-sub" title={`${meta ? meta.label : s.kind} · ${s.value}`}>
                <span className="feed-sub-kind">{tag}</span>{s.label || s.value}
                <button className="feed-sub-x" title="Unfollow" onClick={() => unfollow(s.id)}>×</button>
              </span>
            );
          })}
          {!subs.length ? <span className="discover-hint">Follow a source to start your feed.</span> : null}
        </div>
        <div className="searchbar">
          {sourceMeta.length > 1 ? (
            <select className="lib-sort" value={selKind} onChange={e => setSelKind(e.target.value)}>
              {sourceMeta.map(m => <option key={m.kind} value={m.kind}>{m.label}</option>)}
            </select>
          ) : null}
          <input
            value={cat} onChange={e => setCat(e.target.value)} list="feed-source-suggestions"
            placeholder={(sourceMeta.find(m => m.kind === selKind) || {}).placeholder || "Follow a source…"}
            onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); follow(); } }}
          />
          <datalist id="feed-source-suggestions">
            {((sourceMeta.find(m => m.kind === selKind) || {}).suggestions || []).map(c => <option key={c} value={c} />)}
          </datalist>
          <button className="btn btn-ghost" onClick={follow} disabled={!cat.trim()}>Follow</button>
          <button className="btn btn-primary" onClick={refresh} disabled={refreshing || !subs.length}>
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        <div className="feed-controls">
          <div className="tags-srcfilter">
            {["all", "unread", "starred"].map(f => (
              <button key={f} className={"tags-srcfilter-btn" + (filter === f ? " on" : "")} onClick={() => setFilter(f)}>
                {f === "all" ? "All" : f === "unread" ? `Unread${unread ? ` (${unread})` : ""}` : "Starred"}
              </button>
            ))}
          </div>
          {unread ? <button className="btn btn-link" onClick={markAllRead}>Mark all read</button> : null}
        </div>
      </div>
      <div className="pane-list-body">
        {!subs.length
          ? <div className="discover-empty">Your feed is empty. Follow a bioRxiv category above, then Refresh to pull recent preprints.</div>
          : !items.length
            ? <div className="discover-empty">No items{filter !== "all" ? ` (${filter})` : ""}. Refresh to poll your followed sources.</div>
            : null}
        {items.map(it => (
          <div key={it.id} className={"discover-item feed-item" + (it.is_read ? " read" : "")} onClick={() => setRead(it, true)}>
            <div className="feed-row-top">
              {!it.is_read ? <span className="feed-unread-dot" title="Unread" /> : null}
              <div className="discover-title">{it.title}</div>
            </div>
            <div className="paper-meta">
              {it.authors && it.authors.length
                ? <span className="paper-authors">{it.authors.slice(0, 3).join("; ")}{it.authors.length > 3 ? " et al." : ""}</span>
                : null}
              {it.posted_date ? <span className="mono">{it.posted_date}</span> : (it.year ? <span className="mono">{it.year}</span> : null)}
              {it.journal ? <span className="paper-venue">{it.journal}</span> : null}
            </div>
            <div className="discover-foot">
              <button className={"feed-star" + (it.is_starred ? " on" : "")} title={it.is_starred ? "Unstar" : "Star"}
                onClick={(e) => { e.stopPropagation(); toggleStar(it); }}>{it.is_starred ? "★" : "☆"}</button>
              {it.in_library
                ? <span className="discover-inlib">✓ in library</span>
                : <button className="btn btn-link" disabled={savingKey === it.id}
                    onClick={(e) => { e.stopPropagation(); save(it); }}>{savingKey === it.id ? "Saving…" : "Save"}</button>}
              {it.abstract
                ? <button className="btn btn-link" onClick={(e) => { e.stopPropagation(); toggleExpand(it.id); }}>
                    {expanded.has(it.id) ? "Hide abstract" : "Abstract"}
                  </button>
                : null}
            </div>
            {expanded.has(it.id) && it.abstract ? <div className="discover-abstract">{it.abstract}</div> : null}
          </div>
        ))}
      </div>
    </div>
  );
}
