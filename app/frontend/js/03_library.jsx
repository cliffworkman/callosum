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
    setMethodsOpen, setSettingsOpen, onOpenSynthesis,
    setTagRefresh, setAxisRefresh, readOnly, healthLoaded,
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
  const [libraryTextHealthFilter, setLibraryTextHealthFilter] = useState(null);  // local-only PDF text-health view: {key,label,paperIds}
  const [libraryReferenceFilter, setLibraryReferenceFilter] = useState(null);  // local-only refs triage view: {label,paperIds}
  const [libraryReading, setLibraryReading] = useState({ read: "", priority: "" });  // inc-221: read/priority facet ("" = no filter)
  const [libraryMissingPdf, setLibraryMissingPdf] = useState(false);  // inc-301: only papers with no local PDF
  const [statcheckFlagged, setStatcheckFlagged] = useState(0);  // inc-100: # papers the last statcheck run flagged → header chip
  const [retractionFlagged, setRetractionFlagged] = useState(0);  // inc-131: # papers a registry records retracted → header chip
  const [openDataDetected, setOpenDataDetected] = useState(0);  // # papers where open-data disclosure was detected → signal chip
  const [lmmFlagged, setLmmFlagged] = useState(0);  // backlog #23 (F1): # papers with an incomplete LMM reporting checklist → header chip
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
  const [critSetIds, setCritSetIds] = useState(null);      // #12: critically review a SET of papers together (modal)

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

  // inc-62 → inc 287/298: "summarize N" → drive Synthesize → Ask to summarize the selected subset.
  const bulkSummarizePapers = useCallback((focus) => {
    const ids = [...selectedLibraryIds];
    if (!ids.length) return;
    setPendingSummarize(prev => ({ paper_ids: ids, count: ids.length, nonce: (prev ? prev.nonce : 0) + 1, focus: (focus || "").trim() || null }));
    if (onOpenSynthesis) onOpenSynthesis();
    setSelectedLibraryIds(new Set());
  }, [selectedLibraryIds, onOpenSynthesis]);

  const bulkPcurvePapers = useCallback(() => {
    const ids = [...selectedLibraryIds];
    if (ids.length) { setPcurvePapers(ids); setSelectedLibraryIds(new Set()); }
  }, [selectedLibraryIds]);

  const bulkMergePapers = useCallback(() => {
    const ids = [...selectedLibraryIds];
    if (ids.length >= 2) setMergeIds(ids);
  }, [selectedLibraryIds]);
  // #12: critically review the selected papers TOGETHER (cross-paper contradictions + a fact-matrix; a signal).
  const bulkCriticalReadPapers = useCallback(() => {
    const ids = [...selectedLibraryIds];
    if (ids.length >= 2) setCritSetIds(ids);
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

  // inc 117 (SP1) → inc 287: summarize an explicit id set (from the My Publications tab) → drive Synthesis.
  const summarizePaperIds = useCallback((ids) => {
    if (!ids || !ids.length) return;
    setPendingSummarize(prev => ({ paper_ids: ids, count: ids.length, nonce: (prev ? prev.nonce : 0) + 1 }));
    if (onOpenSynthesis) onOpenSynthesis();
  }, [onOpenSynthesis]);

  const bulkExportPapers = useCallback((format) => downloadCitationExport([...selectedLibraryIds], format), [selectedLibraryIds]);
  const bulkBibliography = useCallback((style) => downloadBibliography([...selectedLibraryIds], style), [selectedLibraryIds]);
  const bulkReferenceCheckDone = useCallback(async () => {
    const overview = await api("/reference-integrity/overview");
    if (overview.ok) {
      const ids = (overview.data || []).filter(r => r.active_count > 0).map(r => r.paper_id);
      if (ids.length) {
        setLibraryReferenceFilter({ label: `${ids.length} papers with active signals`, paperIds: ids });
        setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false);
        setLibrarySignalFilter(null); setLibraryTextHealthFilter(null); setPage(0);
      }
    }
    setReferenceWarningsRefresh(n => n + 1);
    setLibRefresh(n => n + 1);
  }, []);

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
    setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); setLibrarySignalFilter(null); setLibraryTextHealthFilter(null); setLibraryReferenceFilter(null);
    setPage(0);
  }, []);

  // --- view filters (axis / tag / needs-review / signal); each is exclusive with the others + cancels focus ---
  const filterToAxis = useCallback((axis) => {
    setLibraryAxisFilter({ id: axis.id, label: axis.label, hideUncertain: !!axis.hideUncertain });
    setLibraryTagFilter(null); setActiveTab("library"); setPage(0); setSelectedLibraryIds(new Set());
    setTrashView(false); setLibraryNeedsReview(false); setLibrarySignalFilter(null); setLibraryTextHealthFilter(null); setLibraryReferenceFilter(null); cancelFocus();
  }, [setActiveTab, cancelFocus]);
  const clearAxisFilter = useCallback(() => { setLibraryAxisFilter(null); setPage(0); }, []);
  const filterToTag = useCallback((tag) => {
    setLibraryTagFilter({ id: tag.id, name: tag.name });
    setLibraryAxisFilter(null); setActiveTab("library"); setPage(0); setSelectedLibraryIds(new Set());
    setTrashView(false); setLibraryNeedsReview(false); setLibrarySignalFilter(null); setLibraryTextHealthFilter(null); setLibraryReferenceFilter(null); cancelFocus();
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
      if (next) { setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibrarySignalFilter(null); setLibraryTextHealthFilter(null); setLibraryReferenceFilter(null); cancelFocus(); }
      return next;
    });
    setSelectedLibraryIds(new Set()); setPage(0);
  }, [cancelFocus]);
  const clearNeedsReview = useCallback(() => { setLibraryNeedsReview(false); setPage(0); }, []);
  const showNeedsReview = useCallback(() => {
    setLibraryNeedsReview(true);
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibrarySignalFilter(null); setLibraryTextHealthFilter(null); setLibraryReferenceFilter(null); cancelFocus();
    setSelectedLibraryIds(new Set()); setPage(0);
  }, [cancelFocus]);

  const showStatcheckFlagged = useCallback(() => {
    setLibrarySignalFilter("statcheck-inconsistent");
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); setLibraryTextHealthFilter(null); setLibraryReferenceFilter(null); cancelFocus();
    setSelectedLibraryIds(new Set());
    pendingSelectTopRef.current = true;  // inc-140: select the top of the freshly-loaded FLAGGED list
    setSettingsOpen(false); setActiveTab("library"); setMethodsOpen("statcheck"); setPage(0);
  }, [cancelFocus, setSettingsOpen, setActiveTab, setMethodsOpen]);
  const clearSignalFilter = useCallback(() => { setLibrarySignalFilter(null); setPage(0); }, []);
  const showRetractionFlagged = useCallback(() => {
    setLibrarySignalFilter("retraction-retracted");
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); setLibraryTextHealthFilter(null); setLibraryReferenceFilter(null); cancelFocus();
    setSelectedLibraryIds(new Set()); setSettingsOpen(false); setActiveTab("library"); setPage(0);
  }, [cancelFocus, setSettingsOpen, setActiveTab]);
  // inc-251: jump to a transparency review queue (the chip → data-availability; the panel's per-disclosure links pass
  // each of the 7 keys). A review queue ("not detected — go look"), never a "hides data" verdict.
  const showTransparencyReview = useCallback((signalKey = "transparency-data-not-detected") => {
    setLibrarySignalFilter(signalKey);
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); setLibraryTextHealthFilter(null); setLibraryReferenceFilter(null); cancelFocus();
    setSelectedLibraryIds(new Set()); setSettingsOpen(false); setActiveTab("library"); setPage(0);
  }, [cancelFocus, setSettingsOpen, setActiveTab]);
  // backlog #23 (F1): jump to the library's "incomplete LMM reporting" queue — mirrors showRetractionFlagged.
  const showLmmFlagged = useCallback(() => {
    setLibrarySignalFilter("lmm-incomplete");
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); setLibraryTextHealthFilter(null); setLibraryReferenceFilter(null); cancelFocus();
    setSelectedLibraryIds(new Set()); setSettingsOpen(false); setActiveTab("library"); setPage(0);
  }, [cancelFocus, setSettingsOpen, setActiveTab]);
  const showTextHealthFilter = useCallback((filter) => {
    const paperIds = [...new Set((filter.paperIds || []).map(Number).filter(Boolean))];
    if (!paperIds.length) return;
    setLibraryTextHealthFilter({ key: filter.key || filter.flag || "text-health", label: filter.label || "Text Health", paperIds });
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); setLibrarySignalFilter(null); setLibraryReferenceFilter(null); cancelFocus();
    setSelectedLibraryIds(new Set()); setSettingsOpen(false); setActiveTab("library"); setPage(0);
  }, [cancelFocus, setSettingsOpen, setActiveTab]);
  const clearTextHealthFilter = useCallback(() => { setLibraryTextHealthFilter(null); setPage(0); }, []);
  const clearReferenceFilter = useCallback(() => { setLibraryReferenceFilter(null); setPage(0); }, []);

  // Clear just the view filters — wired to useFocusMode's onEnterClearFilters (breaks the focus↔library cycle).
  const clearViewFilters = useCallback(() => { setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibrarySignalFilter(null); setLibraryTextHealthFilter(null); setLibraryReferenceFilter(null); }, []);

  // --- the statcheck / retraction "N flagged" header chips (cache-only counts) ---
  const refreshStatcheckChip = useCallback(() => {
    api("/methods/statcheck/summary").then(r => { if (r.ok) setStatcheckFlagged(r.data.flagged || 0); });
  }, []);
  const refreshRetractionChip = useCallback(() => {
    api("/methods/retraction/summary").then(r => { if (r.ok) setRetractionFlagged(r.data.retracted || 0); });
  }, []);
  const refreshTransparencyChip = useCallback(() => {
    api("/methods/transparency/summary").then(r => { if (r.ok) setOpenDataDetected(r.data.data_detected || 0); });
  }, []);
  const refreshLmmChip = useCallback(() => {
    api("/methods/lmm/summary").then(r => { if (r.ok) setLmmFlagged(r.data.incomplete || 0); });
  }, []);

  // --- findings overview → the "N to review" badge + FactMark; re-fetched after a review ---
  const [findingsByPaper, setFindingsByPaper] = useState({});
  const [findingsRefresh, setFindingsRefresh] = useState(0);
  const [referenceWarningsByPaper, setReferenceWarningsByPaper] = useState({});
  const [referenceWarningsRefresh, setReferenceWarningsRefresh] = useState(0);
  useEffect(() => {
    api("/findings/overview").then(r => {
      if (!r.ok) return;
      const m = {}; r.data.forEach(o => { m[o.paper_id] = o; }); setFindingsByPaper(m);
    });
  }, [findingsRefresh, libRefresh]);
  useEffect(() => {
    api("/reference-integrity/overview").then(r => {
      if (!r.ok) return;
      const m = {}; r.data.forEach(o => { m[o.paper_id] = o; }); setReferenceWarningsByPaper(m);
    });
  }, [referenceWarningsRefresh, libRefresh]);
  const findingsToReview = Object.values(findingsByPaper).filter(o => o.unreviewed_count > 0).length;
  const showFindingsToReview = useCallback(() => {
    setLibrarySignalFilter("needs-review");
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); setLibraryTextHealthFilter(null); setLibraryReferenceFilter(null); cancelFocus();
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
    setLibraryTextHealthFilter(null);
    setLibraryReferenceFilter(null);
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
    if (!healthLoaded || readOnly || rescanInFlight.current) return;
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
  }, [readOnly, healthLoaded, setTagRefresh]);

  // --- Retraction Watch mirror: opt-in cadence auto-refresh on launch + focus (backlog #31) ---
  // Client-driven, staleness-gated pull (no backend scheduler exists) — mirrors triggerWatchedRescan's shape above
  // and Feed's opt-in/staleness-gated auto-refresh precedent (30e_feed.jsx). Default off; the Settings checkbox
  // (35_settings.jsx) reads/writes the same localStorage key, decoupled — no prop/ctx threading needed.
  const retractionRefreshInFlight = useRef(false);
  const lastRetractionAttempt = useRef(0);
  const triggerRetractionAutoRefresh = useCallback(() => {
    if (!healthLoaded || readOnly || retractionRefreshInFlight.current) return;
    let optedIn = false;
    try { optedIn = localStorage.getItem("callosum.retractionAutoRefresh") === "1"; } catch (e) { /* ignore */ }
    if (!optedIn) return;
    // Safety-net throttle (≤1/hour) alongside the 30-day staleness gate: without it, a mirror that can never
    // become fresh (e.g. no contact email set, so every refresh attempt fails) would re-run the full per-paper
    // check batch — real Crossref/OpenAlex calls per paper — on every single window focus, indefinitely.
    if (Date.now() - lastRetractionAttempt.current < 3600000) return;
    lastRetractionAttempt.current = Date.now();
    retractionRefreshInFlight.current = true;
    api("/methods/retraction/database").then(r => {
      const retrievedAt = r.ok ? r.data.retrieved_at : null;
      const ageDays = retrievedAt ? Math.floor((Date.now() - new Date(retrievedAt).getTime()) / 86400000) : null;
      if (ageDays != null && ageDays <= 30) { retractionRefreshInFlight.current = false; return; }  // fresh enough
      apiPost("/methods/retraction/run", {}).then(rr => {
        if (!rr.ok) { retractionRefreshInFlight.current = false; return; }
        const poll = (jobId) => api(`/methods/retraction/run/${jobId}`).then(rp => {
          if (!rp.ok) { retractionRefreshInFlight.current = false; return; }
          if (rp.data.status === "done") { retractionRefreshInFlight.current = false; refreshRetractionChip(); }
          else if (rp.data.status === "error") retractionRefreshInFlight.current = false;
          else setTimeout(() => poll(jobId), 2000);
        });
        poll(rr.data.job_id);
      });
    });
  }, [readOnly, healthLoaded, refreshRetractionChip]);

  useEffect(() => {
    triggerWatchedRescan();  // on launch
    triggerRetractionAutoRefresh();
    const onFocus = () => { triggerWatchedRescan(); triggerRetractionAutoRefresh(); };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [triggerWatchedRescan, triggerRetractionAutoRefresh]);

  // --- debounce search ---
  useEffect(() => {
    const t = setTimeout(() => { setDebounced(query); setPage(0); }, 280);
    return () => clearTimeout(t);
  }, [query]);

  // --- shared query-string builders ---
  // inc 319: `buildFilterQs` (the full normal-view contract, incl. axis/tag/trash/needs_review/signal) is used
  // both by the main fetch below and the reveal-selected-paper effect, so they can never drift apart — both need
  // to ask the backend the exact same "what does the current view look like" question. `addCommonParams` is the
  // subset the local-filter (Text-Health/Reference) page-walk also needs, deliberately WITHOUT axis/tag/trash/
  // needs_review/signal (those don't compose with a local filter today) — factored out once so the two call
  // sites can't silently drift on the params they do share.
  const addCommonParams = useCallback((qs) => {
    if (debounced.trim()) qs.set("q", debounced.trim());
    if (debounced.trim() && librarySearchField !== "all") qs.set("search_field", librarySearchField);
    if (libraryItemType) qs.set("item_type", libraryItemType);
    if (libraryReading.read) qs.set("read_status", libraryReading.read);  // inc-221: read/priority facet
    if (libraryReading.priority) qs.set("priority", libraryReading.priority);
    if (libraryMissingPdf) qs.set("missing_pdf", "true");  // inc-301: papers with no local PDF
    if (librarySort !== "added") qs.set("sort", librarySort);
  }, [debounced, librarySearchField, libraryItemType, libraryReading, libraryMissingPdf, librarySort]);

  const buildFilterQs = useCallback(() => {
    const qs = new URLSearchParams();
    addCommonParams(qs);
    if (trashView) qs.set("deleted", "true");
    if (libraryAxisFilter) {
      qs.set("axis_id", libraryAxisFilter.id);
      if (libraryAxisFilter.hideUncertain) qs.set("axis_hide_uncertain", "true");  // A10: match the card view
    }
    if (libraryTagFilter) qs.set("tag_id", libraryTagFilter.id);
    if (libraryNeedsReview) qs.set("needs_review", "true");
    if (librarySignalFilter === "needs-review") qs.set("finding", "needs-review");  // inc-133: the to-review view
    else if (librarySignalFilter) qs.set("signal", librarySignalFilter);
    return qs;
  }, [addCommonParams, trashView, libraryAxisFilter, libraryTagFilter, libraryNeedsReview, librarySignalFilter]);

  // --- load papers (page + filter) ---
  useEffect(() => {
    let live = true;
    setListState(s => ({ ...s, status: "loading" }));
    const localPaperFilter = libraryTextHealthFilter || libraryReferenceFilter;
    if (localPaperFilter) {
      const wanted = new Set(localPaperFilter.paperIds || []);
      (async () => {
        const all = [];
        for (let offset = 0; live; offset += PAGE_SIZE) {
          const qs = new URLSearchParams({ limit: PAGE_SIZE, offset });
          addCommonParams(qs);
          const r = await api(`/papers?${qs.toString()}`);
          if (!live) return;
          if (!r.ok) {
            setListState({ status: "error", error: r.error, authRequired: r.authRequired, papers: [] });
            return;
          }
          all.push(...(r.data || []).filter(p => wanted.has(p.id)));
          if (!r.data || r.data.length < PAGE_SIZE) break;
        }
        const start = page * PAGE_SIZE;
        setListState({ status: "ready", papers: all.slice(start, start + PAGE_SIZE), total: all.length });
      })();
      return () => { live = false; };
    }
    const qs = buildFilterQs();
    qs.set("limit", PAGE_SIZE);
    qs.set("offset", page * PAGE_SIZE);
    api(`/papers?${qs.toString()}`).then(r => {
      if (!live) return;
      if (r.ok) {
        setListState({ status: "ready", papers: r.data });
        if (pendingSelectTopRef.current) {  // inc-140: select the top of THIS freshly-loaded list, not the stale one
          pendingSelectTopRef.current = false;
          setSelected(r.data.length ? r.data[0].id : null);
        }
      }
      else setListState({ status: "error", error: r.error, authRequired: r.authRequired, papers: [] });  // inc 254: 401 → honest lockout copy
    });
    return () => { live = false; };
  }, [page, debounced, librarySearchField, libraryItemType, trashView, libRefresh, libraryAxisFilter, libraryTagFilter, libraryNeedsReview, librarySignalFilter, libraryTextHealthFilter, libraryReferenceFilter, libraryReading, libraryMissingPdf, librarySort, findingsRefresh, setSelected, buildFilterQs, addCommonParams]);

  // --- reveal the selected paper in the library list (inc 319) ---
  // Keyed ONLY on `selected` -- a filter changing on its own must never trigger a jump, only `selected` changing
  // does (this effect body is a fresh closure each render, so it still reads current filter values whenever it
  // does fire). If the paper is already on the loaded page, PaperCard's own isSelected-keyed effect scrolls to it
  // directly -- nothing to do here. Local-only filters (Text-Health/Reference) are v1-out-of-scope: rare,
  // modal-triggered secondary views computed by walking pages client-side, not worth replicating a rank-lookup
  // for. A 404 (doesn't match the active filter) is a silent no-op -- the filter is never cleared/overridden to
  // force a reveal, per the user's explicit requirement.
  useEffect(() => {
    if (selected == null) return;
    if (listState.papers.some(p => p.id === selected)) return;  // already on the loaded page
    if (libraryTextHealthFilter || libraryReferenceFilter) return;
    const qs = buildFilterQs();
    api(`/papers/${selected}/position?${qs.toString()}`).then(r => {
      if (r.ok && r.data && r.data.index != null) {
        const target = Math.floor(r.data.index / PAGE_SIZE);
        setPage(p => (p === target ? p : target));
      }
      // 404 / not-ok → doesn't match the active filter: do nothing.
    });
  }, [selected]);

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
  useEffect(() => { refreshTransparencyChip(); }, [refreshTransparencyChip]);
  useEffect(() => { refreshLmmChip(); }, [refreshLmmChip]);

  // The LibraryFrame prop bundle (minus the focus + selected props App still owns + spreads in).
  const libraryBits = {
    state: listState, query, onQuery: setQuery,
    page, onPage: setPage,
    total: null,
    trashView, selectedLibraryIds, librarySort, onSortChange: changeSort,
    librarySearchField, onSearchFieldChange: (f) => { setLibrarySearchField(f); setPage(0); },
    libraryItemType, itemTypes, onItemTypeChange: (t) => { setLibraryItemType(t); setPage(0); },
    libraryReading, onReadingFilter: changeReadingFilter,
    libraryMissingPdf, onToggleMissingPdf: () => { setLibraryMissingPdf(v => !v); setPage(0); },
    onToggleLibrarySelect: toggleLibrarySelect, onClearLibrarySelect: clearLibrarySelect,
    onBulkDelete: bulkDeletePapers, onBulkSummarize: bulkSummarizePapers, onBulkPcurve: bulkPcurvePapers, onBulkMerge: bulkMergePapers, onBulkCriticalRead: bulkCriticalReadPapers, onBulkExport: bulkExportPapers, onBulkExportBundle: bulkExportBundle, onBulkBibliography: bulkBibliography, onSelectAll: selectAllLibrary,
    onBulkReferenceCheckDone: bulkReferenceCheckDone,
    libraryAxisFilter, onClearAxisFilter: clearAxisFilter,
    libraryTagFilter, onClearTagFilter: clearTagFilter,
    libraryNeedsReview, onToggleNeedsReview: toggleNeedsReview, onClearNeedsReview: clearNeedsReview,
    librarySignalFilter, onClearSignalFilter: clearSignalFilter,
    libraryTextHealthFilter, onClearTextHealthFilter: clearTextHealthFilter,
    libraryReferenceFilter, onClearReferenceFilter: clearReferenceFilter,
    statcheckFlagged, onShowStatcheckFlagged: showStatcheckFlagged,
    retractionFlagged, onShowRetractionFlagged: showRetractionFlagged,
    openDataDetected, onShowTransparencyReview: showTransparencyReview,
    lmmFlagged, onShowLmmFlagged: showLmmFlagged,
    findingsToReview, onShowFindingsToReview: showFindingsToReview,
    findingsByPaper, referenceWarningsByPaper,
    onToggleTrash: toggleTrash, onRestore: restorePaper,
    onPurge: purgePaper, onEmptyTrash: emptyTrash,
    onCitationsRefreshed: () => setLibRefresh(n => n + 1), onEnriched: () => setLibRefresh(n => n + 1),
    onRetractionRan: () => { refreshRetractionChip(); setLibRefresh(n => n + 1); setFindingsRefresh(n => n + 1); },
    savedSearches, onApplySavedSearch: applySavedSearch, onSaveSearch: saveCurrentSearch, onDeleteSavedSearch: deleteSavedSearch,
  };

  return {
    libraryBits, setLibRefresh,
    pendingSummarize, summarizePaperIds,
    filterToTag, filterToAxis, clearViewFilters, showNeedsReview,
    showStatcheckFlagged, showRetractionFlagged, showTransparencyReview, showLmmFlagged,
    refreshStatcheckChip, refreshRetractionChip, refreshTransparencyChip, refreshLmmChip, setFindingsRefresh, setReferenceWarningsRefresh, showTextHealthFilter,
    pcurvePapers, setPcurvePapers, mergeIds, setMergeIds, onMerged,
    critSetIds, setCritSetIds,
  };
}
