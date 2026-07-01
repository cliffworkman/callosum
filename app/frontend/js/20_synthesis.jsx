// inc 203 (A9): the citation-status pill class. `contradicted` (the source actively disagrees) is its own distinct
// state — not lumped into amber "flagged" with weak/unverified. verified → green, contradicted → red alarm, else amber.
function citeStatusClass(status) {
  return status === "verified" ? "verified" : status === "contradicted" ? "contradicted" : "flagged";
}

// inc 124: scroll to + briefly flash the verified claim(s) an Overview sentence traces to (by ordinal).
function flashClaims(ordinals) {
  (ordinals || []).forEach((ord, idx) => {
    const el = document.getElementById("summary-claim-" + ord);
    if (!el) return;
    if (idx === 0) el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("claim-flash");
    setTimeout(() => el.classList.remove("claim-flash"), 1400);
  });
}

// inc 124: an evidence-traceable Overview — a short narration OF the verified claims (not authoritative prose).
// Each line restates one or more verified claims and links back to them: click → the claim(s) flash below.
function OverviewBlock({ overview }) {
  if (!overview || overview.length === 0) return null;
  return (
    <section className="synth-overview">
      <p className="eyebrow">Overview — synthesized from the verified claims below</p>
      {overview.map((item, i) => (
        <button key={i} className="overview-line" title="Show the verified claim(s) this restates"
          onClick={() => flashClaims(item.claim_ordinals)}>
          {item.text}
          <span className="overview-trace">
            {(item.claim_ordinals || []).map(o => "[" + (o + 1) + "]").join(" ")}
          </span>
        </button>
      ))}
    </section>
  );
}

