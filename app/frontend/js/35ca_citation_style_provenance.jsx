// Pure display helpers for citation-style provenance. Loaded before the style-manager chunk.
function citationStyleProvenanceLabel(style, catalog) {
  const provenance = style && style.provenance;
  if (!provenance) return "";
  if (provenance.source_type === "repository") return "CSL repository";
  if (provenance.source_type === "url") return "Imported URL";
  if (provenance.source_type === "local_file") {
    return provenance.source_name ? `Local .csl file (${provenance.source_name})` : "Local .csl file";
  }
  if (provenance.source_type === "duplicate") {
    const source = catalog.styles.find(item => item.id === provenance.source_style_id);
    return `Independent copy of ${(source && (source.full_title || source.title)) || provenance.source_style_id}`;
  }
  if (provenance.source_type === "personal") return "Personal style (source not recorded)";
  return "";
}

function citationStyleDateLabel(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString();
}
