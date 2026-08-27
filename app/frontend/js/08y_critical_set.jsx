// 08y_critical_set.jsx — Set (multi-paper) critical review (backlog #12). Launched from the synthesis pane
// ("Critically review these sources") or the library bulk bar ("critical read"). Reviews a CHOSEN SET of papers
// TOGETHER: a fact-matrix of each paper's stored method signals (Tier 1, local), the claims papers in the set
// contest in one another (Tier 1, local), and — opt-in, egress-gated — AI-proposed CROSS-PAPER critique CANDIDATES
// through the #13 verbatim bar (Tier 2) that the human accepts/rejects. Facts and candidates stay distinct
// (amber = candidate). No composite score, no ranking; the critique is of claims + methods, never the authors.
// Only a candidate's anchor quote is verified — "the model relates this to…" is the model's framing, not a link.

function _crSetKinds(aggregate) {
  // The distinct method-signal kinds across the set → the matrix columns (first-appearance order).
  const seen = [];
  (aggregate || []).forEach(row => (row.method_signals || []).forEach(s => {
    if (s.kind && !seen.includes(s.kind)) seen.push(s.kind);
  }));
  return seen;
}

function CriticalSetMatrix({ aggregate }) {
  const kinds = _crSetKinds(aggregate);
  return (
    <div className="cr-matrix-wrap">
      <table className="cr-matrix">
        <thead>
          <tr>
            <th>Paper</th>
            {kinds.map(k => <th key={k}>{k}</th>)}
            <th>contested</th>
          </tr>
        </thead>
        <tbody>
          {(aggregate || []).map(row => {
            const byKind = {};
            (row.method_signals || []).forEach(s => { byKind[s.kind] = s; });
            return (
              <tr key={row.paper_id}>
                <td className="cr-matrix-title" title={row.title}>{row.title}</td>
                {kinds.map(k => (
                  <td key={k} title={byKind[k] ? (byKind[k].detail || byKind[k].label || "") : ""}>
                    {byKind[k] ? (byKind[k].label || "•") : "—"}
                  </td>
                ))}
                <td>{row.contested_count || 0}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="cr-matrix-caption">
        Facts each check surfaced — <b>not a score</b>. An empty cell means <i>this check found nothing on this
        paper</i>, not a clean bill of health.
        {kinds.length === 0 &&
          <span> No method checks (statcheck, transparency, …) have been <b>run</b> on these papers yet — run them
          from each paper’s Synthesize → Critique tab to populate this. The <i>contested</i> column reflects only intra-set
          disagreement, which needs no prior check.</span>}
      </div>
    </div>
  );
}

function CriticalSetDisagreements({ contested, titleById, onOpen, triageOnly }) {
  const label = (id) => titleById[id] || ("Paper " + id);
  const all = contested || [];
  const shown = all.filter(c => critiqueTriageVisible(c, triageOnly));
  if (!all.length) {
    return (
      <div className="tag-suggest-empty">
        Nothing surfaced by this check — no paper in the set contradicts another’s claims that these signals caught.
        That isn’t agreement, only silence from <i>these</i> checks.
      </div>
    );
  }
  if (!shown.length) {
    return <div className="tag-suggest-empty">All {all.length} disagreement(s) here were triaged as lower-yield — switch to “All rows” to see them.</div>;
  }
  return shown.map((c, i) => (
    <div key={i} className="bayes-check-item">
      <div className="bayes-check-note"><b>{label(c.claim_paper_id)}:</b> “{c.claim}”</div>
      <button className="bayes-check-ev" title={c.page != null ? "Open page " + c.page : "Open the contesting paper"}
        onClick={() => onOpen(c.other_paper_id, c.page)}>
        Contested by “{label(c.other_paper_id)}”: “{c.passage}”
      </button>
      <div className="lmm-basis">stance: {c.stance} · confidence {Math.round((c.confidence || 0) * 100)}%</div>
      <TriageBadge triage={c.llm_triage} />
    </div>
  ));
}

function CriticalSetCandidate({ c, titleById, onAccept, onReject }) {
  const related = (c.related_paper_ids_json || []).map(id => titleById[id] || ("Paper " + id));
  return (
    <div className={"cr-candidate" + (c.status === "accepted" ? " cr-accepted" : "")}>
      <div className="bayes-check-note">{c.concern}</div>
      <div className="cr-quote">“{c.anchor_quote}”</div>
      <div className="lmm-basis">
        in “{titleById[c.paper_id] || ("Paper " + c.paper_id)}”
        {c.stance ? " · stance: " + c.stance : ""}
        {c.confidence != null ? " · confidence " + Math.round(c.confidence * 100) + "%" : ""}
      </div>
      {related.length > 0 &&
        <div className="cr-related">
          The model relates this to: {related.join("; ")}{" "}
          <span className="cr-related-note">(the model’s framing, not a verified link)</span>
        </div>}
      <TriageBadge triage={c.llm_triage} />
      {c.status === "accepted"
        ? <span className="cite-status verified">✓ accepted</span>
        : <div className="cr-actions">
            <button className="btn-link" onClick={onAccept}>Accept</button>
            <button className="btn-link" onClick={onReject}>Reject</button>
          </div>}
    </div>
  );
}

function CriticalSetModal({ ids, resumeJobId, onClose, onOpenPaper }) {
  const [phase, setPhase] = useState("idle");  // idle | loading | ready | error
  const [report, setReport] = useState(null);
  const [err, setErr] = useState(null);
  const [aiReady, setAiReady] = useState(false);
  const [wantLlm, setWantLlm] = useState(false);
  const [wantTriage, setWantTriage] = useState(false);
  const [triageOnly, setTriageOnly] = useState(false);
  const pollersRef = useRef(new Set());
  const activeJobKey = `callosum.active-job.critical-read-set.${ids.join(",")}`;

  // Run or resume a set critical-read job.  The held GET is notification only;
  // its terminal response remains the authoritative report.
  const runSet = useCallback((wantLlm, wantTriage, resumeJobId) => new Promise((resolve, reject) => {
    const observe = jobId => {
      rememberActiveJob(activeJobKey, jobId);
      let cancel = null;
      const finish = callback => value => {
        pollersRef.current.delete(cancel);
        rememberActiveJob(activeJobKey, null);
        callback(value);
      };
      cancel = observeJobUntilTerminal(`/critical-read/set/${jobId}`, {
        onDone: data => finish(resolve)(data.report),
        onError: finish(reject),
      });
      pollersRef.current.add(cancel);
    };
    if (resumeJobId) {
      observe(resumeJobId);
      return;
    }
    apiPost("/critical-read/set", { paper_ids: ids, llm: !!wantLlm, triage: !!wantTriage }).then(r => {
      if (!r.ok) { reject(r.error); return; }
      observe(r.data.job_id);
    });
  }), [ids, activeJobKey]);

  // Only auto-resume without the button when there's a real in-flight/finished job to reattach to (a Status-nav
  // resumeJobId, or a recalled sessionStorage job for this exact set) -- a genuinely fresh open shows the idle button.
  useEffect(() => {
    const resume = resumeJobId || recalledActiveJob(activeJobKey);
    if (!resume) { setPhase("idle"); return undefined; }
    let live = true;
    setPhase("loading"); setReport(null); setErr(null);
    runSet(false, false, resume)
      .then(rep => { if (live) { setReport(rep); setPhase("ready"); } })
      .catch(e => { if (live) { setErr(e); setPhase("error"); } });
    return () => { live = false; };
  }, [runSet, activeJobKey, resumeJobId]);

  useEffect(() => {
    let live = true;
    api("/settings").then(r => { if (live && r.ok) setAiReady(Boolean(r.data.data_egress_enabled)); });
    return () => { live = false; };
  }, []);

  useEffect(() => () => {
    pollersRef.current.forEach(cancel => cancel());
    pollersRef.current.clear();
  }, []);

  const start = () => {
    setPhase("loading"); setReport(null); setErr(null);
    runSet(wantLlm, wantTriage, null)
      .then(rep => { setReport(rep); setPhase("ready"); })
      .catch(e => { setErr(e); setPhase("error"); });
  };
  const act = async (cid, action) => {
    const r = await apiPost(`/critical-read/candidates/${cid}/${action}`, {});
    if (!r.ok) return;
    setReport(prev => {
      if (!prev) return prev;
      const cands = action === "reject"
        ? (prev.candidates || []).filter(c => c.id !== cid)
        : (prev.candidates || []).map(c => (c.id === cid ? { ...c, status: "accepted" } : c));
      return { ...prev, candidates: cands };
    });
  };
  const open = (pid, page) => {
    if (onOpenPaper) onOpenPaper({ id: pid }, page != null ? { page, precision: "region" } : {});
    onClose();
  };

  const titleById = {};
  ((report && report.aggregate) || []).forEach(r => { titleById[r.paper_id] = r.title; });
  const contestedAll = (report && report.contested_claims) || [];
  const candidatesAll = ((report && report.candidates) || []).filter(c => c.status !== "rejected");
  const candidates = candidatesAll.filter(c => critiqueTriageVisible(c, triageOnly));
  const llmStatus = report && report.llm_status;
  const generated = !!llmStatus && llmStatus.status !== "not_searched";  // Tier-2 ran as part of this run
  const hasTriage = contestedAll.some(c => c.llm_triage) || candidatesAll.some(c => c.llm_triage);
  const hiddenCount = (contestedAll.length - contestedAll.filter(c => critiqueTriageVisible(c, true)).length)
    + (candidatesAll.length - candidatesAll.filter(c => critiqueTriageVisible(c, true)).length);

  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal cr-set-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Critically review {ids.length} sources</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          What a skeptical reader should check before trusting these papers <b>together</b> — a <b>signal, not a
          verdict</b>. Facts come from local method checks + where the set disagrees; AI critiques are <b>candidates
          you confirm</b>. Never a score; the critique is of the work, never the authors.
        </div>

        {phase === "idle" &&
          <div className="cr-run-toggles">
            <CritiqueRunToggles wantLlm={wantLlm} setWantLlm={setWantLlm} wantTriage={wantTriage}
              setWantTriage={setWantTriage} aiReady={aiReady} suggestLabel="Suggest cross-paper critiques (AI)" />
            <button className="btn btn-primary" onClick={start}>Run critique</button>
          </div>}
        {phase === "loading" && <ProgressBar label="Assembling the scrutiny surface…" managedBy="backend-job" />}
        {phase === "error" && <div className="axis-err">Couldn’t assemble: {String(err)}</div>}
        {phase === "ready" && report && <React.Fragment>
          <TriageFilterControls hasTriage={hasTriage} triageOnly={triageOnly} onView={setTriageOnly} hiddenCount={hiddenCount} />
          <div className="cr-set-section">
            <p className="eyebrow">What the checks surfaced (facts)</p>
            <CriticalSetMatrix aggregate={report.aggregate} />
          </div>

          <div className="cr-set-section">
            <p className="eyebrow">Where these papers disagree</p>
            <CriticalSetDisagreements contested={contestedAll} titleById={titleById} onOpen={open} triageOnly={triageOnly} />
          </div>

          <div className="cr-set-section cr-tier2">
            <p className="eyebrow">AI cross-paper critiques (candidates)</p>
            {!generated && !aiReady &&
              <div className="tag-suggest-empty">
                Enable AI features in Settings for AI-suggested cross-paper critiques — the facts above need no AI.
              </div>}
            {!generated && aiReady &&
              <div className="tag-suggest-empty">Not requested for this run — re-run with “Suggest cross-paper critiques” checked.</div>}
            {generated && llmStatus.status === "unavailable" &&
              <div className="tag-suggest-empty">{llmStatus.detail}</div>}
            {generated && llmStatus.status === "success" && !candidatesAll.length &&
              <div className="tag-suggest-empty">No grounded cross-paper concerns surfaced — nothing quoted a paper verbatim.</div>}
            {candidates.map(c => (
              <CriticalSetCandidate key={c.id} c={c} titleById={titleById}
                onAccept={() => act(c.id, "accept")} onReject={() => act(c.id, "reject")} />
            ))}
          </div>
        </React.Fragment>}
      </div>
    </div>
  );
}
