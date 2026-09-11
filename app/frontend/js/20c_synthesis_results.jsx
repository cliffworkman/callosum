// Synthesis results-rendering components, split out of 20_synthesis.jsx (issue #30, rule #1 600-line
// cap). SummaryHistory, SummarySentence, and CitationCard are function declarations hoisted across the
// shared IIFE, so SynthesisPane (20_synthesis.jsx) and GroupedSummarySentences (20b_summary_groups.jsx)
// call them unchanged — the same shared-scope hoist precedent as 20b/19c/35b. Pure presentational: they
// take props and reuse top-level helpers (citeStatusClass, EvidenceQuote, fmt*/page/precision helpers).

function SummaryHistory({ state, activeSummaryId, onLoad, onDelete, readOnly }) {
  return (
    <div className="history">
      <p className="eyebrow">History</p>
      {state.status === "loading" &&
        <div className="history-meta">Loading saved syntheses...</div>}
      {state.status === "error" &&
        <div className="errbox" style={{ margin: "8px 0 0" }}>Couldn't load synthesis history.<br />{state.error}</div>}
      {state.status === "ready" && state.items.length === 0 &&
        <div className="history-meta">No saved syntheses yet.</div>}
      {state.status === "ready" && state.items.map(item => {
        const verified = item.status === "verified";
        return (
          <button key={item.summary_id} className="history-row" onClick={() => onLoad(item.summary_id)}>
            <span>
              <span className="history-title">{item.scope_label || `Summary ${item.summary_id}`}</span>
              <span className="history-meta">
                #{item.summary_id} · {fmtDateTime(item.created_at)} · {item.sentence_count} sentences · {item.verified_sentence_count} verified · {item.flagged_sentence_count} flagged
              </span>
              {activeSummaryId === item.summary_id &&
                <span className="history-meta" style={{ color: "var(--accent)" }}>current</span>}
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span className={"cite-status " + citeStatusClass(item.status)}>{item.status}</span>
              {!readOnly && <span className="history-delete" onClick={(event) => onDelete(item.summary_id, event)}>Delete</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function SummarySentence({ sentence, onOpenCitation, onSaveHighlight }) {
  const flagged = !!sentence.flagged;
  return (
    <div id={"summary-claim-" + sentence.ordinal} className={"summary-sentence " + (flagged ? "flagged" : "verified")}>
      <div className="sent-head">
        <p className="sent-text">{sentence.text}</p>
        <span className={"sent-badge " + (flagged ? "flagged" : "verified")}>{flagged ? "flagged" : "verified"}</span>
      </div>
      {sentence.citations && sentence.citations.length > 0
        ? sentence.citations.map(citation => <CitationCard key={citation.mapping_id} citation={citation} onOpenCitation={onOpenCitation} onSaveHighlight={onSaveHighlight} />)
        : <div className="citation"><span className="placeholder">No citations returned for this sentence.</span></div>}
    </div>
  );
}

function CitationCard({ citation, onOpenCitation, onSaveHighlight }) {
  const verified = citation.status === "verified";
  const precision = citation.coordinate_precision || "none";
  const canOpen = onOpenCitation && citation.paper_id != null && (citation.page_start != null || citation.page_end != null);
  // B2 SP2: an imported citation whose source paper the recipient doesn't have — evidence still shown, no link.
  const srcLabel = citation.paper_title || (citation.paper_id != null ? `Paper ${citation.paper_id}` : "Source not in your library");
  const [saveState, setSaveState] = useState("idle");  // idle | saving | saved | error
  // Honesty contract: a citation may be saved as a *precise* durable highlight ONLY when
  // it is verified AND its coordinates are exact (and there is at least one real bbox).
  // Region/null precision or a flagged status → not saveable (button disabled + tooltip).
  const canSave = !!onSaveHighlight
    && citation.coordinate_precision === "exact"
    && citation.status === "verified"
    && citation.paper_id != null
    && normalizeBboxes(citation.bbox_json).length > 0;
  const onSave = async (event) => {
    event.preventDefault();
    if (!canSave || saveState === "saving") return;
    setSaveState("saving");
    const r = await onSaveHighlight(citation);
    setSaveState(r && r.ok ? "saved" : "error");
  };
  return (
    <details className="citation">
      <summary>
        <span>{srcLabel} · {pageLabel(citation)}</span>
        <span className={"cite-status " + citeStatusClass(citation.status)}>
          {citation.status === "contradicted" ? "⚠ source disagrees" : citation.status}
        </span>
      </summary>
      <div className="citation-card">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "flex-start" }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 12.5 }}>{srcLabel}</div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--ink-3)", marginTop: 2 }}>
              {citation.chunk_id != null ? `chunk ${citation.chunk_id} · ` : ""}{pageLabel(citation)}
            </div>
          </div>
          <span className={"coord " + (precision === "exact" ? "exact" : precision === "region" ? "region" : "none")}>
            {precisionText(citation.coordinate_precision)}
          </span>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
          {canOpen &&
            <button
              className="btn btn-ghost"
              onClick={(event) => { event.preventDefault(); onOpenCitation(citation); }}
            >
              Open source {citation.coordinate_precision === "exact" ? "and highlight" : citation.coordinate_precision === "region" ? "region" : "page"}
            </button>}
          {onSaveHighlight && (saveState === "saved"
            ? <span className="source-saved">✓ Saved to highlights</span>
            : <button
                className="source-save"
                disabled={!canSave || saveState === "saving"}
                title={canSave
                  ? "Save this verified passage as a durable highlight"
                  : "Only verified, exact-coordinate citations can be saved as a precise highlight."}
                onClick={onSave}
              >
                {saveState === "saving" ? "Saving…" : saveState === "error" ? "Couldn't save — retry" : "Save as highlight"}
              </button>)}
        </div>
        <EvidenceQuote
          text={citation.quote}
          label="Evidence quote"
          section={citation.section}
          precision={citation.coordinate_precision}
          hasSourcePage={citation.page_start != null || citation.page_end != null}
          className="quote"
          maxChars={520}
          onOpen={canOpen ? (event) => { event.preventDefault(); onOpenCitation(citation); } : null}
          openLabel={citation.coordinate_precision === "exact" ? "Open source and highlight this quote" : "Open source page for this quote"}
        />
        {citation.coordinate_precision === "region" &&
          <div style={{ fontSize: 11.5, color: "var(--flag)", marginTop: 4 }}>
            Region-level source area only. Do not treat this as an exact quote highlight.
          </div>}
        {!citation.coordinate_precision &&
          <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 4 }}>
            No coordinate claim is available for this citation.
          </div>}
        <div className="conf-grid">
          <div className="conf"><span className="k">Retrieval</span><span className="v">{fmtScore(citation.retrieval_confidence)}</span></div>
          <div className="conf"><span className="k">Quote</span><span className="v">{fmtScore(citation.quote_confidence)}</span></div>
          <div className="conf"><span className="k">Support</span><span className="v">{fmtScore(citation.support_confidence)}</span></div>
        </div>
      </div>
    </details>
  );
}
