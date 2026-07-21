// Literature Feed — the Feed center tab (backlog #28 SP2b, inc 188; backend SP2a inc 187).
// Follow bioRxiv categories (pull-only, opt-in) → Refresh polls them → triage the items (read / star / save).
// AI never filters: the complete polled list is shown; read/starred are the user's own state. Save is metadata-only
// (reuses /discovery/save; no PDF). Function declarations hoist in the IIFE, so 30c_frame references this.

function FeedPane({ onSaved, active, embedded }) {
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
  const [libJournals, setLibJournals] = useState([]); // inc 295: journals already in the library (Suggest + typeahead)
  const [suggestOpen, setSuggestOpen] = useState(false);
  // SP2c-3: opt-in auto-refresh when the Feed is opened + a source is stale (pull-first; default off).
  const [autoRefresh, setAutoRefresh] = useState(() => localStorage.getItem("callosum.feedAutoRefresh") === "1");
  const autoRanRef = useRef(0);

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
  // inc 295: the library's own journals (venue + count) drive the journal typeahead + the Suggest modal — local, no egress.
  useEffect(() => { api("/feed/library-journals").then(r => { if (r.ok) setLibJournals(r.data.journals || []); }); }, []);

  const followJournal = useCallback(async (title) => {
    const r = await apiPost("/feed/subscriptions", { kind: "journal", value: title, label: title });
    if (r.ok) loadSubs();
  }, [loadSubs]);

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

  const toggleAuto = useCallback(() => {
    setAutoRefresh(v => { const n = !v; localStorage.setItem("callosum.feedAutoRefresh", n ? "1" : "0"); return n; });
  }, []);

  // Auto-refresh on opening the Feed: opt-in, staleness-gated (newest poll > 6h ago, or never), throttled to ≤1/min.
  // Mirrors the watched-folders on-open rescan (inc 98/136) — pull-first, never a background daemon. The naive UTC
  // last_polled_at is treated as UTC (append Z) so the staleness compare isn't skewed by the local timezone.
  useEffect(() => {
    if (!active || !autoRefresh || refreshing || !subs.length) return;
    if (Date.now() - autoRanRef.current < 60000) return;
    const newest = subs.reduce((mx, s) => {
      if (!s.last_polled_at) return mx;
      const iso = /[Z+]/.test(s.last_polled_at) ? s.last_polled_at : s.last_polled_at + "Z";
      return Math.max(mx, Date.parse(iso) || 0);
    }, 0);
    if (newest && Date.now() - newest < 6 * 3600 * 1000) return; // fresh enough
    autoRanRef.current = Date.now();
    refresh();
  }, [active, autoRefresh, subs, refreshing, refresh]);

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
      title: item.title, doi: item.doi || null, pmid: item.pmid || null, abstract: item.abstract || null,
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
    <div className={embedded ? "feed discover-feed-embedded" : "discover feed"}>
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
            {(selKind === "journal"
              ? libJournals.map(j => j.journal)  // inc 295: predict from YOUR library's journals as you type
              : ((sourceMeta.find(m => m.kind === selKind) || {}).suggestions || [])
            ).map(c => <option key={c} value={c} />)}
          </datalist>
          <button className="btn btn-ghost" onClick={follow} disabled={!cat.trim()}>Follow</button>
          {selKind === "journal"
            ? <button className="btn btn-ghost" onClick={() => setSuggestOpen(true)} title="Journals already in your library">Suggest</button>
            : null}
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
          <div className="feed-controls-right">
            <label className="auto-refresh-toggle" title="When you open the Feed and a source is stale (>6h), refresh it automatically">
              <input type="checkbox" checked={autoRefresh} onChange={toggleAuto} /> Auto-refresh on open
            </label>
            {unread ? <button className="btn btn-link" onClick={markAllRead}>Mark all read</button> : null}
          </div>
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
      {suggestOpen
        ? <FeedSuggestModal journals={libJournals} subs={subs} onFollow={followJournal} onClose={() => setSuggestOpen(false)} />
        : null}
    </div>
  );
}

// inc 295: journals already in the user's library (venue + paper count) — follow one to seed the feed. Ranked by
// count (a transparent tally of the user's own library, not a quality ranking). Reuses the axis-modal + gap-row recipes.
function FeedSuggestModal({ journals, subs, onFollow, onClose }) {
  const followed = new Set((subs || []).filter(s => s.kind === "journal").map(s => (s.value || "").toLowerCase()));
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Journals in your library</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Journals you already have papers from — <b>Follow</b> one to pull its recent articles into your feed. Ordered
          by how many papers you have from each (a tally of your own library, not a quality ranking).
        </div>
        {!journals.length
          ? <div className="axis-hint">No journals in your library yet — import some papers, then their journals show up here.</div>
          : journals.map(j => {
            const isFollowed = followed.has((j.journal || "").toLowerCase());
            return (
              <div key={j.journal} className="gap-row">
                <div className="gap-row-info">
                  <div className="gap-row-title">{j.journal}</div>
                  <div className="gap-row-meta"><span className="gap-count">{j.count} paper{j.count === 1 ? "" : "s"} in your library</span></div>
                </div>
                <div className="gap-row-actions">
                  {isFollowed
                    ? <span className="discover-inlib">✓ Following</span>
                    : <button className="axis-link" onClick={() => onFollow(j.journal)}>Follow</button>}
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
