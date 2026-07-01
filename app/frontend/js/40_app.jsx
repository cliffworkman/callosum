// App: the root component. Cohesive pieces live in their own chunks to keep this file small: layout helpers +
// the Divider + useUiPrefs in 04_layout.jsx (inc 128); the library-list subsystem (filters/fetch/bulk/saved-
// searches/chips/findings) in useLibrary, 03_library.jsx (inc 221); the axis focus-mode hook useFocusMode in
// 39_focus.jsx (inc 167); the citation-download helpers in 00_lib.jsx (inc 167). App owns the shell + wiring.
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
    mobile, mobilePane, setMobilePane,
  } = useUiPrefs();

  const [selected, setSelected] = useState(null);
  // tabbed library frame: a persistent Library tab plus open PDF tabs.
  const [tabs, setTabs] = useState([]);            // [{ key, paperId, title, target }]
  const [activeTab, setActiveTab] = useState("library");
  // Bumped after a synthesis highlight is saved, so an already-open PdfViewer refetches its annotations (PdfViewer).
  const [annoRefresh, setAnnoRefresh] = useState(0);
  const [queueRefresh, setQueueRefresh] = useState(0);  // inc 219: bump to reload the Queue tab after add/remove
  const [tagRefresh, setTagRefresh] = useState(0);      // inc-96: bump to refetch the sidebar Tags browser

  // Modal-open state (rendered below). Bulk-action modals (p-curve, merge) live in useLibrary (the bulk actions
  // that open them + onMerged do). Refs break the focus↔library cycle: useLibrary's filter/merge callbacks need
  // cancelFocus + setAxisRefresh, which come from useFocusMode (declared after useLibrary). See below.
  const [duplicatesOpen, setDuplicatesOpen] = useState(false);  // inc-56 duplicate-detection modal
  const [wantedOpen, setWantedOpen] = useState(false);          // inc-76 wanted-list / OA re-check modal
  const [gapsOpen, setGapsOpen] = useState(false);              // inc-135 literature gap-finder modal
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
    selected, setSelected, setActiveTab,
    cancelFocus: () => cancelFocusRef.current(),
    setLeftOpen, setTheoryOpen, setMethodsOpen, setSettingsOpen,
    setTagRefresh, setAxisRefresh: (fn) => setAxisRefreshRef.current(fn), autoScanWatched, readOnly, healthLoaded,
  });
  const {
    libraryBits, setLibRefresh, pendingSummarize, summarizePaperIds,
    filterToTag, filterToAxis, clearViewFilters, showNeedsReview,
    showStatcheckFlagged, showRetractionFlagged, refreshStatcheckChip, refreshRetractionChip, setFindingsRefresh,
    pcurvePapers, setPcurvePapers, mergeIds, setMergeIds, onMerged,
  } = lib;

  const {
    focusAxis, focusMembers, focusPending, axisRefresh, setAxisRefresh,
    enterFocus, cancelFocus, toggleFocusPaper, saveFocus,
  } = useFocusMode({ setActiveTab, onEnterClearFilters: clearViewFilters });
  cancelFocusRef.current = cancelFocus;       // resolve the refs the library subsystem calls through
  setAxisRefreshRef.current = setAxisRefresh;

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
  const anyModalOpen = settingsOpen || helpOpen || duplicatesOpen || wantedOpen || gapsOpen || scanOpen || importOpen || bundleImportOpen || !!pcurvePapers;
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

  // inc 121: one prop-bundle the accordion hands to each section's render(ctx).
  const paneCtx = {
    readOnly,  // B5 SP2: hide write controls in every section when the instance is read-only
    conn, selectedPaper: selected, onSelectPaper: setSelected, onOpenPaper: openPdf,
    onOpenCitation: openCitation, onSaveHighlight: saveCitationHighlight,
    onFilterToTag: filterToTag, onFilterToAxis: filterToAxis, onEnterFocus: enterFocus,
    onOpenMyPubsDashboard: openMyPubsDashboard, onTagsChanged: () => setTagRefresh(n => n + 1), onQueueChanged: () => setQueueRefresh(n => n + 1),
    pendingSummarize, axisRefresh, tagRefresh, queueRefresh, hideUncertainDefault, axisCutoffDefault,
    methodsOpen,  // inc-140: the open METHODS section id, so a section can tell when it's the active one (statcheck auto-run)
    onShowStatcheckFlagged: showStatcheckFlagged, onStatcheckRan: refreshStatcheckChip,
    onShowRetractionFlagged: showRetractionFlagged, onRetractionRan: refreshRetractionChip,
    onFindingsChanged: () => setFindingsRefresh(n => n + 1),
    onOpenSettings: () => setSettingsOpen(true), settingsNonce,  // inc 148: synthesis egress-off nudge → open Settings
  };

  // B5 (inc 237): compute the three region nodes + the modals once, then render either the desktop grid or the
  // single-column mobile stack. Only one layout branch renders per pass, so reusing an element instance is safe.
  const sidebarEl = (
    <Sidebar conn={conn} onOpenSettings={() => setSettingsOpen(true)} onOpenHelp={() => setHelpOpen(true)}
      ctx={paneCtx} theoryOpen={theoryOpen} onTheoryOpen={setTheoryOpen} />
  );
  const libraryFrame = (
    <LibraryFrame
      libraryProps={{
        ...libraryBits,
        readOnly,
        selected, onSelect: setSelected,
        focusAxis, focusMembers, focusPending,
        onToggleFocusPaper: toggleFocusPaper, onSaveFocus: saveFocus, onCancelFocus: cancelFocus,
        onFindDuplicates: () => setDuplicatesOpen(true),
        onOpenWanted: () => setWantedOpen(true),
        onOpenGaps: () => setGapsOpen(true),
        onOpenScan: () => setScanOpen(true), onOpenImport: () => setImportOpen(true),
        onOpenImportBundle: () => setBundleImportOpen(true), onExportBundle: () => downloadBundle("library"),
      }}
      tabs={tabs} activeTab={activeTab}
      onActivate={setActiveTab} onClose={closeTab} onOpenPdf={openPdf}
      onSummarizePapers={summarizePaperIds} onSelectPaper={setSelected}
      onDiscoverSaved={() => setLibRefresh(n => n + 1)}
      annoRefresh={annoRefresh}
      readingMode={readingMode} onToggleReading={toggleReading}
    />
  );
  const detailEl = (
    <div className="pane pane-detail"><PaneAccordion paneId="methods" ctx={paneCtx} openId={methodsOpen} onOpen={setMethodsOpen} /></div>
  );
  const modals = (
    <React.Fragment>
      {settingsOpen && <SettingsModal theme={theme} onTheme={setTheme} hideUncertainDefault={hideUncertainDefault} onHideUncertainDefault={setHideUncertainDefault} axisCutoffDefault={axisCutoffDefault} onAxisCutoffDefault={setAxisCutoffDefault} onMyPubsRefreshed={() => setAxisRefresh(n => n + 1)} autoScanWatched={autoScanWatched} onAutoScanWatched={setAutoScanWatched} onClose={() => { setSettingsOpen(false); setSettingsNonce(n => n + 1); }} />}
      {helpOpen && <HelpModal onClose={() => setHelpOpen(false)} />}
      {duplicatesOpen &&
        <DuplicatesModal onClose={() => setDuplicatesOpen(false)} onOpenPaper={openPdf}
          onChanged={() => setLibRefresh(n => n + 1)} onMerge={(ids) => setMergeIds(ids)} />}
      {mergeIds &&
        <MergePapersModal ids={mergeIds} onClose={() => setMergeIds(null)} onMerged={onMerged} />}
      {wantedOpen &&
        <WantedModal onClose={() => setWantedOpen(false)} onOpenPaper={openPdf} onChanged={() => setLibRefresh(n => n + 1)} />}
      {gapsOpen &&
        <GapsModal onClose={() => setGapsOpen(false)} onChanged={() => setLibRefresh(n => n + 1)} />}
      {pcurvePapers &&
        <PcurveModal paperIds={pcurvePapers} onClose={() => setPcurvePapers(null)} onOpenPaper={openPdf} onChanged={() => setLibRefresh(n => n + 1)} />}
      {scanOpen &&
        <ScanModal onClose={() => setScanOpen(false)} onScanned={() => setLibRefresh(n => n + 1)} onShowUnsorted={showNeedsReview} />}
      {importOpen &&
        <ImportModal onClose={() => setImportOpen(false)} onImported={() => setLibRefresh(n => n + 1)} />}
      {bundleImportOpen &&
        <BundleImportModal onClose={() => setBundleImportOpen(false)}
          onImported={() => { setLibRefresh(n => n + 1); setAxisRefresh(n => n + 1); }} />}
    </React.Fragment>
  );

  const readOnlyBadge = readOnly ? <div className="read-only-badge" title="This callosum instance rejects changes — reading only.">🔒 Read-only</div> : null;

  if (mobile) {
    const activeEl = mobilePane === "theory" ? sidebarEl : mobilePane === "methods" ? detailEl : libraryFrame;
    return (
      <div className={"app mobile" + (readOnly ? " read-only" : "")}>
        {readOnlyBadge}
        <div className="mobile-body">{activeEl}</div>
        <MobileNav active={mobilePane} onSelect={setMobilePane} />
        {modals}
      </div>
    );
  }

  return (
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
      {libraryFrame}
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
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