function SynthesisPane({ onOpenCitation, onSaveHighlight, pendingSummarize, onOpenSettings, settingsNonce }) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState({ status: "idle" });
  const [scopeNote, setScopeNote] = useState(null);   // "N selected papers" when summarizing a library selection
  const [scopeMeta, setScopeMeta] = useState(null);   // {total, topK} for the papers scope → the coverage readout (inc 153)
  const [history, setHistory] = useState({ status: "loading", items: [] });
  const [egressOff, setEgressOff] = useState(false);  // inc 148: AI off → show a nudge with a door into Settings
  const pollRef = useRef(null);

  // Re-read egress state on mount + whenever Settings closes (settingsNonce), so the nudge clears once AI is on.
  useEffect(() => {
    api("/settings").then(r => { if (r.ok && r.data) setEgressOff(!r.data.data_egress_enabled); });
  }, [settingsNonce]);

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
    setScopeMeta(null);  // query scope: no fixed N to report coverage against
    launch({ scope_type: "query", query: trimmed, top_k: 8 }, "Starting summarization");
  }, [query, launch]);

  // Summarize a library selection (the bulk-bar "summarize" → App → here). Each click bumps the nonce →
  // re-run, capturing the current focus query. top_k scales with the selection so every chosen paper gets
  // >=1 chunk (round-robin backend), capped at MAX_CHUNKS (the backend's top_k max) to bound prompt/token
  // cost. A non-empty focus query switches the backend to query-RANKED coverage of just the selection — the
  // synthesis textarea doubles as the focus (inc 111).
  useEffect(() => {
    if (!pendingSummarize) return;
    const MAX_CHUNKS = 50;   // SummarizeRequest caps top_k at 50
    const n = pendingSummarize.count;
    // inc-145: prefer the focus typed in the selection bar; fall back to the synthesis textarea (inc-111 behavior).
    const focus = (pendingSummarize.focus != null ? pendingSummarize.focus : query).trim();
    if (pendingSummarize.focus) setQuery(pendingSummarize.focus);  // reflect it in the textarea so it's visible
    const focusShort = focus.length > 60 ? focus.slice(0, 60) + "…" : focus;
    setScopeNote(
      `${n} selected paper${n === 1 ? "" : "s"}`
      + (focus ? ` · focused on “${focusShort}”` : "")
      + (n > MAX_CHUNKS ? ` · capped at ${MAX_CHUNKS} chunks` : ""),
    );
    const topK = Math.min(Math.max(8, n), MAX_CHUNKS);
    setScopeMeta({ total: n, topK });   // for the coverage readout once it's done
    const body = { scope_type: "papers", paper_ids: pendingSummarize.paper_ids, top_k: topK };
    if (focus) body.query = focus;   // focus query → query-ranked coverage of the selection
    launch(body, `Summarizing ${n} selected paper${n === 1 ? "" : "s"}`);
  }, [pendingSummarize ? pendingSummarize.nonce : null]);

  const loadSummary = useCallback((summaryId) => {
    if (pollRef.current) clearTimeout(pollRef.current);
    setScopeNote(null);
    setScopeMeta(null);  // a saved synthesis — the original selection size isn't recorded
    setState({ status: "loading-summary", message: "Loading saved synthesis" });
    api(`/summaries/${summaryId}`).then(r => {
      if (r.ok) setState({ status: "done", result: r.data, loadedSummaryId: summaryId });
      else setState({ status: "error", error: r.error });
    });
  }, []);

  // B2 SP3: re-verify an imported (relayed) synthesis against MY library → convert it in place to native.
  const [reverifying, setReverifying] = useState(false);
  const reverify = useCallback((summaryId) => {
    if (reverifying) return;
    setReverifying(true);
    apiPost(`/summaries/${summaryId}/reverify`, {}).then(r => {
      setReverifying(false);
      if (r.ok) { setState({ status: "done", result: r.data, loadedSummaryId: summaryId }); loadHistory(); }
      else setState(s => ({ ...s, error: r.error }));
    });
  }, [reverifying, loadHistory]);

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
  // inc 153: which selected papers actually contributed a cited passage (the coverage readout).
  const drewFromPapers = (() => {
    const ids = new Set();
    sentences.forEach(s => (s.citations || []).forEach(c => { if (c.paper_id != null) ids.add(c.paper_id); }));
    return ids.size;
  })();

  // inc 148: a friendly "AI is off" nudge with a one-click door into Settings (shown proactively when egress is
  // off, and reactively in place of a raw DataEgressDisabledError). Local features stay usable — this informs.
  const egressNudge = (
    <div className="synth-nudge">
      <span>AI summaries are off. Turn on <b>AI features</b> in Settings to generate a verified synthesis.</span>
      <button className="btn btn-link" onClick={() => onOpenSettings && onOpenSettings()}>Enable in Settings →</button>
    </div>
  );

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

      {egressOff && state.status !== "error" && egressNudge}

      {scopeNote &&
        <div className="synth-scope-note">Summary of <b>{scopeNote}</b> from the library selection.</div>}

      {state.status === "idle" &&
        <div className="state" style={{ padding: "30px 10px" }}>
          <div className="big">Verified synthesis</div>
          Ask a question. Callosum will generate a summary and independently verify each citation.
        </div>}

      {state.status === "error" &&
        (String(state.error || "").includes("DataEgressDisabledError")
          ? egressNudge
          : <div className="errbox" style={{ margin: "14px 0 0" }}>
              <b>Summary could not be generated.</b><br />
              {state.error}
            </div>)}

      {state.status === "done" &&
        <div>
          <div className="summary-meta">
            <button
              className="btn btn-link summary-close"
              title="Close — clear this synthesis and start a new query"
              onClick={() => { setScopeNote(null); setState({ status: "idle" }); }}
            >✕ Close</button>
            summary #{state.result.summary_id} · {state.result.summary_status}
            {` · ${verifiedCount} verified · ${flaggedCount} flagged`}
          </div>
          {state.result.imported &&
            <div className="synth-imported" title="This synthesis came from a shared bundle — its statuses are the sender's, computed against their PDFs, not re-checked here.">
              Imported — the sender's assessment, not re-checked in your library. Sources open at the page (region precision).
              <button className="btn btn-link" disabled={reverifying}
                title="Re-run local verification (retrieval + NLI + quote-location) against your own library — turns this into your verified synthesis. No egress."
                onClick={() => reverify(state.result.summary_id)}>
                {reverifying ? "Re-verifying…" : "Re-verify against my library"}
              </button>
            </div>}
          {scopeMeta && scopeMeta.total != null &&
            <div className="synth-coverage">
              Drew from <b>{drewFromPapers}</b> of {scopeMeta.total} selected paper{scopeMeta.total === 1 ? "" : "s"} · top {scopeMeta.topK} chunks
              {drewFromPapers < scopeMeta.total ? ` · ${scopeMeta.total - drewFromPapers} contributed no cited passage` : ""}
            </div>}
          {sentences.length > 0 && verifiedCount === 0 &&
            <div className="synth-coverage synth-coverage-warn">No claim cleared local verification — your question may not be well-addressed in these papers.</div>}
          {sentences.length === 0 &&
            <div className="state" style={{ padding: "24px 10px" }}>
              <div className="big">No groundable summary produced.</div>
              The generator returned no sentences — your question may not be addressed in this scope.
            </div>}
          {sentences.length > 0 && <OverviewBlock overview={state.result.overview} />}
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
              <span className={"cite-status " + citeStatusClass(item.status)}>{item.status}</span>
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

// inc 121: the old RightPane (inc-57 vertical Synthesis/Details split with a draggable .divider-h) is retired —
// SYNTHESIS now lives in the THEORY (left) accordion and DETAILS in the METHODS (right) accordion (05_panes.jsx).

// ─────────────────────────────────────────────────────────────
// PDF tab — streams /papers/{id}/pdf and renders it with PDF.js.
// Honest about the not-available-locally case; never a blank canvas.
// ─────────────────────────────────────────────────────────────

// inc 121: register SYNTHESIS as a THEORY-pane accordion section (see 05_panes.jsx). RightPane is removed in T3.
registerPaneSection({
  id: "synthesis", label: "Synthesis", paneId: "theory", order: 20,
  render: (ctx) => <SynthesisPane onOpenCitation={ctx.onOpenCitation} onSaveHighlight={ctx.onSaveHighlight}
    pendingSummarize={ctx.pendingSummarize} onOpenSettings={ctx.onOpenSettings} settingsNonce={ctx.settingsNonce} />,
});
