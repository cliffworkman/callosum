// inc 121: THEORY/METHODS side panes as an accordion on an extensible module registry. Each section chunk
// self-registers at load (chunk order 05<10<15<20<25 ⇒ this array exists before the register calls run). The
// accordion renders ALL of its pane's sections but shows only the open one (mount-but-hide), so an in-progress
// synthesis survives a section switch. Pane labels are deliberately "soft" (section headers only) for now; the
// paneId ("theory"|"methods") is the internal architecture + the eventual rename. See DESIGN.md (placement rubric).
//
// inc 139: a section can hold MULTIPLE TABS (like-with-like submenus) — e.g. AXES = [Axes | Tags], or the 2x2-grid
// Checklists = [Transparency | Mixed-model | Bayesian | Meta-analysis]. A section with one tab renders it directly
// (no strip); with >=2 it shows a segmented tab strip + the active tab (the inactive tabs stay mounted-but-hidden,
// like sections, so their in-progress state survives a tab switch). Every render(ctx, isVisible) also receives
// whether ITS section is open AND it is the active tab — a tab-owning component can no longer assume its own id
// equals the open section's id (2026-07-21, needed once Checklists made that assumption false for the first time).
// The tab strip's className carries a per-section "pane-tabs-<id>" hook so one section (e.g. Checklists) can opt
// into a bespoke layout (CSS-only) without changing this render logic again. DESIGN.md §5.
const PANE_SECTIONS = [];
function _ensureSection(id) {
  let s = PANE_SECTIONS.find(x => x.id === id);
  if (!s) { s = { id, label: id, paneId: "theory", order: 0, hideInReadOnly: false, tabs: [], defined: false }; PANE_SECTIONS.push(s); }
  return s;
}
function _addPaneTab(section, tab) {
  if (!section.tabs.some(t => t.id === tab.id)) section.tabs.push(tab);  // idempotent by tab id
}
function registerPaneSection(section) {
  // Defines a section: its label/paneId/order/hideInReadOnly are authoritative regardless of chunk-load order (so a
  // tab-adding chunk that loads first only seeds a placeholder). Adds its content as the first tab; `tabLabel`
  // overrides that tab's label (else the section label) — used when a section holds >1 tab (inc 248).
  const s = _ensureSection(section.id);
  s.label = section.label; s.paneId = section.paneId; s.order = section.order; s.hideInReadOnly = section.hideInReadOnly; s.defined = true;
  _addPaneTab(s, { id: section.id, label: section.tabLabel || section.label, order: 0, render: section.render, hideInReadOnly: section.hideInReadOnly });
}
function registerPaneTab(host, tab) {
  // Adds a tab to a (find-or-create) section. Host metadata seeds a not-yet-`defined` section only. A tab may carry
  // its own `hideInReadOnly` (inc 248) — hidden on a read-only companion even when the section stays visible.
  const s = _ensureSection(host.id);
  if (!s.defined) { s.label = host.label; s.paneId = host.paneId; s.order = host.order; if (host.hideInReadOnly != null) s.hideInReadOnly = host.hideInReadOnly; }
  _addPaneTab(s, tab);
}
function paneSections(paneId) {
  // ordered by the section's `order` (ascending) so display order is data-driven, not chunk-load order.
  return PANE_SECTIONS.filter(s => s.paneId === paneId).sort((a, b) => (a.order || 0) - (b.order || 0));
}
function sectionTabs(section, readOnly) {
  // inc 248: drop per-tab hideInReadOnly tabs on a read-only companion (the section itself may still be shown).
  return [...section.tabs].filter(t => !(readOnly && t.hideInReadOnly)).sort((a, b) => (a.order || 0) - (b.order || 0));
}

// The DETAILS (methods) section is registered here rather than in 25_detail.jsx because that file is at the
// 600-line cap (rule #1); DetailContent is a hoisted global so the render closure resolves it fine. AXES (with its
// Tags tab) / SYNTHESIS self-register in their own chunks (15/20/10). A later split of 25_detail.jsx can move this back.
registerPaneSection({
  id: "details", label: "Details", paneId: "methods", order: 10,
  render: (ctx) => ctx.researchContext && ctx.researchContext.kind === "manuscript"
    ? <WipDetails manuscript={ctx.researchContext.entity} onUpdate={ctx.onUpdateWip}
        onRelinked={ctx.onReloadWip} onOpenPaper={ctx.onOpenPaper} externalRefresh={ctx.wipRefresh} />
    : ctx.selectedPaper != null
    ? <DetailContent paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper} onOpenWip={ctx.onOpenWip}
        readOnly={ctx.readOnly}
        refreshKey={ctx.findingsRefresh}
        onFilterToTag={ctx.onFilterToTag} onTagsChanged={ctx.onTagsChanged} onQueueChanged={ctx.onQueueChanged}
        onLibraryChanged={ctx.onLibraryChanged} />
    : <div className="axis-hint">Select a paper to see its details.</div>,
});

