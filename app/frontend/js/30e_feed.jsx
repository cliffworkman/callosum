// Literature Feed — the Feed center tab (backlog #28 SP2b, inc 188; backend SP2a inc 187). Consolidated with
// the former standalone Followed Authors tab 2026-08-27: follow an author (name or ORCID, auto-detected)
// directly from this tab's own add-source row; the Suggest modal now covers all five source kinds (30g_feed_
// suggest.jsx). Follow bioRxiv categories (pull-only, opt-in) → Refresh polls them → triage the items
// (read / star / save). AI never filters: the complete polled list is shown; read/starred are the user's own
// state. Save is metadata-only (reuses /discovery/save; no PDF). Function declarations hoist in the IIFE, so
// 30c_frame references this.

const FEED_ORCID_RE = /^(?:https?:\/\/orcid\.org\/)?\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/i;

function FeedPane({ onSaved, onFilterToAuthorPapers, active, embedded }) {
  const [subs, setSubs] = useState([]);
  const [sourceMeta, setSourceMeta] = useState([]); // [{kind,label,placeholder,suggestions}] — drives the Follow picker
  const [selKind, setSelKind] = useState("");
  const [cat, setCat] = useState("");
  const [authorFollowErr, setAuthorFollowErr] = useState("");
  const [items, setItems] = useState([]);
  const [relevance, setRelevance] = useState({});
  const [relevanceLoading, setRelevanceLoading] = useState(false);
  const [unread, setUnread] = useState(0);
  const [filter, setFilter] = useState("all"); // all | unread | highlighted | starred (one exclusive toggle)
  const [refreshing, setRefreshing] = useState(false);
  const [savingKey, setSavingKey] = useState(null);
  const [expanded, setExpanded] = useState(() => new Set());
  const [libJournals, setLibJournals] = useState([]); // inc 295: journals already in the library (Suggest + typeahead)
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [subsOverflow, setSubsOverflow] = useState(false);
  const [subsModalOpen, setSubsModalOpen] = useState(false);
  const subsRowRef = useRef(null);
  // SP2c-3: opt-in auto-refresh when the Feed is opened + a source is stale (pull-first; default off).
  const [autoRefresh, setAutoRefresh] = useState(() => localStorage.getItem("callosum.feedAutoRefresh") === "1");
  const autoRanRef = useRef(0);

  const loadSubs = useCallback(async () => {
    const r = await api("/feed/subscriptions");
    if (r.ok) {
      setSubs(r.data.subscriptions || []);
      const meta = r.data.source_meta || [];
      setSourceMeta(meta);
      // inc 455: user_addable===false kinds (e.g. followed-author) are dispatch-only — never the default pick
      const addable = meta.filter(m => m.user_addable !== false);
      setSelKind(k => k || (addable[0] ? addable[0].kind : ""));
    }
  }, []);

  const loadItems = useCallback(async () => {
    const qs = filter === "unread" ? "?unread=true" : filter === "starred" ? "?starred=true" : "";
    const r = await api(`/feed${qs}`);
    if (!r.ok) return;
    const rows = r.data.items || [];
    setItems(rows); setUnread(r.data.unread_count || 0);
    // Relevance is keyed by the stable feed_items id, so switching filters within the SAME underlying item
    // universe keeps any already-computed badges rather than flashing them off and recomputing needlessly.
    // Axis-relevance highlight (mirrors 30d_discover.jsx's identical Search-tab pattern): a best-effort,
    // never-filtering hint. feed_view() rows have no dedup_key (only id) -- score_axis_relevance treats this
    // field as an opaque caller-chosen lookup key, never interpreted, so reusing `id` here is contract-safe.
    if (!isDemoMode() && rows.length) {
      setRelevanceLoading(true);
      const rr = await apiPost("/discovery/relevance", {
        items: rows.map(it => ({ dedup_key: String(it.id), title: it.title || "", abstract: it.abstract || null })),
      });
      if (rr.ok && rr.data && rr.data.relevance) setRelevance(rr.data.relevance);
      setRelevanceLoading(false);
    }
  }, [filter]);

  useEffect(() => { loadSubs(); }, [loadSubs]);
  useEffect(() => { loadItems(); }, [loadItems]);
  // inc 295: the library's own journals (venue + count) drive the journal typeahead + the Suggest modal — local, no egress.
  useEffect(() => { api("/feed/library-journals").then(r => { if (r.ok) setLibJournals(r.data.journals || []); }); }, []);

  // The followed-sources pill row is capped to one visible line (CSS max-height); a real measured overflow
  // check -- not a guessed pill count, which would be wrong on many viewport widths -- shows the "…" button
  // only when pills actually got clipped.
  useEffect(() => {
    const el = subsRowRef.current;
    if (!el) return;
    const check = () => setSubsOverflow(el.scrollHeight > el.clientHeight + 1);
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [subs]);

  // Shared by the Suggest modal's Journal/bioRxiv/medRxiv/PubMed tabs -- every non-author kind follows the
  // same {kind, value, label} shape.
  const followFromSuggest = useCallback(async (kind, value) => {
    const r = await apiPost("/feed/subscriptions", { kind, value, label: value });
    if (r.ok) loadSubs();
  }, [loadSubs]);

  // inc 2026-08-27 (Followed Authors consolidation): "Author" is a frontend-only pseudo-kind -- the backend's
  // real followed_author kind stays user_addable=False (a raw OpenAlex id is never something to type), so
  // following by name/ORCID goes through the SAME resolve endpoint the former standalone tab used, and the
  // matching feed_subscriptions row appears via the backend's existing dual-write (loadSubs() alone surfaces it).
  // Returns true only on a genuine follow (status "followed"/"already-following"), false on any failure --
  // callers (e.g. the Suggest modal's Author tab) must never show a success state without checking this.
  const followAuthor = useCallback(async (raw) => {
    const trimmed = (raw || "").trim();
    if (!trimmed) return false;
    setAuthorFollowErr("");
    const value = trimmed.replace(/^https?:\/\/orcid\.org\//i, "");
    const body = FEED_ORCID_RE.test(trimmed) ? { orcid: value } : { name: value };
    const r = await apiPost("/followed-authors", body);
    if (!r.ok) { setAuthorFollowErr(r.error || "Couldn't follow that author."); return false; }
    if (r.data.status === "no-match") { setAuthorFollowErr("No OpenAlex author matched that name/ORCID."); return false; }
    setCat(""); loadSubs();
    return true;
  }, [loadSubs]);

  const follow = useCallback(async () => {
    if (selKind === "author") { await followAuthor(cat); return; }
    // bioRxiv categories are lowercase in the API; PubMed queries keep the user's casing.
    const value = selKind === "biorxiv_category" ? cat.trim().toLowerCase() : cat.trim();
    if (!value || !selKind) return;
    await followFromSuggest(selKind, value);
    setCat("");
  }, [cat, selKind, followFromSuggest, followAuthor]);

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

  const resetDemoTriage = useCallback(async () => {
    const r = await apiPost("/demo/feed-state/reset", {});
    if (r.ok) loadItems();
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

  // inc 455: kinds like followed-author are dispatch-only (their `value` is a bare OpenAlex author id, not
  // something a user should type) — omitted from the real picker; "Author" below is a frontend-only pseudo-kind
  // that routes through the resolve endpoint instead. sourceMeta itself stays full so an already-followed
  // subscription's chip label lookup still resolves.
  const addableSourceMeta = sourceMeta.filter(m => m.user_addable !== false);
  const followedAuthorSubIds = new Set(subs.filter(s => s.kind === "followed_author").map(s => s.id));
  // "Highlighted" is a view filter only (like the critique-triage "AI-focused" toggle elsewhere in the app) --
  // it never changes what's polled/stored, and one click back to "All" always recovers the complete list.
  const visibleItems = filter === "highlighted" ? items.filter(it => relevance[String(it.id)]) : items;

  return (
    <div className={embedded ? "feed discover-feed-embedded" : "discover feed"}>
      <div className="pane-head">
        <div className="feed-subs-row">
          <div className="feed-subs feed-subs-capped" ref={subsRowRef}>
            {subs.map(s => {
              const meta = sourceMeta.find(m => m.kind === s.kind);
              const tag = (meta ? meta.label : s.kind).split(" ")[0];
              return (
                <span key={s.id} className="feed-sub" title={`${meta ? meta.label : s.kind} · ${s.value}`}>
                  <span className="feed-sub-kind">{tag}</span>{s.label || s.value}
                  <button className="feed-sub-x" title={isDemoMode() ? "Unfollowing needs the persistent local library" : "Unfollow"}
                    onClick={() => unfollow(s.id)}>×</button>
                </span>
              );
            })}
            {!subs.length ? <span className="discover-hint">Follow a source to start your feed.</span> : null}
          </div>
          {subsOverflow
            ? <button className="feed-sub-more" onClick={() => setSubsModalOpen(true)} title="Show every followed source">…</button>
            : null}
        </div>
        <div className="searchbar">
          {addableSourceMeta.length > 1 ? (
            <select className="lib-sort" value={selKind} disabled={isDemoMode()}
              onChange={e => { setSelKind(e.target.value); setAuthorFollowErr(""); }}>
              {addableSourceMeta.map(m => <option key={m.kind} value={m.kind}>{m.label}</option>)}
              <option value="author">Author</option>
            </select>
          ) : null}
          <input
            value={cat} onChange={e => setCat(e.target.value)} list="feed-source-suggestions"
            disabled={isDemoMode()}
            placeholder={selKind === "author"
              ? "an author name or ORCID iD, e.g. Jane Doe or 0000-0002-1825-0097"
              : (addableSourceMeta.find(m => m.kind === selKind) || {}).placeholder || "Follow a source…"}
            onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); follow(); } }}
          />
          <datalist id="feed-source-suggestions">
            {(selKind === "journal"
              ? libJournals.map(j => j.journal)  // inc 295: predict from YOUR library's journals as you type
              : ((addableSourceMeta.find(m => m.kind === selKind) || {}).suggestions || [])
            ).map(c => <option key={c} value={c} />)}
          </datalist>
          <button className="btn btn-ghost" onClick={follow} disabled={isDemoMode() || !cat.trim()}>Follow</button>
          <button className="btn btn-ghost" onClick={() => setSuggestOpen(true)}
            title="Suggested sources to follow, based on your library and axes">Suggest</button>
          <button className="btn btn-primary" onClick={refresh} disabled={refreshing || !subs.length}
            title={isDemoMode() ? "Refresh needs external journal and search providers" : undefined}>
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        {authorFollowErr ? <div className="axis-err">{authorFollowErr}</div> : null}
        <div className="feed-controls">
          <div className="tags-srcfilter">
            {["all", "unread", "highlighted", "starred"].map(f => (
              <button key={f} className={"tags-srcfilter-btn" + (filter === f ? " on" : "")} onClick={() => setFilter(f)}
                title={f === "highlighted" ? "Items with a likely axis match (a hint, not a filter on what exists — just what's shown here)" : undefined}>
                {f === "all" ? "All" : f === "unread" ? `Unread${unread ? ` (${unread})` : ""}` : f === "highlighted" ? "Highlighted" : "Starred"}
              </button>
            ))}
          </div>
          <div className="feed-controls-right">
            <label className="auto-refresh-toggle" title="When you open the Feed and a source is stale (>6h), refresh it automatically">
              <input type="checkbox" checked={autoRefresh} onChange={toggleAuto} /> Auto-Refresh
            </label>
            {unread ? <button className="btn btn-link" onClick={markAllRead}>Mark All Read</button> : null}
          </div>
        </div>
        {isDemoMode() &&
          <div className="settings-note">
            The reviewed snapshot contains 1,240 cached public-metadata records; this view loads the same 200-item
            default as live Callosum. The sample star and any read/star changes are practice state stored only in
            this browser. <button className="btn-link" onClick={resetDemoTriage}>Reset Read/Star Practice</button>
          </div>}
      </div>
      <div className="pane-list-body">
        {!subs.length
          ? <div className="discover-empty">Your feed is empty. Follow a bioRxiv category above, then Refresh to pull recent preprints.</div>
          : !items.length
            ? <div className="discover-empty">No items{filter !== "all" && filter !== "highlighted" ? ` (${filter})` : ""}. Refresh to poll your followed sources.</div>
            : filter === "highlighted" && !visibleItems.length
              ? <div className="discover-empty">
                  {relevanceLoading
                    ? "Checking axis matches…"
                    : "No items here matched one of your axes closely enough to highlight — that isn’t \"nothing relevant,\" just nothing this local check flagged. Switch back to All to see everything."}
                </div>
              : null}
        {visibleItems.map(it => (
          <div key={it.id} className={"discover-item feed-item" + (it.is_read ? " read" : "") + (relevance[String(it.id)] ? " relevance-row-highlight" : "")} onClick={() => setRead(it, true)}>
            <div className="feed-row-top">
              {!it.is_read ? <span className={"feed-unread-dot" + (relevance[String(it.id)] ? " feed-unread-dot-highlight" : "")} title="Unread" /> : null}
              <div className="discover-title">{it.title}</div>
              {followedAuthorSubIds.has(it.subscription_id)
                ? <span className="feed-followed-badge" title="From a followed author">Followed</span>
                : null}
              {relevance[String(it.id)]
                ? <span className="relevance-highlight" title="A likely match to one of your axes (a hint — the full list is never filtered).">
                    likely: {relevance[String(it.id)].axis_label} · match {relevance[String(it.id)].similarity.toFixed(2)}
                  </span>
                : null}
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
        ? <FeedSuggestModal
            subs={subs} libJournals={libJournals} sourceMeta={sourceMeta}
            onFollow={followFromSuggest} onFollowAuthor={followAuthor}
            onFilterToAuthorPapers={onFilterToAuthorPapers}
            onClose={() => setSuggestOpen(false)}
          />
        : null}
      {subsModalOpen
        ? <FeedSubsOverflowModal subs={subs} sourceMeta={sourceMeta} onUnfollow={unfollow} onClose={() => setSubsModalOpen(false)} />
        : null}
    </div>
  );
}
