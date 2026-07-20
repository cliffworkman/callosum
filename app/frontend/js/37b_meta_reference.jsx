// Meta-Reference (Work/Extract reorg): 3 reference-list analysis tools — formerly separate nested tabs under
// Work → Cite (08j_reference_integrity.jsx, 08b_methods_citation_equity.jsx, 08c_methods_citation_context.jsx) —
// as stacked subsections on one panel instead of tab-switching between them. Each tool is unchanged internally;
// this is presentation only. Reuses the existing .settings-subsection divider recipe (DESIGN.md rule #8).
function MetaReferencePane({ ctx }) {
  return (
    <div className="cite-workspace">
      <p className="eyebrow">Meta Reference List</p>
      <MetaReferenceList ctx={ctx} />
      <div className="settings-subsection">
        <p className="eyebrow">Citation concentration</p>
        <CitationEquitySection ctx={ctx} />
      </div>
      <div className="settings-subsection">
        <p className="eyebrow">How it's cited</p>
        <CitationContextSection ctx={ctx} />
      </div>
    </div>
  );
}

registerWorkspaceTab(
  { id: "work", label: "Work", order: 50 },
  { id: "meta-reference", label: "Meta-Reference", order: 20, hideInReadOnly: true, render: (ctx) => <MetaReferencePane ctx={ctx} /> },
);
