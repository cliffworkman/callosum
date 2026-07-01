// inc 128: layout helpers + the persisted-UI-state hook, extracted from 40_app.jsx (which hit the 600-line cap).
// Loads early so its module-scope helpers/constants are defined before any consumer runs (30_viewer.jsx uses
// _loadLayout/_saveLayout for its page-view pref; App uses the rest). Behavior-preserving relocation.

// --- resizable + collapsible side panels -------------------------------------------------
function _loadLayout(key, fallback) {
  try { const v = window.localStorage.getItem(key); return v == null ? fallback : v; } catch (e) { return fallback; }
}
function _saveLayout(key, value) {
  try { window.localStorage.setItem(key, String(value)); } catch (e) { /* ignore */ }
}
function _clampW(w, lo, hi) { return Math.max(lo, Math.min(hi, w)); }
// inc-104: side-panel min widths + Spotify-style pull-to-collapse. While dragging, a panel sticks at its min
// (the clamp floors it); pulling the resizer ~80px further past the min crosses COLLAPSE_AT → the panel collapses.
const LEFT_MIN = 300, LEFT_MAX = 600, LEFT_COLLAPSE_AT = 220;
const RIGHT_MIN = 415, RIGHT_MAX = 640, RIGHT_COLLAPSE_AT = 335;
function _beginDrag(e, onMove) {
  e.preventDefault();
  const move = (ev) => onMove(ev.clientX, ev.clientY);  // horizontal callers use x; the vertical split uses y
  const up = () => {
    document.removeEventListener("mousemove", move);
    document.removeEventListener("mouseup", up);
    document.body.style.userSelect = "";
  };
  document.addEventListener("mousemove", move);
  document.addEventListener("mouseup", up);
  document.body.style.userSelect = "none";  // no text selection while dragging
}

// Divider between a side panel and the center: drag the full-height grip to resize, click the
// chevron to collapse/expand the panel (so the user can focus on the PDF viewer).
function Divider({ side, open, onToggle, onDragStart }) {
  const chevron = side === "left" ? (open ? "‹" : "›") : (open ? "›" : "‹");
  return (
    <div className={"divider divider-" + side + (open ? "" : " collapsed")}>
      {open && <div className="divider-grip" onMouseDown={onDragStart} title="Drag to resize" />}
      <button className="divider-toggle" onClick={onToggle} title={open ? "Collapse panel" : "Expand panel"}>{chevron}</button>
    </div>
  );
}

// inc 128: the app's persisted UI state — theme + axis/scan prefs + side-panel layout + accordion-open +
// the transient Reading mode. All localStorage-backed bar readingMode. Extracted verbatim from App so the
// root component stays under the 600-line cap; behavior is unchanged.
function useUiPrefs() {
  // theme (light/dark) — the no-flash bootstrap in index.html already set data-theme on <html>; mirror it
  // into state, and the Settings toggle writes the attribute + localStorage.
  const [theme, setThemeState] = useState(() => {
    try { return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light"; }
    catch (e) { return "light"; }
  });
  const setTheme = useCallback((next) => {
    setThemeState(next);
    try { document.documentElement.setAttribute("data-theme", next); localStorage.setItem("callosum.theme", next); } catch (e) { /* ignore */ }
  }, []);
  // Axis default: start each axis card with its uncertain papers hidden (the inc-51 👁, as a Settings default).
  const [hideUncertainDefault, setHideUncertainDefaultState] = useState(() => _loadLayout("callosum.hideUncertainDefault", "0") === "1");
  const setHideUncertainDefault = useCallback((on) => {
    setHideUncertainDefaultState(on);
    _saveLayout("callosum.hideUncertainDefault", on ? "1" : "0");
  }, []);
  // inc-105: default axis cutoff — the value a new/unscored axis's re-score flipper starts at (per-axis override still wins).
  const [axisCutoffDefault, setAxisCutoffDefaultState] = useState(() => {
    const v = Number(_loadLayout("callosum.axisCutoffDefault", "0.35"));
    return v >= 0.2 && v <= 0.6 ? v : 0.35;
  });
  const setAxisCutoffDefault = useCallback((v) => {
    setAxisCutoffDefaultState(v);
    _saveLayout("callosum.axisCutoffDefault", v);
  }, []);
  const [autoScanWatched, setAutoScanWatchedState] = useState(() => _loadLayout("callosum.autoScanWatched", "1") === "1");  // inc-98: re-scan watched folders on launch
  const setAutoScanWatched = useCallback((on) => {
    setAutoScanWatchedState(on);
    _saveLayout("callosum.autoScanWatched", on ? "1" : "0");
  }, []);

  // side-panel layout (persisted): widths + collapsed state.
  const [leftW, setLeftW] = useState(() => Math.max(LEFT_MIN, Number(_loadLayout("callosum.leftW", LEFT_MIN)) || LEFT_MIN));
  const [rightW, setRightW] = useState(() => Math.max(RIGHT_MIN, Number(_loadLayout("callosum.rightW", RIGHT_MIN)) || RIGHT_MIN));
  const [leftOpen, setLeftOpen] = useState(() => _loadLayout("callosum.leftOpen", "1") !== "0");
  const [rightOpen, setRightOpen] = useState(() => _loadLayout("callosum.rightOpen", "1") !== "0");
  useEffect(() => { _saveLayout("callosum.leftW", leftW); }, [leftW]);
  useEffect(() => { _saveLayout("callosum.rightW", rightW); }, [rightW]);
  useEffect(() => { _saveLayout("callosum.leftOpen", leftOpen ? "1" : "0"); }, [leftOpen]);
  useEffect(() => { _saveLayout("callosum.rightOpen", rightOpen ? "1" : "0"); }, [rightOpen]);

  // inc 121: the open accordion section per pane (THEORY left = axes|synthesis|tags; METHODS right = details).
  const [theoryOpen, setTheoryOpen] = useState(() => _loadLayout("callosum.theoryOpen", "axes"));
  const [methodsOpen, setMethodsOpen] = useState(() => _loadLayout("callosum.methodsOpen", "details"));
  useEffect(() => { _saveLayout("callosum.theoryOpen", theoryOpen); }, [theoryOpen]);
  useEffect(() => { _saveLayout("callosum.methodsOpen", methodsOpen); }, [methodsOpen]);

  // inc-101: Reading mode is a transient visual override. It must not mutate leftOpen/rightOpen: those values
  // are persisted, so doing so would leave both panels collapsed after a reload from Reading mode.
  const [readingMode, setReadingMode] = useState(false);
  const toggleReading = useCallback(() => setReadingMode(on => !on), []);

  // B5 (inc 237): responsive mobile layout. `mobile` tracks a phone-width viewport (the inc-34 matchMedia-listener
  // pattern); `mobilePane` is which region shows one-at-a-time on mobile. Transient (not persisted — it follows
  // the device). The read-only guarantee lives at the cloudflared tunnel ingress, not here.
  const [mobile, setMobile] = useState(() => window.matchMedia("(max-width: 760px)").matches);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 760px)");
    const onChange = () => setMobile(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  const [mobilePane, setMobilePane] = useState("library");

  return {
    theme, setTheme,
    hideUncertainDefault, setHideUncertainDefault,
    axisCutoffDefault, setAxisCutoffDefault,
    autoScanWatched, setAutoScanWatched,
    leftW, setLeftW, rightW, setRightW, leftOpen, setLeftOpen, rightOpen, setRightOpen,
    theoryOpen, setTheoryOpen, methodsOpen, setMethodsOpen,
    readingMode, toggleReading,
    mobile, mobilePane, setMobilePane,
  };
}
