// inc 582: extracted from 20_synthesis.jsx to keep it under the 600-line cap (rule #1). Shared-IIFE
// hoist — GroupedSummarySentences is a function declaration callable from SynthesisPane in 20_synthesis.jsx,
// and it in turn calls SummarySentence (which stays in 20_synthesis.jsx). Same precedent as 19c/35b.
//
// A broad (faceted) synthesis carries a per-claim `responsiveness` label ("finding"/"descriptive"/
// "unknown"); a narrow one does not. When present, the (UNCHANGED) verified set is split into substantive
// Findings and lower-answer-value "Study context". Study context is VERIFIED material — same trust chrome,
// never amber, never hidden; it is lower answer-value, NOT lower confidence. Narrow Ask is untouched.
function GroupedSummarySentences({ sentences, onOpenCitation, onSaveHighlight }) {
  const ordered = [...sentences].sort((a, b) => (a.ordinal ?? 0) - (b.ordinal ?? 0));
  const verified = ordered.filter(sentence => !sentence.flagged);
  const flagged = ordered.filter(sentence => sentence.flagged);
  const hasResponsiveness = ordered.some(sentence => sentence.responsiveness);
  const findings = hasResponsiveness ? verified.filter(s => s.responsiveness !== "descriptive") : verified;
  const context = hasResponsiveness ? verified.filter(s => s.responsiveness === "descriptive") : [];
  const renderSentence = sentence => (
    <SummarySentence key={sentence.sentence_id} sentence={sentence} onOpenCitation={onOpenCitation} onSaveHighlight={onSaveHighlight} />
  );
  return (
    <>
      {findings.length > 0 &&
        <section className="summary-section verified">
          <div className="summary-section-head">
            <span className="label">{hasResponsiveness ? "Findings" : "Verified"}</span>
            <span className="summary-section-note">{findings.length} stood-up sentence{findings.length === 1 ? "" : "s"}</span>
          </div>
          {findings.map(renderSentence)}
        </section>}

      {context.length > 0 &&
        <section className="summary-section verified">
          <div className="summary-section-head">
            <span className="label">Study context</span>
            <span className="summary-section-note">{context.length} verified · lower answer-value framing</span>
          </div>
          {context.map(renderSentence)}
        </section>}

      {flagged.length > 0 &&
        <section className="summary-section flagged">
          <div className="summary-section-head">
            <span className="label">Flagged · needs review</span>
            <span className="summary-section-note">{flagged.length} sentence{flagged.length === 1 ? "" : "s"} could not be fully verified</span>
          </div>
          {verified.length === 0 &&
            <div className="errbox" style={{ margin: "0 0 10px" }}>
              No sentence in this synthesis cleared verification. Review the evidence below before relying on it.
            </div>}
          {flagged.map(renderSentence)}
        </section>}
    </>
  );
}
