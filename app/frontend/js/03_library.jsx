// inc 221: useLibrary — the library-list subsystem extracted from the App god-component (40_app.jsx was pinned at
// the 600-line cap; this frees room for the read/priority filter facet + pays down long-flagged debt). Owns the
// filter/query/list-fetch state, pagination, the bulk + trash + filter actions, saved searches, the findings
// overview + the statcheck/retraction "N flagged" chips, the watched-folder rescan, and the p-curve/merge modal
// state. The cross-cutting setters it can't own (selection, tabs, focus-mode, the THEORY/METHODS accordion,
// settings, tag/axis refresh) come in via `opts`; the focus↔library cycle (focus-enter clears the view filters /
// the filter actions cancel focus) is broken by App passing cancelFocus through a ref + wiring focus's
// onEnterClearFilters to the returned `clearViewFilters`. Returns `libraryBits` (the LibraryFrame prop bundle, sans
// the focus + selected props App still owns) plus the handful of values App's paneCtx / modals need.
function useLibrary(opts) {
  const {
    selected, setSelected, setActiveTab, cancelFocus,
    setLeftOpen, setTheoryOpen, setMethodsOpen, setSettingsOpen,
    setTagRefresh, setAxisRefresh, autoScanWatched, readOnly, healthLoaded,
  } = opts;

  const [listState, setListState] = useState({ status: "loading", papers: [] });
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(0);

  const [selectedLibraryIds, setSelectedLibraryIds] = useState(() => new Set());
  const [pendingSummarize, setPendingSummarize] = useState(null);  // inc-62: drives the Synthesis pane to summarize a library selection
  const [libraryAxisFilter, setLibraryAxisFilter] = useState(null);  // inc-63: {id, label} → library shows only this axis's papers
  const [libraryTagFilter, setLibraryTagFilter] = useState(null);    // inc-71: {id, name} → library shows only this tag's papers
  const [trashView, setTrashView] = useState(false);
  const [libraryNeedsReview, setLibraryNeedsReview] = useState(false);  // inc-79: the "Unsorted" (needs-metadata) view
  const [librarySignalFilter, setLibrarySignalFilter] = useState(null);  // inc-97: a Methods-signal view, e.g. "statcheck-inconsistent"
  const [libraryReading, setLibraryReading] = useState({ read: "", priority: "" });  // inc-221: read/priority facet ("" = no filter)
  const [statcheckFlagged, setStatcheckFlagged] = useState(0);  // inc-100: # papers the last statcheck run flagged → header chip
  const [retractionFlagged, setRetractionFlagged] = useState(0);  // inc-131: # papers a registry records retracted → header chip
  const [librarySort, setLibrarySort] = useState(() => {  // inc-69; persisted inc-94
    try { return localStorage.getItem("callosum.librarySort") || "added"; } catch (e) { return "added"; }
  });
  const [librarySearchField, setLibrarySearchField] = useState("all");  // inc-89: search scope (all/title/author/journal)
  const [libraryItemType, setLibraryItemType] = useState("");  // inc-91: filter to a single CSL item type ("" = all)
  const [itemTypes, setItemTypes] = useState([]);  // inc-91: distinct item types present in the library (Type dropdown)
  const [libRefresh, setLibRefresh] = useState(0);
  const pendingSelectTopRef = useRef(false);  // inc-140: a view-change wants the next loaded list's top paper selected
  const [pcurvePapers, setPcurvePapers] = useState(null);  // inc-126: collection p-curve over the selection (modal)
  const [mergeIds, setMergeIds] = useState(null);          // inc-161: merge ≥2 papers into a survivor (modal)

  // --- selection (checkbox multi-select) ---
  const toggleLibrarySelect = useCallback((id) => {
    setSelectedLibraryIds(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }, []);
  const clearLibrarySelect = useCallback(() => setSelectedLibraryIds(new Set()), []);
  const selectAllLibrary = useCallback((ids) => setSelectedLibraryIds(new Set(ids)), []);

  // --- bulk actions over the selection ---
  const bulkDeletePapers = useCallback(() => {
    const ids = [...selectedLibraryIds];
    if (!ids.length) return;
    if (!window.confirm(`Move ${ids.length} ${ids.length === 1 ? "paper" : "papers"} to Trash? You can restore from Trash.`)) return;
    Promise.all(ids.map(id => apiDelete(`/papers/${id}`))).then(() => {
      setSelectedLibraryIds(new Set());
      setSelected(prev => (ids.includes(prev) ? null : prev));  // clear the Detail pane if it was trashed
      setLibRefresh(n => n + 1);
    });
  }, [selectedLibraryIds, setSelected]);

  // inc-62: "summarize N" → drive the (always-visible) Synthesis pane to summarize the selected subset.
  const bulkSummarizePapers = useCallback((focus) => {
    const ids = [...selectedLibraryIds];
    if (!ids.length) return;
    setPendingSummarize(prev => ({ paper_ids: ids, count: ids.length, nonce: (prev ? prev.nonce : 0) + 1, focus: (focus || "").trim() || null }));
    setLeftOpen(true); setTheoryOpen("synthesis");
    setSelectedLibraryIds(new Set());
  }, [selectedLibraryIds, setLeftOpen, setTheoryOpen]);

  const bulkPcurvePapers = useCallback(() => {
    const ids = [...selectedLibraryIds];
    if (ids.length) { setPcurvePapers(ids); setSelectedLibraryIds(new Set()); }
  }, [selectedLibraryIds]);

  const bulkMergePapers = useCallback(() => {
    const ids = [...selectedLibraryIds];
    if (ids.length >= 2) setMergeIds(ids);
  }, [selectedLibraryIds]);
  // B2 SP1: export the selected papers as a portable bundle (metadata + tags + annotations, NO PDFs).
  const bulkExportBundle = useCallback(() => {
    const ids = [...selectedLibraryIds];
    if (ids.length) downloadBundle("selection", ids);
  }, [selectedLibraryIds]);
  const onMerged = useCallback((survivorId) => {
    setMergeIds(null);
    setSelectedLibraryIds(new Set());
    setSelected(survivorId || null);  // show the merged record; the merged-away copies are now in Trash
    setLibRefresh(n => n + 1); setAxisRefresh(n => n + 1); setTagRefresh(n => n + 1);
  }, [setSelected, setAxisRefresh, setTagRefresh]);

  // inc 117 (SP1): summarize an explicit id set (from the My Publications tab) → drive the synthesis section.
  const summarizePaperIds = useCallback((ids) => {
    if (!ids || !ids.length) return;
    setPendingSummarize(prev => ({ paper_ids: ids, count: ids.length, nonce: (prev ? prev.nonce : 0) + 1 }));
    setLeftOpen(true); setTheoryOpen("synthesis");
  }, [setLeftOpen, setTheoryOpen]);

  const bulkExportPapers = useCallback((format) => downloadCitationExport([...selectedLibraryIds], format), [selectedLibraryIds]);
  const bulkBibliography = useCallback((style) => downloadBibliography([...selectedLibraryIds], style), [selectedLibraryIds]);

  // --- trash lifecycle ---
  const restorePaper = useCallback((id) => {
    apiPost(`/papers/${id}/restore`, {}).then(r => { if (r.ok) setLibRefresh(n => n + 1); });
  }, []);
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
    setSelectedLibraryIds(new Set());
    setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); setLibrarySignalFilter(null);
    setPage(0);
  }, []);

  // --- view filters (axis / tag / needs-review / signal); each is exclusive with the others + cancels focus ---
  const filterToAxis = useCallback((axis) => {
    setLibraryAxisFilter({ id: axis.id, label: axis.label, hideUncertain: !!axis.hideUncertain });
    setLibraryTagFilter(null); setActiveTab("library"); setPage(0); setSelectedLibraryIds(new Set());
    setTrashView(false); setLibraryNeedsReview(false); setLibrarySignalFilter(null); cancelFocus();
  }, [setActiveTab, cancelFocus]);
  const clearAxisFilter = useCallback(() => { setLibraryAxisFilter(null); setPage(0); }, []);
  const filterToTag = useCallback((tag) => {
    setLibraryTagFilter({ id: tag.id, name: tag.name });
    setLibraryAxisFilter(null); setActiveTab("library"); setPage(0); setSelectedLibraryIds(new Set());
    setTrashView(false); setLibraryNeedsReview(false); setLibrarySignalFilter(null); cancelFocus();
  }, [setActiveTab, cancelFocus]);
  const clearTagFilter = useCallback(() => { setLibraryTagFilter(null); setPage(0); }, []);
  const changeSort = useCallback((s) => {  // inc-69: re-sort from page 1; inc-94: persist the choice
    setLibrarySort(s); setPage(0);
    try { localStorage.setItem("callosum.librarySort", s); } catch (e) { /* ignore */ }
  }, []);
  // inc 221: the read/priority filter facet — set read ("read"/"unread"/"") + priority level, from page 1.
  const changeReadingFilter = useCallback((next) => { setLibraryReading(next); setPage(0); }, []);

  const toggleNeedsReview = useCallback(() => {
    setLibraryNeedsReview(v => {
      const next = !v;
      if (next) { setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibrarySignalFilter(null); cancelFocus(); }
      return next;
    });
    setSelectedLibraryIds(new Set()); setPage(0);
  }, [cancelFocus]);
  const clearNeedsReview = useCallback(() => { setLibraryNeedsReview(false); setPage(0); }, []);
  const showNeedsReview = useCallback(() => {
    setLibraryNeedsReview(true);
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibrarySignalFilter(null); cancelFocus();
    setSelectedLibraryIds(new Set()); setPage(0);
  }, [cancelFocus]);

  const showStatcheckFlagged = useCallback(() => {
    setLibrarySignalFilter("statcheck-inconsistent");
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); cancelFocus();
    setSelectedLibraryIds(new Set());
    pendingSelectTopRef.current = true;  // inc-140: select the top of the freshly-loaded FLAGGED list
    setSettingsOpen(false); setActiveTab("library"); setMethodsOpen("statcheck"); setPage(0);
  }, [cancelFocus, setSettingsOpen, setActiveTab, setMethodsOpen]);
  const clearSignalFilter = useCallback(() => { setLibrarySignalFilter(null); setPage(0); }, []);
  const showRetractionFlagged = useCallback(() => {
    setLibrarySignalFilter("retraction-retracted");
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); cancelFocus();
    setSelectedLibraryIds(new Set()); setSettingsOpen(false); setActiveTab("library"); setPage(0);
  }, [cancelFocus, setSettingsOpen, setActiveTab]);

  // Clear just the view filters — wired to useFocusMode's onEnterClearFilters (breaks the focus↔library cycle).
  const clearViewFilters = useCallback(() => { setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibrarySignalFilter(null); }, []);

  // --- the statcheck / retraction "N flagged" header chips (cache-only counts) ---
  const refreshStatcheckChip = useCallback(() => {
    api("/methods/statcheck/summary").then(r => { if (r.ok) setStatcheckFlagged(r.data.flagged || 0); });
  }, []);
  const refreshRetractionChip = useCallback(() => {
    api("/methods/retraction/summary").then(r => { if (r.ok) setRetractionFlagged(r.data.retracted || 0); });
  }, []);

  // --- findings overview → the "N to review" badge + FactMark; re-fetched after a review ---
  const [findingsByPaper, setFindingsByPaper] = useState({});
  const [findingsRefresh, setFindingsRefresh] = useState(0);
  useEffect(() => {
    api("/findings/overview").then(r => {
      if (!r.ok) return;
      const m = {}; r.data.forEach(o => { m[o.paper_id] = o; }); setFindingsByPaper(m);
    });
  }, [findingsRefresh, libRefresh]);
  const findingsToReview = Object.values(findingsByPaper).filter(o => o.unreviewed_count > 0).length;
  const showFindingsToReview = useCallback(() => {
    setLibrarySignalFilter("needs-review");
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); cancelFocus();
    setSelectedLibraryIds(new Set()); setSettingsOpen(false); setActiveTab("library"); setPage(0);
  }, [cancelFocus, setSettingsOpen, setActiveTab]);

  // --- saved searches: a named bundle of the existing filter params (inc 208) ---
  const [savedSearches, setSavedSearches] = useState([]);
  const loadSavedSearches = useCallback(() => {
    api("/saved-searches").then(r => { if (r.ok) setSavedSearches(r.data || []); });
  }, []);
  useEffect(() => { loadSavedSearches(); }, [loadSavedSearches]);
  const currentSearchParams = useCallback(() => ({
    q: query,
    search_field: librarySearchField,
    item_type: libraryItemType,
    axis: libraryAxisFilter
      ? { id: libraryAxisFilter.id, label: libraryAxisFilter.label || "", hideUncertain: !!libraryAxisFilter.hideUncertain }
      : null,
    tag: libraryTagFilter ? { id: libraryTagFilter.id, name: libraryTagFilter.name || "" } : null,
    needs_review: libraryNeedsReview,
    signal: librarySignalFilter,
    sort: librarySort,
  }), [query, librarySearchField, libraryItemType, libraryAxisFilter, libraryTagFilter, libraryNeedsReview, librarySignalFilter, librarySort]);
  const applySavedSearch = useCallback((p) => {
    setQuery(p.q || ""); setDebounced(p.q || "");   // set both → no 280ms double-fetch lag
    setLibrarySearchField(p.search_field || "all");
    setLibraryItemType(p.item_type || "");
    setLibraryAxisFilter(p.axis ? { id: p.axis.id, label: p.axis.label, hideUncertain: !!p.axis.hideUncertain } : null);
    setLibraryTagFilter(p.tag ? { id: p.tag.id, name: p.tag.name } : null);
    setLibraryNeedsReview(!!p.needs_review);
    setLibrarySignalFilter(p.signal || null);
    setLibrarySort(p.sort || "added");
    try { localStorage.setItem("callosum.librarySort", p.sort || "added"); } catch (e) { /* ignore */ }
    setTrashView(false); setActiveTab("library"); setPage(0); setSelectedLibraryIds(new Set());
    cancelFocus();
  }, [setActiveTab, cancelFocus]);
  const saveCurrentSearch = useCallback((name) => {
    if (!name || !name.trim()) return;
    apiPost("/saved-searches", { name: name.trim(), params: currentSearchParams() }).then(r => {
      if (r.ok) loadSavedSearches();
    });
  }, [currentSearchParams, loadSavedSearches]);
  const deleteSavedSearch = useCallback((id) => {
    apiDelete(`/saved-searches/${id}`).then(r => { if (r.ok) loadSavedSearches(); });
  }, [loadSavedSearches]);

  // --- watched-folder rescan on launch + window focus (inc 98/136) ---
  const rescanInFlight = useRef(false);
  const lastRescan = useRef(0);
  const triggerWatchedRescan = useCallback(() => {
    // B5 SP2: wait for /health, then never write on a read-only companion (else the launch rescan 403s before readOnly is known).
    if (!healthLoaded || !autoScanWatched || readOnly || rescanInFlight.current) return;
    if (Date.now() - lastRescan.current < 20000) return;  // at most once per 20s
    rescanInFlight.current = true;
    lastRescan.current = Date.now();
    apiPost("/library/watched/rescan", {}).then(r => {
      if (!r.ok) { rescanInFlight.current = false; return; }
      const poll = (jobId) => api(`/library/watched/rescan/${jobId}`).then(rr => {
        if (!rr.ok) { rescanInFlight.current = false; return; }
        if (rr.data.status === "done") {
          rescanInFlight.current = false;
          const sm = rr.data.summary;
          if (sm && (sm.added || sm.removed)) { setLibRefresh(n => n + 1); setTagRefresh(n => n + 1); }
        } else if (rr.data.status === "error") rescanInFlight.current = false;
        else setTimeout(() => poll(jobId), 2000);
      });
      poll(r.data.job_id);
    });
  }, [autoScanWatched, readOnly, healthLoaded, setTagRefresh]);
  useEffect(() => {
    triggerWatchedRescan();  // on launch
    const onFocus = () => triggerWatchedRescan();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [triggerWatchedRescan]);

  // --- debounce search ---
  useEffect(() => {
    const t = setTimeout(() => { setDebounced(query); setPage(0); }, 280);
    return () => clearTimeout(t);
  }, [query]);

  // --- load papers (page + filter) ---
  useEffect(() => {
    let live = true;
    setListState(s => ({ ...s, status: "loading" }));
    const qs = new URLSearchParams({ limit: PAGE_SIZE, offset: page * PAGE_SIZE });
    if (debounced.trim()) qs.set("q", debounced.trim());
    if (debounced.trim() && librarySearchField !== "all") qs.set("search_field", librarySearchField);
    if (trashView) qs.set("deleted", "true");
    if (libraryAxisFilter) {
      qs.set("axis_id", libraryAxisFilter.id);
      if (libraryAxisFilter.hideUncertain) qs.set("axis_hide_uncertain", "true");  // A10: match the card view
    }
    if (libraryTagFilter) qs.set("tag_id", libraryTagFilter.id);
    if (libraryItemType) qs.set("item_type", libraryItemType);
    if (libraryNeedsReview) qs.set("needs_review", "true");
    if (librarySignalFilter === "needs-review") qs.set("finding", "needs-review");  // inc-133: the to-review view
    else if (librarySignalFilter) qs.set("signal", librarySignalFilter);
    if (libraryReading.read) qs.set("read_status", libraryReading.read);  // inc-221: read/priority facet
    if (libraryReading.priority) qs.set("priority", libraryReading.priority);
    if (librarySort !== "added") qs.set("sort", librarySort);
    api(`/papers?${qs.toString()}`).then(r => {
      if (!live) return;
      if (r.ok) {
        setListState({ status: "ready", papers: r.data });
        if (pendingSelectTopRef.current) {  // inc-140: select the top of THIS freshly-loaded list, not the stale one
          pendingSelectTopRef.current = false;
          setSelected(r.data.length ? r.data[0].id : null);
        }
      }
      else setListState({ status: "error", error: r.error, papers: [] });
    });
    return () => { live = false; };
  }, [page, debounced, librarySearchField, libraryItemType, trashView, libRefresh, libraryAxisFilter, libraryTagFilter, libraryNeedsReview, librarySignalFilter, libraryReading, librarySort, findingsRefresh, setSelected]);

  // inc-91: distinct item types present in the library (for the Type filter dropdown)
  useEffect(() => {
    api("/papers/item-types").then(r => { if (r.ok) setItemTypes(r.data); });
  }, [libRefresh]);

  // inc-138: auto-select the top library paper on load so Details start populated (not the empty hint).
  useEffect(() => {
    if (selected == null && !trashView && listState.status === "ready" && listState.papers.length > 0) {
      setSelected(listState.papers[0].id);
    }
  }, [selected, trashView, listState, setSelected]);

  // inc-100/122: the statcheck / retraction header chips — fetched on mount.
  useEffect(() => { refreshStatcheckChip(); }, [refreshStatcheckChip]);
  useEffect(() => { refreshRetractionChip(); }, [refreshRetractionChip]);

  // The LibraryFrame prop bundle (minus the focus + selected props App still owns + spreads in).
  const libraryBits = {
    state: listState, query, onQuery: setQuery,
    page, onPage: setPage,
    total: null,
    trashView, selectedLibraryIds, librarySort, onSortChange: changeSort,
    librarySearchField, onSearchFieldChange: (f) => { setLibrarySearchField(f); setPage(0); },
    libraryItemType, itemTypes, onItemTypeChange: (t) => { setLibraryItemType(t); setPage(0); },
    libraryReading, onReadingFilter: changeReadingFilter,
    onToggleLibrarySelect: toggleLibrarySelect, onClearLibrarySelect: clearLibrarySelect,
    onBulkDelete: bulkDeletePapers, onBulkSummarize: bulkSummarizePapers, onBulkPcurve: bulkPcurvePapers, onBulkMerge: bulkMergePapers, onBulkExport: bulkExportPapers, onBulkExportBundle: bulkExportBundle, onBulkBibliography: bulkBibliography, onSelectAll: selectAllLibrary,
    libraryAxisFilter, onClearAxisFilter: clearAxisFilter,
    libraryTagFilter, onClearTagFilter: clearTagFilter,
    libraryNeedsReview, onToggleNeedsReview: toggleNeedsReview, onClearNeedsReview: clearNeedsReview,
    librarySignalFilter, onClearSignalFilter: clearSignalFilter,
    statcheckFlagged, onShowStatcheckFlagged: showStatcheckFlagged,
    retractionFlagged, onShowRetractionFlagged: showRetractionFlagged,
    findingsToReview, onShowFindingsToReview: showFindingsToReview,
    findingsByPaper,
    onToggleTrash: toggleTrash, onRestore: restorePaper,
    onPurge: purgePaper, onEmptyTrash: emptyTrash,
    onCitationsRefreshed: () => setLibRefresh(n => n + 1), onEnriched: () => setLibRefresh(n => n + 1),
    savedSearches, onApplySavedSearch: applySavedSearch, onSaveSearch: saveCurrentSearch, onDeleteSavedSearch: deleteSavedSearch,
  };

  return {
    libraryBits, setLibRefresh,
    pendingSummarize, summarizePaperIds,
    filterToTag, filterToAxis, clearViewFilters, showNeedsReview,
    showStatcheckFlagged, showRetractionFlagged,
    refreshStatcheckChip, refreshRetractionChip, setFindingsRefresh,
    pcurvePapers, setPcurvePapers, mergeIds, setMergeIds, onMerged,
  };
}
