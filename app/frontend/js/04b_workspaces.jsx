// Workspaces (the menu bar) — a SECOND navigation dimension above the THEORY/METHODS side accordions. Where the
// accordions are *lenses on the current paper* (05_panes.jsx), a workspace is *what you're doing right now*:
// Profile | Library | Discover | Extract (primary) + Help | Settings (right-aligned utilities). Sections-are-data,
// exactly like 05_panes.jsx: a workspace self-registers with an order; it holds EITHER a single `render` (Profile,
// Help, Settings) OR >=2 sub-tabs (Discover: Search|Journals|Funding; Extract: Workbench|Effect-size|Meta).
// Library is registered as a shell-rendered workspace (no registered tabs) because its content — the library list +
// the dynamic open-PDF tabs — is bespoke and owned by 40_app. Render closures resolve their components by hoist
// (the 05_panes `details`→`DetailContent` precedent), so a workspace defined here can reference a component from a
// later chunk. See DESIGN.md §5.
const WORKSPACES = [];

function _ensureWs(id) {
  let w = WORKSPACES.find(x => x.id === id);
  if (!w) { w = { id, label: id, order: 0, hideInReadOnly: false, utility: false, tabs: [], render: null, defined: false }; WORKSPACES.push(w); }
  return w;
}
function _addWsTab(ws, tab) {
  if (!ws.tabs.some(t => t.id === tab.id)) ws.tabs.push(tab);  // idempotent by tab id
}

// Define a workspace. label/order/hideInReadOnly/utility are authoritative regardless of chunk-load order. A
// `render` makes it a single-view workspace (added as its lone tab); omit it for a shell-rendered workspace
// (Library/Profile) whose body 40_app supplies, or when only registerWorkspaceTab calls will populate it.
function registerWorkspace(ws) {
  const w = _ensureWs(ws.id);
  w.label = ws.label; w.order = ws.order || 0; w.hideInReadOnly = !!ws.hideInReadOnly; w.utility = !!ws.utility; w.defined = true;
  if (ws.render) { w.render = ws.render; _addWsTab(w, { id: ws.id, label: ws.tabLabel || ws.label, order: 0, render: ws.render, hideInReadOnly: !!ws.hideInReadOnly }); }
  return w;
}
// Add a sub-tab to a (find-or-create) workspace. Host metadata seeds a not-yet-`defined` workspace only.
function registerWorkspaceTab(host, tab) {
  const w = _ensureWs(host.id);
  if (!w.defined) { w.label = host.label; w.order = host.order || 0; if (host.hideInReadOnly != null) w.hideInReadOnly = !!host.hideInReadOnly; if (host.utility != null) w.utility = !!host.utility; }
  _addWsTab(w, tab);
}

function _wsHiddenReadOnly(w) {
  // Hidden on a read-only companion if the workspace is flagged, or it has registered tabs and EVERY one is hidden.
  // A shell-rendered workspace (0 registered tabs, e.g. Library/Profile) shows unless explicitly hideInReadOnly.
  if (w.hideInReadOnly) return true;
  return w.tabs.length > 0 && w.tabs.every(t => t.hideInReadOnly);
}
function workspaces(readOnly) {
  return WORKSPACES.filter(w => !(readOnly && _wsHiddenReadOnly(w))).sort((a, b) => (a.order || 0) - (b.order || 0));
}
function workspaceTabs(w, readOnly) {
  return [...w.tabs].filter(t => !(readOnly && t.hideInReadOnly)).sort((a, b) => (a.order || 0) - (b.order || 0));
}
function getWorkspace(id) { return WORKSPACES.find(w => w.id === id) || null; }

// The global top bar: brand + the primary workspace switcher + right-aligned utilities (Help/Settings).
function MenuBar({ active, onActivate, readOnly }) {
  const all = workspaces(readOnly);
  const primary = all.filter(w => !w.utility);
  const utils = all.filter(w => w.utility);
  const item = (w) => (
    <button key={w.id} role="tab" aria-selected={w.id === active}
      className={"menubar-item" + (w.id === active ? " active" : "")}
      onClick={() => onActivate(w.id)}>{w.label}</button>
  );
  return (
    <div className="menubar">
      <nav className="menubar-nav" role="tablist" aria-label="Workspaces">{primary.map(item)}</nav>
      <div className="menubar-utils">{utils.map(item)}</div>
    </div>
  );
}

