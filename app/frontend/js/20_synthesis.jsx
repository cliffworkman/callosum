function SynthesisPane({ onOpenCitation, onSaveHighlight, pendingSummarize }) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState({ status: "idle" });
  const [scopeNote, setScopeNote] = useState(null);   // "N selected papers" when summarizing a library selection
  const [history, setHistory] = useState({ status: "loading", items: [] });
  const pollRef = useRef(null);

  const loadHistory = useCallback(() => {
    setHistory(h => ({ ...h, status: "loading" }));
    api("/summaries?limit=20&offset=0").then(r => {
      if (r.ok) setHistory({ status: "ready", items: r.data });
      else setHistory({ status: "error", items: [], error: r.error });
    });
  }, []);

  useEffect(() => {
    loadHistory();
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [loadHistory]);

  const pollJob = useCallback((jobId) => {
    api(`/summarize/${jobId}`).then(r => {
      if (!r.ok) {
        setState({ status: "error", error: r.error, jobId });
        return;
      }
      const data = r.data;
      if (data.status === "done") {
        setState({ status: "done", result: data, jobId });
        loadHistory();
      } else if (data.status === "error") {
        setState({ status: "error", error: data.detail || "Summarization failed.", jobId });
      } else {
        setState({ status: "running", jobId, message: data.status === "pending" ? "Queued for verification" : "Generating and verifying" });
        pollRef.current = setTimeout(() => pollJob(jobId), 1200);
      }
    });
  }, [loadHistory]);

  // Shared POST + poll for any scope (a query or a papers selection).
  const launch = useCallback((requestBody, runningMessage) => {
    if (pollRef.current) clearTimeout(pollRef.current);
    setState({ status: "running", message: runningMessage });
    apiPost("/summarize", requestBody).then(r => {
      if (!r.ok) {
        setState({ status: "error", error: r.error });
        return;
      }
      setState({ status: "running", jobId: r.data.job_id, message: "Generating and verifying" });
      pollJob(r.data.job_id);
    });
  }, [pollJob]);

  const start = useCallback(() => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setScopeNote(null);
    launch({ scope_type: "query", query: trimmed, top_k: 8 }, "Starting summarization");
  }, [query, launch]);

  // Summarize a library selection (the bulk-bar "summarize" → App → here). Each click bumps the nonce →
  // re-runs. top_k scales with the selection so every chosen paper gets >=1 chunk (round-robin backend),
  // bounded at 24 to keep the prompt/token cost in check.
  useEffect(() => {
    if (!pendingSummarize) return;
    const n = pendingSummarize.count;
    setScopeNote(`${n} selected paper${n === 1 ? "" : "s"}`);
    launch(
      { scope_type: "papers", paper_ids: pendingSummarize.paper_ids, top_k: Math.min(Math.max(8, n), 24) },
      `Summarizing ${n} selected paper${n === 1 ? "" : "s"}`,
    );
  }, [pendingSummarize ? pendingSummarize.nonce : null]);

  const loadSummary = useCallback((summaryId) => {
    if (pollRef.current) clearTimeout(pollRef.current);
    setScopeNote(null);
    setState({ status: "loading-summary", message: "Loading saved synthesis" });
    api(`/summaries/${summaryId}`).then(r => {
      if (r.ok) setState({ status: "done", result: r.data, loadedSummaryId: summaryId });
      else setState({ status: "error", error: r.error });
    });
  }, []);

  const removeSummary = useCallback((summaryId, event) => {
    event.stopPropagation();
    if (!window.confirm("Delete this synthesis? This removes the saved summary and its citation evidence.")) return;
    apiDelete(`/summaries/${summaryId}`).then(r => {
      if (!r.ok) {
        setHistory(h => ({ ...h, error: r.error }));
        return;
      }
      setHistory(h => ({ ...h, items: h.items.filter(item => item.summary_id !== summaryId) }));
      if (state.result && state.result.summary_id === summaryId) {
        setState({ status: "idle" });
      }
    });
  }, [state.result]);

  const busy = state.status === "running" || state.status === "loading-summary";
  const sentences = state.result && state.result.sentences ? state.result.sentences : [];
  const verifiedCount = sentences.filter(s => !s.flagged).length;
  const flaggedCount = sentences.filter(s => s.flagged).length;

  return (
    <div className="synth">
      <textarea
        className="synth-input"
        placeholder="Ask a synthesis question about the library..."
        value={query}
        onChange={e => setQuery(e.target.value)}
        disabled={busy}
      />
      <div className="synth-actions">
        <button disabled={busy || !query.trim()} onClick={start}>Synthesize</button>
        <span className={"synth-status" + (busy ? " running" : "")}>
          {busy ? (state.message || "Generating and verifying") : "query scope · top 8 chunks"}
        </span>
      </div>
      {busy && <ProgressBar />}

      {scopeNote &&
        <div className="synth-scope-note">Summary of <b>{scopeNote}</b> from the library selection.</div>}

      {state.status === "idle" &&
        <div className="state" style={{ padding: "30px 10px" }}>
          <div className="big">Verified synthesis</div>
          Ask a question. Callosum will generate a summary and independently verify each citation.
        </div>}

      {state.status === "error" &&
        <div className="errbox" style={{ margin: "14px 0 0" }}>
          <b>Summary could not be generated.</b><br />
          {state.error}
        </div>}

      {state.status === "done" &&
        <div>
          <div className="summary-meta">
            summary #{state.result.summary_id} · {state.result.summary_status}
            {` · ${verifiedCount} verified · ${flaggedCount} flagged`}
          </div>
          {sentences.length === 0 &&
            <div className="state" style={{ padding: "24px 10px" }}>
              <div className="big">No groundable summary produced.</div>
              The generator returned no sentences for this scope.
            </div>}
          {sentences.length > 0 && <GroupedSummarySentences sentences={sentences} onOpenCitation={onOpenCitation} onSaveHighlight={onSaveHighlight} />}
        </div>}

      <SummaryHistory
        state={history}
        activeSummaryId={state.result && state.result.summary_id}
        onLoad={loadSummary}
        onDelete={removeSummary}
      />
    </div>
  );
}

