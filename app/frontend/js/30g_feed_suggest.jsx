// Feed's Suggest modal (2026-08-27) — one shared shell, 5 tabs, one per add-source kind on 30e_feed.jsx's
// dropdown. Journal keeps its original inc-295 library-frequency list unchanged. bioRxiv/medRxiv/PubMed need
// NO new backend endpoint: the fixed category lists already ride sourceMeta (BioRxivFeedSource.suggestions),
// search history is a frontend localStorage read (_discoverLoadSearchHistory, 30d_discover.jsx — function
// declarations hoist across the shared IIFE regardless of chunk order), and axes/tags are existing endpoints
// Feed simply hadn't called before. Only Author needs a new endpoint (GET /feed/suggest-authors — a plain
// library-frequency tally, self- and already-followed-excluded server-side).
//
// Also houses the followed-sources overflow modal (30e_feed.jsx caps the pill row to one visible line and
// opens this when it detects real clipping) — a secondary-modal sibling to Suggest, not a separate chunk.

const FEED_SUGGEST_TABS = [
  { id: "journal", label: "Journal" },
  { id: "biorxiv_category", label: "bioRxiv Categories" },
  { id: "medrxiv_category", label: "medRxiv Categories" },
  { id: "pubmed_query", label: "PubMed Search" },
  { id: "author", label: "Author" },
];

