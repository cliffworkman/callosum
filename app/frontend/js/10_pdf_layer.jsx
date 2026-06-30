// inc-91: friendly labels for the library Type filter. Known CSL types get a readable name; an unknown
// raw type is prettified ("article-newspaper" → "Article newspaper") so nothing shows as a bare slug.
const _CSL_TYPE_LABELS = {
  "article-journal": "Journal article", "article": "Article", "paper-conference": "Conference paper",
  "chapter": "Book chapter", "book": "Book", "report": "Report", "thesis": "Thesis", "dataset": "Dataset",
  "posted-content": "Preprint", "manuscript": "Manuscript", "webpage": "Web page", "review": "Review",
};
function _typeLabel(t) {
  if (_CSL_TYPE_LABELS[t]) return _CSL_TYPE_LABELS[t];
  const s = String(t || "").replace(/[-_]+/g, " ").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : String(t);
}

// AddMenu (inc 93/94) + SavedSearchMenu (inc 208) were extracted to js/10b_libmenus.jsx in inc 208 — the
// saved-search menu pushed this file over the 600-line cap (rule #1). Both are used by PaperList below via the
// shared-IIFE function hoist.

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

// Indeterminate progress bar (inc 79) — a consistent "working…" affordance for the long async jobs
// (summarize / axis score+suggest / dedup / acquire-oa / wanted re-check / my-pubs refresh). Honors
// prefers-reduced-motion (a static half-filled bar instead of the sweep).
// inc-142: a determinate `progress` prop ({current,total,label}) renders a real fill + "label  X / N" so a long
// import/scan answers "how far / is it stuck", not just "alive"; without it the bar stays the indeterminate pulse.
function ProgressBar({ label, progress }) {
  const det = progress && progress.total > 0;
  const pct = det ? Math.min(100, Math.round((progress.current / progress.total) * 100)) : null;
  const text = det ? `${progress.label} — ${progress.current} / ${progress.total}` : label;
  return (
    <div className="progress" role="progressbar" aria-busy="true" aria-label={text || "Working"}
      aria-valuenow={det ? progress.current : undefined} aria-valuemax={det ? progress.total : undefined}>
      <div className="progress-track">
        <div className={"progress-fill" + (det ? " progress-fill-det" : "")} style={det ? { width: pct + "%" } : undefined} />
      </div>
      {text ? <span className="progress-label">{text}</span> : null}
    </div>
  );
}

// inc-96: a sidebar Tags browser — the whole tag vocabulary (each with its paper count), click to filter the
// library (reuses the inc-71 tag filter). Read-only; refetches when `tagRefresh` bumps (a tag added/removed in
// Details). Stacks below the Axes panel; the sidebar scrolls as one column. No panel when there are no tags.
// inc 121: rendered inside the THEORY accordion (its "Tags" header + collapse is the accordion's now, so no
// self-collapse). Always shown with an empty-state hint when there are no tags (discoverability — was return null).
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
          : shown.map(t => (
              <button key={t.id} className={"tags-panel-item" + (!t.color && tagIsImported(t.source) ? " tags-panel-item-imported" : "")}
                title={tagSourceLabel(t.source) + " · filter the library to “" + t.name + "”"}
                onClick={() => onFilterToTag && onFilterToTag({ id: t.id, name: t.name })}>
                <span className="tags-panel-name">
                  {t.color && <span className={"tags-panel-dot tag-color-" + t.color} />}{t.name}</span>
                <span className="tags-panel-count">{t.paper_count}</span>
              </button>))}
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

// inc 121: the left pane = the brand/⚙/❓ header + the THEORY accordion (AXES / SYNTHESIS / TAGS), one open at a
// time. Sections self-register (05_panes.jsx); App owns the open-section state + the shared ctx.
function Sidebar({ conn, onOpenSettings, onOpenHelp, ctx, theoryOpen, onTheoryOpen }) {
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
      <PaneAccordion paneId="theory" ctx={ctx} openId={theoryOpen} onOpen={onTheoryOpen} />
    </div>
  );
}

