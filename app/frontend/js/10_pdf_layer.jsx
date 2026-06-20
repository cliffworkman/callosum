function clearUserAnnotations(host) {
  if (!host) return;
  host.querySelectorAll(".pdf-user-highlight-group, .pdf-user-highlight, .pdf-synthesis-outline").forEach(node => node.remove());
}

// Draw all user highlights into each page's annotation layer using the SAME
// percentage-of-source-dimensions transform as citation overlays (increment 29),
// so they stay aligned across zoom. Separate layer from citation overlays so the
// two systems never clobber each other.
function renderUserAnnotations(host, annots) {
  if (!host) return;
  clearUserAnnotations(host);
  if (!Array.isArray(annots) || annots.length === 0) return;
  annots.forEach(ann => {
    const pageEl = host.querySelector(`[data-page="${ann.page}"]`);
    if (!pageEl) return;
    const layer = pageEl.querySelector(".pdf-annotation-layer");
    if (!layer) return;
    const sourceWidth = Number(pageEl.dataset.sourceWidth);
    const sourceHeight = Number(pageEl.dataset.sourceHeight);
    if (!(sourceWidth > 0 && sourceHeight > 0)) return;
    if (Number(pageEl.dataset.rotation || 0) !== 0) return;  // match citation rotated-page limitation
    const hasNote = !!(ann.note && String(ann.note).trim());
    // One isolated group per annotation. Its per-line rects are painted OPAQUE so they
    // union cleanly (overlapping same-color rects don't double); the group then composites
    // translucently via multiply (see .pdf-user-highlight-group CSS) — uniform opacity on
    // every row, darkening toward the page text rather than veiling it.
    const group = document.createElement("div");
    group.className = "pdf-user-highlight-group";
    group.dataset.annotationId = String(ann.id);
    const onPageRects = normalizeBboxes(ann.bboxes_json)
      .filter(rect => rect.page == null || rect.page === Number(ann.page));
    onPageRects.forEach((rect, ri) => {
        const box = document.createElement("div");
        box.className = "pdf-user-highlight";
        // Mark only the first rect of a note-bearing annotation, so a multi-line
        // highlight shows a single dot rather than one per line fragment.
        if (hasNote && ri === 0) box.classList.add("has-note");
        box.dataset.annotationId = String(ann.id);
        box.style.background = hexToRgba(ann.color, 1);  // opaque; translucency comes from the group
        box.style.left = `${Math.max(0, Math.min(100, (rect.x0 / sourceWidth) * 100))}%`;
        box.style.top = `${Math.max(0, Math.min(100, (rect.y0 / sourceHeight) * 100))}%`;
        box.style.width = `${Math.max(0, Math.min(100, ((rect.x1 - rect.x0) / sourceWidth) * 100))}%`;
        box.style.height = `${Math.max(0, Math.min(100, ((rect.y1 - rect.y0) / sourceHeight) * 100))}%`;
        box.title = hasNote ? `Note: ${ann.note}` : (ann.anchor_text ? `Highlight: ${ann.anchor_text}` : "Highlight");
        group.appendChild(box);
      });
    if (group.childElementCount > 0) {
      layer.appendChild(group);
      // Synthesis-sourced highlights get a single dashed outline tracing the passage
      // bounds, so a machine-saved highlight stays distinguishable from a hand-made one
      // even after a recolor. Drawn as a layer sibling (not inside the multiply group)
      // so the dashed border renders crisply; same percentage transform as the rects.
      if (ann.source === "synthesis") {
        const x0 = Math.min(...onPageRects.map(r => r.x0));
        const y0 = Math.min(...onPageRects.map(r => r.y0));
        const x1 = Math.max(...onPageRects.map(r => r.x1));
        const y1 = Math.max(...onPageRects.map(r => r.y1));
        const outline = document.createElement("div");
        outline.className = "pdf-synthesis-outline";
        outline.dataset.annotationId = String(ann.id);
        outline.style.left = `${Math.max(0, Math.min(100, (x0 / sourceWidth) * 100))}%`;
        outline.style.top = `${Math.max(0, Math.min(100, (y0 / sourceHeight) * 100))}%`;
        outline.style.width = `${Math.max(0, Math.min(100, ((x1 - x0) / sourceWidth) * 100))}%`;
        outline.style.height = `${Math.max(0, Math.min(100, ((y1 - y0) / sourceHeight) * 100))}%`;
        outline.title = "Saved from synthesis";
        layer.appendChild(outline);
      }
    }
  });
}