function FeedSuggestModal({ subs, libJournals, sourceMeta, onFollow, onFollowAuthor, onFilterToAuthorPapers, onClose }) {
  const [tab, setTab] = useState("journal");
  const [axes, setAxes] = useState(null);
  const [tags, setTags] = useState(null);
  const [authorSuggestions, setAuthorSuggestions] = useState(null);
  const [excludeCoauthors, setExcludeCoauthors] = useState(true);  // on by default -- the common case is wanting NEW people, not your own collaborators
  const [authorAxisId, setAuthorAxisId] = useState("");  // "" = whole library, matching the gap-finder axis-scope convention

  useEffect(() => {
    if (isDemoMode()) return;  // these 4 new tabs need real library/axis data -- not available in the shared demo
    // The My Publications axis (kind="my_publications") tracks the user's OWN papers -- it's not a research
    // topic/keyword to match a bioRxiv category or follow as a PubMed query against, so it's excluded a priori
    // rather than surfaced as if it were an ordinary axis.
    api("/axes").then(r => setAxes(r.ok ? r.data.filter(a => a.kind !== "my_publications") : []));
    api("/tags").then(r => setTags(r.ok ? r.data : []));
  }, []);

  const loadAuthorSuggestions = React.useCallback(() => {
    if (isDemoMode()) return;
    const qs = new URLSearchParams();
    if (authorAxisId) qs.set("axis_id", authorAxisId);
    if (excludeCoauthors) qs.set("exclude_coauthors", "true");
    api(`/feed/suggest-authors?${qs.toString()}`).then(r => setAuthorSuggestions(r.ok ? (r.data.authors || []) : []));
  }, [authorAxisId, excludeCoauthors]);
  useEffect(() => { loadAuthorSuggestions(); }, [loadAuthorSuggestions]);

  const followedByKind = (kind) => new Set(
    (subs || []).filter(s => s.kind === kind).map(s => (s.value || "").toLowerCase())
  );

  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal feed-suggest-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Suggested sources to follow</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="tags-srcfilter">
          {FEED_SUGGEST_TABS.map(t => (
            <button key={t.id} className={"tags-srcfilter-btn" + (tab === t.id ? " on" : "")} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="feed-suggest-body">
          {tab === "journal" &&
            <FeedSuggestJournals journals={libJournals} followed={followedByKind("journal")} onFollow={(v) => onFollow("journal", v)} />}
          {(tab === "biorxiv_category" || tab === "medrxiv_category") &&
            <FeedSuggestCategories
              kind={tab}
              categories={(sourceMeta.find(m => m.kind === tab) || {}).suggestions || []}
              axes={axes} tags={tags}
              followed={followedByKind(tab)}
              onFollow={(v) => onFollow(tab, v)}
            />}
          {tab === "pubmed_query" &&
            <FeedSuggestQueries axes={axes} tags={tags} followed={followedByKind("pubmed_query")} onFollow={(v) => onFollow("pubmed_query", v)} />}
          {tab === "author" &&
            <FeedSuggestAuthors
              authors={authorSuggestions} onFollow={onFollowAuthor}
              axes={axes} axisId={authorAxisId} onAxisChange={setAuthorAxisId}
              excludeCoauthors={excludeCoauthors} onExcludeCoauthorsChange={setExcludeCoauthors}
              onFilterToAuthorPapers={onFilterToAuthorPapers} onClose={onClose}
            />}
        </div>
      </div>
    </div>
  );
}

// inc 295: journals already in the user's library (venue + paper count) — follow one to seed the feed. Ranked by
// count (a transparent tally of the user's own library, not a quality ranking). Unchanged logic, just a tab pane.
function FeedSuggestJournals({ journals, followed, onFollow }) {
  return (
    <>
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
    </>
  );
}

// A category is "matched" by a plain, disclosed, case-insensitive substring check against the user's own axis
// label/description text and tag names -- never a hidden semantic score. The fixed bioRxiv/medRxiv category
// lists are short enough to show in full regardless of match (unlike journals, an open-ended set).
function _categoryMatchReasons(category, axes, tags) {
  const cat = category.toLowerCase();
  const reasons = [];
  (axes || []).forEach(a => {
    const label = (a.label || "").toLowerCase();
    const desc = (a.description || "").toLowerCase();
    if ((label && (label.includes(cat) || cat.includes(label))) || (desc && (desc.includes(cat) || cat.includes(desc)))) {
      reasons.push(`your axis "${a.label}"`);
    }
  });
  (tags || []).forEach(t => {
    const name = (t.name || "").toLowerCase();
    if (name && (name.includes(cat) || cat.includes(name))) reasons.push(`your tag "${t.name}"`);
  });
  return reasons;
}

function FeedSuggestCategories({ kind, categories, axes, tags, followed, onFollow }) {
  const loading = axes === null || tags === null;
  const server = kind === "biorxiv_category" ? "bioRxiv" : "medRxiv";
  const sorted = categories
    .map(c => ({ category: c, reasons: loading ? [] : _categoryMatchReasons(c, axes, tags) }))
    .sort((a, b) => (b.reasons.length - a.reasons.length) || a.category.localeCompare(b.category));
  return (
    <>
      <div className="axis-modal-note">
        Every {server} category. Ones matching one of your axes or tags are listed first, with the match named — a
        plain text match, not a semantic score. <b>Follow</b> pulls its recent preprints into your feed.
      </div>
      {loading
        ? <div className="axis-hint">Checking your axes and tags…</div>
        : sorted.map(({ category, reasons }) => {
          const isFollowed = followed.has(category.toLowerCase());
          return (
            <div key={category} className="gap-row">
              <div className="gap-row-info">
                <div className="gap-row-title">{category}</div>
                {reasons.length ? <div className="gap-row-meta"><span className="gap-count">matches {reasons.join(", ")}</span></div> : null}
              </div>
              <div className="gap-row-actions">
                {isFollowed
                  ? <span className="discover-inlib">✓ Following</span>
                  : <button className="axis-link" onClick={() => onFollow(category)}>Follow</button>}
              </div>
            </div>
          );
        })}
    </>
  );
}

function FeedSuggestQueries({ axes, tags, followed, onFollow }) {
  const loading = axes === null || tags === null;
  const candidates = [];
  const seen = new Set();
  const add = (text, source) => {
    const trimmed = (text || "").trim();
    const key = trimmed.toLowerCase();
    if (!trimmed || seen.has(key)) return;
    seen.add(key);
    candidates.push({ text: trimmed, source });
  };
  if (!loading) {
    (_discoverLoadSearchHistory() || []).forEach(h => add(h.q, "your recent search"));
    (axes || []).forEach(a => add(a.label, "one of your axes"));
    (tags || []).forEach(t => add(t.name, tagIsImported(t.source) ? "an imported keyword tag" : "one of your tags"));
  }
  return (
    <>
      <div className="axis-modal-note">
        Suggested from your recent Search queries, your axes, and your tags (keywords + your own). <b>Follow</b>
        saves the exact text as a PubMed search that polls for new matches.
      </div>
      {loading
        ? <div className="axis-hint">Checking your axes and tags…</div>
        : !candidates.length
          ? <div className="axis-hint">Nothing to suggest yet — search the literature, add an axis, or tag a paper first.</div>
          : candidates.map(c => {
            const isFollowed = followed.has(c.text.toLowerCase());
            return (
              <div key={c.text} className="gap-row">
                <div className="gap-row-info">
                  <div className="gap-row-title">{c.text}</div>
                  <div className="gap-row-meta"><span className="gap-count">from {c.source}</span></div>
                </div>
                <div className="gap-row-actions">
                  {isFollowed
                    ? <span className="discover-inlib">✓ Following</span>
                    : <button className="axis-link" onClick={() => onFollow(c.text)}>Follow</button>}
                </div>
              </div>
            );
          })}
    </>
  );
}

function FeedSuggestAuthors({
  authors, onFollow, axes, axisId, onAxisChange, excludeCoauthors, onExcludeCoauthorsChange,
  onFilterToAuthorPapers, onClose,
}) {
  const [justFollowed, setJustFollowed] = useState(() => new Set());
  const loading = authors === null;
  const handleFollow = async (name) => {
    const ok = await onFollow(name);  // never mark "Following" without a genuine backend success
    if (ok) setJustFollowed(prev => new Set(prev).add(name.toLowerCase()));
  };
  const showInLibrary = (a) => {
    if (onFilterToAuthorPapers) onFilterToAuthorPapers({ label: a.name, paperIds: a.paper_ids || [] });
    if (onClose) onClose();
  };
  return (
    <>
      <div className="axis-modal-note">
        Authors who recur across your library, ranked by paper count — excluding you and anyone already followed.
        A plain tally of your own library, never a ranking of the author's work or a recommendation to collaborate.
      </div>
      <div className="gaps-controls">
        <select className="lib-sort" value={axisId} onChange={e => onAxisChange(e.target.value)} title="Scope to an axis">
          <option value="">All Papers</option>
          {(axes || []).map(a => <option key={a.id} value={a.id}>{a.label}</option>)}
        </select>
        <label className="settings-check">
          <input type="checkbox" checked={excludeCoauthors} onChange={e => onExcludeCoauthorsChange(e.target.checked)} />
          Exclude Your Co-Authors
        </label>
      </div>
      {loading
        ? <div className="axis-hint">Checking your library…</div>
        : !authors.length
          ? <div className="axis-hint">No recurring authors found yet.</div>
          : authors.map(a => {
            const isFollowed = justFollowed.has(a.name.toLowerCase());
            return (
              <div key={a.name} className="gap-row">
                <div className="gap-row-info">
                  <div className="gap-row-title">{a.name}</div>
                  <div className="gap-row-meta">
                    <button className="gap-count axis-link" onClick={() => showInLibrary(a)}
                      title="Show this author's papers in your Library">
                      {a.paper_count} paper{a.paper_count === 1 ? "" : "s"} in your library
                    </button>
                  </div>
                </div>
                <div className="gap-row-actions">
                  {isFollowed
                    ? <span className="discover-inlib">✓ Following</span>
                    : <button className="axis-link" onClick={() => handleFollow(a.name)}>Follow</button>}
                </div>
              </div>
            );
          })}
    </>
  );
}

// The followed-sources pill row is capped to one visible line in 30e_feed.jsx (a real measured overflow check,
// not a guessed count); this modal is the "…" button's destination — every followed source, unconstrained,
// with the same pills (and their existing × unfollow button) as the header row.
function FeedSubsOverflowModal({ subs, sourceMeta, onUnfollow, onClose }) {
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>All followed sources</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">Every journal, category, search, and author you follow. Click × to unfollow.</div>
        <div className="feed-subs">
          {(subs || []).map(s => {
            const meta = sourceMeta.find(m => m.kind === s.kind);
            const tag = (meta ? meta.label : s.kind).split(" ")[0];
            return (
              <span key={s.id} className="feed-sub" title={`${meta ? meta.label : s.kind} · ${s.value}`}>
                <span className="feed-sub-kind">{tag}</span>{s.label || s.value}
                <button className="feed-sub-x" title={isDemoMode() ? "Unfollowing needs the persistent local library" : "Unfollow"}
                  onClick={() => onUnfollow(s.id)}>×</button>
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
