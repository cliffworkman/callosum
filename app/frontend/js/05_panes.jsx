// inc 121: THEORY/METHODS side panes as an accordion on an extensible module registry. Each section chunk
// self-registers at load (chunk order 05<10<15<20<25 ⇒ this array exists before the register calls run). The
// accordion renders ALL of its pane's sections but shows only the open one (mount-but-hide), so an in-progress
// synthesis survives a section switch. Pane labels are deliberately "soft" (section headers only) for now; the
// paneId ("theory"|"methods") is the internal architecture + the eventual rename. See DESIGN.md (placement rubric).
const PANE_SECTIONS = [];
function registerPaneSection(section) {
  if (!PANE_SECTIONS.some(s => s.id === section.id)) PANE_SECTIONS.push(section);  // idempotent by id
}
function paneSections(paneId) {
  // ordered by the section's `order` (ascending) so display order is data-driven, not chunk-load order.
  return PANE_SECTIONS.filter(s => s.paneId === paneId).sort((a, b) => (a.order || 0) - (b.order || 0));
}

// The DETAILS (methods) section is registered here rather than in 25_detail.jsx because that file is at the
// 600-line cap (rule #1); DetailContent is a hoisted global so the render closure resolves it fine. AXES/
// SYNTHESIS/TAGS self-register in their own chunks (15/20/10). A later split of 25_detail.jsx can move this back.
registerPaneSection({
  id: "details", label: "Details", paneId: "methods", order: 10,
  render: (ctx) => ctx.selectedPaper != null
    ? <DetailContent paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper}
        onFilterToTag={ctx.onFilterToTag} onTagsChanged={ctx.onTagsChanged} />
    : <div className="axis-hint">Select a paper to see its details.</div>,
});

function PaneAccordion({ paneId, ctx, openId, onOpen }) {
  const sections = paneSections(paneId);
  if (sections.length === 0) return null;
  // fall back to the first section if the persisted openId no longer matches a registered section
  const active = sections.some(s => s.id === openId) ? openId : sections[0].id;
  return (
    <div className="pane-accordion">
      {sections.map(s => (
        <section key={s.id} className={"acc-section" + (s.id === active ? " open" : "")}>
          <button className="acc-header" aria-expanded={s.id === active}
            onClick={() => onOpen(s.id)} title={s.label}>
            <span className="acc-chevron">{s.id === active ? "▾" : "▸"}</span>
            <span className="acc-label">{s.label}</span>
          </button>
          {/* mount-but-hide: every body stays mounted; inactive ones are display:none via .acc-section:not(.open) */}
          <div className="acc-body">{s.render(ctx)}</div>
        </section>
      ))}
    </div>
  );
}
