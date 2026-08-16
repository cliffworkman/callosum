// Citation style manager (inc 365): the shared local CSL catalog, application default, favorites/recents, and
// real citeproc preview. Document-specific selection remains embedded in each word-processor manuscript.
function CitationStylesSettings() {
  const [catalog, setCatalog] = useState(null);
  const [selectedId, setSelectedId] = useState("");
  const [locale, setLocale] = useState("en-US");
  const [query, setQuery] = useState("");
  const [view, setView] = useState("installed");
  const [preview, setPreview] = useState({ status: "idle" });
  const [repository, setRepository] = useState({ status: "idle", styles: [] });
  const [urlInput, setUrlInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [installBusy, setInstallBusy] = useState(false);
  const [remoteBusy, setRemoteBusy] = useState("");
  const [editorStyle, setEditorStyle] = useState(null);
  const [msg, setMsg] = useState("");
  const fileInputRef = useRef(null);

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
    if (!selectedId || view === "repository") return;
    let live = true;
    setPreview({ status: "loading" });
    apiPost("/citations/styles/preview", { style: selectedId, locale }).then(r => {
      if (!live) return;
      setPreview(r.ok ? { status: "ready", data: r.data } : { status: "error", error: r.error || "error" });
    });
    return () => { live = false; };
  }, [selectedId, locale, view]);

  const update = async (body, success) => {
    setBusy(true); setMsg("");
    const r = await apiPut("/citations/styles/preferences", { style: selectedId, locale, ...body });
    setBusy(false);
    if (!r.ok) { setMsg("Couldn't update citation styles: " + (r.error || "error")); return; }
    setCatalog(r.data);
    setMsg(success);
  };

  const postStyleFile = async (path, filename, csl, replace = false) => {
    try {
      const response = await callosumFetch(API_BASE + path, {
        method: "POST",
        headers: { "Accept": "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ filename, csl, replace }),
      });
      const data = await response.json().catch(() => null);
      return response.ok
        ? { ok: true, data }
        : { ok: false, error: data && data.detail ? data.detail : `HTTP ${response.status}` };
    } catch (error) {
      return { ok: false, error: `Could not reach the ${API_LABEL}. Is uvicorn running?` };
    }
  };

  const installFile = async (event) => {
    const file = event.target.files && event.target.files[0];
    event.target.value = "";
    if (!file) return;
    setInstallBusy(true); setMsg("");
    try {
      if (file.size > 1000180) {
        setMsg("Couldn't install citation style: the file is larger than 1000 KB.");
        return;
      }
      const csl = await file.text();
      if (!csl.trim()) {
        setMsg("Couldn't install citation style: the file is empty.");
        return;
      }
      const validation = await postStyleFile("/citations/styles/validate", file.name, csl);
      if (!validation.ok) {
        const detail = typeof validation.error === "string"
          ? validation.error : (validation.error && validation.error.message) || "validation failed";
        setMsg("Couldn't validate citation style: " + detail);
        return;
      }
      if (!validation.data.valid) {
        setMsg("Couldn't install citation style: " + validation.data.error);
        return;
      }
      const pending = validation.data.install;
      if (pending.action === "already_installed") {
        setCatalog(validation.data);
        setSelectedId(pending.style.id);
        setView("installed");
        setQuery("");
        setMsg(`${pending.style.full_title} is already installed.`);
        return;
      }
      let replace = false;
      if (pending.action === "update_available") {
        const confirmed = window.confirm(
          `${pending.style.full_title} is already installed with different CSL content. Replace the installed version?`
        );
        if (!confirmed) { setMsg("Citation style update cancelled."); return; }
        replace = true;
      }
      const result = await postStyleFile("/citations/styles/install", file.name, csl, replace);
      if (!result.ok) {
        const detail = typeof result.error === "string"
          ? result.error : (result.error && result.error.message) || "validation failed";
        setMsg("Couldn't install citation style: " + detail);
        return;
      }
      const installed = result.data.install;
      setCatalog(result.data);
      setSelectedId(installed.style.id);
      setView("installed");
      setQuery("");
      setMsg(installed.action === "updated"
        ? `${installed.style.full_title} saved.`
        : installed.action === "already_installed"
          ? `${installed.style.full_title} is already installed.`
          : `${installed.style.full_title} installed.`);
    } catch (error) {
      setMsg("Couldn't read the selected CSL file.");
    } finally {
      setInstallBusy(false);
    }
  };

  const postRemoteStyle = async (path, body) => {
    try {
      const response = await callosumFetch(API_BASE + path, {
        method: "POST",
        headers: { "Accept": "application/json", "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json().catch(() => null);
      return {
        ok: response.ok,
        status: response.status,
        data,
        error: data && data.detail ? data.detail : `HTTP ${response.status}`,
      };
    } catch (error) {
      return { ok: false, status: 0, error: `Could not reach the ${API_LABEL}. Is uvicorn running?` };
    }
  };

  const installRemoteStyle = async (path, body, busyId) => {
    setRemoteBusy(busyId); setMsg("");
    try {
      const validation = await postRemoteStyle(path.replace("/install", "/validate"), body);
      if (!validation.ok) {
        const detail = typeof validation.error === "string"
          ? validation.error : (validation.error && validation.error.message) || "validation failed";
        setMsg("Couldn't validate citation style: " + detail);
        return;
      }
      if (!validation.data.valid) {
        setMsg("Couldn't install citation style: " + validation.data.error);
        return;
      }
      const pending = validation.data.install;
      if (pending.action === "already_installed") {
        setCatalog(validation.data);
        setSelectedId(pending.style.id);
        setView("installed");
        setQuery("");
        setRepository({ status: "idle", styles: [] });
        setMsg(`${pending.style.full_title || pending.style.title} is already installed.`);
        return;
      }
      let replace = false;
      if (pending.action === "update_available") {
        const confirmed = window.confirm(
          `${pending.style.full_title} is already installed with different CSL content. Replace the installed version?`
        );
        if (!confirmed) { setMsg("Citation style update cancelled."); return; }
        replace = true;
      }
      const result = await postRemoteStyle(path, {
        ...body,
        replace,
        preflight_token: pending.token,
      });
      if (!result.ok) {
        const detail = typeof result.error === "string"
          ? result.error : (result.error && result.error.message) || "download failed";
        setMsg("Couldn't install citation style: " + detail);
        return;
      }
      const installed = result.data.install;
      setCatalog(result.data);
      setSelectedId(installed.style.id);
      setView("installed");
      setQuery("");
      setRepository({ status: "idle", styles: [] });
      setMsg(installed.action === "updated"
        ? `${installed.style.full_title} saved.`
        : installed.action === "already_installed"
          ? `${installed.style.full_title} is already installed.`
          : `${installed.style.full_title} installed.`);
    } finally {
      setRemoteBusy("");
    }
  };

  const searchRepository = async (event) => {
    event.preventDefault();
    const value = query.trim();
    if (value.length < 2) return;
    setRepository({ status: "loading", styles: [] }); setMsg("");
    const r = await api("/citations/styles/repository/search?q=" + encodeURIComponent(value));
    if (!r.ok) {
      setRepository({ status: "error", styles: [] });
      setMsg("Couldn't search citation styles: " + (r.error || "error"));
      return;
    }
    setRepository({ status: "ready", styles: r.data.styles || [], data: r.data });
  };

  const installUrl = async (event) => {
    event.preventDefault();
    const url = urlInput.trim();
    if (!url) return;
    await installRemoteStyle("/citations/styles/url/install", { url }, "url");
    setUrlInput("");
  };

  const downloadSelected = async () => {
    if (!selected || !selected.custom) return;
    setBusy(true); setMsg("");
    try {
      const response = await callosumFetch(API_BASE + `/citations/styles/${encodeURIComponent(selected.id)}/export`);
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        setMsg("Couldn't export citation style: " + ((data && data.detail) || `HTTP ${response.status}`));
        return;
      }
      _downloadBlob(await response.blob(), `${selected.id}.csl`);
      setMsg(`${selected.full_title || selected.title} exported.`);
    } catch (error) {
      setMsg(`Couldn't reach the ${API_LABEL}. Is uvicorn running?`);
    } finally {
      setBusy(false);
    }
  };

  const removeSelected = async () => {
    if (!selected || !selected.custom || selected.application_default) return;
    const confirmed = window.confirm(
      `Remove ${selected.full_title || selected.title}? Existing documents that use it will not render until ` +
      "the same CSL style is reinstalled. Export a copy first. This cannot be undone."
    );
    if (!confirmed) return;
    setBusy(true); setMsg("");
    try {
      const response = await callosumFetch(API_BASE + `/citations/styles/${encodeURIComponent(selected.id)}`, {
        method: "DELETE",
        headers: { "Accept": "application/json" },
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        setMsg("Couldn't remove citation style: " + ((data && data.detail) || `HTTP ${response.status}`));
        return;
      }
      setCatalog(data);
      setSelectedId(data.default_style || (data.styles[0] && data.styles[0].id) || "");
      setMsg(`${selected.full_title || selected.title} removed.`);
    } catch (error) {
      setMsg(`Couldn't reach the ${API_LABEL}. Is uvicorn running?`);
    } finally {
      setBusy(false);
    }
  };

  const duplicateSelected = async (openEditor = false) => {
    if (!selected) return;
    const proposed = `${selected.full_title || selected.title} - Copy`;
    const title = window.prompt("Name the independent personal copy:", proposed);
    if (title === null) return;
    if (!title.trim()) { setMsg("Enter a name for the personal copy."); return; }
    setBusy(true); setMsg("");
    const r = await apiPost(
      `/citations/styles/${encodeURIComponent(selected.id)}/duplicate`,
      { title: title.trim() },
    );
    setBusy(false);
    if (!r.ok) { setMsg("Couldn't duplicate citation style: " + (r.error || "error")); return; }
    setCatalog(r.data);
    setSelectedId(r.data.install.style.id);
    setView("installed");
    setQuery("");
    if (openEditor) setEditorStyle(r.data.install.style);
    setMsg(`${r.data.install.style.full_title} created as an independent personal style.`);
  };

  const checkSelectedUpdate = async () => {
    if (!selected || !["repository", "url"].includes(selected.provenance?.source_type)) return;
    setBusy(true); setMsg("");
    const checked = await apiPost(
      `/citations/styles/${encodeURIComponent(selected.id)}/check-update`,
      {},
    );
    if (!checked.ok) {
      setBusy(false);
      setMsg("Couldn't check citation style: " + (checked.error || "error"));
      return;
    }
    setCatalog(checked.data);
    const update = checked.data.update;
    if (update.status === "current") {
      setBusy(false);
      setMsg(`${selected.full_title || selected.title} is current as of this check.`);
      return;
    }
    const confirmed = window.confirm(
      `An update is available for ${selected.full_title || selected.title}. Replace the installed version?`
    );
    if (!confirmed) {
      setBusy(false);
      setMsg("Citation style update left uninstalled.");
      return;
    }
    const result = await postRemoteStyle(update.install.path, {
      ...update.install.body,
      replace: true,
      preflight_token: update.install.preflight_token,
    });
    setBusy(false);
    if (!result.ok) {
      const detail = typeof result.error === "string"
        ? result.error : (result.error && result.error.message) || "update failed";
      setMsg("Couldn't update citation style: " + detail);
      return;
    }
    setCatalog(result.data);
    setMsg(`${result.data.install.style.full_title} updated.`);
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
      <div className="citation-style-install-row">
        <input ref={fileInputRef} type="file" accept=".csl,application/xml,text/xml"
          onChange={installFile} hidden />
        <button type="button" className="btn btn-ghost" disabled={installBusy}
          onClick={() => fileInputRef.current && fileInputRef.current.click()}>
          {installBusy ? "Validating…" : "Install .csl"}
        </button>
        <form className="citation-style-url-form" onSubmit={installUrl}>
          <input className="settings-input" type="url" aria-label="Citation style URL"
            placeholder="https://…/style.csl" value={urlInput}
            onChange={event => setUrlInput(event.target.value)} />
          <button type="submit" className="btn btn-ghost" disabled={!urlInput.trim() || !!remoteBusy}>
            {remoteBusy === "url" ? "Importing…" : "Import URL"}
          </button>
        </form>
      </div>
      <div className="citation-style-browser">
        <label className="settings-field-label" htmlFor="citation-style-search">Find a citation style</label>
        <form className="citation-style-search-form" onSubmit={searchRepository}>
          <input id="citation-style-search" className="settings-input" type="search"
            placeholder="Journal, discipline, acronym, or style name"
            value={query} onChange={event => setQuery(event.target.value)} />
          {view === "repository" &&
            <button type="submit" className="btn" disabled={query.trim().length < 2 || repository.status === "loading"}>
              {repository.status === "loading" ? "Searching…" : "Search"}
            </button>}
        </form>
        <div className="citation-style-views" aria-label="Citation style view">
          {[
            ["installed", "Installed"],
            ["favorites", `Favorites${catalog && catalog.favorite_style_ids.length ? ` (${catalog.favorite_style_ids.length})` : ""}`],
            ["recent", "Recent"],
            ["repository", "Repository"],
          ].map(([id, label]) =>
            <button key={id} type="button" className={view === id ? "active" : ""}
              aria-pressed={view === id} onClick={() => setView(id)}>{label}</button>)}
        </div>
        <div className="citation-style-list" role="listbox"
          aria-label={view === "repository" ? "CSL repository styles" : "Installed citation styles"}>
          {view === "repository"
            ? <>
                {repository.styles.map(style =>
                  <div className="citation-style-list-row repository" key={style.repository_id}>
                    <div className="citation-style-select">
                      <span>{style.title}</span>
                      <small>{[
                        style.short_title,
                        style.citation_format.replaceAll("-", " "),
                        ...(style.fields || []).map(field => field.replaceAll("_", " ")),
                      ].filter(Boolean).join(" · ")}</small>
                    </div>
                    <button type="button" className="btn" disabled={!!remoteBusy || !!style.installed_id}
                      onClick={() => installRemoteStyle(
                        "/citations/styles/repository/install",
                        { repository_id: style.repository_id },
                        style.repository_id,
                      )}>
                      {style.installed_id ? "Installed" : remoteBusy === style.repository_id ? "Installing…" : "Install"}
                    </button>
                  </div>)}
                {repository.status === "ready" && repository.styles.length === 0 &&
                  <div className="citation-style-empty">No repository styles match this search.</div>}
                {repository.status === "idle" &&
                  <div className="citation-style-empty">No repository search yet.</div>}
              </>
            : <>
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
              </>}
        </div>
      </div>

      <div className="citation-style-detail">
        {view === "repository"
          ? <div className="citation-style-repository-detail">
              <h3>CSL repository</h3>
              <div className="citation-style-meta">
                <span>{repository.status === "ready" ? `${repository.styles.length} results` : "Remote catalog"}</span>
              </div>
              <p className="citation-style-summary">
                Styles are provided by the{" "}
                <a href="https://citationstyles.org/" target="_blank" rel="noreferrer">Citation Style Language project</a>.
              </p>
            </div>
          : selected
          ? <>
              <div className="citation-style-detail-head">
                <div>
                  <h3>{selected.full_title || selected.title}</h3>
                  <div className="citation-style-meta">
                    <span>{selected.family === "note" ? "Note style" : selected.citation_format.replaceAll("-", " ")}</span>
                    <span>{selected.independent ? "Independent CSL" : `Depends on ${selected.parent_style}`}</span>
                    {selected.custom && <span>Personal style</span>}
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
              {selected.custom &&
                <p className="citation-style-summary">
                  Source: {citationStyleProvenanceLabel(selected, catalog)}
                  {selected.provenance.source_url &&
                    <> · <a href={selected.provenance.source_url} target="_blank" rel="noreferrer">View source</a></>}
                  {selected.provenance.installed_at && ` · Installed ${citationStyleDateLabel(selected.provenance.installed_at)}`}
                  {selected.provenance.last_checked_at && ` · Checked ${citationStyleDateLabel(selected.provenance.last_checked_at)}`}
                  {selected.provenance.locally_modified_at && ` · Edited ${citationStyleDateLabel(selected.provenance.locally_modified_at)}`}
                </p>}
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
              <div className="citation-style-personal-actions">
                {selected.custom && selected.independent &&
                  <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => setEditorStyle(selected)}>
                    Edit source
                  </button>}
                <button type="button" className="btn btn-ghost" disabled={busy}
                  onClick={() => duplicateSelected(!(selected.custom && selected.independent))}>
                  {selected.custom && selected.independent ? "Duplicate" : "Duplicate to edit"}
                </button>
                {["repository", "url"].includes(selected.provenance?.source_type) &&
                  <button type="button" className="btn btn-ghost" disabled={busy} onClick={checkSelectedUpdate}>
                    {busy ? "Checking…" : "Check for updates"}
                  </button>}
                {selected.custom &&
                  <>
                    <button type="button" className="btn btn-ghost" disabled={busy} onClick={downloadSelected}>
                      Download .csl
                    </button>
                    <button type="button" className="btn btn-ghost danger"
                      disabled={busy || selected.application_default}
                      title={selected.application_default ? "Choose another application default before removing this style" : ""}
                      onClick={removeSelected}>
                      Remove
                    </button>
                  </>}
              </div>
              {selected.custom && selected.application_default &&
                <span className="settings-sub citation-style-default-note">
                  Choose another application default before removing this style.
                </span>}
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
      {editorStyle &&
        <CitationStyleEditorModal style={editorStyle} locale={locale} onClose={() => setEditorStyle(null)}
          onSaved={data => {
            setCatalog(data);
            setSelectedId(data.editor.source.style_id);
            setPreview({ status: "ready", data: data.editor.preview });
            setEditorStyle(null);
            setMsg(data.editor.saved
              ? `${data.editor.source.full_title} saved.`
              : "Citation style source is unchanged.");
          }} />}
    </div>
  );
}
