// 08x_methods_critical.jsx — Critical read (backlog #12): a grounded SCRUTINY SURFACE (signal, never a verdict).
// Tier 1 (deterministic/local, auto-runs): compose the paper's method-check flags + claims the rest of your corpus
// contests. Tier 2 (opt-in, egress-gated): the LLM proposes critique CANDIDATES through the #13 verbatim bar; the
// human accepts/rejects. Facts (Tier 1) and candidates (Tier 2) are visually + epistemically distinct (amber =
// candidate). No composite score anywhere; the critique is of claims + methods, never of the authors.

function ScrutinyBackboneView({ backbone, onOpen }) {
  const ms = backbone.method_signals || [];
  const cc = backbone.contested_claims || [];
  const nothing = !ms.length && !cc.length && !backbone.citation_signal;
  return (
    <div className="cr-backbone">
      <p className="eyebrow">What the checks surfaced (facts)</p>
      {nothing &&
        <div className="tag-suggest-empty">
          Nothing surfaced by these checks. That isn’t a clean bill of health — it means <i>these particular
          signals</i> found nothing to flag. Read on your own judgment.
        </div>}
      {ms.map((s, i) => (
        <div key={"ms" + i} className="bayes-check-item">
          <div className="bayes-check-head">
            <span className="bayes-check-label">{s.label}</span>
            <span className="bayes-check-muted">{s.kind}</span>
          </div>
          {s.detail && <div className="bayes-check-note">{s.detail}</div>}
        </div>
      ))}
      {cc.length > 0 && <p className="eyebrow">Claims your corpus contests</p>}
      {cc.map((c, i) => (
        <div key={"cc" + i} className="bayes-check-item">
          <div className="bayes-check-note"><b>This paper:</b> “{c.claim}”</div>
          <button className="bayes-check-ev" title={c.page != null ? "Open page " + c.page : "Open the contesting paper"}
            onClick={() => onOpen(c.other_paper_id, c.page)}>
            Contested by another paper: “{c.passage}”
          </button>
          <div className="lmm-basis">stance: {c.stance} · confidence {Math.round((c.confidence || 0) * 100)}%</div>
        </div>
      ))}
    </div>
  );
}

function CriticalCandidate({ c, onAccept, onReject }) {
  return (
    <div className={"cr-candidate" + (c.status === "accepted" ? " cr-accepted" : "")}>
      <div className="bayes-check-note">{c.concern}</div>
      <div className="cr-quote">“{c.anchor_quote}”</div>
      {c.confidence != null &&
        <div className="lmm-basis">stance: {c.stance || "—"} · confidence {Math.round(c.confidence * 100)}%</div>}
      {c.status === "accepted"
        ? <span className="cite-status verified">✓ accepted</span>
        : <div className="cr-actions">
            <button className="btn-link" onClick={onAccept}>Accept</button>
            <button className="btn-link" onClick={onReject}>Reject</button>
          </div>}
    </div>
  );
}

