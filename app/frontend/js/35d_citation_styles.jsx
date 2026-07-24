// Citation style manager (inc 365): the shared local CSL catalog, application default, favorites/recents, and
// real citeproc preview. Document-specific selection remains embedded in each word-processor manuscript.
function CitationStylesSettings() {
  const [catalog, setCatalog] = useState(null);
  const [selectedId, setSelectedId] = useState("");
  const [locale, setLocale] = useState("en-US");
  const [query, setQuery] = useState("");
  const [view, setView] = useState("installed");
  const [preview, setPreview] = useState({ status: "idle" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const load = async () => {
    const r = await api("/citations/styles");
    if (!r.ok) { setMsg("Couldn't load citation styles: " + (r.error || "error")); return; }
    setCatalog(r.data);
    setSelectedId(current => (r.data.styles || []).some(style => style.id === current)
      ? current : (r.data.default_style || (r.data.styles[0] && r.data.styles[0].id) || ""));
    setLocale(r.data.default_locale || "en-US");
  };

  useEffect(() => {
    load();
    if (window.location.hash === "#citation-styles") {
      requestAnimationFrame(() => document.getElementById("citation-styles")?.scrollIntoView({ block: "start" }));
    }
  }, []);

  const selected = catalog && catalog.styles.find(style => style.id === selectedId);
  useEffect(() => {
    if (!selectedId) return;
    let live = true;
    setPreview({ status: "loading" });
    apiPost("/citations/styles/preview", { style: selectedId, locale }).then(r => {
      if (!live) return;
      setPreview(r.ok ? { status: "ready", data: r.data } : { status: "error", error: r.error || "error" });
    });
    return () => { live = false; };
  }, [selectedId, locale]);

  const update = async (body, success) => {
    setBusy(true); setMsg("");
    const r = await apiPut("/citations/styles/preferences", { style: selectedId, locale, ...body });
    setBusy(false);
    if (!r.ok) { setMsg("Couldn't update citation styles: " + (r.error || "error")); return; }
    setCatalog(r.data);
    setMsg(success);
  };

  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  let visible = catalog ? catalog.styles.filter(style => {
    const haystack = [
      style.id, style.title, style.full_title, style.short_title, style.summary,
      style.citation_format, ...(style.fields || []),
    ].join(" ").replaceAll("_", " ").toLowerCase();
    return words.every(word => haystack.includes(word));
  }) : [];
  if (view === "favorites") visible = visible.filter(style => style.favorite);
  if (view === "recent") visible = visible.filter(style => style.recent_rank != null)
    .sort((a, b) => a.recent_rank - b.recent_rank);

  return (
    <div className="citation-style-manager">
      <div className="citation-style-browser">
        <label className="settings-field-label" htmlFor="citation-style-search">Find a citation style</label>
        <input id="citation-style-search" className="settings-input" type="search"
          placeholder="Journal, discipline, acronym, or style name"
          value={query} onChange={event => setQuery(event.target.value)} />
        <div className="citation-style-views" aria-label="Citation style view">
          {[
            ["installed", "Installed"],
            ["favorites", `Favorites${catalog && catalog.favorite_style_ids.length ? ` (${catalog.favorite_style_ids.length})` : ""}`],
            ["recent", "Recent"],
          ].map(([id, label]) =>
            <button key={id} type="button" className={view === id ? "active" : ""}
              aria-pressed={view === id} onClick={() => setView(id)}>{label}</button>)}
        </div>
        <div className="citation-style-list" role="listbox" aria-label="Installed citation styles">
          {visible.map(style =>
            <div className={"citation-style-list-row" + (style.id === selectedId ? " selected" : "")}
              key={style.id}>
              <button type="button" className="citation-style-select" role="option"
                aria-selected={style.id === selectedId} onClick={() => setSelectedId(style.id)}>
                <span>{style.title}</span>
                <small>{style.family === "note" ? "Notes" : style.citation_format.replaceAll("-", " ")}</small>
              </button>
              <button type="button" className={"citation-style-favorite" + (style.favorite ? " on" : "")}
                title={style.favorite ? "Remove from favorites" : "Add to favorites"}
                aria-label={`${style.favorite ? "Remove" : "Add"} ${style.title} ${style.favorite ? "from" : "to"} favorites`}
                disabled={busy} onClick={() => {
                  setSelectedId(style.id);
                  setBusy(true); setMsg("");
                  apiPut("/citations/styles/preferences", {
                    style: style.id, locale, favorite: !style.favorite,
                  }).then(r => {
                    setBusy(false);
                    if (r.ok) setCatalog(r.data);
                    else setMsg("Couldn't update favorites: " + (r.error || "error"));
                  });
                }}>{style.favorite ? "★" : "☆"}</button>
            </div>)}
          {catalog && visible.length === 0 &&
            <div className="citation-style-empty">No styles match this view and search.</div>}
        </div>
      </div>

      <div className="citation-style-detail">
        {selected
          ? <>
              <div className="citation-style-detail-head">
                <div>
                  <h3>{selected.full_title || selected.title}</h3>
                  <div className="citation-style-meta">
                    <span>{selected.family === "note" ? "Note style" : selected.citation_format.replaceAll("-", " ")}</span>
                    <span>{selected.independent ? "Independent CSL" : `Depends on ${selected.parent_style}`}</span>
                    {selected.application_default && <span className="citation-style-default">Application default</span>}
                  </div>
                </div>
                <button type="button" className={"citation-style-favorite detail" + (selected.favorite ? " on" : "")}
                  title={selected.favorite ? "Remove from favorites" : "Add to favorites"}
                  aria-label={selected.favorite ? "Remove selected style from favorites" : "Add selected style to favorites"}
                  disabled={busy} onClick={() => update({ favorite: !selected.favorite }, selected.favorite ? "Removed from favorites." : "Added to favorites.")}>
                  {selected.favorite ? "★" : "☆"}
                </button>
              </div>
              {selected.summary && <p className="citation-style-summary">{selected.summary}</p>}
              {selected.fields.length > 0 &&
                <div className="citation-style-fields">{selected.fields.map(field =>
                  <span key={field}>{field.replaceAll("_", " ")}</span>)}</div>}
              <div className="citation-style-actions">
                <label className="settings-field-label">Preview locale
                  <select className="settings-input" value={locale} onChange={event => setLocale(event.target.value)}>
                    {(catalog.locales || []).map(item =>
                      <option key={item} value={item}>{item === "en-US" ? "English (United States)" : "English (United Kingdom)"}</option>)}
                  </select>
                </label>
                <button type="button" className="btn btn-primary" disabled={busy || selected.application_default}
                  onClick={() => update({ set_default: true, mark_used: true }, "Application default saved.")}>
                  {selected.application_default ? "Application default" : "Use as application default"}
                </button>
              </div>
              <span className="settings-sub citation-style-default-note">
                New word-processor documents inherit this application default. Existing documents keep their embedded style and locale.
              </span>
              <div className="citation-style-preview" aria-live="polite">
                <p className="eyebrow">Preview (example references)</p>
                {preview.status === "loading" && <div className="settings-note">Rendering preview…</div>}
                {preview.status === "error" && <div className="settings-note settings-note-err">Preview unavailable: {preview.error}</div>}
                {preview.status === "ready" &&
                  <>
                    <div className="citation-style-preview-block">
                      <span className="settings-field-label">{selected.family === "note" ? "First note" : "Citation"}</span>
                      <div>{preview.data.citations[0]}</div>
                    </div>
                    {selected.family === "note" && preview.data.citations[1] &&
                      <div className="citation-style-preview-block">
                        <span className="settings-field-label">Subsequent note</span>
                        <div>{preview.data.citations[1]}</div>
                      </div>}
                    <div className="citation-style-preview-block">
                      <span className="settings-field-label">Bibliography</span>
                      <div className="citation-style-bibliography">{preview.data.bibliography_text || "This style does not produce a bibliography."}</div>
                    </div>
                  </>}
              </div>
            </>
          : <div className="citation-style-empty">Select a citation style to inspect it.</div>}
        {msg && <div className="settings-note">{msg}</div>}
      </div>
    </div>
  );
}