// inc-103: per-card quick-copy of the paper's BibTeX. Since .paper cards are user-select:none (inc 98), this
// restores a one-click way to grab a card's citation. Reuses the inc-70 /papers/export endpoint (raw fetch —
// apiPost forces .json(); clipboard works on the 127.0.0.1 secure context). Mirrors 25_detail.jsx CiteRow.
function ClipboardIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}
function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}
function PaperCopyButton({ paperId }) {
  const [copied, setCopied] = useState(false);
  const copy = async (e) => {
    e.stopPropagation();  // don't select/open the card
    try {
      const res = await fetch(API_BASE + "/papers/export", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: [paperId], format: "bibtex" }),
      });
      if (!res.ok) { console.warn("[callosum] copy BibTeX failed:", res.status); return; }
      await navigator.clipboard.writeText(await res.text());
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) { console.warn("[callosum] copy BibTeX error:", err); }
  };
  return (
    <button
      className={"paper-copy" + (copied ? " copied" : "")} onClick={copy}
      title={copied ? "Copied BibTeX ✓" : "Copy BibTeX citation"} aria-label="Copy BibTeX citation"
    >
      {copied ? <CheckIcon /> : <ClipboardIcon />}
    </button>
  );
}

// inc 117 (My-Pubs SP1): the per-paper library card, extracted from PaperList so the My Publications tab can
// render the same aesthetic + parity (#13). `selecting` shows the copy button + checkbox; `footExtra` lets a
// caller append context buttons (the library passes its focus/trash buttons here).
function PaperCard({ paper: p, selecting, isSelected, onSelect, onOpen, checked, onToggleCheck, findings, footExtra, citeInfo }) {
  const unresolved = needsMetadata(p);
  return (
    <div
      className={"paper" + (isSelected ? " sel" : "")}
      onClick={() => onSelect && onSelect(p.id)}
      onDoubleClick={() => onOpen && onOpen(p)}  // inc-98: always open; .paper has user-select:none (copy from Details)
      title="Double-click to open the PDF · drag onto an axis to add it"
      draggable  // A6 (inc 206): drag a card onto an axis card (in the AXES pane) to manually add it
      onDragStart={e => { e.dataTransfer.setData("application/x-callosum-paper", String(p.id)); e.dataTransfer.effectAllowed = "copy"; }}
    >
      {selecting && <PaperCopyButton paperId={p.id} />}
      {selecting &&
        <input
          type="checkbox" className="paper-select" checked={!!checked}
          title="Select"
          onClick={e => e.stopPropagation()}
          onChange={() => onToggleCheck && onToggleCheck(p.id)}
        />}
      <p className="paper-title">{p.title || <span className="placeholder">Untitled</span>}</p>
      <div className="paper-meta">
        {unresolved
          ? <span className="placeholder">metadata not yet resolved</span>
          : <>
              {p.authors && p.authors.length > 0 && <span className="paper-authors">{fmtAuthors(p.authors)}</span>}
              {p.year && <span>· {p.year}</span>}
              {p.venue && <span className="paper-venue">· {p.venue}</span>}
            </>}
      </div>
      <div className="paper-foot">
        <span className={"tier " + tierClass(p.processing_tier)}>{tierLabel(p.processing_tier)}</span>
        {p.attachment_count > 0 && <span className="chip">{p.attachment_count} file{p.attachment_count > 1 ? "s" : ""}</span>}
        {unresolved && <span className="needs-doi">needs DOI</span>}
        {/* inc 130: findings — a neutral FactMark + the work-state "N to review" badge (zero shows nothing). */}
        {findings && findings.has_facts && <span className="fact-mark fact-mark-card" title="Has a fact finding (e.g. retracted)">◆ fact</span>}
        {findings && findings.unreviewed_count > 0 && <span className="finding-badge" title="Unreviewed candidate findings to review">{findings.unreviewed_count} to review</span>}
        {/* inc 119 (SP3 #14): OpenAlex cited-by count; clickable (→ citing list) once the work id is known. */}
        {citeInfo && (citeInfo.workId
          ? <button className="paper-cite" title="Papers that cite this, per OpenAlex — click to view"
              onClick={e => { e.stopPropagation(); citeInfo.onOpenCiting(citeInfo.workId, p); }}>
              {citeInfo.count} cited-by
            </button>
          : <span className="paper-cite paper-cite-static"
              title={citeInfo.asOf ? `Cited by ${citeInfo.count}, per OpenAlex · as of ${String(citeInfo.asOf).slice(0, 10)}` : "Cited-by count, per OpenAlex"}>{citeInfo.count} cited-by</span>)}
        {footExtra}
      </div>
    </div>
  );
}

