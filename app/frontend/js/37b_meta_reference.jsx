// Meta-Reference (Work/Extract reorg): reference-list analysis tools — formerly separate nested tabs under
// Work → Cite (08j_reference_integrity.jsx, 08b_methods_citation_equity.jsx, 08c_methods_citation_context.jsx) —
// as stacked subsections on one panel instead of tab-switching between them. Each tool is unchanged internally;
// this is presentation only. Reuses the existing .settings-subsection divider recipe (DESIGN.md rule #8).
// Citation context's two directions (formerly one toggle-switched subsection) are now two always-visible
// subsections — CitationContextSection takes a fixed `direction` prop instead of holding internal toggle state.
// backlog #48 (inc 447): the WIP-manuscript branch. Reference-integrity and citation-concentration are
// tractable against a manuscript's own "cited" wip_references links; citation-context ("how it's cited") needs
// the manuscript's own DOI indexed in Semantic Scholar's citation graph, which an unpublished draft cannot
// have — omitted with a plain explanatory note rather than silently vanishing (maintainer decision, 2026-07-27).
function MetaReferencePaneWip({ ctx, manuscript }) {
  return (
    <div className="cite-workspace ws-pad">
      <p className="eyebrow">Meta Reference List</p>
      <WipMetaReferenceList manuscriptId={manuscript.id} onOpenPaper={ctx.onOpenPaper} onReload={ctx.onReloadWip} refreshKey={ctx.wipRefresh} />
      <div className="settings-subsection">
        <p className="eyebrow">Citation concentration</p>
        <CitationEquitySectionWip manuscript={manuscript} />
      </div>
      <div className="settings-subsection">
        <p className="eyebrow">How it's cited</p>
        <div className="tag-suggest-empty">
          This manuscript has no DOI, so it can't have an indexed incoming- or outgoing-citation graph in
          Semantic Scholar — citation context needs a published record. This becomes available once the
          manuscript is published and linked to its own Library entry.
        </div>
      </div>
    </div>
  );
}

function MetaReferencePane({ ctx }) {
  if (ctx.researchContext && ctx.researchContext.kind === "manuscript") {
    return <MetaReferencePaneWip ctx={ctx} manuscript={ctx.researchContext.entity} />;
  }
  return (
    <div className="cite-workspace ws-pad">
      <p className="eyebrow">Meta Reference List</p>
      <MetaReferenceList ctx={ctx} />
      <div className="settings-subsection">
        <p className="eyebrow">Citation concentration</p>
        <CitationEquitySection ctx={ctx} />
      </div>
      <div className="settings-subsection">
        <p className="eyebrow">How it's cited</p>
        <CitationContextSection ctx={ctx} direction="citations" />
      </div>
      <div className="settings-subsection">
        <p className="eyebrow">How it cites its sources</p>
        <CitationContextSection ctx={ctx} direction="references" />
      </div>
    </div>
  );
}

registerWorkspaceTab(
  { id: "work", label: "Work", order: 50 },
  { id: "meta-reference", label: "Meta-Reference", order: 20, hideInReadOnly: true, render: (ctx) => <MetaReferencePane ctx={ctx} /> },
);