// Capture short verbatim context around a selection for durable re-anchoring
// (stored now; re-anchoring recovery is a later increment).
function selectionContext(textLayer, range, len = 40) {
  let prefix = "", suffix = "";
  try {
    const pre = document.createRange();
    pre.setStart(textLayer, 0);
    pre.setEnd(range.startContainer, range.startOffset);
    prefix = pre.toString().slice(-len);
  } catch (e) { /* ignore */ }
  try {
    const suf = document.createRange();
    suf.setStart(range.endContainer, range.endOffset);
    suf.setEnd(textLayer, textLayer.childNodes.length);
    suffix = suf.toString().slice(0, len);
  } catch (e) { /* ignore */ }
  return { prefix, suffix };
}

function fmtDateTime(value) {
  if (!value) return "unknown time";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

// ─────────────────────────────────────────────────────────────

function Sidebar({ conn, onSelectPaper, selectedPaper, onOpenPaper, onOpenSettings, onOpenHelp, onEnterFocus, onFilterToAxis, axisRefresh }) {
  return (
    <div className="pane pane-sidebar">
      <div className="pane-head">
        <button className="icon-help" title="Help & tips" onClick={onOpenHelp}>?</button>
        <button className="icon-gear" title="Settings" onClick={onOpenSettings}>⚙</button>
        <div className="brand">
          <div className={"brand-logo" + (conn.state === "ok" ? " connected" : "")} role="img" aria-label="Callosum" title={conn.state === "ok" ? ("Connected" + (conn.version ? " (" + conn.version + ")" : "")) : conn.state === "bad" ? "Disconnected" : "Connecting..."} />
          <h1>Callosum</h1>
        </div>
      </div>
      <AxesPanel onSelectPaper={onSelectPaper} selectedPaper={selectedPaper} onOpenPaper={onOpenPaper} onEnterFocus={onEnterFocus} onFilterToAxis={onFilterToAxis} axisRefresh={axisRefresh} />
    </div>
  );
}

function PaperList({ state, query, onQuery, selected, onSelect, page, onPage, total, onOpenPdf,
                    focusAxis, focusMembers, focusPending, onToggleFocusPaper, onSaveFocus, onCancelFocus,
                    trashView, selectedLibraryIds, librarySort, onSortChange, onToggleLibrarySelect, onClearLibrarySelect, onBulkDelete,
                    onBulkSummarize, onBulkExport, onSelectAll, libraryAxisFilter, onClearAxisFilter,
                    libraryTagFilter, onClearTagFilter,
                    onToggleTrash, onRestore, onPurge, onEmptyTrash, onFindDuplicates }) {
  const pendingOps = focusAxis ? Object.values(focusPending || {}) : [];
  const pendingAdd = pendingOps.filter(o => o === "add").length;
  const pendingRemove = pendingOps.filter(o => o === "remove").length;
  const selecting = !focusAxis && !trashView;            // checkbox multi-select mode (inc 54)
  const selCount = selectedLibraryIds ? selectedLibraryIds.size : 0;
  return (
    <div className="pane-list-body">
      <div className="pane-head">
        <div className="lib-head">
          <p className="eyebrow">{trashView ? "Trash" : "Library"}</p>
          <span className="lib-head-actions">
            {!trashView &&
              <button className="trash-toggle" onClick={onFindDuplicates} title="Scan for likely duplicates">Duplicates</button>}
            {trashView && state.status === "ready" && state.papers.length > 0 &&
              <button className="trash-toggle danger" onClick={onEmptyTrash}
                title="Permanently delete every paper in Trash — cannot be undone">Empty Trash</button>}
            <button className="trash-toggle" onClick={onToggleTrash} title={trashView ? "Back to the library" : "View deleted papers"}>
              {trashView ? "← Library" : "Trash"}
            </button>
          </span>
        </div>
        {focusAxis &&
          <div className="focus-card">
            <div className="focus-card-head">Adding to <b>{focusAxis.label}</b> — click <b>+ add</b> on the papers below.</div>
            <div className="focus-card-foot">
              <span className="focus-count">
                {pendingAdd || pendingRemove ? `+${pendingAdd} −${pendingRemove} staged` : "no changes yet"}
              </span>
              <button className="axis-btn" disabled={!(pendingAdd || pendingRemove)} onClick={onSaveFocus}>Save</button>
              <button className="axis-link" onClick={onCancelFocus}>Cancel</button>
            </div>
          </div>}
        {libraryAxisFilter &&
          <div className="focus-card">
            <div className="focus-card-head">Filtered to axis <b>{libraryAxisFilter.label}</b></div>
            <div className="focus-card-foot">
              <span className="focus-count">{state.status === "ready" ? `${state.papers.length} shown` : ""}</span>
              <button className="axis-link" onClick={onClearAxisFilter}>clear</button>
            </div>
          </div>}
        {libraryTagFilter &&
          <div className="focus-card">
            <div className="focus-card-head">Filtered to tag <b>{libraryTagFilter.name}</b></div>
            <div className="focus-card-foot">
              <span className="focus-count">{state.status === "ready" ? `${state.papers.length} shown` : ""}</span>
              <button className="axis-link" onClick={onClearTagFilter}>clear</button>
            </div>
          </div>}
        <div className="searchbar">
          <input
            placeholder="Search title or author…"
            value={query}
            onChange={e => onQuery(e.target.value)}
            spellCheck={false}
          />
        </div>
        <div className="lib-sort-row">
          <span className="lib-sort-label">Sort</span>
          <select className="lib-sort" value={librarySort} onChange={e => onSortChange(e.target.value)} title="Sort the library">
            <option value="added">Date added</option>
            <option value="recent">Recently added</option>
            <option value="title">Title (A–Z)</option>
            <option value="year_desc">Year (newest)</option>
            <option value="year_asc">Year (oldest)</option>
            <option value="author">Author (A–Z)</option>
          </select>
        </div>
        {state.status === "ready" &&
          <div className="list-meta">
            {total != null ? `${total} shown` : `${state.papers.length} shown`}
            {query ? ` · filtered by “${query}”` : ""}
            {` · page ${page + 1}`}
            {selecting && state.papers.length > 0 &&
              <button className="lib-select-all" onClick={() => onSelectAll(state.papers.map(p => p.id))}>select all</button>}
          </div>}
      </div>

      {selecting && selCount > 0 &&
        <div className="axis-bulk-bar">
          <span className="axis-bulk-count">{selCount} selected</span>
          <button className="axis-link" onClick={onBulkSummarize} title="Generate a verified synthesis of the selected papers">summarize</button>
          <select className="bulk-export" value="" title="Export citations for the selected papers"
            onChange={e => { if (e.target.value) { onBulkExport(e.target.value); e.target.value = ""; } }}>
            <option value="" disabled>export…</option>
            <option value="bibtex">BibTeX (.bib)</option>
            <option value="ris">RIS (.ris)</option>
            <option value="csl-json">CSL-JSON</option>
          </select>
          <button className="axis-link axis-danger" onClick={onBulkDelete}>delete</button>
          <button className="axis-link" onClick={onClearLibrarySelect}>clear</button>
        </div>}

      {state.status === "loading" &&
        Array.from({ length: 8 }).map((_, i) => (
          <div className="skel" key={i}>
            <div className="bar" style={{ width: "70%", marginBottom: 8 }}></div>
            <div className="bar" style={{ width: "45%" }}></div>
          </div>
        ))}

      {state.status === "error" &&
        <div className="errbox">
          <b>Can't load the library.</b><br />
          {state.error}<br /><br />
          Start the backend, then reload:<br />
          <code>uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080</code>
        </div>}

      {state.status === "ready" && state.papers.length === 0 &&
        <div className="state">
          <div className="big">{trashView ? "Trash is empty." : `No papers${query ? " match that search" : " in this library"}.`}</div>
          {trashView ? "Deleted papers appear here and can be restored." : (query ? "Try a different term." : "Ingest PDFs or import a Zotero library to begin.")}
        </div>}

      {state.status === "ready" && state.papers.map(p => {
        const unresolved = needsMetadata(p);
        const fStaged = focusAxis ? (focusPending || {})[p.id] : undefined;
        const fIn = fStaged ? fStaged === "add" : !!(focusAxis && focusMembers && focusMembers.has(p.id));
        return (
          <div
            key={p.id}
            className={"paper" + (selected === p.id ? " sel" : "")}
            onClick={() => onSelect(p.id)}
            onDoubleClick={() => onOpenPdf && onOpenPdf(p)}
            title="Double-click to open the PDF"
          >
            {selecting &&
              <input
                type="checkbox" className="paper-select" checked={selectedLibraryIds.has(p.id)}
                title="Select for delete"
                onClick={e => e.stopPropagation()}
                onChange={() => onToggleLibrarySelect(p.id)}
              />}
            <p className="paper-title">{p.title || <span className="placeholder">Untitled</span>}</p>
            <div className="paper-meta">
              {unresolved
                ? <span className="placeholder">metadata not yet resolved</span>
                : <>
                    {p.authors && p.authors.length > 0 &&
                      <span className="paper-authors">{fmtAuthors(p.authors)}</span>}
                    {p.year && <span>· {p.year}</span>}
                    {p.venue && <span className="paper-venue">· {p.venue}</span>}
                  </>}
            </div>
            <div className="paper-foot">
              <span className={"tier " + tierClass(p.processing_tier)}>{tierLabel(p.processing_tier)}</span>
              <span className="chip">{p.chunk_count} chunks</span>
              {p.attachment_count > 0 && <span className="chip">{p.attachment_count} file{p.attachment_count > 1 ? "s" : ""}</span>}
              {unresolved && <span className="needs-doi">needs DOI</span>}
              {focusAxis &&
                <button
                  className={"paper-axis-add" + (fIn ? " in" : "") + (fStaged ? " staged" : "")}
                  title={fIn ? "On this axis — click to remove" : "Add to this axis"}
                  onClick={e => { e.stopPropagation(); onToggleFocusPaper(p.id); }}
                >
                  {fStaged === "add" ? "✓ staged" : fStaged === "remove" ? "− staged" : fIn ? "✓ in axis" : "+ add"}
                </button>}
              {trashView &&
                <button className="paper-restore" title="Restore from Trash"
                  onClick={e => { e.stopPropagation(); onRestore(p.id); }}>Restore</button>}
              {trashView &&
                <button className="paper-restore danger" title="Permanently delete — cannot be undone"
                  onClick={e => { e.stopPropagation(); onPurge(p.id); }}>Delete forever</button>}
            </div>
          </div>
        );
      })}

      {state.status === "ready" && (page > 0 || state.papers.length === PAGE_SIZE) &&
        <div className="pginate">
          <button disabled={page === 0} onClick={() => onPage(page - 1)}>← Prev</button>
          <button disabled={state.papers.length < PAGE_SIZE} onClick={() => onPage(page + 1)}>Next →</button>
        </div>}
    </div>
  );
}