// Renders a registered workspace's sub-tabs (a segmented `.tags-srcfilter` strip when >=2) or its single view.
// Sub-tab bodies mount-but-hide (`.pane-tab:not(.active){display:none}`) so an in-progress action survives a switch.
// `wsActive` = whether this whole workspace is the active one, so a tab render can poll only when truly visible
// (FeedPane): render(ctx, isVisible). The active sub-tab persists to callosum.workspacetab.<id>.
function WorkspacePane({ ws, ctx, readOnly, wsActive }) {
  const tabs = workspaceTabs(ws, readOnly);
  const [activeTab, setActiveTab] = useState(() => _loadLayout("callosum.workspacetab." + ws.id, tabs[0] ? tabs[0].id : null));
  if (tabs.length === 0) return null;
  const at = tabs.some(t => t.id === activeTab) ? activeTab : tabs[0].id;
  const setTab = (id) => { setActiveTab(id); _saveLayout("callosum.workspacetab." + ws.id, id); };
  return (
    <div className="workspace-pane">
      {tabs.length > 1 &&
        <div className="tags-srcfilter workspace-tabs" role="tablist">
          {tabs.map(t => (
            <button key={t.id} role="tab" aria-selected={t.id === at}
              className={"tags-srcfilter-btn" + (t.id === at ? " on" : "")}
              onClick={() => setTab(t.id)}>{t.label}</button>
          ))}
        </div>}
      {tabs.map(t => (
        <div key={t.id} className={"workspace-body pane-tab" + (t.id === at ? " active" : "")}>
          {t.render(ctx, !!wsActive && t.id === at)}
        </div>
      ))}
    </div>
  );
}

// ── the built-in workspaces ─────────────────────────────────────────────────────────────────────────────────
// Library + Profile are SHELL-RENDERED (no `render`): 40_app owns their bespoke bodies (the library list + dynamic
// open-PDF tabs; the impact dashboard). Discover + Extract are populated by tabs (self-registered here for the
// built-ins; Stage 2 relocates Journals/Funding/Effect-size/Meta-analysis into them by `registerWorkspaceTab`).
// Every write surface's tab carries `hideInReadOnly` so the whole workspace drops on a read-only companion.
registerWorkspace({ id: "profile", label: "Profile", order: 10 });
registerWorkspace({ id: "library", label: "Library", order: 20 });
registerWorkspace({ id: "discover", label: "Discover", order: 30 });
registerWorkspace({ id: "extract", label: "Extract", order: 40 });

registerWorkspaceTab({ id: "discover" }, {
  id: "search", label: "Search", order: 10, hideInReadOnly: true,
  render: (ctx, active) => <DiscoverPane onSaved={ctx.onDiscoverSaved} active={active}
    onOpenWanted={ctx.onOpenWanted} onOpenGaps={ctx.onOpenGaps} onOpenOverlooked={ctx.onOpenOverlooked} />,
});
registerWorkspaceTab({ id: "extract" }, {
  id: "workbench", label: "Workbench", order: 10, hideInReadOnly: true,
  render: (ctx, active) => <WorkbenchPane active={active} onOpenPdf={ctx.onOpenPdf}
    capture={ctx.capture} onArmCapture={ctx.onArmCapture} onCaptureApplied={ctx.onCaptureApplied} />,
});

// inc 280 (stage 3): the right-aligned utility workspaces (Help, Settings) — formerly modals. Shell-rendered:
// 40_app supplies HelpView / SettingsView (with its many prefs props) in centerEl, like Library/Profile.
registerWorkspace({ id: "help", label: "Help", order: 100, utility: true });
registerWorkspace({ id: "settings", label: "Settings", order: 110, utility: true });
