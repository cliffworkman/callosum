// inc 121: THEORY/METHODS side panes as an accordion on an extensible module registry. Each section chunk
// self-registers at load (chunk order 05<10<15<20<25 ⇒ this array exists before the register calls run). The
// accordion renders ALL of its pane's sections but shows only the open one (mount-but-hide), so an in-progress
// synthesis survives a section switch. Pane labels are deliberately "soft" (section headers only) for now; the
// paneId ("theory"|"methods") is the internal architecture + the eventual rename. See DESIGN.md (placement rubric).
//
// inc 139: a section can hold MULTIPLE TABS (like-with-like submenus) — e.g. AXES = [Axes | Tags]. A section with
// one tab renders it directly (no strip); with >=2 it shows a segmented tab strip + the active tab (the inactive
// tabs stay mounted-but-hidden, like sections, so their in-progress state survives a tab switch). DESIGN.md §5.
const PANE_SECTIONS = [];
function registerPaneSection(section) {
  // a single-content section = a section with one (implicit) tab; no tab strip is shown for it.
  registerPaneTab(
    { id: section.id, label: section.label, paneId: section.paneId, order: section.order },
    { id: section.id, label: section.label, order: 0, render: section.render },
  );
}
function registerPaneTab(host, tab) {
  let section = PANE_SECTIONS.find(s => s.id === host.id);
  if (!section) {
    section = { id: host.id, label: host.label, paneId: host.paneId, order: host.order, tabs: [] };
    PANE_SECTIONS.push(section);
  }
  if (!section.tabs.some(t => t.id === tab.id)) section.tabs.push(tab);  // idempotent by tab id
}
function paneSections(paneId) {
  // ordered by the section's `order` (ascending) so display order is data-driven, not chunk-load order.
  return PANE_SECTIONS.filter(s => s.paneId === paneId).sort((a, b) => (a.order || 0) - (b.order || 0));
}
function sectionTabs(section) {
  return [...section.tabs].sort((a, b) => (a.order || 0) - (b.order || 0));
}

// The DETAILS (methods) section is registered here rather than in 25_detail.jsx because that file is at the
// 600-line cap (rule #1); DetailContent is a hoisted global so the render closure resolves it fine. AXES (with its
// Tags tab) / SYNTHESIS self-register in their own chunks (15/20/10). A later split of 25_detail.jsx can move this back.
registerPaneSection({
  id: "details", label: "Details", paneId: "methods", order: 10,
  render: (ctx) => ctx.selectedPaper != null
    ? <DetailContent paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper}
        onFilterToTag={ctx.onFilterToTag} onTagsChanged={ctx.onTagsChanged} onQueueChanged={ctx.onQueueChanged} />
    : <div className="axis-hint">Select a paper to see its details.</div>,
});

function PaneAccordion({ paneId, ctx, openId, onOpen }) {
  const sections = paneSections(paneId);
  const [tabState, setTabState] = useState({});  // sectionId -> active tabId (also persisted to localStorage)
  if (sections.length === 0) return null;
  // fall back to the first section if the persisted openId no longer matches a registered section
  const active = sections.some(s => s.id === openId) ? openId : sections[0].id;
  const activeTabId = (s) => {
    const tabs = sectionTabs(s);
    const cur = tabState[s.id] ?? _loadLayout("callosum.panetab." + s.id, tabs[0].id);
    return tabs.some(t => t.id === cur) ? cur : tabs[0].id;
  };
  const setTab = (sid, tid) => {
    setTabState(m => ({ ...m, [sid]: tid }));
    _saveLayout("callosum.panetab." + sid, tid);
  };
  return (
    <div className="pane-accordion">
      {sections.map(s => {
        const tabs = sectionTabs(s);
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
                  <div className="tags-srcfilter pane-tabs" role="tablist">
                    {tabs.map(t => (
                      <button key={t.id} role="tab" aria-selected={t.id === at}
                        className={"tags-srcfilter-btn" + (t.id === at ? " on" : "")}
                        onClick={() => setTab(s.id, t.id)}>{t.label}</button>
                    ))}
                  </div>
                  {/* tabs mount-but-hide too (.pane-tab:not(.active){display:none}) so an open axis / running
                      action survives switching tab and back */}
                  {tabs.map(t => (
                    <div key={t.id} className={"pane-tab" + (t.id === at ? " active" : "")}>{t.render(ctx)}</div>
                  ))}
                </React.Fragment>
              ) : tabs[0].render(ctx)}
            </div>
          </section>
        );
      })}
    </div>
  );
}
