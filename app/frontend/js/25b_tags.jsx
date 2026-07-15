// inc 207: extracted verbatim from 25_detail.jsx (which crossed the 600-line cap when the color picker landed —
// rule #1). TagsRow is self-contained (its own state; props paperId/initialTags/onFilterToTag/onTagsChanged), so it
// lives here and DetailContent (in 25_detail.jsx) calls it via the shared-IIFE function hoist. Loads at 25b (after
// 25_detail) — the chunk order is irrelevant for a hoisted function declaration.

// inc-71: lightweight free-form tags. Local state seeded from the paper detail (the parent keys this by
// paper id so it remounts on paper switch); add via POST, remove via DELETE, datalist suggests existing
// tags. Clicking a chip's name filters the library to that tag. inc-207: an optional per-tag color (a swatch
// popover off each chip's color dot; colored chips override the inc-100 provenance styling).
function TagsRow({ paperId, initialTags, onFilterToTag, onTagsChanged, readOnly }) {
  const [tags, setTags] = useState(initialTags || []);
  const [all, setAll] = useState([]);
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState([]);   // inc-72: c-TF-IDF candidates
  const [suggested, setSuggested] = useState(false);    // have we fetched candidates at least once?
  const [palette, setPalette] = useState([]);           // inc-207: the fixed tag-color palette keys
  const [picking, setPicking] = useState(null);         // inc-207: the tag id whose color popover is open
  const [error, setError] = useState("");               // a rejected add/color/remove was previously silent (QA route_20/30)
  const errorId = `tag-error-${paperId}`;
  const sortByName = (ts) => [...ts].sort((x, y) => x.name.toLowerCase().localeCompare(y.name.toLowerCase()));
  const refreshSuggestions = () => api("/tags").then(r => { if (r.ok) setAll(r.data); });
  useEffect(() => { refreshSuggestions(); }, []);
  useEffect(() => { api("/tags/colors").then(r => { if (r.ok) setPalette(r.data || []); }); }, []);
  // inc-207: set (or clear, color=null) a tag's palette color. Optimistic; refreshes the sidebar Tags browser.
  const setColor = async (tagId, color) => {
    setPicking(null);
    const r = await apiPost(`/tags/${tagId}/color`, { color });
    if (r.ok) {
      setError("");
      setTags(ts => ts.map(t => (t.id === tagId ? { ...t, color } : t)));
      refreshSuggestions();
      if (onTagsChanged) onTagsChanged();
    } else {
      setError(r.error || "Couldn't set that color.");
    }
  };
  const setLocked = async (tagId, locked) => {
    const r = await apiPost(`/papers/${paperId}/tags/${tagId}/lock`, { locked });
    if (r.ok) {
      setError("");
      setTags(ts => ts.map(t => (t.id === tagId ? { ...t, locked: !!r.data.locked } : t)));
      if (onTagsChanged) onTagsChanged();
    } else {
      setError(r.error || "Couldn't update that tag lock.");
    }
  };
  // Re-sync to server truth when the parent refetches the detail (e.g. 🔎 re-resolve adds keyword tags for
  // the SAME paper id, so the key={p.id} remount doesn't fire). initialTags identity only changes on a real
  // detail refetch, so optimistic add/remove between refetches is preserved.
  useEffect(() => { setTags(initialTags || []); setError(""); }, [initialTags, paperId]);
  const add = async (nameArg) => {
    const name = (nameArg != null ? nameArg : input).trim();
    if (!name) return;
    if (nameArg == null) setInput("");
    const r = await apiPost(`/papers/${paperId}/tags`, { name });
    if (r.ok) {
      setError("");
      setTags(ts => ts.some(t => t.id === r.data.id) ? ts : sortByName([...ts, r.data]));
      setSuggestions(s => s.filter(x => x.toLowerCase() !== name.toLowerCase()));  // drop the accepted candidate
      refreshSuggestions();
      if (onTagsChanged) onTagsChanged();  // refresh the sidebar Tags browser (inc 96)
    } else {
      setError(r.error || `Couldn't add "${name}".`);  // honest inline feedback instead of a silent 422
    }
  };
  const remove = async (tagId) => {
    const r = await apiDelete(`/papers/${paperId}/tags/${tagId}`);
    if (r.ok) { setError(""); setTags(ts => ts.filter(t => t.id !== tagId)); refreshSuggestions(); if (onTagsChanged) onTagsChanged(); }
    else setError(r.error || "Couldn't remove that tag.");
  };
  const suggest = async () => {   // inc-72: local c-TF-IDF — propose distinctive terms, the user opts in
    const r = await api(`/papers/${paperId}/suggested-tags`);
    setSuggested(true);
    if (r.ok) setSuggestions(r.data.suggestions || []);
  };
  return (
    <div className="detail-tags">
      <span className="detail-cite-label">Tags</span>
      <div className="detail-tags-chips">
        {tags.map(t => (
          <span key={t.id}
            className={"tag-chip" + (t.color ? " tag-colored tag-color-" + t.color : (tagIsImported(t.source) ? " tag-chip-imported" : ""))}>
            {!readOnly && <button className="tag-chip-dot" title="Set a color for this tag"
              onClick={() => setPicking(p => (p === t.id ? null : t.id))}>●</button>}
            {!readOnly && <button className={"tag-chip-lock" + (t.locked ? " on" : "")}
              title={t.locked ? "Unlock this tag before removing it from this paper" : "Lock this tag on this paper"}
              aria-label={t.locked ? "Unlock this tag on this paper" : "Lock this tag on this paper"}
              aria-pressed={!!t.locked}
              onClick={() => setLocked(t.id, !t.locked)}>{t.locked ? "locked" : "lock"}</button>}
            <button className="tag-chip-name" title={tagSourceLabel(t.source) + " · click to filter the library"}
              onClick={() => onFilterToTag && onFilterToTag({ id: t.id, name: t.name })}>{t.name}</button>
            {!readOnly && !t.locked && <button className="tag-chip-x" title="Remove this tag" onClick={() => remove(t.id)}>×</button>}
            {!readOnly && picking === t.id &&
              <span className="tag-swatches" role="listbox" aria-label="Tag color">
                {palette.map(c => (
                  <button key={c} className={"tag-swatch tag-color-" + c + (t.color === c ? " on" : "")}
                    title={c} aria-label={c} onClick={() => setColor(t.id, c)} />
                ))}
                <button className="tag-swatch tag-swatch-none" title="No color" aria-label="No color"
                  onClick={() => setColor(t.id, null)}>×</button>
              </span>}
          </span>
        ))}
        {!readOnly && <React.Fragment>
          <input className="tag-add" list="tag-suggestions" placeholder="add tag…" value={input} spellCheck={false}
            aria-invalid={!!error} aria-describedby={error ? errorId : undefined}
            onChange={e => { setInput(e.target.value); if (error) setError(""); }}
            onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
            onBlur={() => add()} />
          <datalist id="tag-suggestions">{all.map(t => <option key={t.id} value={t.name} />)}</datalist>
          <button className="btn-link" title="Suggest tags from this paper's text (local, no AI sent off-device)"
            onClick={suggest}>✨ Suggest</button>
          {suggestions.map(name => (
            <button key={"sug-" + name} className="term-chip tag-suggest-chip" title="Add this suggested tag"
              onClick={() => add(name)}>+ {name}</button>
          ))}
          {suggested && suggestions.length === 0 && <span className="tag-suggest-empty">no new suggestions</span>}
        </React.Fragment>}
      </div>
      {error && <div id={errorId} className="axis-err tag-error" role="alert">{error}</div>}
    </div>
  );
}
