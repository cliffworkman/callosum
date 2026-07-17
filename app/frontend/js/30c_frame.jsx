// The Library workspace body — the library list + one sub-tab per open PDF, with a Reading-mode toggle. (Formerly
// the whole center frame; in inc 280 the Discover/Feed/Extract top-level tabs graduated to menu-bar *workspaces*
// [04b_workspaces.jsx] and the My-Pubs dashboard to the Profile workspace, so this is now just Library.) PDF tabs
// stay mounted (hidden) so switching back doesn't re-stream them. The Extract "select-in-PDF" capture (inc 255) now
// lives in the shell (40_app) and is threaded through so a PdfViewer surfaces the capture UI + returns the anchor —
// arming it opens the paper under Library, and applying it switches back to Extract. Hoists reference PdfViewer /
// PaperList regardless of chunk order.
const WORKSPACES_WHATSNEW_KEY = "callosum.workspaces-whatsnew";

function WorkspacesWhatsNewHint({ readOnly }) {
  const [dismissed, setDismissed] = useState(() => _loadLayout(WORKSPACES_WHATSNEW_KEY, "0") === "1");
  if (readOnly !== false || dismissed) return null;
  const dismiss = () => {
    setDismissed(true);
    _saveLayout(WORKSPACES_WHATSNEW_KEY, "1");
  };
  return (
    <div className="axis-hint workspace-whatsnew" role="status">
      <span>New layout: <b>Wanted</b>, <b>Gaps</b>, and <b>Overlooked</b> are under <b>Discover → Search</b>; <b>Where to submit</b> + <b>Funding</b> under <b>Discover</b>; <b>Effect-size</b> + <b>Meta-analysis</b> under <b>Extract</b>; <b>Help</b> + <b>Settings</b> are on the menu bar.</span>
      <button type="button" className="btn-icon workspace-whatsnew-dismiss" aria-label="Dismiss workspace layout notice" title="Dismiss" onClick={dismiss}>×</button>
    </div>
  );
}

function LibraryFrame({ libraryProps, tabs, activeTab, onActivate, onClose, onOpenPdf, annoRefresh, readingMode, onToggleReading, mobile, capture, onCaptureAnchor, onCancelCapture }) {
  return (
    <div className="lib-frame">
      <WorkspacesWhatsNewHint readOnly={libraryProps && libraryProps.readOnly} />
      <div className="frame-tabs">
        <button
          className={"frame-tab" + (activeTab === "library" ? " active" : "")}
          onClick={() => onActivate("library")}
        >Library</button>
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
      {tabs.map(t => (
        <div key={t.key} className="frame-pane" style={{ display: activeTab === t.key ? "flex" : "none" }}>
          <PdfViewer paperId={t.paperId} title={t.title} target={t.target || null} annoRefresh={annoRefresh} mobile={mobile}
            armedCapture={capture && !capture.result && capture.paperId === t.paperId ? capture : null}
            onCaptureAnchor={onCaptureAnchor} onCancelCapture={onCancelCapture} />
        </div>
      ))}
    </div>
  );
}
