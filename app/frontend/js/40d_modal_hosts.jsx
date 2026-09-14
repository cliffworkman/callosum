// App-root self-hosted modal controllers (inc 602). Unlike the state-driven overlays in 40_app (pcurve, gaps,
// text-health, …) that render off App state, these are singleton hosts wired to window events
// (`callosum:open-critical-read`, `callosum:open-axis-ask`) so any surface can open them without prop-threading
// through App. Grouped here so App's render stays focused and adding another event-hosted modal doesn't grow
// 40_app.jsx. App supplies only the shared navigation/evidence handlers.
function AppEventModalHosts({ onOpenPaper, onOpenCitation, onSaveHighlight, onOpenSettings }) {
  return (
    <>
      <CriticalReadModalHost onOpenPaper={onOpenPaper} />{/* inc 601: reaccessible per-paper critique (reader + Status) */}
      <AxisAskModalHost onOpenCitation={onOpenCitation} onSaveHighlight={onSaveHighlight}
        onOpenSettings={onOpenSettings} />{/* inc 602 (#82): axis-scoped Ask interstitial + run */}
    </>
  );
}
