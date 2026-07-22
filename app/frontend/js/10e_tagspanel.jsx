// inc-96: a sidebar Tags browser — the whole tag vocabulary (each with its paper count), click to filter the
// library (reuses the inc-71 tag filter). Read-only; refetches when `tagRefresh` bumps (a tag added/removed in
// Details). Stacks below the Axes panel; the sidebar scrolls as one column. No panel when there are no tags.
// inc 121: rendered inside the THEORY accordion (its "Tags" header + collapse is the accordion's now, so no
// self-collapse). Always shown with an empty-state hint when there are no tags (discoverability — was return null).
// Extracted from js/10_pdf_layer.jsx in the #9 tag-provenance-grouping pass (over the 600-line cap once grouping
// landed) — the inc-208/222 shared-IIFE hoist precedent; called unchanged via registerPaneTab below.

// inc-9 (backlog #9): group a tag list by its exact provenance source, "Your tags" always first, remaining
// groups ordered alphabetically by their header label for stability. Returns null (no grouping) when only one
// group is present — a single redundant header adds noise, not signal.
function _groupTagsBySource(list) {
  const bySource = new Map();
  for (const t of list) {
    const key = t.source || "user";
    if (!bySource.has(key)) bySource.set(key, []);
    bySource.get(key).push(t);
  }
  if (bySource.size <= 1) return null;
  const groups = [...bySource.entries()].map(([source, items]) => ({ source, label: tagSourceGroupLabel(source), items }));
  groups.sort((a, b) => (a.source === "user" ? -1 : b.source === "user" ? 1 : a.label.localeCompare(b.label)));
  return groups;
}

function TagsPanel({ onFilterToTag, tagRefresh }) {
  const [tags, setTags] = useState(null);
  const [filter, setFilter] = useState("");
  const [src, setSrc] = useState("all");  // inc-105: all | mine | imported — filter by tag provenance (inc-73/100 source)
  useEffect(() => { api("/tags").then(r => setTags(r.ok ? r.data : [])); }, [tagRefresh]);
  if (tags == null) return null;  // still loading
  const q = filter.trim().toLowerCase();
  const hasImported = tags.some(t => tagIsImported(t.source));
  const hasMine = tags.some(t => !tagIsImported(t.source));
  const shown = tags.filter(t =>
    (!q || t.name.toLowerCase().includes(q)) &&
    (src === "all" || (src === "imported") === tagIsImported(t.source))
  );
  const groups = _groupTagsBySource(shown);
  const tagButton = (t) => (
    <button key={t.id} className={"tags-panel-item" + (!t.color && tagIsImported(t.source) ? " tags-panel-item-imported" : "")}
      title={tagSourceLabel(t.source) + " · filter the library to “" + tagDisplayName(t) + "”"}
      onClick={() => onFilterToTag && onFilterToTag({ id: t.id, name: tagDisplayName(t) })}>
      <span className="tags-panel-name">
        {t.color && <span className={"tags-panel-dot tag-color-" + t.color} />}{tagDisplayName(t)}</span>
      <span className="tags-panel-count">{t.paper_count}</span>
    </button>
  );
  return (
    <div className="tags-panel">
      {tags.length > 8 &&
        <input className="axis-filter" placeholder="Filter tags…" value={filter} onChange={e => setFilter(e.target.value)} spellCheck={false} />}
      {tags.length > 0 && hasImported && hasMine &&
        <div className="tags-srcfilter">
          {[["all", "All"], ["mine", "Yours"], ["imported", "Keywords"]].map(([k, lbl]) => (
            <button key={k} className={"tags-srcfilter-btn" + (src === k ? " on" : "")}
              title={k === "imported" ? "Show only imported author/index keywords" : k === "mine" ? "Show only tags you added" : "Show all tags"}
              onClick={() => setSrc(k)}>{lbl}</button>
          ))}
        </div>}
      <div className="tags-panel-list">
        {tags.length === 0
          ? <span className="tag-suggest-empty">No tags yet — add tags from a paper's Details pane.</span>
          : groups
            ? groups.map(g => (
                <div className="tags-panel-group" key={g.source}>
                  <div className="tags-panel-group-label">{g.label} · {g.items.length}</div>
                  {g.items.map(tagButton)}
                </div>))
            : shown.map(tagButton)}
        {tags.length > 0 && shown.length === 0 && <span className="tag-suggest-empty">no matching tags</span>}
      </div>
    </div>
  );
}

// inc 121 / inc 139: TAGS is the second tab of the AXES section (like-with-like — your labels alongside your
// conceptual lenses), not its own accordion section. See 05_panes.jsx + DESIGN.md §5.
registerPaneTab(
  { id: "axes", label: "Axes", paneId: "theory", order: 10 },
  { id: "tags-tab", label: "Tags", order: 20,
    render: (ctx) => <TagsPanel onFilterToTag={ctx.onFilterToTag} tagRefresh={ctx.tagRefresh} /> },
);
