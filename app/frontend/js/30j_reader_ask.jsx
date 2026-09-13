// Paper-scoped Ask in the reader (inc 596, "stay with the paper"). A THIN new CLIENT of canonical Ask — NOT a
// new Ask. It invokes the SAME production endpoint (POST /summarize), the SAME job poller
// (observeJobUntilTerminal), and the SAME result/evidence/failure components (GroupedSummarySentences,
// SynthesisFailure) as Synthesize → Ask. The ONLY reader-specific thing is a deterministic single-paper scope
// (scope_type:"papers", paper_ids:[paperId]). No new retrieval/prompt/generator/verification/evidence/
// provenance/artifact — and it touches NO 0.6/0.7 experimental surface (zero backend change). A reader-launched
// Ask is an ordinary summary artifact whose scope_ref records paper_ids, so it stays discoverable by paper later.
//
// Drift guard (amendment 2): the production submit/request logic (launch/launchPrepared/pollJob) is closure-bound
// inside SynthesisPane — there is no clean standalone seam to reuse without refactoring that component. So the
// request body is built by the exported pure readerAskRequest() below, and tests/test_reader_ask_scope.py pins
// the invariant that this papers+query single-paper scope restricts retrieval to exactly that paper and passes
// the question to the generator through the canonical pipeline — i.e. reader Ask == canonical Ask semantics
// except for the deterministic single-paper scope.

const READER_ASK_TOP_K = 8; // matches canonical query Ask (20_synthesis.jsx start(): top_k 8)

// Pure + exported for the drift-guard reasoning. The one reader-specific thing is paper_ids = [this paper].
function readerAskRequest(paperId, query) {
  return { scope_type: "papers", paper_ids: [paperId], query: query, top_k: READER_ASK_TOP_K };
}

function readerAskPaperValid(paperId) {
  return Number.isInteger(paperId) && paperId > 0;
}

function ReaderAsk({ paperId, title, onOpenCitation, onSaveHighlight, onOpenSettings }) {
  const valid = readerAskPaperValid(paperId);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [state, setState] = useState({ status: "idle" }); // idle | running | done | error
  const pollRef = useRef(null);

  // Cancel any in-flight poll on unmount (e.g. the reader tab closes mid-Ask).
  useEffect(() => () => { if (pollRef.current) pollRef.current(); }, []);

  const close = useCallback(() => {
    if (pollRef.current) { pollRef.current(); pollRef.current = null; }
    setOpen(false);
  }, []);

  // Explicit egress: the /summarize call fires ONLY from this click (or Retry) — never from opening the reader.
  const ask = useCallback(() => {
    const q = query.trim();
    if (!q || !valid) return;
    if (pollRef.current) pollRef.current();
    setState({ status: "running", message: "Generating and verifying" });
    apiPost("/summarize", readerAskRequest(paperId, q)).then(r => {
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      setState({ status: "running", jobId: r.data.job_id, message: "Generating and verifying" });
      pollRef.current = observeJobUntilTerminal("/summarize/" + r.data.job_id, {
        onProgress: data => setState({
          status: "running",
          message: data.status === "pending" ? "Queued for verification" : "Generating and verifying",
        }),
        onDone: data => { pollRef.current = null; setState({ status: "done", result: data }); },
        onError: error => { pollRef.current = null; setState({ status: "error", error: error || "Ask failed." }); },
      });
    });
  }, [query, valid, paperId]);

  // Evidence "Open source" navigates the current PDF to the passage, then closes so the page is revealed. The
  // cited paper IS this reader paper, so the canonical onOpenCitation lands in the already-open tab.
  const openEvidence = useCallback((citation) => { if (onOpenCitation) onOpenCitation(citation); close(); }, [onOpenCitation, close]);

  if (isDemoMode()) return null; // live Ask needs the backend; the demo ships saved syntheses to inspect

  const busy = state.status === "running";
  const result = state.result;
  const sentences = (result && result.sentences) || [];

  return (
    <>
      <button className="pdf-ask-btn" disabled={!valid}
        title={valid ? "Ask a question about this paper" : "Open a paper to ask about it"}
        onClick={() => setOpen(true)}>✦ Ask</button>
      {open &&
        <div className="axis-modal-overlay reader-ask-overlay" onMouseDown={close}>
          <div className="axis-modal reader-ask-modal" role="dialog" aria-label="Ask this paper"
            onMouseDown={e => e.stopPropagation()}>
            <div className="axis-modal-head">
              <span>Ask this paper</span>
              <button className="axis-link" aria-label="Close" onClick={close}>×</button>
            </div>
            <div className="reader-ask-scope">Asking about: <b>{title || ("Paper " + paperId)}</b></div>
            <div className="axis-modal-note">
              Runs Callosum's ordinary Ask — grounded only in this paper — and verifies every citation against it.
            </div>
            <textarea className="reader-ask-input" placeholder="Ask a question about this paper…"
              value={query} disabled={busy} maxLength={4000}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask(); }} />
            <div className="reader-ask-actions">
              <button className="btn btn-ghost" onClick={close}>Close</button>
              <button className="btn btn-primary" disabled={busy || !query.trim()} onClick={ask}>
                {busy ? "Asking…" : "Ask"}
              </button>
            </div>
            {busy && <div className="axis-hint">{state.message || "Generating and verifying"}…</div>}
            {state.status === "error" &&
              <SynthesisFailure error={state.error} onOpenSettings={onOpenSettings} onRetry={ask} canRetry={!!query.trim()} />}
            {state.status === "done" && result &&
              <div className="reader-ask-result">
                {result.source_chunk_count != null &&
                  <div className="synth-coverage">
                    Retrieved <b>{result.source_chunk_count}</b> source chunk{result.source_chunk_count === 1 ? "" : "s"} from this paper
                  </div>}
                {result.generation_truncated &&
                  <div className="errbox" role="status" style={{ margin: "8px 0 0" }}>
                    <b>This answer is incomplete.</b> The AI ran out of room before finishing, so only part of what it set out to say is shown.
                  </div>}
                {sentences.length === 0 &&
                  <div className="state" style={{ padding: "18px 6px" }}>
                    <div className="big">No groundable summary produced.</div>
                    The generator returned no sentences — your question may not be addressed in this paper.
                  </div>}
                {sentences.length > 0 &&
                  <GroupedSummarySentences sentences={sentences} onOpenCitation={openEvidence} onSaveHighlight={onSaveHighlight} />}
              </div>}
          </div>
        </div>}
    </>
  );
}
