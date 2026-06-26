// App: the root component. Layout helpers, the Divider, and the persisted-UI-state hook (useUiPrefs) live in
// 04_layout.jsx (extracted inc 128 to keep this file under the 600-line cap).
function App() {
  const [conn, setConn] = useState({ state: "wait" });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsNonce, setSettingsNonce] = useState(0);  // bumped on Settings close → panes re-read egress state (inc 148)
  const [helpOpen, setHelpOpen] = useState(false);

  // theme + axis/scan prefs + side-panel layout + accordion-open + Reading mode (all in 04_layout.jsx).
  const {
    theme, setTheme,
    hideUncertainDefault, setHideUncertainDefault,
    axisCutoffDefault, setAxisCutoffDefault,
    autoScanWatched, setAutoScanWatched,
    leftW, setLeftW, rightW, setRightW, leftOpen, setLeftOpen, rightOpen, setRightOpen,
    theoryOpen, setTheoryOpen, methodsOpen, setMethodsOpen,
    readingMode, toggleReading,
  } = useUiPrefs();

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
  const [libraryNeedsReview, setLibraryNeedsReview] = useState(false);  // inc-79: the "Unsorted" (needs-metadata) view
  const [librarySignalFilter, setLibrarySignalFilter] = useState(null);  // inc-97: a Methods-signal view, e.g. "statcheck-inconsistent"
  const [statcheckFlagged, setStatcheckFlagged] = useState(0);  // inc-100: # papers the last statcheck run flagged → header chip
  const [retractionFlagged, setRetractionFlagged] = useState(0);  // inc-131: # papers a registry records retracted → header chip
  const [librarySort, setLibrarySort] = useState(() => {  // inc-69; persisted inc-94
    try { return localStorage.getItem("callosum.librarySort") || "added"; } catch (e) { return "added"; }
  });
  const [librarySearchField, setLibrarySearchField] = useState("all");  // inc-89: search scope (all/title/author/journal)
  const [libraryItemType, setLibraryItemType] = useState("");  // inc-91: filter to a single CSL item type ("" = all)
  const [itemTypes, setItemTypes] = useState([]);  // inc-91: distinct item types present in the library (Type dropdown)
  const [libRefresh, setLibRefresh] = useState(0);
  const pendingSelectTopRef = useRef(false);  // inc-140: a view-change (e.g. the flagged chip) wants the next loaded list's top paper selected
  const [tagRefresh, setTagRefresh] = useState(0);  // inc-96: bump to refetch the sidebar Tags browser (tag add/remove)
  const [duplicatesOpen, setDuplicatesOpen] = useState(false);  // inc-56 duplicate-detection modal
  const [wantedOpen, setWantedOpen] = useState(false);          // inc-76 wanted-list / OA re-check modal
  const [gapsOpen, setGapsOpen] = useState(false);              // inc-135 literature gap-finder modal
  const [scanOpen, setScanOpen] = useState(false);              // inc-87 scan-a-folder modal
  const [importOpen, setImportOpen] = useState(false);          // inc-93 import-citations modal

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

  // inc-81: open the My Publications impact dashboard as a frame tab (reuses the LibraryFrame tab system).
  const openMyPubsDashboard = useCallback((axis) => {
    const key = "dashboard:my-publications";
    setTabs(prev => (prev.some(t => t.key === key)
      ? prev
      : [...prev, { key, type: "dashboard", title: "My Publications", axisId: axis && axis.id }]));
    setActiveTab(key);
  }, []);

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
    setLibrarySignalFilter(null);
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
  // A nonce makes each click a fresh trigger; inc 121: synthesis lives in the THEORY (left) accordion now, so
  // open the left pane + switch it to the SYNTHESIS section so the result is visible.
  const bulkSummarizePapers = useCallback((focus) => {
    const ids = [...selectedLibraryIds];
    if (!ids.length) return;
    // inc-145: an optional focus query from the selection bar → a query-RANKED synthesis of just the selection.
    setPendingSummarize(prev => ({ paper_ids: ids, count: ids.length, nonce: (prev ? prev.nonce : 0) + 1, focus: (focus || "").trim() || null }));
    setLeftOpen(true); setTheoryOpen("synthesis");
    setSelectedLibraryIds(new Set());
  }, [selectedLibraryIds]);

  // inc-126: run a collection-level p-curve over the selection (the modal owns the job + render). null = closed.
  const [pcurvePapers, setPcurvePapers] = useState(null);
  const bulkPcurvePapers = useCallback(() => {
    const ids = [...selectedLibraryIds];
    if (ids.length) { setPcurvePapers(ids); setSelectedLibraryIds(new Set()); }
  }, [selectedLibraryIds]);

  // inc 117 (SP1): summarize an explicit id set (from the My Publications tab) → drive the synthesis section.
  const summarizePaperIds = useCallback((ids) => {
    if (!ids || !ids.length) return;
    setPendingSummarize(prev => ({ paper_ids: ids, count: ids.length, nonce: (prev ? prev.nonce : 0) + 1 }));
    setLeftOpen(true); setTheoryOpen("synthesis");
  }, []);

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

  // inc-106: download a FORMATTED bibliography for the selection (citeproc engine → sanitized HTML → .html file).
  const bulkBibliography = useCallback((style) => {
    const ids = [...selectedLibraryIds];
    if (!ids.length) return;
    (async () => {
      const r = await apiPost("/citations/render", { paper_ids: ids, style });
      if (!r.ok) { console.warn("[callosum] bibliography failed:", r.error); return; }
      const entries = (r.data && r.data.bibliography_html) || [];
      if (!entries.length) return;
      const body = entries.map(e => `<p style="text-indent:-2em;padding-left:2em;margin:0 0 .6em">${e}</p>`).join("");
      const html = `<!doctype html><meta charset="utf-8"><title>Bibliography (${style})</title>` +
        `<body style="font-family:Georgia,'Times New Roman',serif;font-size:12pt;line-height:1.5;max-width:46em;margin:2em auto">${body}</body>`;
      const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
      const a = document.createElement("a");
      a.href = url; a.download = `callosum-bibliography-${style}.html`;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(url);
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
    setLibraryNeedsReview(false);      // …and the Unsorted view
    setLibrarySignalFilter(null);      // …and the statcheck signal view
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
    setLibraryNeedsReview(false);
    setLibrarySignalFilter(null);
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
    setLibraryNeedsReview(false);
    setLibrarySignalFilter(null);
    cancelFocus();
  }, [cancelFocus]);
  const clearTagFilter = useCallback(() => { setLibraryTagFilter(null); setPage(0); }, []);
  const selectAllLibrary = useCallback((ids) => setSelectedLibraryIds(new Set(ids)), []);
  const changeSort = useCallback((s) => {  // inc-69: re-sort from page 1; inc-94: persist the choice
    setLibrarySort(s);
    setPage(0);
    try { localStorage.setItem("callosum.librarySort", s); } catch (e) { /* ignore */ }
  }, []);

  // inc-79: the "Unsorted" view — papers whose metadata still needs review (raw scaffolds / Crossref-unresolved
  // / no source). A view like Trash (exclusive with trash/axis/tag/focus) but keeps checkbox-select usable.
  const toggleNeedsReview = useCallback(() => {
    setLibraryNeedsReview(v => {
      const next = !v;
      if (next) { setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibrarySignalFilter(null); cancelFocus(); }
      return next;
    });
    setSelectedLibraryIds(new Set());
    setPage(0);
  }, [cancelFocus]);
  const clearNeedsReview = useCallback(() => { setLibraryNeedsReview(false); setPage(0); }, []);
  // inc-142: jump straight to the Unsorted view (e.g. from the scan done-summary's "Review unsorted →" door).
  const showNeedsReview = useCallback(() => {
    setLibraryNeedsReview(true);
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibrarySignalFilter(null); cancelFocus();
    setSelectedLibraryIds(new Set()); setPage(0);
  }, [cancelFocus]);

  // inc-97: the statcheck library lens — set from Settings after a batch run. A view like the others (clears
  // trash/axis/tag/needs-review/focus); filters to papers with a persisted reporting inconsistency.
  const showStatcheckFlagged = useCallback(() => {
    setLibrarySignalFilter("statcheck-inconsistent");
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); cancelFocus();
    setSelectedLibraryIds(new Set());
    pendingSelectTopRef.current = true;  // inc-140: select the top of the freshly-loaded FLAGGED list (not the stale one) so the section lands on a flagged paper
    setSettingsOpen(false);
    setActiveTab("library");
    setMethodsOpen("statcheck");  // inc-140: open the METHODS Statistics check section so the flagged paper's check is right there (auto-runs)
    setPage(0);
  }, [cancelFocus, setMethodsOpen]);
  const clearSignalFilter = useCallback(() => { setLibrarySignalFilter(null); setPage(0); }, []);

  // inc-122: refresh the header "N flagged" chip from the persisted statcheck summary (cache-only count). Called
  // on mount and by the METHODS "Statistics check" section after a batch run (ctx.onStatcheckRan).
  const refreshStatcheckChip = useCallback(() => {
    api("/methods/statcheck/summary").then(r => { if (r.ok) setStatcheckFlagged(r.data.flagged || 0); });
  }, []);

  // inc-131: the retraction library lens — mirror the statcheck chip/filter. A registry FACT (verify before
  // citing), never an accusation. The chip jumps to the "Retracted" filter view; the count is cache-only.
  const showRetractionFlagged = useCallback(() => {
    setLibrarySignalFilter("retraction-retracted");
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); cancelFocus();
    setSelectedLibraryIds(new Set());
    setSettingsOpen(false);
    setActiveTab("library");
    setPage(0);
  }, [cancelFocus]);
  const refreshRetractionChip = useCallback(() => {
    api("/methods/retraction/summary").then(r => { if (r.ok) setRetractionFlagged(r.data.retracted || 0); });
  }, []);

  // inc-130: per-paper findings overview → the library "N to review" badge + FactMark. Re-fetched after a review.
  const [findingsByPaper, setFindingsByPaper] = useState({});
  const [findingsRefresh, setFindingsRefresh] = useState(0);
  useEffect(() => {
    api("/findings/overview").then(r => {
      if (!r.ok) return;
      const m = {}; r.data.forEach(o => { m[o.paper_id] = o; }); setFindingsByPaper(m);
    });
  }, [findingsRefresh, libRefresh]);
  // inc-133: the unified review queue — # papers with an unreviewed candidate (cheap derive); the header chip
  // jumps to the needs-review filter view (reuses librarySignalFilter, like the statcheck/retraction chips).
  const findingsToReview = Object.values(findingsByPaper).filter(o => o.unreviewed_count > 0).length;
  const showFindingsToReview = useCallback(() => {
    setLibrarySignalFilter("needs-review");
    setTrashView(false); setLibraryAxisFilter(null); setLibraryTagFilter(null); setLibraryNeedsReview(false); cancelFocus();
    setSelectedLibraryIds(new Set());
    setSettingsOpen(false);
    setActiveTab("library");
    setPage(0);
  }, [cancelFocus]);

  // health check
  useEffect(() => {
    api("/health").then(r => {
      if (r.ok) setConn({ state: "ok", version: (r.data && (r.data.verification_version || r.data.version)) || null });
      else setConn({ state: "bad" });
    });
  }, []);

  // inc-98: re-scan watched folders on launch (default on; Settings toggle). Non-blocking background job — the
  // rescan endpoint no-ops if there are no watched folders. Bumps libRefresh/tagRefresh when new papers land.
  // inc-136: rescan on launch AND whenever the window regains focus (you dropped a PDF in the folder, then
  // switched back) — so a watched folder feels live without a manual "Re-scan all". Throttled to avoid hammering
  // the disk on rapid focus changes; in-flight guard prevents overlapping scans.
  const rescanInFlight = useRef(false);
  const lastRescan = useRef(0);
  const triggerWatchedRescan = useCallback(() => {
    if (!autoScanWatched || rescanInFlight.current) return;
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
  }, [autoScanWatched]);
  useEffect(() => {
    triggerWatchedRescan();  // on launch
    const onFocus = () => triggerWatchedRescan();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [triggerWatchedRescan]);

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
    if (debounced.trim() && librarySearchField !== "all") qs.set("search_field", librarySearchField);
    if (trashView) qs.set("deleted", "true");
    if (libraryAxisFilter) qs.set("axis_id", libraryAxisFilter.id);
    if (libraryTagFilter) qs.set("tag_id", libraryTagFilter.id);
    if (libraryItemType) qs.set("item_type", libraryItemType);
    if (libraryNeedsReview) qs.set("needs_review", "true");
    // inc-133: the unified "to review" view reuses librarySignalFilter with the sentinel "needs-review" (→ the
    // findings filter); any other value is a Methods signal (→ the signal filter).
    if (librarySignalFilter === "needs-review") qs.set("finding", "needs-review");
    else if (librarySignalFilter) qs.set("signal", librarySignalFilter);
    if (librarySort !== "added") qs.set("sort", librarySort);
    api(`/papers?${qs.toString()}`).then(r => {
      if (!live) return;
      if (r.ok) {
        setListState({ status: "ready", papers: r.data });
        if (pendingSelectTopRef.current) {  // inc-140: select the top of THIS freshly-loaded list (e.g. the flagged filter), not the stale one
          pendingSelectTopRef.current = false;
          setSelected(r.data.length ? r.data[0].id : null);
        }
      }
      else setListState({ status: "error", error: r.error, papers: [] });
    });
    return () => { live = false; };
  }, [page, debounced, librarySearchField, libraryItemType, trashView, libRefresh, libraryAxisFilter, libraryTagFilter, libraryNeedsReview, librarySignalFilter, librarySort, findingsRefresh]);

  // inc-91: distinct item types present in the library (for the Type filter dropdown); refresh on library change
  useEffect(() => {
    api("/papers/item-types").then(r => { if (r.ok) setItemTypes(r.data); });
  }, [libRefresh]);

  // inc-138: auto-select the top library paper on load so Details start populated (not the empty hint). Fires
  // only when nothing is selected and the (non-trash) list is ready with papers — covers first load + a cleared
  // selection (e.g. the selected paper was trashed). Never overrides a paper the user has already selected.
  useEffect(() => {
    if (selected == null && !trashView && listState.status === "ready" && listState.papers.length > 0) {
      setSelected(listState.papers[0].id);
    }
  }, [selected, trashView, listState]);

  // inc-100/122: the statcheck "N flagged" header chip — fetched on mount; refreshed after a batch run via the
  // METHODS "Statistics check" section's ctx.onStatcheckRan (the batch no longer lives in Settings).
  useEffect(() => { refreshStatcheckChip(); }, [refreshStatcheckChip]);
  useEffect(() => { refreshRetractionChip(); }, [refreshRetractionChip]);

  // Esc exits Reading mode (skip while a modal owns Escape, so it closes the modal first).
  const anyModalOpen = settingsOpen || helpOpen || duplicatesOpen || wantedOpen || gapsOpen || scanOpen || importOpen || !!pcurvePapers;
  useEffect(() => {
    if (!readingMode) return;
    const onKey = (e) => { if (e.key === "Escape" && !anyModalOpen) toggleReading(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [readingMode, anyModalOpen, toggleReading]);

  // Reading mode zeroes the divider tracks too (the panel tracks are already 0 via leftOpen/rightOpen).
  const cols = readingMode
    ? "0px 0px minmax(340px, 1fr) 0px 0px"
    : `${leftOpen ? leftW : 0}px 12px minmax(340px, 1fr) 12px ${rightOpen ? rightW : 0}px`;

  // inc 121: one prop-bundle the accordion hands to each section's render(ctx) — centralizes the threading the
  // old Sidebar/RightPane wrappers did. Each section picks the props it needs (see registerPaneSection calls).
  const paneCtx = {
    conn, selectedPaper: selected, onSelectPaper: setSelected, onOpenPaper: openPdf,
    onOpenCitation: openCitation, onSaveHighlight: saveCitationHighlight,
    onFilterToTag: filterToTag, onFilterToAxis: filterToAxis, onEnterFocus: enterFocus,
    onOpenMyPubsDashboard: openMyPubsDashboard, onTagsChanged: () => setTagRefresh(n => n + 1),
    pendingSummarize, axisRefresh, tagRefresh, hideUncertainDefault, axisCutoffDefault,
    methodsOpen,  // inc-140: the open METHODS section id, so a section can tell when it's the active one (statcheck auto-run)
    onShowStatcheckFlagged: showStatcheckFlagged, onStatcheckRan: refreshStatcheckChip,
    onShowRetractionFlagged: showRetractionFlagged, onRetractionRan: refreshRetractionChip,
    onFindingsChanged: () => setFindingsRefresh(n => n + 1),
    onOpenSettings: () => setSettingsOpen(true), settingsNonce,  // inc 148: synthesis egress-off nudge → open Settings
  };

  return (
    <div className={"app" + (readingMode ? " reading" : "")} style={{ gridTemplateColumns: cols }}>
      {leftOpen && !readingMode
        ? <Sidebar conn={conn} onOpenSettings={() => setSettingsOpen(true)} onOpenHelp={() => setHelpOpen(true)}
            ctx={paneCtx} theoryOpen={theoryOpen} onTheoryOpen={setTheoryOpen} />
        : <div className="pane-collapsed" />}
      <Divider
        side="left" open={leftOpen} onToggle={() => setLeftOpen(o => !o)}
        onDragStart={(e) => { const sx = e.clientX, sw = leftW; _beginDrag(e, (x) => {
          const proposed = sw + (x - sx);
          if (proposed < LEFT_COLLAPSE_AT) setLeftOpen(false);
          else { setLeftOpen(true); setLeftW(_clampW(proposed, LEFT_MIN, LEFT_MAX)); }
        }); }}
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
          librarySearchField, onSearchFieldChange: (f) => { setLibrarySearchField(f); setPage(0); },
          libraryItemType, itemTypes, onItemTypeChange: (t) => { setLibraryItemType(t); setPage(0); },
          onToggleLibrarySelect: toggleLibrarySelect, onClearLibrarySelect: clearLibrarySelect,
          onBulkDelete: bulkDeletePapers, onBulkSummarize: bulkSummarizePapers, onBulkPcurve: bulkPcurvePapers, onBulkExport: bulkExportPapers, onBulkBibliography: bulkBibliography, onSelectAll: selectAllLibrary,
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
          onFindDuplicates: () => setDuplicatesOpen(true),
          onOpenWanted: () => setWantedOpen(true),
          onOpenGaps: () => setGapsOpen(true),
          onOpenScan: () => setScanOpen(true),
          onOpenImport: () => setImportOpen(true),
        }}
        tabs={tabs} activeTab={activeTab}
        onActivate={setActiveTab} onClose={closeTab} onOpenPdf={openPdf}
        onSummarizePapers={summarizePaperIds} onSelectPaper={setSelected}
        annoRefresh={annoRefresh}
        readingMode={readingMode} onToggleReading={toggleReading}
      />
      <Divider
        side="right" open={rightOpen} onToggle={() => setRightOpen(o => !o)}
        onDragStart={(e) => { const sx = e.clientX, sw = rightW; _beginDrag(e, (x) => {
          const proposed = sw - (x - sx);
          if (proposed < RIGHT_COLLAPSE_AT) setRightOpen(false);
          else { setRightOpen(true); setRightW(_clampW(proposed, RIGHT_MIN, RIGHT_MAX)); }
        }); }}
      />
      {rightOpen && !readingMode
        ? <div className="pane pane-detail"><PaneAccordion paneId="methods" ctx={paneCtx} openId={methodsOpen} onOpen={setMethodsOpen} /></div>
        : <div className="pane-collapsed" />}
      {settingsOpen && <SettingsModal theme={theme} onTheme={setTheme} hideUncertainDefault={hideUncertainDefault} onHideUncertainDefault={setHideUncertainDefault} axisCutoffDefault={axisCutoffDefault} onAxisCutoffDefault={setAxisCutoffDefault} onMyPubsRefreshed={() => setAxisRefresh(n => n + 1)} autoScanWatched={autoScanWatched} onAutoScanWatched={setAutoScanWatched} onClose={() => { setSettingsOpen(false); setSettingsNonce(n => n + 1); }} />}
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
      {gapsOpen &&
        <GapsModal
          onClose={() => setGapsOpen(false)}
          onChanged={() => setLibRefresh(n => n + 1)}
        />}
      {pcurvePapers &&
        <PcurveModal
          paperIds={pcurvePapers}
          onClose={() => setPcurvePapers(null)}
          onOpenPaper={openPdf}
          onChanged={() => setLibRefresh(n => n + 1)}
        />}
      {scanOpen &&
        <ScanModal
          onClose={() => setScanOpen(false)}
          onScanned={() => setLibRefresh(n => n + 1)}
          onShowUnsorted={showNeedsReview}
        />}
      {importOpen &&
        <ImportModal
          onClose={() => setImportOpen(false)}
          onImported={() => setLibRefresh(n => n + 1)}
        />}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
