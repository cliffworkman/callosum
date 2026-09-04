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

const SYNTH_SECTION_OPTIONS = [
  "abstract",
  "methods",
  "results",
  "discussion",
  "data_availability",
  "funding",
  "ethics",
];
const SYNTHESIS_ACTIVE_JOB_KEY = "callosum.active-job.synthesis";

function selectedSynthesisSections(sectionFilter) {
  return SYNTH_SECTION_OPTIONS.filter(key => !!sectionFilter[key]);
}

function sectionFilterSummary(sections) {
  const selected = sections || [];
  if (!selected.length) return "all sections";
  return selected.map(sectionLabel).join(" + ");
}

function SynthesisPane({ onOpenCitation, onSaveHighlight, pendingSummarize, requestedSummary, onOpenSettings, onOpenTextHealth, settingsNonce, readOnly, onCriticalReviewSources }) {
  const [query, setQuery] = useState("");
  const [sectionFilter, setSectionFilter] = useState({});
  const [state, setState] = useState({ status: "idle" });
  const [scopeNote, setScopeNote] = useState(null);   // "N selected papers" when summarizing a library selection
  const [scopeMeta, setScopeMeta] = useState(null);   // {total, topK} for the papers scope → the coverage readout (inc 153)
  const [history, setHistory] = useState({ status: "loading", items: [] });
  const [aiUnavailable, setAiUnavailable] = useState(false);  // inc 148: AI off → show a nudge with a door into Settings
  const [sourceDiagnostic, setSourceDiagnostic] = useState(null);
  const pollRef = useRef(null);
  const lastLaunchRef = useRef(null);
  const overviewLifecycle = useSynthesisOverview(state, setState);

  // Re-read egress state on mount + whenever Settings closes (settingsNonce), so the nudge clears once AI is on.
  useEffect(() => {
    api("/settings").then(r => { if (r.ok && r.data) setAiUnavailable(!r.data.generation_provider_available); });
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
      if (pollRef.current) pollRef.current();
    };
  }, [loadHistory]);

  const pollJob = useCallback((jobId) => {
    if (pollRef.current) pollRef.current();
    rememberActiveJob(SYNTHESIS_ACTIVE_JOB_KEY, jobId);
    pollRef.current = observeJobUntilTerminal(`/summarize/${jobId}`, {
      onProgress: data => {
        setState({ status: "running", jobId, message: data.status === "pending" ? "Queued for verification" : "Generating and verifying" });
      },
      onDone: data => {
        pollRef.current = null;
        rememberActiveJob(SYNTHESIS_ACTIVE_JOB_KEY, null);
        setState({ status: "done", result: data, jobId });
        loadHistory();
      },
      onError: error => {
        pollRef.current = null;
        rememberActiveJob(SYNTHESIS_ACTIVE_JOB_KEY, null);
        setState({ status: "error", error: error || "Summarization failed.", jobId });
      },
    });
  }, [loadHistory]);

  useEffect(() => {
    const jobId = recalledActiveJob(SYNTHESIS_ACTIVE_JOB_KEY);
    if (!jobId) return;
    setState({ status: "running", jobId, message: "Reconnecting to synthesis" });
    pollJob(jobId);
  }, [pollJob]);

  const launchPrepared = useCallback((body, runningMessage) => {
    if (pollRef.current) pollRef.current();
    lastLaunchRef.current = { body, runningMessage };
    setState({ status: "running", message: runningMessage });
    apiPost("/summarize", body).then(r => {
      if (!r.ok) {
        setState({ status: "error", error: r.error });
        return;
      }
      setState({ status: "running", jobId: r.data.job_id, message: "Generating and verifying" });
      pollJob(r.data.job_id);
    });
  }, [pollJob]);

  // Shared POST + poll for any scope (a query or a papers selection).
  const launch = useCallback((requestBody, runningMessage) => {
    const sections = selectedSynthesisSections(sectionFilter);
    const body = sections.length ? { ...requestBody, sections } : requestBody;
    launchPrepared(body, runningMessage);
  }, [launchPrepared, sectionFilter]);

  const retryLast = useCallback(() => {
    const last = lastLaunchRef.current;
    if (!last) return;
    launchPrepared(last.body, last.runningMessage || "Retrying synthesis");
  }, [launchPrepared]);

  const repairCacheAndRetry = useCallback(() => {
    setState({ status: "running", message: "Repairing synthesis cache" });
    apiPost("/settings/repair-summary-cache", {}).then(r => {
      if (!r.ok) {
        setState({ status: "error", error: "Synthesis cache repair failed: " + (r.error || "error") });
        return;
      }
      retryLast();
    });
  }, [retryLast]);
  const openTextHealthForSynthesis = useCallback(() => {
    if (!onOpenTextHealth) return;
    const last = lastLaunchRef.current;
    const body = (last && last.body) || {};
    onOpenTextHealth({ source: "synthesis", paperIds: body.paper_ids || [], onRetry: retryLast });
  }, [onOpenTextHealth, retryLast]);

  useEffect(() => {
    const sourceChunkCount = state.result && state.result.source_chunk_count;
    const shouldExplain = state.status === "error" || (state.status === "done" && sourceChunkCount === 0);
    if (!shouldExplain) { setSourceDiagnostic(null); return; }
    const body = (lastLaunchRef.current && lastLaunchRef.current.body) || {};
    api("/papers/text-health/overview").then(r => {
      const items = r.ok && r.data ? (r.data.items || []) : [];
      setSourceDiagnostic(synthesisSourceDiagnostic(body, items, sourceChunkCount, state.error));
    });
  }, [state.status, state.error, state.result && state.result.source_chunk_count]);

  const toggleSection = useCallback((section) => {
    setSectionFilter(current => ({ ...current, [section]: !current[section] }));
  }, []);

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
    if (pollRef.current) pollRef.current();
    rememberActiveJob(SYNTHESIS_ACTIVE_JOB_KEY, null);
    setScopeNote(null);
    setScopeMeta(null);  // a saved synthesis — the original selection size isn't recorded
    setState({ status: "loading-summary", message: "Loading saved synthesis" });
    api(`/summaries/${summaryId}`).then(r => {
      if (r.ok) setState({ status: "done", result: r.data, loadedSummaryId: summaryId });
      else setState({ status: "error", error: r.error });
    });
  }, []);

  // inc 415: Status-popover click-through for a FINISHED Ask job → reopen that exact saved synthesis.
  // Nonce-gated exactly like the pendingSummarize effect above (and workspaceTabRequest's own idiom), so a
  // repeat click on the same job re-fires even though summaryId itself hasn't changed.
  useEffect(() => {
    if (!requestedSummary || requestedSummary.summaryId == null) return;
    loadSummary(requestedSummary.summaryId);
  }, [requestedSummary ? requestedSummary.nonce : null]);

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
  const citedPaperIds = (() => {
    const ids = new Set();
    sentences.forEach(s => (s.citations || []).forEach(c => { if (c.paper_id != null) ids.add(c.paper_id); }));
    return [...ids];
  })();
  const drewFromPapers = citedPaperIds.length;

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
      {isDemoMode() &&
        <div className="synth-nudge demo-synth-note">
          <span><b>Saved synthesis.</b> Generation is unavailable in the online demo; the claims, verification states, evidence quotations, and source locations below remain fully inspectable.</span>
        </div>}
      {/* B5 SP2: on a read-only companion, hide the run controls — reading saved syntheses (below) still works. */}
      {!readOnly && <React.Fragment>
        <textarea
          className="synth-input"
          placeholder="Ask a synthesis question about the library..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          disabled={busy}
        />
        <div className="tags-srcfilter synth-section-filter" role="group" aria-label="Synthesis evidence section filter">
          <button type="button" className={"tags-srcfilter-btn" + (selectedSynthesisSections(sectionFilter).length ? "" : " on")}
            aria-pressed={!selectedSynthesisSections(sectionFilter).length} disabled={busy}
            title="Search all eligible chunks"
            onClick={() => setSectionFilter({})}>All</button>
          {SYNTH_SECTION_OPTIONS.map(section => {
            const on = !!sectionFilter[section];
            return (
              <button key={section} type="button" className={"tags-srcfilter-btn" + (on ? " on" : "")}
                aria-pressed={on} disabled={busy}
                title={`Search ${sectionLabel(section)} chunks when available`}
                onClick={() => toggleSection(section)}>
                {sectionLabel(section)}
              </button>
            );
          })}
        </div>
        <div className="synth-actions">
          <button disabled={busy || !query.trim()} onClick={start}>Synthesize</button>
          <span className={"synth-status" + (busy ? " running" : "")}>
            {busy ? (state.message || "Generating and verifying") : "query scope · top 8 chunks"}
          </span>
        </div>
        {busy && <ProgressBar managedBy="backend-job" />}
      </React.Fragment>}

      {!readOnly && aiUnavailable && state.status !== "error" && egressNudge}

      {scopeNote &&
        <div className="synth-scope-note">Summary of <b>{scopeNote}</b> from the library selection.</div>}

      {state.status === "idle" &&
        <div className="state" style={{ padding: "30px 10px" }}>
          <div className="big">Verified synthesis</div>
          Ask a question. Callosum will generate a summary and independently verify each citation.
        </div>}

      {state.status === "error" &&
        <SynthesisFailure
          error={state.error}
          diagnostic={sourceDiagnostic}
          onOpenSettings={onOpenSettings}
          onOpenTextHealth={openTextHealthForSynthesis}
          onRepairCache={repairCacheAndRetry}
          onRetry={retryLast}
          canRetry={!!lastLaunchRef.current}
        />}

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
          {/* The model hit its output ceiling before finishing. The claims below are real and were
              verified normally — but they are not the whole answer it set out to give, and a partial
              synthesis must never read as a complete one (PRINCIPLES #6: silence is not a certificate). */}
          {state.result.generation_truncated &&
            <div className="errbox" style={{ margin: "10px 0 0" }} role="status">
              <b>This answer is incomplete.</b><br />
              The AI ran out of room before it finished, so {verifiedCount + flaggedCount} claim
              {verifiedCount + flaggedCount === 1 ? " is" : "s are"} shown rather than everything it set out to say.
              Asking about fewer things at once — or narrowing the sections or papers in scope — gives it room to finish.
            </div>}
          {!readOnly && onCriticalReviewSources && citedPaperIds.length >= 2 && citedPaperIds.length <= 12 &&
            <div className="synth-critical-review">
              <button className="btn btn-link" onClick={() => onCriticalReviewSources(citedPaperIds)}
                title="Critically review the papers this synthesis cites — cross-paper contradictions + each paper's method-check signals; a signal to weigh before trusting the synthesis, never a verdict">
                Critically review these sources ({citedPaperIds.length})
              </button>
            </div>}
          {state.result.imported &&
            <div className="synth-imported" title="This synthesis came from a shared bundle — its statuses are the sender's, computed against their PDFs, not re-checked here.">
              Imported — the sender's assessment, not re-checked in your library. Sources open at the page (region precision).
              {!readOnly &&
                <button className="btn btn-link" disabled={reverifying}
                  title="Re-run local verification (retrieval + NLI + quote-location) against your own library — turns this into your verified synthesis. No egress."
                  onClick={() => reverify(state.result.summary_id)}>
                  {reverifying ? "Re-verifying…" : "Re-verify against my library"}
                </button>}
            </div>}
          {scopeMeta && scopeMeta.total != null &&
            <div className="synth-coverage">
              Drew from <b>{drewFromPapers}</b> of {scopeMeta.total} selected paper{scopeMeta.total === 1 ? "" : "s"} · top {scopeMeta.topK} chunks
              {drewFromPapers < scopeMeta.total ? ` · ${scopeMeta.total - drewFromPapers} contributed no cited passage` : ""}
            </div>}
          {state.result.source_chunk_count != null &&
            <div className="synth-coverage">
              Retrieved <b>{state.result.source_chunk_count}</b> source chunk{state.result.source_chunk_count === 1 ? "" : "s"}
              {" · "}{sectionFilterSummary(state.result.section_filter)}
              {state.result.section_filter && state.result.section_filter.length
                ? " · section filter only narrows retrieval; verification thresholds are unchanged"
                : ""}
            </div>}
          {sentences.length > 0 && verifiedCount === 0 &&
            <div className="synth-coverage synth-coverage-warn">No claim cleared local verification — your question may not be well-addressed in these papers.</div>}
          {sentences.length === 0 &&
            <div className="state" style={{ padding: "24px 10px" }}>
              <div className="big">No groundable summary produced.</div>
              The generator returned no sentences — your question may not be addressed in this scope.
              {state.result.source_chunk_count === 0 && onOpenTextHealth &&
                <SynthesisSourceDiagnostic diagnostic={sourceDiagnostic} onOpenTextHealth={openTextHealthForSynthesis} />}
            </div>}
          {sentences.length > 0 && <OverviewBlock overview={state.result.overview}
            status={state.result.overview_status || (state.result.overview ? "complete" : "not_requested")}
            updatedAt={state.result.overview_updated_at}
            onRetry={readOnly ? null : overviewLifecycle.retry} retrying={overviewLifecycle.retrying} />}
          {sentences.length > 0 && <GroupedSummarySentences sentences={sentences} onOpenCitation={onOpenCitation} onSaveHighlight={readOnly ? null : onSaveHighlight} />}
        </div>}

      <SummaryHistory
        readOnly={readOnly}
        state={history}
        activeSummaryId={state.result && state.result.summary_id}
        onLoad={loadSummary}
        onDelete={removeSummary}
      />
    </div>
  );
}

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

