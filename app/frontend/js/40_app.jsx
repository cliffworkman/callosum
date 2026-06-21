// --- resizable + collapsible side panels -------------------------------------------------
function _loadLayout(key, fallback) {
  try { const v = window.localStorage.getItem(key); return v == null ? fallback : v; } catch (e) { return fallback; }
}
function _saveLayout(key, value) {
  try { window.localStorage.setItem(key, String(value)); } catch (e) { /* ignore */ }
}
function _clampW(w, lo, hi) { return Math.max(lo, Math.min(hi, w)); }
function _beginDrag(e, onMove) {
  e.preventDefault();
  const move = (ev) => onMove(ev.clientX, ev.clientY);  // horizontal callers use x; the vertical split uses y
  const up = () => {
    document.removeEventListener("mousemove", move);
    document.removeEventListener("mouseup", up);
    document.body.style.userSelect = "";
  };
  document.addEventListener("mousemove", move);
  document.addEventListener("mouseup", up);
  document.body.style.userSelect = "none";  // no text selection while dragging
}

// Divider between a side panel and the center: drag the full-height grip to resize, click the
// chevron to collapse/expand the panel (so the user can focus on the PDF viewer).
function Divider({ side, open, onToggle, onDragStart }) {
  const chevron = side === "left" ? (open ? "‹" : "›") : (open ? "›" : "‹");
  return (
    <div className={"divider divider-" + side + (open ? "" : " collapsed")}>
      {open && <div className="divider-grip" onMouseDown={onDragStart} title="Drag to resize" />}
      <button className="divider-toggle" onClick={onToggle} title={open ? "Collapse panel" : "Expand panel"}>{chevron}</button>
    </div>
  );
}