function PaneAccordion({ paneId, ctx, openId, onOpen }) {
  const readOnly = !!(ctx && ctx.readOnly);
  // B5 SP2 / inc 248: on a read-only instance drop a section that's explicitly hideInReadOnly OR whose every tab is
  // hidden read-only (per-tab hideInReadOnly). A section with a surviving tab (e.g. Cite → Suggest) stays.
  const sections = paneSections(paneId).filter(s => !(readOnly && (s.hideInReadOnly || sectionTabs(s, true).length === 0)));
  const [tabState, setTabState] = useState({});  // sectionId -> active tabId (also persisted to localStorage)
  if (sections.length === 0) return null;
  // fall back to the first section if the persisted openId no longer matches a registered section
  const active = sections.some(s => s.id === openId) ? openId : sections[0].id;
  const activeTabId = (s) => {
    const tabs = sectionTabs(s, readOnly);
    const cur = tabState[s.id] ?? _loadLayout("callosum.panetab." + s.id, tabs[0].id);
    return tabs.some(t => t.id === cur) ? cur : tabs[0].id;
  };
  const setTab = (sid, tid) => {
    setTabState(m => ({ ...m, [sid]: tid }));
    _saveLayout("callosum.panetab." + sid, tid);
  };
  const requested = ctx?.paneTabRequest;
  useEffect(() => {
    if (!requested || requested.pane !== paneId) return;
    if (requested.section) onOpen(requested.section);
    if (requested.section && requested.tab) setTab(requested.section, requested.tab);
  }, [requested?.nonce, paneId]);
  return (
    <div className="pane-accordion">
      {sections.map(s => {
        const tabs = sectionTabs(s, readOnly);
        const at = activeTabId(s);
        return (
          <section key={s.id} className={"acc-section" + (s.id === active ? " open" : "")}>
            <button className="acc-header" aria-expanded={s.id === active}
              onClick={() => onOpen(s.id)} title={s.label}>
              <span className="acc-chevron">{s.id === active ? "▾" : "▸"}</span>
              <span className="acc-label">{s.label}</span>
            </button>
            {/* mount-but-hide: every body stays mounted; inactive ones are display:none via .acc-section:not(.open) */}
            <div className="acc-body">
              {tabs.length > 1 ? (
                <React.Fragment>
                  <div className={"tags-srcfilter pane-tabs pane-tabs-" + s.id} role="tablist">
                    {tabs.map(t => (
                      <button key={t.id} role="tab" aria-selected={t.id === at}
                        className={"tags-srcfilter-btn" + (t.id === at ? " on" : "")}
                        onClick={() => setTab(s.id, t.id)}>{t.label}</button>
                    ))}
                  </div>
                  {/* tabs mount-but-hide too (.pane-tab:not(.active){display:none}) so an open axis / running
                      action survives switching tab and back. render(ctx, isVisible) mirrors WorkspacePane's own
                      render(ctx, active) contract — a section being open is not enough; the tab within it must
                      also be the selected one (inc: the Checklists 2x2-grid tab group, 2026-07-21). */}
                  {tabs.map(t => (
                    <div key={t.id} className={"pane-tab" + (t.id === at ? " active" : "")}>
                      <StatusScope nav={{ pane: paneId, section: s.id, tab: t.id, paper_id: ctx?.selectedPaper ?? null }}>
                        {t.render(ctx, s.id === active && t.id === at)}
                      </StatusScope>
                    </div>
                  ))}
                </React.Fragment>
              ) : <StatusScope nav={{ pane: paneId, section: s.id, tab: tabs[0].id, paper_id: ctx?.selectedPaper ?? null }}>
                    {tabs[0].render(ctx, s.id === active)}
                  </StatusScope>}
            </div>
          </section>
        );
      })}
    </div>
  );
}