// inc 121: the old RightPane (inc-57 vertical Synthesis/Details split with a draggable .divider-h) is retired.
// inc 287: SYNTHESIS now lives in the center menu bar as its own workspace; DETAILS remains in METHODS.
// inc 298: relabeled to Synthesize and split into Ask (this pane) + Critique (single-paper critical read).

// ─────────────────────────────────────────────────────────────
// PDF tab — streams /papers/{id}/pdf and renders it with PDF.js.
// Honest about the not-available-locally case; never a blank canvas.
// ─────────────────────────────────────────────────────────────

registerWorkspace({
  id: "synthesis", label: "Synthesize", order: 30, hideInReadOnly: false,
});
registerWorkspaceTab({ id: "synthesis" }, {
  id: "ask", label: "Ask", order: 10, hideInReadOnly: false,
  render: (ctx) => <SynthesisPane onOpenCitation={ctx.onOpenCitation} onSaveHighlight={ctx.onSaveHighlight}
    pendingSummarize={ctx.pendingSummarize} requestedSummary={ctx.requestedSummary} onOpenSettings={ctx.onOpenSettings} settingsNonce={ctx.settingsNonce}
    onOpenTextHealth={ctx.onOpenTextHealth} readOnly={ctx.readOnly} onCriticalReviewSources={ctx.onCriticalReviewSources} />,
});