function App() {
  const [conn, setConn] = useState({ state: "wait" });

  // theme (light/dark) — the no-flash bootstrap in index.html already set data-theme on <html>; mirror it
  // into state, and the Settings toggle writes the attribute + localStorage.
  const [theme, setThemeState] = useState(() => {
    try { return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light"; }
    catch (e) { return "light"; }
  });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const setTheme = useCallback((next) => {
    setThemeState(next);
    try { document.documentElement.setAttribute("data-theme", next); localStorage.setItem("callosum.theme", next); } catch (e) { /* ignore */ }
  }, []);
  // Axis default: start each axis card with its uncertain papers hidden (the inc-51 👁, as a Settings default).
  const [hideUncertainDefault, setHideUncertainDefaultState] = useState(() => _loadLayout("callosum.hideUncertainDefault", "0") === "1");
  const setHideUncertainDefault = useCallback((on) => {
    setHideUncertainDefaultState(on);
    _saveLayout("callosum.hideUncertainDefault", on ? "1" : "0");
  }, []);

  // side-panel layout (persisted): widths + collapsed state.
  const [leftW, setLeftW] = useState(() => Number(_loadLayout("callosum.leftW", 270)) || 270);
  const [rightW, setRightW] = useState(() => Number(_loadLayout("callosum.rightW", 400)) || 400);
  const [leftOpen, setLeftOpen] = useState(() => _loadLayout("callosum.leftOpen", "1") !== "0");
  const [rightOpen, setRightOpen] = useState(() => _loadLayout("callosum.rightOpen", "1") !== "0");
  useEffect(() => { _saveLayout("callosum.leftW", leftW); }, [leftW]);
  useEffect(() => { _saveLayout("callosum.rightW", rightW); }, [rightW]);
  useEffect(() => { _saveLayout("callosum.leftOpen", leftOpen ? "1" : "0"); }, [leftOpen]);
  useEffect(() => { _saveLayout("callosum.rightOpen", rightOpen ? "1" : "0"); }, [rightOpen]);

  const [listState, setListState] = useState({ status: "loading", papers: [] });
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState(null);

  // tabbed library frame: a persistent Library tab plus open PDF tabs.
  const [tabs, setTabs] = useState([]);            // [{ key, paperId, title, target }]
  const [activeTab, setActiveTab] = useState("library");
  // Bumped after a synthesis highlight is saved, so an already-open PdfViewer refetches
  // its annotations and shows the new highlight without a reload (see PdfViewer).
  const [annoRefresh, setAnnoRefresh] = useState(0);

  // Library focus-mode (inc-50 C): add/remove papers to an axis from the library list. Changes are
  // STAGED (focusPending: paperId → "add"|"remove", relative to focusMembers) and committed on Save.
  const [focusAxis, setFocusAxis] = useState(null);                    // {id, label} | null
  const [focusMembers, setFocusMembers] = useState(() => new Set());   // paper ids already on the axis
  const [focusPending, setFocusPending] = useState({});                // staged changes
  const [axisRefresh, setAxisRefresh] = useState(0);                   // bumped after Save → AxesPanel reloads

  // Library delete (inc-54 D): soft-delete multi-select + a Trash view. selectedLibraryIds = checkbox
  // multi-select; trashView toggles the live/Trash listing; libRefresh forces a reload after delete/restore.
  const [selectedLibraryIds, setSelectedLibraryIds] = useState(() => new Set());
  const [pendingSummarize, setPendingSummarize] = useState(null);  // inc-62: drives the Synthesis pane to summarize a library selection
  const [libraryAxisFilter, setLibraryAxisFilter] = useState(null);  // inc-63: {id, label} → library shows only this axis's papers
  const [libraryTagFilter, setLibraryTagFilter] = useState(null);    // inc-71: {id, name} → library shows only this tag's papers
  const [trashView, setTrashView] = useState(false);
  const [librarySort, setLibrarySort] = useState("added");  // inc-69: library ordering (added/recent/title/year_*/author)
  const [libRefresh, setLibRefresh] = useState(0);
  const [duplicatesOpen, setDuplicatesOpen] = useState(false);  // inc-56 duplicate-detection modal
  const [wantedOpen, setWantedOpen] = useState(false);          // inc-76 wanted-list / OA re-check modal

  const openPdf = useCallback((paper, target) => {
    const key = "pdf:" + paper.id;
    const title = paper.title || ("Paper " + paper.id);
    setTabs(prev => {
      const found = prev.some(t => t.key === key);
      const nextTarget = target === undefined ? null : target;
      if (!found) return [...prev, { key, paperId: paper.id, title, target: nextTarget }];
      return prev.map(t => t.key === key ? { ...t, title, target: nextTarget } : t);
    });
    setActiveTab(key);  // focuses the existing tab if already open
  }, []);

  const openCitation = useCallback((citation) => {
    const target = citationTarget(citation);
    if (!target) return;
    openPdf({ id: target.paperId, title: target.paperTitle }, target);
  }, [openPdf]);

  // Save a verified, exact-coordinate citation passage as a durable annotation
  // (source="synthesis"). Re-checks the honesty contract here too, so the precise-save
  // path can never be reached for region/null/flagged citations. Does NOT force-open the
  // PDF tab (the reader stays in synthesis); an already-open viewer refreshes via the nonce.
  const saveCitationHighlight = useCallback(async (citation) => {
    if (!citation || citation.paper_id == null) return { ok: false, error: "No paper for this citation." };
    const bboxes = normalizeBboxes(citation.bbox_json);
    if (citation.coordinate_precision !== "exact" || citation.status !== "verified" || bboxes.length === 0) {
      return { ok: false, error: "Only verified, exact-coordinate citations can be saved as a precise highlight." };
    }
    const r = await apiPost(`/papers/${citation.paper_id}/annotations`, {
      page: citation.page_start,
      color: HIGHLIGHT_COLORS[0],
      bboxes,
      anchor_text: citation.quote || "",
      source: "synthesis",
    });
    if (r.ok) setAnnoRefresh(n => n + 1);
    return r;
  }, []);

  const closeTab = useCallback((key) => {
    setTabs(prev => prev.filter(t => t.key !== key));
    setActiveTab(prev => (prev === key ? "library" : prev));
  }, []);

  const enterFocus = useCallback((axis) => {
    setFocusAxis(axis);
    setLibraryAxisFilter(null);  // the add-papers focus replaces any view filter
    setLibraryTagFilter(null);
    setFocusPending({});
    setFocusMembers(new Set());
    setActiveTab("library");  // bring the library list (where the add buttons live) into view
    api(`/axes/${axis.id}/clusters`).then(r => {
      if (r.ok) setFocusMembers(new Set((r.data || []).flatMap(n => n.papers || []).map(p => p.id)));
    });
  }, []);

  const cancelFocus = useCallback(() => { setFocusAxis(null); setFocusPending({}); setFocusMembers(new Set()); }, []);

  // Toggle a paper's staged membership. effective = staged ? (staged==="add") : isMember; click flips it,
  // collapsing back to "no change" when the flip matches the persisted state.
  const toggleFocusPaper = useCallback((paperId) => {
    setFocusPending(prev => {
      const next = { ...prev };
      const isMember = focusMembers.has(paperId);
      const staged = prev[paperId];
      const effective = staged ? staged === "add" : isMember;
      if (effective) {
        if (isMember) next[paperId] = "remove"; else delete next[paperId];
      } else {
        if (isMember) delete next[paperId]; else next[paperId] = "add";
      }
      return next;
    });
  }, [focusMembers]);

  const saveFocus = useCallback(async () => {
    if (!focusAxis) return;
    const entries = Object.entries(focusPending);
    const adds = entries.filter(([, op]) => op === "add").map(([id]) => Number(id));
    const removes = entries.filter(([, op]) => op === "remove").map(([id]) => Number(id));
    await Promise.all([
      ...adds.map(pid => apiPost(`/axes/${focusAxis.id}/papers`, { paper_id: pid })),
      ...removes.map(pid => apiDelete(`/axes/${focusAxis.id}/papers/${pid}`)),
    ]);
    setAxisRefresh(n => n + 1);   // AxesPanel reloads counts + the open axis's papers
    cancelFocus();
  }, [focusAxis, focusPending, cancelFocus]);

  const toggleLibrarySelect = useCallback((id) => {
    setSelectedLibraryIds(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }, []);
  const clearLibrarySelect = useCallback(() => setSelectedLibraryIds(new Set()), []);

  const bulkDeletePapers = useCallback(() => {
    const ids = [...selectedLibraryIds];
    if (!ids.length) return;
    if (!window.confirm(`Move ${ids.length} ${ids.length === 1 ? "paper" : "papers"} to Trash? You can restore from Trash.`)) return;
    Promise.all(ids.map(id => apiDelete(`/papers/${id}`))).then(() => {
      setSelectedLibraryIds(new Set());
      setSelected(prev => (ids.includes(prev) ? null : prev));  // clear the Detail pane if it was trashed
      setLibRefresh(n => n + 1);
    });
  }, [selectedLibraryIds]);

  // inc-62: "summarize N" → drive the (always-visible) Synthesis pane to summarize the selected subset.
  // A nonce makes each click a fresh trigger; the right pane is forced open so the result is visible.
  const bulkSummarizePapers = useCallback(() => {
    const ids = [...selectedLibraryIds];
    if (!ids.length) return;
    setPendingSummarize(prev => ({ paper_ids: ids, count: ids.length, nonce: (prev ? prev.nonce : 0) + 1 }));
    setRightOpen(true);
    setSelectedLibraryIds(new Set());
  }, [selectedLibraryIds]);

  // inc-70: export the selected papers' citations as a downloaded file. Raw fetch (apiPost forces .json());
  // selection is kept so you can export another format. Non-destructive.
  const bulkExportPapers = useCallback((format) => {
    const ids = [...selectedLibraryIds];
    if (!ids.length) return;
    const ext = format === "ris" ? "ris" : format === "csl-json" ? "json" : "bib";
    (async () => {
      try {
        const res = await fetch(API_BASE + "/papers/export", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ paper_ids: ids, format }),
        });
        if (!res.ok) { console.warn("[callosum] export failed:", res.status); return; }
        const url = URL.createObjectURL(await res.blob());
        const a = document.createElement("a");
        a.href = url; a.download = `callosum-citations.${ext}`;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (e) { console.warn("[callosum] export error:", e); }
    })();
  }, [selectedLibraryIds]);

  const restorePaper = useCallback((id) => {
    apiPost(`/papers/${id}/restore`, {}).then(r => { if (r.ok) setLibRefresh(n => n + 1); });
  }, []);

  // Permanent (irreversible) delete from Trash — double-confirm; only reachable from the Trash view (inc 65).
  const purgePaper = useCallback((id) => {
    if (!window.confirm("Permanently delete this paper? This removes its text, highlights, and search index, and cannot be undone.")) return;
    apiDelete(`/papers/${id}/permanent`).then(r => { if (r.ok) setLibRefresh(n => n + 1); });
  }, []);

  const emptyTrash = useCallback(() => {
    if (!window.confirm("Permanently delete EVERY paper in Trash? This cannot be undone.")) return;
    apiPost("/papers/trash/empty", {}).then(r => { if (r.ok) setLibRefresh(n => n + 1); });
  }, []);

  const toggleTrash = useCallback(() => {
    setTrashView(v => !v);
    setSelectedLibraryIds(new Set());  // selection doesn't carry across the live/Trash views
    setLibraryAxisFilter(null);        // Trash is its own view — drop any axis/tag filter
    setLibraryTagFilter(null);
    setPage(0);
  }, []);

  // inc-63: filter the Library to one axis's papers (a view, exclusive with trash/focus/tag but compatible
  // with checkbox-select → the filter→select-all→summarize synergy). Select-all selects the current page.
  const filterToAxis = useCallback((axis) => {
    setLibraryAxisFilter({ id: axis.id, label: axis.label });
    setLibraryTagFilter(null);         // axis & tag filters are mutually exclusive
    setActiveTab("library");
    setPage(0);
    setSelectedLibraryIds(new Set());
    setTrashView(false);
    cancelFocus();
  }, [cancelFocus]);
  const clearAxisFilter = useCallback(() => { setLibraryAxisFilter(null); setPage(0); }, []);

  // inc-71: filter the Library to one tag's papers (mirrors the axis filter; mutually exclusive with it).
  const filterToTag = useCallback((tag) => {
    setLibraryTagFilter({ id: tag.id, name: tag.name });
    setLibraryAxisFilter(null);
    setActiveTab("library");
    setPage(0);
    setSelectedLibraryIds(new Set());
    setTrashView(false);
    cancelFocus();
  }, [cancelFocus]);
  const clearTagFilter = useCallback(() => { setLibraryTagFilter(null); setPage(0); }, []);
  const selectAllLibrary = useCallback((ids) => setSelectedLibraryIds(new Set(ids)), []);
  const changeSort = useCallback((s) => { setLibrarySort(s); setPage(0); }, []);  // inc-69: re-sort from page 1

  // health check
  useEffect(() => {
    api("/health").then(r => {
      if (r.ok) setConn({ state: "ok", version: (r.data && (r.data.verification_version || r.data.version)) || null });
      else setConn({ state: "bad" });
    });
  }, []);

  // debounce search
  useEffect(() => {
    const t = setTimeout(() => { setDebounced(query); setPage(0); }, 280);
    return () => clearTimeout(t);
  }, [query]);

  // load papers (page + filter)
  useEffect(() => {
    let live = true;
    setListState(s => ({ ...s, status: "loading" }));
    const qs = new URLSearchParams({ limit: PAGE_SIZE, offset: page * PAGE_SIZE });
    if (debounced.trim()) qs.set("q", debounced.trim());
    if (trashView) qs.set("deleted", "true");
    if (libraryAxisFilter) qs.set("axis_id", libraryAxisFilter.id);
    if (libraryTagFilter) qs.set("tag_id", libraryTagFilter.id);
    if (librarySort !== "added") qs.set("sort", librarySort);
    api(`/papers?${qs.toString()}`).then(r => {
      if (!live) return;
      if (r.ok) setListState({ status: "ready", papers: r.data });
      else setListState({ status: "error", error: r.error, papers: [] });
    });
    return () => { live = false; };
  }, [page, debounced, trashView, libRefresh, libraryAxisFilter, libraryTagFilter, librarySort]);

  const cols = `${leftOpen ? leftW : 0}px 12px minmax(340px, 1fr) 12px ${rightOpen ? rightW : 0}px`;

  return (
    <div className="app" style={{ gridTemplateColumns: cols }}>
      {leftOpen
        ? <Sidebar conn={conn} onSelectPaper={setSelected} selectedPaper={selected} onOpenPaper={openPdf} onOpenSettings={() => setSettingsOpen(true)} onOpenHelp={() => setHelpOpen(true)} onEnterFocus={enterFocus} onFilterToAxis={filterToAxis} axisRefresh={axisRefresh} hideUncertainDefault={hideUncertainDefault} />
        : <div className="pane-collapsed" />}
      <Divider
        side="left" open={leftOpen} onToggle={() => setLeftOpen(o => !o)}
        onDragStart={(e) => { const sx = e.clientX, sw = leftW; _beginDrag(e, (x) => setLeftW(_clampW(sw + (x - sx), 180, 600))); }}
      />
      <LibraryFrame
        libraryProps={{
          state: listState, query, onQuery: setQuery,
          selected, onSelect: setSelected,
          page, onPage: setPage,
          total: listState.status === "ready" ? null : null,
          focusAxis, focusMembers, focusPending,
          onToggleFocusPaper: toggleFocusPaper, onSaveFocus: saveFocus, onCancelFocus: cancelFocus,
          trashView, selectedLibraryIds, librarySort, onSortChange: changeSort,
          onToggleLibrarySelect: toggleLibrarySelect, onClearLibrarySelect: clearLibrarySelect,
          onBulkDelete: bulkDeletePapers, onBulkSummarize: bulkSummarizePapers, onBulkExport: bulkExportPapers, onSelectAll: selectAllLibrary,
          libraryAxisFilter, onClearAxisFilter: clearAxisFilter,
          libraryTagFilter, onClearTagFilter: clearTagFilter,
          onToggleTrash: toggleTrash, onRestore: restorePaper,
          onPurge: purgePaper, onEmptyTrash: emptyTrash,
          onFindDuplicates: () => setDuplicatesOpen(true),
          onOpenWanted: () => setWantedOpen(true),
        }}
        tabs={tabs} activeTab={activeTab}
        onActivate={setActiveTab} onClose={closeTab} onOpenPdf={openPdf}
        annoRefresh={annoRefresh}
      />
      <Divider
        side="right" open={rightOpen} onToggle={() => setRightOpen(o => !o)}
        onDragStart={(e) => { const sx = e.clientX, sw = rightW; _beginDrag(e, (x) => setRightW(_clampW(sw - (x - sx), 280, 640))); }}
      />
      {rightOpen
        ? <RightPane paperId={selected} onOpenCitation={openCitation} onSaveHighlight={saveCitationHighlight} onOpenPaper={openPdf} onFilterToTag={filterToTag} pendingSummarize={pendingSummarize} />
        : <div className="pane-collapsed" />}
      {settingsOpen && <SettingsModal theme={theme} onTheme={setTheme} hideUncertainDefault={hideUncertainDefault} onHideUncertainDefault={setHideUncertainDefault} onMyPubsRefreshed={() => setAxisRefresh(n => n + 1)} onClose={() => setSettingsOpen(false)} />}
      {helpOpen && <HelpModal onClose={() => setHelpOpen(false)} />}
      {duplicatesOpen &&
        <DuplicatesModal
          onClose={() => setDuplicatesOpen(false)}
          onOpenPaper={openPdf}
          onChanged={() => setLibRefresh(n => n + 1)}
        />}
      {wantedOpen &&
        <WantedModal
          onClose={() => setWantedOpen(false)}
          onOpenPaper={openPdf}
          onChanged={() => setLibRefresh(n => n + 1)}
        />}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
