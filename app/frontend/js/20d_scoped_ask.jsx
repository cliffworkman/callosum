// Shared scoped-Ask shell (inc 602). Reader paper-Ask (30j) and axis-Ask (31c) differ ONLY in scope
// selection/resolution + the request payload; the canonical question → submit → poll → result-render flow is
// identical, so it lives here once (constraint c3 — no forked Ask client). useScopedAsk owns the job lifecycle
// (POST /summarize → observeJobUntilTerminal → state machine + cleanup); ScopedAskResult owns the done-state
// rendering (reusing the SAME GroupedSummarySentences the Synthesize tab uses). Each caller supplies its own
// scope header + a request-body builder. Function declarations hoist across the shared IIFE, so callers in
// later chunks reference these regardless of load order.

// The job lifecycle. `run(body)` POSTs the canonical /summarize body the caller builds and polls to terminal;
// state is {status: idle|running|done|error, ...}. cancel() aborts an in-flight poll; reset() returns to idle.
function useScopedAsk() {
  const [state, setState] = useState({ status: "idle" });
  const pollRef = useRef(null);
  useEffect(() => () => { if (pollRef.current) pollRef.current(); }, []);
  const cancel = useCallback(() => { if (pollRef.current) { pollRef.current(); pollRef.current = null; } }, []);
  const reset = useCallback(() => { cancel(); setState({ status: "idle" }); }, [cancel]);
  const run = useCallback((body) => {
    cancel();
    setState({ status: "running", message: "Generating and verifying" });
    apiPost("/summarize", body).then(r => {
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
  }, [cancel]);
  return { state, run, cancel, reset };
}

// The done-state renderer: the retrieved-chunk line, the incomplete-answer notice, the honest no-groundable
// state, then the SAME per-claim evidence cards as Synthesize → Ask. `coverageNoun` ("from this paper" / "in
// this axis") and `emptyNote` are the only scope-specific copy.
function ScopedAskResult({ result, onOpenCitation, onSaveHighlight, coverageNoun, emptyNote }) {
  const sentences = (result && result.sentences) || [];
  return (
    <div className="reader-ask-result">
      {result.source_chunk_count != null &&
        <div className="synth-coverage">
          Retrieved <b>{result.source_chunk_count}</b> source chunk{result.source_chunk_count === 1 ? "" : "s"} {coverageNoun}
        </div>}
      {result.generation_truncated &&
        <div className="errbox" role="status" style={{ margin: "8px 0 0" }}>
          <b>This answer is incomplete.</b> The AI ran out of room before finishing, so only part of what it set out to say is shown.
        </div>}
      {sentences.length === 0 &&
        <div className="state" style={{ padding: "18px 6px" }}>
          <div className="big">No groundable summary produced.</div>
          {emptyNote}
        </div>}
      {sentences.length > 0 &&
        <GroupedSummarySentences sentences={sentences} onOpenCitation={onOpenCitation} onSaveHighlight={onSaveHighlight} />}
    </div>
  );
}
