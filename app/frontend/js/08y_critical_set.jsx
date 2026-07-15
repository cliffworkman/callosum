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
      </div>
    </div>
  );
}

function CriticalSetDisagreements({ contested, titleById, onOpen }) {
  const label = (id) => titleById[id] || ("Paper " + id);
  if (!contested || !contested.length) {
    return (
      <div className="tag-suggest-empty">
        Nothing surfaced by this check — no paper in the set contradicts another’s claims that these signals caught.
        That isn’t agreement, only silence from <i>these</i> checks.
      </div>
    );
  }
  return contested.map((c, i) => (
    <div key={i} className="bayes-check-item">
      <div className="bayes-check-note"><b>{label(c.claim_paper_id)}:</b> “{c.claim}”</div>
      <button className="bayes-check-ev" title={c.page != null ? "Open page " + c.page : "Open the contesting paper"}
        onClick={() => onOpen(c.other_paper_id, c.page)}>
        Contested by “{label(c.other_paper_id)}”: “{c.passage}”
      </button>
      <div className="lmm-basis">stance: {c.stance} · confidence {Math.round((c.confidence || 0) * 100)}%</div>
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
      {c.status === "accepted"
        ? <span className="cite-status verified">✓ accepted</span>
        : <div className="cr-actions">
            <button className="btn-link" onClick={onAccept}>Accept</button>
            <button className="btn-link" onClick={onReject}>Reject</button>
          </div>}
    </div>
  );
}

function CriticalSetModal({ ids, onClose, onOpenPaper }) {
  const [phase, setPhase] = useState("loading");  // loading | ready | error
  const [report, setReport] = useState(null);
  const [err, setErr] = useState(null);
  const [aiReady, setAiReady] = useState(false);
  const [gen, setGen] = useState("idle");          // idle | generating | error

  // Run a set critical-read job (Tier-1 always; Tier-2 when wantLlm) → resolves the report. POST → poll GET.
  const runSet = useCallback((wantLlm) => new Promise((resolve, reject) => {
    const poll = (jid) => api(`/critical-read/set/${jid}`).then(rr => {
      if (!rr.ok) { reject(rr.error); return; }
      const d = rr.data;
      if (d.status === "done") resolve(d.report);
      else if (d.status === "error") reject(d.detail || "failed");
      else setTimeout(() => poll(jid), 1200);
    });
    apiPost("/critical-read/set", { paper_ids: ids, llm: !!wantLlm }).then(r => {
      if (!r.ok) { reject(r.error); return; }
      poll(r.data.job_id);
    });
  }), [ids]);

  useEffect(() => {
    let live = true;
    setPhase("loading"); setReport(null); setErr(null);
    runSet(false)
      .then(rep => { if (live) { setReport(rep); setPhase("ready"); } })
      .catch(e => { if (live) { setErr(e); setPhase("error"); } });
    api("/settings").then(r => { if (live && r.ok) setAiReady(Boolean(r.data.data_egress_enabled)); });
    return () => { live = false; };
  }, [runSet]);

  const generate = () => {
    setGen("generating");
    runSet(true).then(rep => { setReport(rep); setGen("idle"); }).catch(() => setGen("error"));
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
  const candidates = ((report && report.candidates) || []).filter(c => c.status !== "rejected");
  const llmStatus = report && report.llm_status;
  const generated = !!llmStatus && llmStatus.status !== "not_searched";  // Tier-2 already ran this session

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

        {phase === "loading" && <ProgressBar label="Assembling the scrutiny surface…" />}
        {phase === "error" && <div className="axis-err">Couldn’t assemble: {String(err)}</div>}
        {phase === "ready" && report && <React.Fragment>
          <div className="cr-set-section">
            <p className="eyebrow">What the checks surfaced (facts)</p>
            <CriticalSetMatrix aggregate={report.aggregate} />
          </div>

          <div className="cr-set-section">
            <p className="eyebrow">Where these papers disagree</p>
            <CriticalSetDisagreements contested={report.contested_claims} titleById={titleById} onOpen={open} />
          </div>

          <div className="cr-set-section cr-tier2">
            <p className="eyebrow">AI cross-paper critiques (candidates)</p>
            {!aiReady &&
              <div className="tag-suggest-empty">
                Enable AI features in Settings for AI-suggested cross-paper critiques — the facts above need no AI.
              </div>}
            {aiReady && !generated &&
              <button className="btn-link" disabled={gen === "generating"} onClick={generate}
                title="The AI proposes concerns spanning these papers; each must quote a paper verbatim, and you confirm or reject it.">
                {gen === "generating" ? "Suggesting…" : "Suggest cross-paper critiques (AI)"}
              </button>}
            {gen === "error" && <div className="axis-err">Couldn’t suggest critiques — is AI enabled with a key (Settings)?</div>}
            {generated && llmStatus.status === "unavailable" &&
              <div className="tag-suggest-empty">{llmStatus.detail}</div>}
            {generated && llmStatus.status === "success" && !candidates.length &&
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
