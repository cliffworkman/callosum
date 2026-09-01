function classifySynthesisFailure(error) {
  const detail = String(error || "Summarization failed.");
  const lower = detail.toLowerCase();
  if (lower.includes("local ai is not ready")) {
    return {
      kind: "settings",
      title: "Local AI isn't ready yet.",
      message: "Open Settings to check Local AI's setup status, then retry once it shows Ready.",
      primary: "Open Settings",
      detail,
    };
  }
  if (lower.includes("dataegressdisablederror") || lower.includes("data-egress consent")) {
    return {
      kind: "settings",
      title: "AI summaries are off.",
      message: "Turn on AI features in Settings to generate a verified synthesis.",
      primary: "Open Settings",
      detail,
    };
  }
  if (lower.includes("api key") || lower.includes("no key") || lower.includes("authenticated")) {
    return {
      kind: "settings",
      title: "The active AI provider needs attention.",
      message: "Check the selected provider, key, model, and egress setting in Settings.",
      primary: "Open Settings",
      detail,
    };
  }
  if (lower.includes("chunk_") || lower.includes("invalid literal for int") || lower.includes("malformed cached")) {
    return {
      kind: "cache",
      title: "A cached draft citation could not be read.",
      message: "Repair the local synthesis cache, then retry the same request.",
      primary: "Repair cache and retry",
      detail,
    };
  }
  if (lower.includes("no chunks") || lower.includes("source chunk") || lower.includes("retrievable")) {
    return {
      kind: "text-health",
      title: "No usable source text was available.",
      message: "Check PDF Text Health for missing extraction, OCR candidates, or stale chunks.",
      primary: "Open Text Health",
      detail,
    };
  }
  if (lower.includes("provider") || lower.includes("http ") || lower.includes("timeout") || lower.includes("rate")) {
    return {
      kind: "retry",
      title: "The provider did not return a usable draft.",
      message: "The local verifier did not run because generation failed. You can retry or check Settings.",
      primary: "Retry",
      detail,
    };
  }
  return {
    kind: "generic",
    title: "Summary could not be generated.",
    message: "The request did not complete. The technical detail is preserved below.",
    primary: "Retry",
    detail,
  };
}

function SynthesisFailure({ error, diagnostic, onOpenSettings, onOpenTextHealth, onRepairCache, onRetry, canRetry }) {
  const failure = classifySynthesisFailure(error);
  const primary = () => {
    if (failure.kind === "settings") return onOpenSettings && onOpenSettings();
    if (failure.kind === "cache") return onRepairCache && onRepairCache();
    if (failure.kind === "text-health") return onOpenTextHealth && onOpenTextHealth();
    return onRetry && onRetry();
  };
  return (
    <div className="errbox" style={{ margin: "14px 0 0" }}>
      <b>{failure.title}</b><br />
      {failure.message}
      <SynthesisSourceDiagnostic diagnostic={diagnostic} onOpenTextHealth={onOpenTextHealth} />
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
        <button className="btn btn-ghost" onClick={primary} disabled={failure.kind !== "settings" && failure.kind !== "text-health" && !canRetry}>
          {failure.primary}
        </button>
        {failure.kind !== "settings" && onOpenSettings &&
          <button className="btn btn-link" onClick={onOpenSettings}>Open Settings</button>}
      </div>
      <details style={{ marginTop: 8 }}>
        <summary>Technical detail</summary>
        <div style={{ marginTop: 6, wordBreak: "break-word" }}>{failure.detail}</div>
      </details>
    </div>
  );
}

function synthesisSourceDiagnostic(body, textHealthItems, sourceChunkCount, error) {
  const detail = String(error || "").toLowerCase();
  if (sourceChunkCount !== 0 && !detail.includes("chunk") && !detail.includes("retrievable")) return null;
  const sections = body && body.sections && body.sections.length ? body.sections.map(sectionLabel).join(" + ") : "";
  const paperIds = body && body.paper_ids ? body.paper_ids.map(Number).filter(Boolean) : [];
  if (!paperIds.length) {
    return {
      text: sections
        ? `No source chunks matched this query after the ${sections} section filter was applied.`
        : "No source chunks matched this query.",
    };
  }
  const byId = new Map((textHealthItems || []).map(item => [Number(item.paper_id), item]));
  const counts = { noLocalPdf: 0, noText: 0, stale: 0, missingSections: 0, tinyText: 0 };
  paperIds.forEach(id => {
    const item = byId.get(id);
    const flags = item ? item.flags || [] : [];
    if (flags.includes("no_local_pdf")) counts.noLocalPdf += 1;
    if (flags.includes("no_chunks")) counts.noText += 1;
    if (flags.includes("stale_chunk_version")) counts.stale += 1;
    if (flags.includes("missing_section_labels")) counts.missingSections += 1;
    if (flags.includes("tiny_text")) counts.tinyText += 1;
  });
  const parts = [`${paperIds.length} selected paper${paperIds.length === 1 ? "" : "s"}`];
  if (counts.noLocalPdf) parts.push(`${counts.noLocalPdf} no local PDF`);
  if (counts.noText) parts.push(`${counts.noText} no extracted text`);
  if (counts.stale) parts.push(`${counts.stale} stale extraction`);
  if (counts.missingSections) parts.push(`${counts.missingSections} missing section labels`);
  if (counts.tinyText) parts.push(`${counts.tinyText} very little text`);
  if (parts.length === 1) parts.push(sections ? `no chunks in ${sections}` : "no text-health issue detected in the scoped overview");
  return { text: parts.join(" · ") };
}

function SynthesisSourceDiagnostic({ diagnostic, onOpenTextHealth }) {
  if (!diagnostic) return null;
  return (
    <div className="synth-coverage synth-coverage-warn">
      {diagnostic.text}
      {onOpenTextHealth && <button className="btn btn-link" onClick={onOpenTextHealth}>Open Scoped Text Health</button>}
    </div>
  );
}