function PaperList({ state, query, onQuery, selected, onSelect, page, onPage, total, onOpenPdf,
                    focusAxis, focusMembers, focusPending, onToggleFocusPaper, onSaveFocus, onCancelFocus,
                    trashView, selectedLibraryIds, librarySort, onSortChange, librarySearchField, onSearchFieldChange,
                    libraryItemType, itemTypes, onItemTypeChange, onToggleLibrarySelect, onClearLibrarySelect, onBulkDelete,
                    onBulkSummarize, onBulkPcurve, onBulkMerge, onBulkExport, onBulkBibliography, onSelectAll, libraryAxisFilter, onClearAxisFilter,
                    libraryTagFilter, onClearTagFilter,
                    libraryNeedsReview, onToggleNeedsReview, onClearNeedsReview, librarySignalFilter, onClearSignalFilter,
                    statcheckFlagged, onShowStatcheckFlagged, retractionFlagged, onShowRetractionFlagged,
                    findingsToReview, onShowFindingsToReview, findingsByPaper,
                    onToggleTrash, onRestore, onPurge, onEmptyTrash, onFindDuplicates, onOpenWanted, onOpenGaps, onOpenScan, onOpenImport,
                    onCitationsRefreshed,
                    savedSearches, onApplySavedSearch, onSaveSearch, onDeleteSavedSearch }) {
  const [bulkFocus, setBulkFocus] = useState("");  // inc-145: optional focus query for the multi-paper synthesis
  const pendingOps = focusAxis ? Object.values(focusPending || {}) : [];
  const pendingAdd = pendingOps.filter(o => o === "add").length;
  const pendingRemove = pendingOps.filter(o => o === "remove").length;
  const selecting = !focusAxis && !trashView;            // checkbox multi-select mode (inc 54)
  const selCount = selectedLibraryIds ? selectedLibraryIds.size : 0;
  // inc-209 (A3): full-text PDF search mode — the "Full text" scope + a query swaps the library list for a
  // self-contained snippet-hit list (FulltextResults does its own fetch; 40_app is untouched).
  const fulltextMode = librarySearchField === "fulltext" && !!(query || "").trim();
  // inc-210 (A2): the freshest cited-by "as of" across the loaded list → shown on the Citations control (attribution).
  const maxCitedAsOf = (state.papers || []).reduce((m, p) => (p.cited_by_as_of && (!m || p.cited_by_as_of > m) ? p.cited_by_as_of : m), null);
  const [citeStyles, setCiteStyles] = useState([]);  // inc-106: bundled CSL styles for the bulk "bibliography…" picker
  useEffect(() => { api("/citations/styles").then(r => { if (r.ok) setCiteStyles(r.data.styles || []); }); }, []);
  return (
    <div className="pane-list-body">
      <div className="pane-head">
        <div className="lib-head">
          <p className="eyebrow">{trashView ? "Trash" : "Library"}</p>
          <span className="lib-head-actions">
            {!trashView && <AddMenu onScan={onOpenScan} onImport={onOpenImport} />}
            {!trashView && <SavedSearchMenu searches={savedSearches} onApply={onApplySavedSearch} onSave={onSaveSearch} onDelete={onDeleteSavedSearch} />}
            {!trashView && statcheckFlagged > 0 && librarySignalFilter !== "statcheck-inconsistent" &&
              <button className="trash-toggle statcheck-chip" onClick={onShowStatcheckFlagged}
                title="Papers with a reporting inconsistency from the last statistics check — usually innocent; a list to review">⚠ {statcheckFlagged} flagged</button>}
            {!trashView && retractionFlagged > 0 && librarySignalFilter !== "retraction-retracted" &&
              <button className="trash-toggle retraction-chip" onClick={onShowRetractionFlagged}
                title="Papers a registry records as retracted — verify before citing">⚠ {retractionFlagged} retracted</button>}
            {!trashView && findingsToReview > 0 && librarySignalFilter !== "needs-review" &&
              <button className="trash-toggle findings-chip" onClick={onShowFindingsToReview}
                title="Findings you haven't reviewed yet — open each paper's Review section">📋 {findingsToReview} to review</button>}
            {!trashView &&
              <button className="trash-toggle" onClick={onToggleNeedsReview}
                title={libraryNeedsReview ? "Back to the full library" : "Papers whose metadata still needs review — raw imports, unresolved DOIs"}>
                {libraryNeedsReview ? "← Library" : "Unsorted"}</button>}
            {!trashView &&
              <button className="trash-toggle" onClick={onOpenWanted} title="Papers you want an OA copy of — re-check open-access sources">Wanted</button>}
            {!trashView &&
              <button className="trash-toggle" onClick={onOpenGaps} title="Works related to several of your papers that you don't have yet — references you cite, or newer work citing you">Gaps</button>}
            {!trashView &&
              <button className="trash-toggle" onClick={onFindDuplicates} title="Scan for likely duplicates">Duplicates</button>}
            {!trashView && <CitationCountsButton asOf={maxCitedAsOf} onRefreshed={onCitationsRefreshed} />}
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
            <div className="focus-card-head">Filtered to axis <b>{libraryAxisFilter.label}</b>{libraryAxisFilter.hideUncertain ? " · assigned only" : ""}</div>
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
        {libraryNeedsReview &&
          <div className="focus-card">
            <div className="focus-card-head">Unsorted — papers whose metadata still needs review (raw imports, unresolved DOIs)</div>
            <div className="focus-card-foot">
              <span className="focus-count">{state.status === "ready" ? `${state.papers.length} shown` : ""}</span>
              <button className="axis-link" onClick={onClearNeedsReview}>clear</button>
            </div>
          </div>}
        {librarySignalFilter === "statcheck-inconsistent" &&
          <div className="focus-card">
            <div className="focus-card-head">Reporting inconsistencies — papers where a reported p-value didn't recompute (statcheck). Usually innocent (typos, rounding); a list to review, not a verdict.</div>
            <div className="focus-card-foot">
              <span className="focus-count">{state.status === "ready" ? `${state.papers.length} shown` : ""}</span>
              <button className="axis-link" onClick={onClearSignalFilter}>clear</button>
            </div>
          </div>}
        {librarySignalFilter === "retraction-retracted" &&
          <div className="focus-card">
            <div className="focus-card-head">Retracted — papers a registry (Crossref / OpenAlex) records as retracted. Verify before citing; open each paper's Review section for the notice.</div>
            <div className="focus-card-foot">
              <span className="focus-count">{state.status === "ready" ? `${state.papers.length} shown` : ""}</span>
              <button className="axis-link" onClick={onClearSignalFilter}>clear</button>
            </div>
          </div>}
        {librarySignalFilter === "needs-review" &&
          <div className="focus-card">
            <div className="focus-card-head">To review — papers with findings you haven't reviewed yet. Open each paper's Review section (METHODS) to Confirm or Note each one.</div>
            <div className="focus-card-foot">
              <span className="focus-count">{state.status === "ready" ? `${state.papers.length} shown` : ""}</span>
              <button className="axis-link" onClick={onClearSignalFilter}>clear</button>
            </div>
          </div>}
        <div className="searchbar">
          <input
            placeholder={fulltextMode || librarySearchField === "fulltext" ? "search inside your PDFs…" : "Search title, author, journal…"}
            value={query}
            onChange={e => onQuery(e.target.value)}
            spellCheck={false}
          />
          <select className="lib-sort" value={librarySearchField} onChange={e => onSearchFieldChange(e.target.value)} title="Search in">
            <option value="all">All fields</option>
            <option value="title">Title</option>
            <option value="author">Author</option>
            <option value="journal">Journal</option>
            <option value="fulltext">Full text (PDFs)</option>
          </select>
          {itemTypes && itemTypes.length > 0 &&
            <select className="lib-sort" value={libraryItemType} onChange={e => onItemTypeChange(e.target.value)} title="Filter by type">
              <option value="">All types</option>
              {itemTypes.map(t => <option key={t.item_type} value={t.item_type}>{_typeLabel(t.item_type)} ({t.count})</option>)}
            </select>}
          <span className="lib-sort-label">Sort</span>
          <select className="lib-sort" value={librarySort} onChange={e => onSortChange(e.target.value)} title="Sort the library">
            <option value="added">Date added</option>
            <option value="recent">Recently added</option>
            <option value="title">Title (A–Z)</option>
            <option value="title_desc">Title (Z–A)</option>
            <option value="year_desc">Year (newest)</option>
            <option value="year_asc">Year (oldest)</option>
            <option value="author">Author (A–Z)</option>
            <option value="author_desc">Author (Z–A)</option>
            <option value="citations_desc">Most cited</option>
          </select>
        </div>
        {state.status === "ready" && !fulltextMode &&
          <div className="list-meta">
            {total != null ? `${total} shown` : `${state.papers.length} shown`}
            {query ? ` · filtered by “${query}”` : ""}
            {` · page ${page + 1}`}
            {selecting && state.papers.length > 0 &&
              <button className="lib-select-all" onClick={() => onSelectAll(state.papers.map(p => p.id))}>select all</button>}
          </div>}
      </div>

      {fulltextMode && <FulltextResults query={query} onOpenPdf={onOpenPdf} />}
      {!fulltextMode && <>

      {selecting && selCount > 0 &&
        <div className="axis-bulk-bar">
          <span className="axis-bulk-count">{selCount} selected</span>
          <input className="bulk-focus" placeholder="Focus on… (optional)" value={bulkFocus}
            title="Optionally focus the synthesis on a question — leave blank for a general summary"
            onChange={e => setBulkFocus(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") onBulkSummarize(bulkFocus); }} />
          <button className="axis-link" onClick={() => onBulkSummarize(bulkFocus)} title="Generate a verified synthesis of the selected papers — focused on your question if you typed one">summarize</button>
          <button className="axis-link" onClick={onBulkPcurve} title="Run a p-curve (evidential value) over the selected papers — collection-level, never per-paper">p-curve</button>
          {selCount >= 2 &&
            <button className="axis-link" onClick={onBulkMerge} title="Merge the selected papers into one record — keeps every PDF, link, tag, and highlight; the others move to Trash">merge</button>}
          <select className="bulk-export" value="" title="Export citations for the selected papers"
            onChange={e => { if (e.target.value) { onBulkExport(e.target.value); e.target.value = ""; } }}>
            <option value="" disabled>export…</option>
            <option value="bibtex">BibTeX (.bib)</option>
            <option value="ris">RIS (.ris)</option>
            <option value="csl-json">CSL-JSON</option>
          </select>
          {citeStyles.length > 0 &&
            <select className="bulk-export" value="" title="Download a formatted bibliography for the selected papers"
              onChange={e => { if (e.target.value) { onBulkBibliography(e.target.value); e.target.value = ""; } }}>
              <option value="" disabled>bibliography…</option>
              {citeStyles.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}
            </select>}
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
        const fStaged = focusAxis ? (focusPending || {})[p.id] : undefined;
        const fIn = fStaged ? fStaged === "add" : !!(focusAxis && focusMembers && focusMembers.has(p.id));
        const footExtra = <>
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
        </>;
        return (
          <PaperCard
            key={p.id} paper={p} selecting={selecting} isSelected={selected === p.id}
            onSelect={onSelect} onOpen={onOpenPdf}
            checked={selectedLibraryIds && selectedLibraryIds.has(p.id)} onToggleCheck={onToggleLibrarySelect}
            findings={findingsByPaper && findingsByPaper[p.id]}
            citeInfo={p.cited_by_count != null ? { count: p.cited_by_count, asOf: p.cited_by_as_of } : undefined}
            footExtra={footExtra}
          />
        );
      })}

      {state.status === "ready" && (page > 0 || state.papers.length === PAGE_SIZE) &&
        <div className="pginate">
          <button disabled={page === 0} onClick={() => onPage(page - 1)}>← Prev</button>
          <button disabled={state.papers.length < PAGE_SIZE} onClick={() => onPage(page + 1)}>Next →</button>
        </div>}
      </>}
    </div>
  );
}