function SummaryHistory({ state, activeSummaryId, onLoad, onDelete }) {
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
              <span className={"cite-status " + (verified ? "verified" : "flagged")}>{item.status}</span>
              <span className="history-delete" onClick={(event) => onDelete(item.summary_id, event)}>Delete</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

function GroupedSummarySentences({ sentences, onOpenCitation, onSaveHighlight }) {
  const ordered = [...sentences].sort((a, b) => (a.ordinal ?? 0) - (b.ordinal ?? 0));
  const verified = ordered.filter(sentence => !sentence.flagged);
  const flagged = ordered.filter(sentence => sentence.flagged);
  return (
    <>
      {verified.length > 0 &&
        <section className="summary-section verified">
          <div className="summary-section-head">
            <span className="label">Verified</span>
            <span className="summary-section-note">{verified.length} stood-up sentence{verified.length === 1 ? "" : "s"}</span>
          </div>
          {verified.map(sentence => (
            <SummarySentence key={sentence.sentence_id} sentence={sentence} onOpenCitation={onOpenCitation} onSaveHighlight={onSaveHighlight} />
          ))}
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
          {flagged.map(sentence => (
            <SummarySentence key={sentence.sentence_id} sentence={sentence} onOpenCitation={onOpenCitation} onSaveHighlight={onSaveHighlight} />
          ))}
        </section>}
    </>
  );
}

function SummarySentence({ sentence, onOpenCitation, onSaveHighlight }) {
  const flagged = !!sentence.flagged;
  return (
    <div className={"summary-sentence " + (flagged ? "flagged" : "verified")}>
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
        <span>{citation.paper_title || `Paper ${citation.paper_id}`} · {pageLabel(citation)}</span>
        <span className={"cite-status " + (verified ? "verified" : "flagged")}>{citation.status}</span>
      </summary>
      <div className="citation-card">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "flex-start" }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 12.5 }}>{citation.paper_title || `Paper ${citation.paper_id}`}</div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--ink-3)", marginTop: 2 }}>
              chunk {citation.chunk_id} · {pageLabel(citation)}
            </div>
          </div>
          <span className={"coord " + (precision === "exact" ? "exact" : precision === "region" ? "region" : "none")}>
            {precisionText(citation.coordinate_precision)}
          </span>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
          {canOpen &&
            <button
              className="source-jump"
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
        <div className="quote">“{citation.quote}”</div>
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

// Right pane = a vertical split (inc 57, backlog F): Synthesis always on top; when a paper is selected
// its editable Details (25_detail.jsx) appear in a lower section sized by a draggable divider. No tabs.
// The divider reuses the inc-42 drag helpers (_beginDrag/_clampW/_loadLayout/_saveLayout — hoisted globals).
function RightPane({ paperId, onOpenCitation, onSaveHighlight, onOpenPaper, onFilterToTag, onTagsChanged, pendingSummarize }) {
  const [detailH, setDetailH] = useState(() => Number(_loadLayout("callosum.detailH", 300)) || 300);
  useEffect(() => { _saveLayout("callosum.detailH", detailH); }, [detailH]);
  const onDragStart = (e) => {
    const sy = e.clientY, sh = detailH;
    _beginDrag(e, (_x, y) => setDetailH(_clampW(sh - (y - sy), 180, 760)));  // drag up → Details grows
  };
  return (
    <div className="pane pane-detail pane-split">
      <div className="rp-synth">
        <div className="pane-head"><p className="eyebrow">Synthesis</p></div>
        <SynthesisPane onOpenCitation={onOpenCitation} onSaveHighlight={onSaveHighlight} pendingSummarize={pendingSummarize} />
      </div>
      {paperId != null &&
        <>
          <div className="divider-h" title="Drag to resize"><div className="divider-grip-h" onMouseDown={onDragStart} /></div>
          <div className="rp-detail" style={{ height: detailH }}>
            <p className="eyebrow rp-detail-head">Detail</p>
            {/* DetailContent lives in 25_detail.jsx (the Mendeley-style editable pane). */}
            <DetailContent paperId={paperId} onOpenPaper={onOpenPaper} onFilterToTag={onFilterToTag} onTagsChanged={onTagsChanged} />
          </div>
        </>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// PDF tab — streams /papers/{id}/pdf and renders it with PDF.js.
// Honest about the not-available-locally case; never a blank canvas.
// ─────────────────────────────────────────────────────────────