function CriticalReadPaper({ paperId, onOpenPaper, active }) {
  const [meta, setMeta] = useState(null);            // { title, hasText } | null
  const [t1, setT1] = useState({ status: "idle" });  // Tier-1 backbone job: idle|running|done|error
  const [aiReady, setAiReady] = useState(false);
  const [cands, setCands] = useState(null);          // Tier-2 candidates
  const [gen, setGen] = useState("idle");            // idle|generating|error

  useEffect(() => {
    setT1({ status: "idle" }); setMeta(null); setCands(null); setGen("idle");
    if (paperId == null) return;
    let live = true;
    api(`/papers/${paperId}`).then(r => {
      if (live && r.ok) setMeta({ title: r.data.title, hasText: (r.data.chunk_count || 0) > 0 });
    });
    api(`/papers/${paperId}/critical-read/candidates`).then(r => { if (live && r.ok) setCands(r.data.candidates); });
    return () => { live = false; };
  }, [paperId]);

  // AI availability: the Tier-2 button only appears when data-egress is enabled (the endpoint still enforces the gate).
  useEffect(() => { api("/settings").then(r => { if (r.ok) setAiReady(Boolean(r.data.data_egress_enabled)); }); }, []);

  const runT1 = () => {
    setT1({ status: "running" });
    const poll = (jid) => api(`/critical-read/${jid}`).then(rr => {
      if (!rr.ok) { setT1({ status: "error", error: rr.error }); return; }
      const d = rr.data;
      if (d.status === "done") setT1({ status: "done", backbone: d.backbone });
      else if (d.status === "error") setT1({ status: "error", error: d.detail || "failed" });
      else setTimeout(() => poll(jid), 1200);
    });
    apiPost(`/papers/${paperId}/critical-read`, {}).then(r => {
      if (!r.ok) { setT1({ status: "error", error: r.error }); return; }
      poll(r.data.job_id);
    });
  };
  useEffect(() => {
    if (active && meta && meta.hasText && t1.status === "idle") runT1();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, meta]);

  const generate = async () => {
    setGen("generating");
    const r = await apiPost(`/papers/${paperId}/critical-read/candidates/generate`, {});
    if (r.ok) { setCands(r.data.candidates); setGen("idle"); } else setGen("error");
  };
  const act = async (cid, action) => {
    const r = await apiPost(`/critical-read/candidates/${cid}/${action}`, {});
    if (!r.ok) return;
    setCands(prev => action === "reject"
      ? prev.filter(c => c.id !== cid)                                   // rejected never returns
      : prev.map(c => (c.id === cid ? { ...c, status: "accepted" } : c)));
  };
  const open = (pid, page) => { if (onOpenPaper && page != null) onOpenPaper({ id: pid }, { page, precision: "region" }); };

  if (paperId == null) return <div className="tag-suggest-empty">Select a paper to read it critically.</div>;
  const shown = (cands || []).filter(c => c.status !== "rejected");
  return (
    <div className="detail-statcheck">
      <span className="detail-cite-label">{meta ? meta.title : "This paper"}</span>
      <div className="statcheck-caveat">
        What a skeptical reader should check before citing — a <b>signal, not a verdict</b>. The facts below are
        gathered from local method checks + the rest of your corpus; the AI suggestions are <b>candidates you
        confirm</b>. Never a score, and the critique is of the work, never the authors.
      </div>
      {meta && !meta.hasText &&
        <span className="tag-suggest-empty">Process a PDF first — the critical read needs the paper’s text.</span>}
      {t1.status === "running" && <ProgressBar label="Assembling the scrutiny surface…" />}
      {t1.status === "error" && <div className="axis-err">Couldn’t assemble: {t1.error}</div>}
      {t1.status === "done" && t1.backbone && <ScrutinyBackboneView backbone={t1.backbone} onOpen={open} />}

      <div className="cr-tier2">
        <p className="eyebrow">AI-suggested critiques (candidates)</p>
        {!aiReady
          ? <div className="tag-suggest-empty">Enable AI features in Settings for AI-suggested critiques — the facts above need no AI.</div>
          : <button className="btn-link" disabled={gen === "generating"} onClick={generate}
              title="The AI proposes concerns; each must quote the paper verbatim, and you confirm or reject it.">
              {gen === "generating" ? "Suggesting…" : "Suggest critiques (AI)"}
            </button>}
        {gen === "error" && <div className="axis-err">Couldn’t suggest critiques — is AI enabled with a key (Settings)?</div>}
        {shown.map(c => <CriticalCandidate key={c.id} c={c} onAccept={() => act(c.id, "accept")} onReject={() => act(c.id, "reject")} />)}
      </div>
    </div>
  );
}

function CriticalReadSection({ ctx }) {
  return (
    <div className="statcheck-section">
      <div className="settings-sub">
        A <b>critical read</b>: what to check before you cite — the paper’s method-check flags, claims the rest of
        your corpus contests, and (opt-in) AI-suggested critique candidates you confirm. A reading aid, never a
        verdict or a score.
      </div>
      <CriticalReadPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper} active={ctx.methodsOpen === "critical_read"} />
    </div>
  );
}

registerPaneSection({
  id: "critical_read", label: "Critical read", paneId: "methods", order: 40, hideInReadOnly: true,
  render: (ctx) => <CriticalReadSection ctx={ctx} />,
});
