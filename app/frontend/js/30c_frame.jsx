// The Library workspace body — the library list + one sub-tab per open PDF, with a Reading-mode toggle. (Formerly
// the whole center frame; in inc 280 the Discover/Feed/Extract top-level tabs graduated to menu-bar *workspaces*
// [04b_workspaces.jsx] and the My-Pubs dashboard to the My Publications workspace, so this is now just Library;
// Extract was later folded into Work → Meta-Analyze.) PDF tabs stay mounted (hidden) so switching back doesn't
// re-stream them. The Workbench "select-in-PDF" capture (inc 255) now lives in the shell (40_app) and is threaded
// through so a PdfViewer surfaces the capture UI + returns the anchor — arming it opens the paper under Library,
// and applying it switches back to Work → Meta-Analyze. Hoists reference PdfViewer / PaperList regardless of
// chunk order.
const LOCAL_AI_WHATSNEW_KEY = "callosum.local-ai-whatsnew.v1";

function LocalAiWhatsNewHint({ readOnly, mobile, onOpenLocalAi }) {
  const [dismissed, setDismissed] = useState(() => _loadLayout(LOCAL_AI_WHATSNEW_KEY, "0") === "1");
  if (readOnly !== false || dismissed) return null;
  const dismiss = () => {
    setDismissed(true);
    _saveLayout(LOCAL_AI_WHATSNEW_KEY, "1");
  };
  return (
    <div className="axis-hint workspace-whatsnew" role="region" aria-label="What's new">
      <span>{mobile
        ? <><b>New: Local AI.</b> Run Callosum's AI features on this device — no API key required.</>
        : <><b>New: Local AI.</b> Run Callosum's compatible AI features on this device — no API key or cloud account required.</>}
      </span>
      <div className="workspace-whatsnew-actions">
        <button type="button" className="btn btn-link" onClick={onOpenLocalAi}>Set up Local AI</button>
        <button type="button" className="btn-icon workspace-whatsnew-dismiss" aria-label="Dismiss Local AI notice" title="Dismiss" onClick={dismiss}>×</button>
      </div>
    </div>
  );
}

const PDF_TAB_DRAG_TYPE = "application/x-callosum-pdftab";
const WIP_TAB_DRAG_TYPE = "application/x-callosum-wiptab";

function LibraryFrame({ libraryProps, wip, wipTabs, selectedWipTab, tabs, selectedPaperTab, activeTab, onActivate, onClose, onCloseWip, onOpenPdf, onOpenWip, onReorderTabs, onReorderWipTabs, annoRefresh, readingMode, onToggleReading, mobile, capture, onCaptureAnchor, onCancelCapture, onOpenLocalAi, onOpenLibraryFolders }) {
  const [dragOverKey, setDragOverKey] = useState(null);
  const openSelectedPaper = () => {
    if (!selectedPaperTab) return;
    onOpenPdf({ id: selectedPaperTab.id, title: selectedPaperTab.title });
  };
  return (
    <div className="lib-frame">
      <LocalAiWhatsNewHint readOnly={libraryProps && libraryProps.readOnly} mobile={mobile} onOpenLocalAi={onOpenLocalAi} />
      <div className="frame-tabs">
        <button
          className={"frame-tab" + (activeTab === "library" ? " active" : "")}
          onClick={() => onActivate("library")}
        >Library</button>
        {wip.enabled && <button
          className={"frame-tab frame-tab-wip" + (activeTab === "wip" ? " active" : "")}
          onClick={() => onActivate("wip")}
        >WIP</button>}
        {selectedPaperTab &&
          <button
            className="frame-tab frame-tab-selected"
            title="Selected paper, not open — click to open the PDF"
            onClick={openSelectedPaper}
          >
            <span className="frame-tab-label">{selectedPaperTab.title}</span>
          </button>}
        {selectedWipTab &&
          <button
            className="frame-tab frame-tab-selected frame-tab-selected-wip"
            title="Selected WIP manuscript, not open — click to open its workspace"
            onClick={() => onOpenWip(selectedWipTab)}
          >
            <span className="wip-badge">WIP</span>
            <span className="frame-tab-label">{selectedWipTab.display_title}</span>
          </button>}
        {wipTabs.map(t => (
          <span key={t.key}
            draggable
            className={"frame-tab frame-tab-wip-manuscript" + (activeTab === t.key ? " active" : "") +
              (dragOverKey === t.key ? " dragover" : "")}
            onClick={() => onActivate(t.key)}
            onDragStart={event => {
              event.dataTransfer.setData(WIP_TAB_DRAG_TYPE, t.key);
              event.dataTransfer.effectAllowed = "move";
            }}
            onDragOver={event => {
              if (!Array.from(event.dataTransfer.types || []).includes(WIP_TAB_DRAG_TYPE)) return;
              event.preventDefault();
              event.dataTransfer.dropEffect = "move";
              setDragOverKey(t.key);
            }}
            onDragLeave={() => setDragOverKey(key => (key === t.key ? null : key))}
            onDrop={event => {
              const dragged = event.dataTransfer.getData(WIP_TAB_DRAG_TYPE);
              setDragOverKey(null);
              if (!dragged || dragged === t.key) return;
              event.preventDefault();
              event.stopPropagation();
              onReorderWipTabs(dragged, t.key);
            }}
            onDragEnd={() => setDragOverKey(null)}>
            <span className="wip-badge">WIP</span>
            <span className="frame-tab-label" title={t.title}>{t.title}</span>
            <button className="frame-tab-close" title="Close manuscript tab"
              onClick={(e) => { e.stopPropagation(); onCloseWip(t.key); }}>×</button>
          </span>
        ))}
        {tabs.map(t => (
          <span
            key={t.key}
            draggable
            className={"frame-tab" + (activeTab === t.key ? " active" : "") + (dragOverKey === t.key ? " dragover" : "")}
            onClick={() => onActivate(t.key)}
            onDragStart={(e) => {
              e.dataTransfer.setData(PDF_TAB_DRAG_TYPE, t.key);
              e.dataTransfer.effectAllowed = "move";
            }}
            onDragOver={(e) => {
              if (!Array.from(e.dataTransfer.types || []).includes(PDF_TAB_DRAG_TYPE)) return;
              e.preventDefault();
              e.dataTransfer.dropEffect = "move";
              setDragOverKey(t.key);
            }}
            onDragLeave={() => setDragOverKey(k => (k === t.key ? null : k))}
            onDrop={(e) => {
              const dragged = e.dataTransfer.getData(PDF_TAB_DRAG_TYPE);
              setDragOverKey(null);
              if (!dragged || dragged === t.key) return;
              e.preventDefault();
              e.stopPropagation();
              onReorderTabs(dragged, t.key);
            }}
            onDragEnd={() => setDragOverKey(null)}
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
      {wip.enabled && <div className="frame-pane" style={{ display: activeTab === "wip" ? "flex" : "none" }}>
        <WipBrowser wip={wip} onOpen={onOpenWip} />
      </div>}
      {wipTabs.map(t => (
        <div key={t.key} className="frame-pane" style={{ display: activeTab === t.key ? "flex" : "none" }}>
          <WipDetails manuscript={t.manuscript} onUpdate={wip.updateManuscript}
            onRelinked={wip.reload} onOpenPaper={onOpenPdf} workspace externalRefresh={wip.refresh} />
        </div>
      ))}
      {tabs.map(t => (
        <div key={t.key} className="frame-pane" style={{ display: activeTab === t.key ? "flex" : "none" }}>
          <PdfViewer paperId={t.paperId} title={t.title} target={t.target || null} annoRefresh={annoRefresh} mobile={mobile}
            knownNoPdf={t.hasPdf === false}
            onOpenRepair={onOpenLibraryFolders}
            armedCapture={capture && !capture.result && capture.paperId === t.paperId ? capture : null}
            onCaptureAnchor={onCaptureAnchor} onCancelCapture={onCancelCapture} />
        </div>
      ))}
    </div>
  );
}
