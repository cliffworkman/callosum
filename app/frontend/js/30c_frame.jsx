// The center library-frame shell — a persistent Library tab + one tab per open PDF (and per dashboard / Search).
// Extracted from 30_viewer.jsx (inc 182) to relieve the 600-line cap there and give the discovery Search tab (#28)
// a home. PDF tabs stay mounted (hidden) so switching back doesn't re-stream them. Function declarations hoist
// within the shared IIFE, so this references PdfViewer / PaperList / MyPubsDashboard regardless of chunk order.
function LibraryFrame({ libraryProps, tabs, activeTab, onActivate, onClose, onOpenPdf, onSummarizePapers, onSelectPaper, onDiscoverSaved, annoRefresh, readingMode, onToggleReading, mobile }) {
  // inc 255 (workbench SP2a-2): shared "select-in-PDF" capture state. It must live above BOTH the Extract grid and
  // the PDF tabs, because arming opens the paper (switching the active center tab away from Extract) and the result
  // is applied back in the grid. null | { paperId, projectId, rowId, fieldKey, fieldLabel, result? }.
  const [capture, setCapture] = useState(null);
  const armCapture = useCallback((t) => {
    setCapture({ paperId: t.paperId, projectId: t.projectId, rowId: t.rowId, fieldKey: t.fieldKey, fieldLabel: t.fieldLabel });
    // open the paper; scroll to the anchored page if one exists (precision:null draws nothing — just lands the page).
    onOpenPdf(t.paper, t.page ? { id: `wbcap:${t.rowId}:${t.fieldKey}`, paperId: t.paperId, page: t.page, precision: null } : undefined);
  }, [onOpenPdf]);
  const captureAnchor = useCallback((result) => { setCapture(c => (c ? { ...c, result } : c)); onActivate("extract"); }, [onActivate]);
  const clearCapture = useCallback(() => setCapture(null), []);
  return (
    <div className="lib-frame">
      <div className="frame-tabs">
        <button
          className={"frame-tab" + (activeTab === "library" ? " active" : "")}
          onClick={() => onActivate("library")}
        >Library</button>
        {/* B5 SP2: Discover + Feed need write/non-forwarded endpoints — hidden on a read-only companion. */}
        {!libraryProps.readOnly && <button
          className={"frame-tab" + (activeTab === "search" ? " active" : "")}
          onClick={() => onActivate("search")}
        >Discover</button>}
        {!libraryProps.readOnly && <button
          className={"frame-tab" + (activeTab === "feed" ? " active" : "")}
          onClick={() => onActivate("feed")}
        >Feed</button>}
        {/* inc 253: the meta-analysis extraction workspace — a write surface, hidden on a read-only companion. */}
        {!libraryProps.readOnly && <button
          className={"frame-tab" + (activeTab === "extract" ? " active" : "")}
          onClick={() => onActivate("extract")}
        >Extract</button>}
        {tabs.map(t => (
          <span
            key={t.key}
            className={"frame-tab" + (activeTab === t.key ? " active" : "")}
            onClick={() => onActivate(t.key)}
          >
            <span className="frame-tab-label" title={t.title}>{t.title}</span>
            <button
              className="frame-tab-close"
              title="Close tab"
              onClick={(e) => { e.stopPropagation(); onClose(t.key); }}
            >×</button>
          </span>
        ))}
        {onToggleReading &&
          <button
            className={"frame-reading" + (readingMode ? " active" : "")}
            title={readingMode ? "Exit reading mode (Esc)" : "Reading mode — hide the side panels and focus the center pane"}
            onClick={onToggleReading}
          >{readingMode ? "⤢ Exit" : "⛶ Read"}</button>}
      </div>
      <div className="frame-pane" style={{ display: activeTab === "library" ? "flex" : "none" }}>
        <PaperList {...libraryProps} onOpenPdf={onOpenPdf} />
      </div>
      <div className="frame-pane" style={{ display: activeTab === "search" ? "flex" : "none" }}>
        <DiscoverPane onSaved={onDiscoverSaved} />
      </div>
      <div className="frame-pane" style={{ display: activeTab === "feed" ? "flex" : "none" }}>
        <FeedPane onSaved={onDiscoverSaved} active={activeTab === "feed"} />
      </div>
      <div className="frame-pane" style={{ display: activeTab === "extract" ? "flex" : "none" }}>
        <WorkbenchPane active={activeTab === "extract"} onOpenPdf={onOpenPdf}
          capture={capture} onArmCapture={armCapture} onCaptureApplied={clearCapture} />
      </div>
      {tabs.map(t => (
        <div key={t.key} className="frame-pane" style={{ display: activeTab === t.key ? "flex" : "none" }}>
          {t.type === "dashboard"
            ? <MyPubsDashboard axisId={t.axisId} onSummarize={onSummarizePapers} onSelectPaper={onSelectPaper} onOpenPdf={onOpenPdf} />
            : <PdfViewer paperId={t.paperId} title={t.title} target={t.target || null} annoRefresh={annoRefresh} mobile={mobile}
                armedCapture={capture && !capture.result && capture.paperId === t.paperId ? capture : null}
                onCaptureAnchor={captureAnchor} onCancelCapture={clearCapture} />}
        </div>
      ))}
    </div>
  );
}
