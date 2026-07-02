// The center library-frame shell — a persistent Library tab + one tab per open PDF (and per dashboard / Search).
// Extracted from 30_viewer.jsx (inc 182) to relieve the 600-line cap there and give the discovery Search tab (#28)
// a home. PDF tabs stay mounted (hidden) so switching back doesn't re-stream them. Function declarations hoist
// within the shared IIFE, so this references PdfViewer / PaperList / MyPubsDashboard regardless of chunk order.
function LibraryFrame({ libraryProps, tabs, activeTab, onActivate, onClose, onOpenPdf, onSummarizePapers, onSelectPaper, onDiscoverSaved, annoRefresh, readingMode, onToggleReading, mobile }) {
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
        <WorkbenchPane active={activeTab === "extract"} onOpenPdf={onOpenPdf} />
      </div>
      {tabs.map(t => (
        <div key={t.key} className="frame-pane" style={{ display: activeTab === t.key ? "flex" : "none" }}>
          {t.type === "dashboard"
            ? <MyPubsDashboard axisId={t.axisId} onSummarize={onSummarizePapers} onSelectPaper={onSelectPaper} onOpenPdf={onOpenPdf} />
            : <PdfViewer paperId={t.paperId} title={t.title} target={t.target || null} annoRefresh={annoRefresh} mobile={mobile} />}
        </div>
      ))}
    </div>
  );
}
