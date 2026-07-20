// App: the root component. Cohesive pieces live in their own chunks to keep this file small: layout helpers +
// the Divider + useUiPrefs in 04_layout.jsx (inc 128); the library-list subsystem (filters/fetch/bulk/saved-
// searches/chips/findings) in useLibrary, 03_library.jsx (inc 221); the axis focus-mode hook useFocusMode in
// 39_focus.jsx (inc 167); the citation-download helpers in 00_lib.jsx (inc 167). App owns the shell + wiring.
function App() {
  const [conn, setConn] = useState({ state: "wait" });
  const [settingsNonce, setSettingsNonce] = useState(0);  // inc 280: bumped on LEAVING the Settings workspace → panes re-read egress state (inc 148)
  const [authLocked, setAuthLocked] = useState(false);  // inc 254: a 401 (Remote access on, no valid token) → AccessLockOverlay

  // theme + axis/scan prefs + side-panel layout + accordion-open + Reading mode (all in 04_layout.jsx).
  const {
    theme, setTheme,
    hideUncertainDefault, setHideUncertainDefault,
    axisCutoffDefault, setAxisCutoffDefault,
    autoScanWatched, setAutoScanWatched,
    leftW, setLeftW, rightW, setRightW, leftOpen, setLeftOpen, rightOpen, setRightOpen,
    theoryOpen, setTheoryOpen, methodsOpen, setMethodsOpen,
    readingMode, toggleReading,
    mobile, mobilePane, setMobilePane,
  } = useUiPrefs();

  const [selected, setSelected] = useState(null);
  // tabbed library frame: a persistent Library tab plus open PDF tabs.
  const [tabs, setTabs] = useState([]);            // [{ key, paperId, title, target }]
  const [selectedPaperTab, setSelectedPaperTab] = useState(null);  // selected in Library, not yet opened as a PDF tab
  const [activeTab, setActiveTab] = useState("library");
  // inc 280: the top-level "what am I doing" workspace (menu bar, 04b_workspaces.jsx). `activeTab` above is now the
  // Library workspace's sub-tab (the list | an open PDF). The active workspace persists across reloads; a
  // library-list navigation (filter/focus, via gotoLibrary) also switches to the Library workspace.
  const [activeWorkspace, setActiveWorkspace] = useState(() => _loadLayout("callosum.workspace", "library"));
  const [workspaceTabRequest, setWorkspaceTabRequest] = useState(null);
  const [citeTabRequest, setCiteTabRequest] = useState(null);
  const selectWorkspace = useCallback((id) => {
    // leaving Settings re-reads egress state in the panes (inc 148), the old modal-close behavior.
    setActiveWorkspace(prev => { if (prev === "settings" && id !== "settings") setSettingsNonce(n => n + 1); return id; });
    _saveLayout("callosum.workspace", id);
  }, []);
  const gotoLibrary = useCallback((t) => { selectWorkspace("library"); setActiveTab(t); }, [selectWorkspace]);
  const openSynthesisWorkspace = useCallback(() => {
    selectWorkspace("synthesis");
    setWorkspaceTabRequest(prev => ({ wsId: "synthesis", tabId: "ask", nonce: (prev ? prev.nonce : 0) + 1 }));
    if (mobile) setMobilePane("library");
  }, [mobile, selectWorkspace, setMobilePane]);
  const requestWorkspaceTab = useCallback((wsId, tabId) => {
    setWorkspaceTabRequest(prev => ({ wsId, tabId, nonce: (prev ? prev.nonce : 0) + 1 }));
  }, []);
  const requestCiteTab = useCallback((tabId) => {
    setCiteTabRequest(prev => ({ tabId, nonce: (prev ? prev.nonce : 0) + 1 }));
  }, []);
  // Bumped after a synthesis highlight is saved, so an already-open PdfViewer refetches its annotations (PdfViewer).
  const [annoRefresh, setAnnoRefresh] = useState(0);
  const [queueRefresh, setQueueRefresh] = useState(0);  // inc 219: bump to reload the Queue tab after add/remove
  const [tagRefresh, setTagRefresh] = useState(0);      // inc-96: bump to refetch the sidebar Tags browser

  // Modal-open state (rendered below). Bulk-action modals (p-curve, merge) live in useLibrary (the bulk actions
  // that open them + onMerged do). Refs break the focus↔library cycle: useLibrary's filter/merge callbacks need
  // cancelFocus + setAxisRefresh, which come from useFocusMode (declared after useLibrary). See below.
  const [duplicatesOpen, setDuplicatesOpen] = useState(false);  // inc-56 duplicate-detection modal
  const [dupMergedIds, setDupMergedIds] = useState(null);       // inc-301: last merged group's ids → hide its dup card
  const [wantedOpen, setWantedOpen] = useState(false);          // inc-76 wanted-list / OA re-check modal
  const [textHealthOpen, setTextHealthOpen] = useState(false);  // local PDF text-health maintenance queue
  const [textHealthContext, setTextHealthContext] = useState(null);  // optional source scope, e.g. Synthesis retry
  const [gapsOpen, setGapsOpen] = useState(false);              // inc-135 literature gap-finder modal
  const [overlookedOpen, setOverlookedOpen] = useState(false);  // #37 overlooked-work lens (per-axis discovery)
  const [scanOpen, setScanOpen] = useState(false);              // inc-87 scan-a-folder modal
  const [importOpen, setImportOpen] = useState(false);          // inc-93 import-citations modal
  const [bundleImportOpen, setBundleImportOpen] = useState(false); // B2 SP1 import-library-bundle modal
  const cancelFocusRef = useRef(() => {});
  const setAxisRefreshRef = useRef(() => {});

  // B5 SP2: read-only mode (from /health.read_only). Declared before useLibrary so the library hook can suppress its
  // on-load watched-folder rescan (a write) — a read-only companion never fires a write. healthLoaded gates the
  // launch rescan until /health has resolved, so it never fires the doomed write before readOnly is known.
  // undefined until /health resolves (so a background read-implemented-as-POST like /citations/render doesn't fire
  // before we know); then true (read-only) or false (read-write). The write-control gates treat undefined as falsy.
  const [readOnly, setReadOnly] = useState(undefined);
  const [healthLoaded, setHealthLoaded] = useState(false);

  // The library-list subsystem (inc 221). Cross-cutting setters go in via opts; cancelFocus + setAxisRefresh are
  // resolved through refs (set after useFocusMode) because useFocusMode is declared after useLibrary but its
  // onEnterClearFilters must call lib.clearViewFilters — breaking the cycle.
  const lib = useLibrary({
    selected, setSelected, setActiveTab: gotoLibrary,
    cancelFocus: () => cancelFocusRef.current(),
    setLeftOpen, setTheoryOpen, setMethodsOpen, setSettingsOpen: () => {}, onOpenSynthesis: openSynthesisWorkspace,
    setTagRefresh, setAxisRefresh: (fn) => setAxisRefreshRef.current(fn), autoScanWatched, readOnly, healthLoaded,
  });
  const {
    libraryBits, setLibRefresh, pendingSummarize, summarizePaperIds,
    filterToTag, filterToAxis, clearViewFilters, showNeedsReview,
    showStatcheckFlagged, showRetractionFlagged, showTransparencyReview, showTextHealthFilter, refreshStatcheckChip, refreshRetractionChip, refreshTransparencyChip, setFindingsRefresh, setReferenceWarningsRefresh,
    pcurvePapers, setPcurvePapers, mergeIds, setMergeIds, onMerged,
    critSetIds, setCritSetIds,
  } = lib;

  const {
    focusAxis, focusMembers, focusPending, axisRefresh, setAxisRefresh,
    enterFocus, cancelFocus, toggleFocusPaper, saveFocus,
  } = useFocusMode({ setActiveTab: gotoLibrary, onEnterClearFilters: clearViewFilters });
  cancelFocusRef.current = cancelFocus;       // resolve the refs the library subsystem calls through
  setAxisRefreshRef.current = setAxisRefresh;

  // B5 (inc 239): when a citation opens a source on mobile, remember to offer a "← Synthesis" back pill (the reader
  // is in a different region than the synthesis it came from). A plain paper-open clears it.
  const [citationReturn, setCitationReturn] = useState(false);

  const openPdf = useCallback((paper, target) => {
    const key = "pdf:" + paper.id;
    const title = paper.title || ("Paper " + paper.id);
    // inc 308 (QA): when the caller already knows this paper has no attachment (the library card carries
    // attachment_count), skip the doomed /pdf fetch entirely instead of opening a tab that 404s. Callers that
    // don't have this info (e.g. a bare {id, title} from a citation jump) pass `undefined` → unchanged behavior.
    const hasPdf = paper.attachment_count == null ? null : paper.attachment_count > 0;
    setTabs(prev => {
      const found = prev.some(t => t.key === key);
      const nextTarget = target === undefined ? null : target;
      if (!found) return [...prev, { key, paperId: paper.id, title, target: nextTarget, hasPdf }];
      // Don't clobber an already-known hasPdf with "unknown" from a caller that didn't pass attachment_count.
      return prev.map(t => t.key === key ? { ...t, title, target: nextTarget, hasPdf: hasPdf == null ? t.hasPdf : hasPdf } : t);
    });
    selectWorkspace("library");  // a PDF opens under the Library workspace
    setActiveTab(key);  // focuses the existing tab if already open
    if (mobile) { setMobilePane("library"); setCitationReturn(false); }  // pull the reader region into view
  }, [mobile, setMobilePane, selectWorkspace]);

  // inc 280: the Extract "select-in-PDF" capture (formerly in LibraryFrame) lives here now that Extract + the Library
  // PDF tabs are different workspaces. Arming opens the paper UNDER Library (openPdf → selectWorkspace("library"));
  // applying the anchor switches back to Extract so the grid can consume the result.
  const [capture, setCapture] = useState(null);
  const armCapture = useCallback((t) => {
    setCapture({ paperId: t.paperId, projectId: t.projectId, rowId: t.rowId, fieldKey: t.fieldKey, fieldLabel: t.fieldLabel });
    openPdf(t.paper, t.page ? { id: `wbcap:${t.rowId}:${t.fieldKey}`, paperId: t.paperId, page: t.page, precision: null } : undefined);
  }, [openPdf]);
  const captureAnchor = useCallback((result) => { setCapture(c => (c ? { ...c, result } : c)); selectWorkspace("extract"); }, [selectWorkspace]);
  const clearCapture = useCallback(() => setCapture(null), []);

  const openCitation = useCallback((citation) => {
    const target = citationTarget(citation);
    if (!target) return;
    openPdf({ id: target.paperId, title: target.paperTitle }, target);
    if (mobile) setCitationReturn(true);   // came from a synthesis → show the back pill on the reader
  }, [openPdf, mobile]);

  const openPaperDetails = useCallback((paper) => {
    if (!paper || paper.id == null) return;
    setSelected(paper.id);
    setMethodsOpen("details");
    if (mobile) setMobilePane("methods");
  }, [mobile, setMethodsOpen, setMobilePane]);

  const openReferenceWarnings = useCallback((paper) => {
    if (!paper || paper.id == null) return;
    setSelected(paper.id);
    requestWorkspaceTab("work", "cite");
    requestCiteTab("meta-references");
    selectWorkspace("work");
    if (mobile) setMobilePane("library");
  }, [mobile, requestWorkspaceTab, requestCiteTab, selectWorkspace, setMobilePane]);
  const openTextHealth = useCallback((context = null) => {
    setTextHealthContext(context || null);
    setTextHealthOpen(true);
  }, []);

  // Save a verified, exact-coordinate citation passage as a durable annotation (source="synthesis"). Re-checks the
  // honesty contract here too, so the precise-save path can never be reached for region/null/flagged citations.
  const saveCitationHighlight = useCallback(async (citation) => {
    if (!citation || citation.paper_id == null) return { ok: false, error: "No paper for this citation." };
    const bboxes = normalizeBboxes(citation.bbox_json);
    if (citation.coordinate_precision !== "exact" || citation.status !== "verified" || bboxes.length === 0) {
      return { ok: false, error: "Only verified, exact-coordinate citations can be saved as a precise highlight." };
    }
    const r = await apiPost(`/papers/${citation.paper_id}/annotations`, {
      page: citation.page_start, color: HIGHLIGHT_COLORS[0], bboxes, anchor_text: citation.quote || "", source: "synthesis",
    });
    if (r.ok) setAnnoRefresh(n => n + 1);
    return r;
  }, []);

  const closeTab = useCallback((key) => {
    setTabs(prev => prev.filter(t => t.key !== key));
    setActiveTab(prev => (prev === key ? "library" : prev));
  }, []);

  const activatePaperTab = useCallback((key) => {
    if (!key) return;
    selectWorkspace("library");
    setActiveTab(key);
    if (mobile) setMobilePane("library");
  }, [mobile, selectWorkspace, setMobilePane]);

  const reorderPdfTabs = useCallback((draggedKey, targetKey) => {
    if (!draggedKey || !targetKey || draggedKey === targetKey) return;
    setTabs(prev => {
      const from = prev.findIndex(t => t.key === draggedKey);
      const to = prev.findIndex(t => t.key === targetKey);
      if (from < 0 || to < 0) return prev;
      const next = [...prev];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  }, []);

  useEffect(() => {
    if (selected == null || tabs.some(t => t.paperId === selected)) {
      setSelectedPaperTab(null);
      return undefined;
    }
    let live = true;
    api(`/papers/${selected}`).then(r => {
      if (!live) return;
      const p = r.ok ? r.data : null;
      setSelectedPaperTab({ id: selected, title: (p && p.title) || `Paper ${selected}` });
    });
    return () => { live = false; };
  }, [selected, tabs]);

  // inc 254: any 401 from the api* helpers means Remote access is on but this browser holds no valid token — a
  // lockout. Register ONE handler (the api* layer notifies it) that raises the honest recovery overlay.
  useEffect(() => { onAuthRequired(() => setAuthLocked(true)); }, []);

  // health check (readOnly declared above, before useLibrary, so the library hook can suppress its on-load write).
  useEffect(() => {
    api("/health").then(r => {
      if (r.ok) {
        setConn({ state: "ok", version: (r.data && (r.data.verification_version || r.data.version)) || null });
        setReadOnly(!!(r.data && r.data.read_only));
      } else setConn({ state: "bad" });
      setHealthLoaded(true);
    });
  }, []);

  // Esc exits Reading mode (skip while a modal owns Escape, so it closes the modal first).
  const anyModalOpen = duplicatesOpen || wantedOpen || textHealthOpen || gapsOpen || overlookedOpen || scanOpen || importOpen || bundleImportOpen || !!pcurvePapers;
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
  const selectedOpenPaperTab = selected == null ? null : (tabs.find(t => t.paperId === selected) || null);

  // inc 121: one prop-bundle the accordion hands to each section's render(ctx).
  const paneCtx = {
    readOnly,  // B5 SP2: hide write controls in every section when the instance is read-only
    conn, selectedPaper: selected, onSelectPaper: setSelected, onOpenPaper: openPdf,
    onOpenCitation: openCitation, onSaveHighlight: saveCitationHighlight,
    onFilterToTag: filterToTag, onFilterToAxis: filterToAxis, onEnterFocus: enterFocus,
    onTagsChanged: () => setTagRefresh(n => n + 1),
    // inc 294: a queue change (drag/add/remove) also reloads the library list so each card's priority control
    // re-syncs from the new papers.priority — keeps the Queue strata and the cards showing one source of truth.
    onQueueChanged: () => { setQueueRefresh(n => n + 1); setLibRefresh(n => n + 1); },
    pendingSummarize, axisRefresh, tagRefresh, queueRefresh, hideUncertainDefault, axisCutoffDefault,
    methodsOpen,  // inc-140: the open METHODS section id, so a section can tell when it's the active one (statcheck auto-run)
    onShowStatcheckFlagged: showStatcheckFlagged, onStatcheckRan: refreshStatcheckChip,
    onShowRetractionFlagged: showRetractionFlagged, onRetractionRan: refreshRetractionChip,
    onShowTransparencyReview: showTransparencyReview, onTransparencyRan: refreshTransparencyChip,  // inc 251
    onFindingsChanged: () => setFindingsRefresh(n => n + 1),
    onReferenceWarningsChanged: () => setReferenceWarningsRefresh(n => n + 1),
    onOpenTextHealth: openTextHealth,
    onOpenSettings: () => selectWorkspace("settings"), settingsNonce,  // inc 148 / inc 280: synthesis egress nudge → Settings workspace
    onCriticalReviewSources: (ids) => setCritSetIds(ids),  // #12: synthesis → critically review its source papers as a set
  };

  // inc 280: props the menu-bar workspace sub-tabs' render(ctx, active) closures need (Discover: Search/Feed via
  // onDiscoverSaved; Extract: Workbench via the capture trio + onOpenPdf).
  const workspaceCtx = {
    ...paneCtx,
    onDiscoverSaved: () => setLibRefresh(n => n + 1),
    onOpenWanted: () => setWantedOpen(true),
    onOpenGaps: () => setGapsOpen(true),
    onOpenOverlooked: () => setOverlookedOpen(true),
    onOpenPdf: openPdf, onOpenPaper: openPdf,
    selectedPaper: selected,  // Work/Discover/Extract tabs read the app-level selection
    selectedPaperTab, selectedOpenPaperTab, onActivatePaperTab: activatePaperTab,
    workspaceTabRequest, citeTabRequest,
    capture, onArmCapture: armCapture, onCaptureApplied: clearCapture,
  };

  // B5 (inc 237): compute the three region nodes + the modals once, then render either the desktop grid or the
  // single-column mobile stack. Only one layout branch renders per pass, so reusing an element instance is safe.
  const sidebarEl = (
    <Sidebar conn={conn} ctx={paneCtx} theoryOpen={theoryOpen} onTheoryOpen={setTheoryOpen} />
  );
  // inc 280: the center pane = the active menu-bar workspace. All workspaces stay mounted (hidden) so in-progress
  // state (a running search, the Extract grid) survives switching. Library + My Publications are shell-rendered here (their
  // bodies are bespoke); Discover + Extract render their registered sub-tabs via WorkspacePane.
  const centerEl = (
    <div className="workspace-frame">
      {/* inc 301: hide the menu bar in read mode (the focused reader); the reader's own Reading toggle exits it. */}
      {!readingMode && <MenuBar active={activeWorkspace} onActivate={selectWorkspace} readOnly={readOnly} mobile={mobile} />}
      <div className="workspace-slot" style={{ display: activeWorkspace === "library" ? "flex" : "none" }}>
        <LibraryFrame
          libraryProps={{
            ...libraryBits,
            readOnly,
            // inc 294: a card priority change reloads the Queue tab (the card is already optimistic, so no library
            // reload needed here) — the other half of keeping the cards ↔ Queue strata in sync.
            onReadingChanged: () => setQueueRefresh(n => n + 1),
            selected, onSelect: setSelected,
            focusAxis, focusMembers, focusPending,
            onToggleFocusPaper: toggleFocusPaper, onSaveFocus: saveFocus, onCancelFocus: cancelFocus,
            onFindDuplicates: () => setDuplicatesOpen(true),
            onOpenTextHealth: () => openTextHealth(),
            onOpenReferenceWarnings: openReferenceWarnings,
            onOpenScan: () => setScanOpen(true), onOpenImport: () => setImportOpen(true),
            onOpenImportBundle: () => setBundleImportOpen(true), onExportBundle: () => downloadBundle("library"),
          }}
          tabs={tabs} selectedPaperTab={selectedPaperTab} activeTab={activeTab}
          onActivate={setActiveTab} onClose={closeTab} onOpenPdf={openPdf} onReorderTabs={reorderPdfTabs}
          annoRefresh={annoRefresh}
          readingMode={readingMode} onToggleReading={toggleReading}
          mobile={mobile}
          capture={capture} onCaptureAnchor={captureAnchor} onCancelCapture={clearCapture}
        />
      </div>
      <div className="workspace-slot" style={{ display: activeWorkspace === "profile" ? "flex" : "none" }}>
        <MyPubsDashboard axisRefresh={axisRefresh}
          onSummarize={summarizePaperIds} onSelectPaper={setSelected} onOpenPdf={openPdf} />
      </div>
      <div className="workspace-slot" style={{ display: activeWorkspace === "synthesis" ? "flex" : "none" }}>
        <WorkspacePane ws={getWorkspace("synthesis")} ctx={workspaceCtx} readOnly={readOnly} wsActive={activeWorkspace === "synthesis"} />
      </div>
      <div className="workspace-slot" style={{ display: activeWorkspace === "discover" ? "flex" : "none" }}>
        <WorkspacePane ws={getWorkspace("discover")} ctx={workspaceCtx} readOnly={readOnly} wsActive={activeWorkspace === "discover"} />
      </div>
      <div className="workspace-slot" style={{ display: activeWorkspace === "work" ? "flex" : "none" }}>
        <WorkspacePane ws={getWorkspace("work")} ctx={workspaceCtx} readOnly={readOnly} wsActive={activeWorkspace === "work"} />
      </div>
      <div className="workspace-slot" style={{ display: activeWorkspace === "extract" ? "flex" : "none" }}>
        <WorkspacePane ws={getWorkspace("extract")} ctx={workspaceCtx} readOnly={readOnly} wsActive={activeWorkspace === "extract"} />
      </div>
      {/* Help + Settings (utility workspaces) lazy-mount — heavier + rarely open, and settings should re-read fresh. */}
      {activeWorkspace === "help" &&
        <div className="workspace-slot" style={{ display: "flex" }}><HelpView /></div>}
      {activeWorkspace === "settings" &&
        <div className="workspace-slot" style={{ display: "flex" }}>
          <SettingsView theme={theme} onTheme={setTheme} hideUncertainDefault={hideUncertainDefault} onHideUncertainDefault={setHideUncertainDefault}
            axisCutoffDefault={axisCutoffDefault} onAxisCutoffDefault={setAxisCutoffDefault} onMyPubsRefreshed={() => setAxisRefresh(n => n + 1)}
            autoScanWatched={autoScanWatched} onAutoScanWatched={setAutoScanWatched} />
        </div>}
    </div>
  );
  const detailEl = (
    <div className="pane pane-detail"><PaneAccordion paneId="methods" ctx={paneCtx} openId={methodsOpen} onOpen={setMethodsOpen} /></div>
  );
  const modals = (
    <React.Fragment>
      {duplicatesOpen &&
        <DuplicatesModal onClose={() => setDuplicatesOpen(false)} onOpenPaper={openPdf}
          onChanged={() => setLibRefresh(n => n + 1)} onMerge={(ids) => setMergeIds(ids)}
          mergedIds={dupMergedIds} onMergeDone={() => setDupMergedIds(null)} />}
      {mergeIds &&
        <MergePapersModal ids={mergeIds} onClose={() => setMergeIds(null)}
          onMerged={(survivorId) => { if (duplicatesOpen) setDupMergedIds(mergeIds); onMerged(survivorId); }} />}
      {critSetIds &&
        <CriticalSetModal ids={critSetIds} onClose={() => setCritSetIds(null)} onOpenPaper={openPdf} />}
      {wantedOpen &&
        <WantedModal onClose={() => setWantedOpen(false)} onOpenPaper={openPdf} onChanged={() => setLibRefresh(n => n + 1)} />}
      {textHealthOpen &&
        <TextHealthModal onClose={() => { setTextHealthOpen(false); setTextHealthContext(null); }} onOpenPaper={openPdf}
          onOpenDetails={openPaperDetails} onShowLibrary={showTextHealthFilter}
          onChanged={() => setLibRefresh(n => n + 1)} context={textHealthContext} />}
      {gapsOpen &&
        <GapsModal onClose={() => setGapsOpen(false)} onChanged={() => setLibRefresh(n => n + 1)} />}
      {overlookedOpen &&
        <OverlookedLensModal onClose={() => setOverlookedOpen(false)} onChanged={() => setLibRefresh(n => n + 1)} />}
      {pcurvePapers &&
        <PcurveModal paperIds={pcurvePapers} onClose={() => setPcurvePapers(null)} onOpenPaper={openPdf} onChanged={() => setLibRefresh(n => n + 1)} />}
      {scanOpen &&
        <ScanModal onClose={() => setScanOpen(false)} onScanned={() => setLibRefresh(n => n + 1)} onShowUnsorted={showNeedsReview} />}
      {importOpen &&
        <ImportModal onClose={() => setImportOpen(false)} onImported={() => setLibRefresh(n => n + 1)} />}
      {bundleImportOpen &&
        <BundleImportModal onClose={() => setBundleImportOpen(false)}
          onImported={() => { setLibRefresh(n => n + 1); setAxisRefresh(n => n + 1); }} />}
      {authLocked && <AccessLockOverlay />}
    </React.Fragment>
  );

  const readOnlyBadge = readOnly ? <div className="read-only-badge" title="This callosum instance rejects changes — reading only.">🔒 Read-only</div> : null;

  if (mobile) {
    const activeEl = mobilePane === "theory" ? sidebarEl : mobilePane === "methods" ? detailEl : centerEl;
    // B5 (inc 239): a one-tap return to the synthesis you came from (only while reading the source it opened).
    const selectMobilePane = (pane) => { setMobilePane(pane); setCitationReturn(false); };
    const backPill = citationReturn && mobilePane === "library"
      ? <button className="pdf-back-pill" onClick={() => { selectWorkspace("synthesis"); selectMobilePane("library"); }}>← Synthesis</button>
      : null;
    return (
      <AppReadOnly.Provider value={readOnly}>
      <div className={"app mobile" + (readOnly ? " read-only" : "")}>
        {readOnlyBadge}
        <div className="mobile-body">{activeEl}</div>
        {backPill}
        <MobileNav active={mobilePane} onSelect={selectMobilePane} />
        {modals}
      </div>
      </AppReadOnly.Provider>
    );
  }

  return (
    <AppReadOnly.Provider value={readOnly}>
    <div className={"app" + (readingMode ? " reading" : "") + (readOnly ? " read-only" : "")} style={{ gridTemplateColumns: cols }}>
      {readOnlyBadge}
      {leftOpen && !readingMode ? sidebarEl : <div className="pane-collapsed" />}
      <Divider
        side="left" open={leftOpen} onToggle={() => setLeftOpen(o => !o)}
        onDragStart={(e) => { const sx = e.clientX, sw = leftW; _beginDrag(e, (x) => {
          const proposed = sw + (x - sx);
          if (proposed < LEFT_COLLAPSE_AT) setLeftOpen(false);
          else { setLeftOpen(true); setLeftW(_clampW(proposed, LEFT_MIN, LEFT_MAX)); }
        }); }}
      />
      {centerEl}
      <Divider
        side="right" open={rightOpen} onToggle={() => setRightOpen(o => !o)}
        onDragStart={(e) => { const sx = e.clientX, sw = rightW; _beginDrag(e, (x) => {
          const proposed = sw - (x - sx);
          if (proposed < RIGHT_COLLAPSE_AT) setRightOpen(false);
          else { setRightOpen(true); setRightW(_clampW(proposed, RIGHT_MIN, RIGHT_MAX)); }
        }); }}
      />
      {rightOpen && !readingMode ? detailEl : <div className="pane-collapsed" />}
      {modals}
    </div>
    </AppReadOnly.Provider>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
