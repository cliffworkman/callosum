// Axis-scoped Ask (GitHub #82, inc 602). "Ask this axis" resolves a semantic axis to a concrete canonical
// paper set and runs ORDINARY production Ask over exactly that set — the axis changes WHICH papers are eligible,
// not HOW Ask reasons. No axis-specific prompt/retrieval/generator/verifier: the whole question→submit→poll→
// result flow is the shared shell (useScopedAsk / ScopedAskResult, 20d_scoped_ask.jsx), the SAME one reader
// paper-Ask uses. This chunk owns only the axis-specific scope selection: an interstitial that makes the corpus
// unmistakable (a live paper count + a full-text-eligible count, per tier) BEFORE the run, with an honest
// empty / no-full-text state and no whole-Library fallback.
//
// Self-hosted controller (the CriticalReadModalHost pattern): listens for `callosum:open-axis-ask`
// (detail.axisId, detail.axisLabel) so the axis card opens it without 40_app prop-threading. Mounted once at root.

const AXIS_ASK_TOP_K = 8; // matches canonical query Ask + reader Ask (deterministic corpus, ordinary reasoning)

function AxisAskModalHost({ onOpenCitation, onSaveHighlight, onOpenSettings }) {
  const [axis, setAxis] = useState(null); // {axisId, axisLabel} | null
  useEffect(() => {
    const open = (e) => {
      const id = e && e.detail && Number(e.detail.axisId);
      if (Number.isInteger(id) && id > 0) setAxis({ axisId: id, axisLabel: (e.detail && e.detail.axisLabel) || "" });
    };
    window.addEventListener("callosum:open-axis-ask", open);
    return () => window.removeEventListener("callosum:open-axis-ask", open);
  }, []);
  if (axis == null) return null;
  return <AxisAskModal axisId={axis.axisId} axisLabel={axis.axisLabel} onClose={() => setAxis(null)}
    onOpenCitation={onOpenCitation} onSaveHighlight={onSaveHighlight} onOpenSettings={onOpenSettings} />;
}

function AxisAskModal({ axisId, axisLabel, onClose, onOpenCitation, onSaveHighlight, onOpenSettings }) {
  const [scope, setScope] = useState({ status: "loading" }); // loading | ready | error
  const [tier, setTier] = useState("assigned"); // default: exclude uncertain (c6)
  const [query, setQuery] = useState("");
  const { state, run, cancel } = useScopedAsk();

  useEffect(() => {
    let live = true;
    api(`/axes/${axisId}/ask-scope`).then(r => {
      if (!live) return;
      setScope(r.ok ? { status: "ready", ...r.data } : { status: "error", error: r.error });
    });
    return () => { live = false; };
  }, [axisId]);

  const close = useCallback(() => { cancel(); onClose(); }, [cancel, onClose]);
  const openEvidence = useCallback((citation) => { if (onOpenCitation) onOpenCitation(citation); close(); }, [onOpenCitation, close]);

  const ask = useCallback(() => {
    const q = query.trim();
    if (!q) return;
    run({ scope_type: "axis", axis_id: axisId, membership_tier: tier, query: q, top_k: AXIS_ASK_TOP_K });
  }, [query, axisId, tier, run]);

  if (isDemoMode()) return null; // live Ask needs the backend; the demo ships saved syntheses to inspect

  const busy = state.status === "running";
  const result = state.result;
  const label = (scope.status === "ready" && scope.axis_label) || axisLabel || ("Axis " + axisId);
  const cur = scope.status === "ready" ? scope[tier] : null;   // {count, eligible_count} for the chosen tier
  const canAsk = !busy && !!query.trim() && cur && cur.eligible_count > 0;

  return (
    <div className="axis-modal-overlay reader-ask-overlay" onMouseDown={close}>
      <div className="axis-modal reader-ask-modal" role="dialog" aria-label="Ask this axis"
        onMouseDown={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Ask this axis</span>
          <button className="axis-link" aria-label="Close" onClick={close}>×</button>
        </div>
        <div className="reader-ask-scope">Asking across: <b>{label}</b></div>
        <div className="axis-modal-note">
          Runs Callosum's ordinary Ask — grounded only in this axis's papers — and verifies every citation against
          them. The axis sets which papers are eligible; it doesn't change how Ask reasons.
        </div>

        {scope.status === "loading" && <div className="axis-hint">Resolving this axis's papers…</div>}
        {scope.status === "error" && <div className="axis-err">Couldn't read this axis: {scope.error}</div>}

        {scope.status === "ready" &&
          <>
            <div className="axis-ask-tiers" role="radiogroup" aria-label="Which papers to include">
              <label className={"axis-ask-tier" + (tier === "assigned" ? " sel" : "")}>
                <input type="radio" name="axis-ask-tier" checked={tier === "assigned"}
                  disabled={busy} onChange={() => setTier("assigned")} />
                <span className="axis-ask-tier-name">Assigned only</span>
                <span className="axis-ask-tier-count">
                  {scope.assigned.count} paper{scope.assigned.count === 1 ? "" : "s"} · {scope.assigned.eligible_count} with usable full text
                </span>
              </label>
              <label className={"axis-ask-tier" + (tier === "all" ? " sel" : "")}>
                <input type="radio" name="axis-ask-tier" checked={tier === "all"}
                  disabled={busy} onChange={() => setTier("all")} />
                <span className="axis-ask-tier-name">Include uncertain</span>
                <span className="axis-ask-tier-count">
                  {scope.all.count} paper{scope.all.count === 1 ? "" : "s"} · {scope.all.eligible_count} with usable full text
                </span>
              </label>
            </div>
            <div className="axis-modal-note axis-ask-tier-note">
              “Assigned” is this axis's similarity/display tier, not a claim that you've endorsed each paper.
              “Uncertain” members scored below the cutoff — candidates to confirm. Only papers with usable full
              text can be retrieved; a run over this axis never falls back to the whole library.
            </div>

            {cur && cur.count === 0 &&
              <div className="axis-hint">This axis has no {tier === "assigned" ? "assigned" : ""} papers yet.
                {tier === "assigned" && scope.all.count > 0 && " Try “Include uncertain”, or add papers to the axis."}</div>}
            {cur && cur.count > 0 && cur.eligible_count === 0 &&
              <div className="axis-hint">None of this tier's {cur.count} paper{cur.count === 1 ? " has" : "s have"} usable
                full text, so there's nothing to retrieve. Acquire or attach PDFs, then ask.</div>}

            <textarea className="reader-ask-input" placeholder="Ask a question across this axis's papers…"
              value={query} disabled={busy} maxLength={4000}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && canAsk) ask(); }} />
            <div className="reader-ask-actions">
              <button className="btn btn-ghost" onClick={close}>Close</button>
              <button className="btn btn-primary" disabled={!canAsk} onClick={ask}>
                {busy ? "Asking…" : "Ask"}
              </button>
            </div>
          </>}

        {busy && <div className="axis-hint">{state.message || "Generating and verifying"}…</div>}
        {state.status === "error" &&
          <SynthesisFailure error={state.error} onOpenSettings={onOpenSettings} onRetry={ask} canRetry={canAsk} />}
        {state.status === "done" && result &&
          <ScopedAskResult result={result} onOpenCitation={openEvidence} onSaveHighlight={onSaveHighlight}
            coverageNoun="from this axis's papers"
            emptyNote="The generator returned no sentences — your question may not be addressed in this axis's papers." />}
      </div>
    </div>
  );
}
