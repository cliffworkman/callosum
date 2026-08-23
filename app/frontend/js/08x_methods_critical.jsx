// 08x_methods_critical.jsx — Critical read (backlog #12): a grounded SCRUTINY SURFACE (signal, never a verdict).
// Tier 1 (deterministic/local, user-triggered via "Run critical read"): compose the paper's method-check flags +
// claims the rest of your corpus contests. Tier 2 (opt-in, egress-gated): the LLM proposes critique CANDIDATES
// through the #13 verbatim bar; the human accepts/rejects. Facts (Tier 1) and candidates (Tier 2) are visually +
// epistemically distinct (amber = candidate). No composite score anywhere; the critique is of claims + methods,
// never of the authors.
//
// The left-pane "Review" accordion (formerly 08_methods_findings.jsx) retired here: its FACTs were already a
// subset of Tier 1's method_signals (both read paper_findings via the backend's _stored_method_signals /
// get_paper_findings), and its library-wide retraction batch duplicated the Library header's own
// RetractionCheckButton (10b_libmenus.jsx). The one piece with no equivalent — the reviewable CANDIDATE queue
// (statcheck-flagged issues etc., Confirmed/Accepted/Noted) — moves here as findingText/FindingCard.

function findingText(f) {
  const p = f.payload || {};
  return p.desc || p.label || p.text || p.title || JSON.stringify(p);
}

function FindingCard({ finding, onReviewed, onOpenPaper }) {
  const [reasonOpen, setReasonOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const reviewed = finding.review_state && finding.review_state !== "unreviewed";
  const page = finding.payload && finding.payload.page;
  const review = async (state, why) => {
    setBusy(true);
    const r = await apiPost(`/findings/${finding.id}/review`, why ? { state, reason: why } : { state });
    setBusy(false);
    if (r.ok && onReviewed) onReviewed();
  };
  return (
    <div className={"finding-card" + (finding.tier === "speculative" ? " speculative" : "") + (reviewed ? " reviewed" : "")}>
      <div className="finding-head">
        <span className="finding-text">{findingText(finding)}</span>
        {finding.tier === "speculative" && <span className="finding-tier">speculative</span>}
      </div>
      {page != null && onOpenPaper &&
        <button className="btn-link finding-anchor" onClick={() => {
          const p = finding.payload || {};
          const exact = p.anchor_state === "exact";
          onOpenPaper({ id: finding.paper_id, title: "" }, { page, precision: exact ? "exact" : "region", bboxJson: exact ? p.bbox_json : null });
        }}>show in paper · p.{page}</button>}
      {reviewed
        ? <div className="finding-reviewed">✓ {finding.review_state}{finding.review_reason ? ` — ${finding.review_reason}` : ""}</div>
        : <div className="finding-actions">
            <button className="btn-link" disabled={busy} onClick={() => review("confirmed")}>Confirmed</button>
            <button className="btn-link" disabled={busy} onClick={() => setReasonOpen(v => !v)}>Accepted…</button>
            <button className="btn-link" disabled={busy} onClick={() => review("noted")}>Noted</button>
          </div>}
      {reasonOpen && !reviewed &&
        <div className="finding-reason">
          <input className="grim-in finding-reason-in" placeholder="why (required)" value={reason} onChange={e => setReason(e.target.value)} />
          <button className="btn-link" disabled={busy || !reason.trim()} onClick={() => review("accepted", reason.trim())}>save</button>
        </div>}
    </div>
  );
}

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
          {s.notice_url &&
            <a className="btn-link" href={s.notice_url} target="_blank" rel="noopener noreferrer">notice</a>}
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

function CriticalReadPaper({ paperId, onOpenPaper, onFindingsChanged }) {
  const [meta, setMeta] = useState(null);            // { title, hasText } | null
  const [t1, setT1] = useState({ status: "idle" });  // Tier-1 backbone job: idle|running|done|error
  const [aiReady, setAiReady] = useState(false);
  const [cands, setCands] = useState(null);          // Tier-2 candidates
  const [gen, setGen] = useState("idle");            // idle|generating|error
  const [findingCands, setFindingCands] = useState([]);  // paper_findings CANDIDATEs (e.g. statcheck-flagged issues)
  const t1PollRef = useRef(null);

  const activeJobKey = paperId == null ? null : `callosum.active-job.critical-read.${paperId}`;
  const pollT1Job = useCallback((jobId) => {
    if (t1PollRef.current) t1PollRef.current();
    if (activeJobKey) rememberActiveJob(activeJobKey, jobId);
    t1PollRef.current = observeJobUntilTerminal(`/critical-read/${jobId}`, {
      onProgress: () => setT1({ status: "running", jobId }),
      onDone: data => {
        t1PollRef.current = null;
        if (activeJobKey) rememberActiveJob(activeJobKey, null);
        setT1({ status: "done", backbone: data.backbone, jobId });
      },
      onError: error => {
        t1PollRef.current = null;
        if (activeJobKey) rememberActiveJob(activeJobKey, null);
        setT1({ status: "error", error: error || "failed", jobId });
      },
    });
  }, [activeJobKey]);

  const loadFindingCands = () => {
    if (paperId == null) return;
    api(`/papers/${paperId}/findings`).then(r => { if (r.ok) setFindingCands(r.data.candidates); });
  };

  useEffect(() => {
    setT1({ status: "idle" }); setMeta(null); setCands(null); setGen("idle"); setFindingCands([]);
    if (paperId == null) return;
    let live = true;
    api(`/papers/${paperId}`).then(r => {
      if (live && r.ok) setMeta({ title: r.data.title, hasText: (r.data.chunk_count || 0) > 0 });
    });
    api(`/papers/${paperId}/critical-read/candidates`).then(r => { if (live && r.ok) setCands(r.data.candidates); });
    api(`/papers/${paperId}/findings`).then(r => { if (live && r.ok) setFindingCands(r.data.candidates); });
    const activeJobId = recalledActiveJob(activeJobKey);
    if (activeJobId) {
      setT1({ status: "running", jobId: activeJobId });
      pollT1Job(activeJobId);
    }
    if (isDemoMode()) api(`/papers/${paperId}/critical-read/saved`).then(r => {
      if (!live) return;
      if (r.ok && r.data.status === "done") setT1({ status: "done", backbone: r.data.backbone });
      else if (!r.ok) setT1({ status: "error", error: r.error });
    });
    return () => {
      live = false;
      if (t1PollRef.current) t1PollRef.current();
      t1PollRef.current = null;
    };
  }, [paperId, activeJobKey, pollT1Job]);

  const onFindingReviewed = () => { loadFindingCands(); if (onFindingsChanged) onFindingsChanged(); };

  // AI availability: the Tier-2 button only appears when data-egress is enabled (the endpoint still enforces the gate).
  useEffect(() => { api("/settings").then(r => { if (r.ok) setAiReady(Boolean(r.data.data_egress_enabled)); }); }, []);

  const runT1 = () => {
    setT1({ status: "running" });
    apiPost(`/papers/${paperId}/critical-read`, {}).then(r => {
      if (!r.ok) { setT1({ status: "error", error: r.error }); return; }
      pollT1Job(r.data.job_id);
    });
  };
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
      {meta && meta.hasText && t1.status === "idle" &&
        <button className="btn btn-primary" onClick={runT1}
          title="Compose this paper's method-check flags + any corpus-contested claims — local, no AI">
          Run critical read
        </button>}
      {t1.status === "running" && <ProgressBar label="Assembling the scrutiny surface…" managedBy="backend-job" />}
      {t1.status === "error" && <div className="axis-err">Couldn’t assemble: {t1.error}</div>}
      {t1.status === "done" && t1.backbone && <ScrutinyBackboneView backbone={t1.backbone} onOpen={open} />}
      {isDemoMode() && <div className="settings-note">Saved deterministic critical read. Reruns and AI critique generation require the local Callosum application.</div>}

      {findingCands.length > 0 &&
        <div className="cr-findings">
          <p className="eyebrow">Needs your review</p>
          {findingCands.map(f => <FindingCard key={f.id} finding={f} onReviewed={onFindingReviewed} onOpenPaper={onOpenPaper} />)}
        </div>}

      <div className="cr-tier2">
        <p className="eyebrow">AI-suggested critiques (candidates)</p>
        {isDemoMode()
          ? <div className="tag-suggest-empty">AI critique generation is unavailable in the online demo; no paper text is sent anywhere.</div>
          : !aiReady
          ? <div className="tag-suggest-empty">Enable AI features in Settings for AI-suggested critiques — the facts above need no AI.</div>
          : <button className="btn-link" disabled={gen === "generating"} onClick={generate}
              title="The AI proposes concerns; each must quote the paper verbatim, and you confirm or reject it.">
              {gen === "generating" ? "Suggesting…" : "Suggest critiques (AI)"}
            </button>}
        {gen === "generating" && <ProgressBar label="Suggesting and locally verifying critiques…" managedBy="tracked-request" />}
        {gen === "error" && <div className="axis-err">Couldn’t suggest critiques — is AI enabled with a key (Settings)?</div>}
        {shown.map(c => <CriticalCandidate key={c.id} c={c} onAccept={() => act(c.id, "accept")} onReject={() => act(c.id, "reject")} />)}
      </div>
    </div>
  );
}

function WipCriticalReadResult({ run, ctx, onOpenSource }) {
  const result = run.structured_result_json || {};
  const retrieval = result.retrieval || {};
  const claims = result.claims || [];
  const contested = result.contested_claims || [];
  const methods = result.method_signals || [];
  const retrievalMessage = {
    "no-claims": "No bounded claim sentences were available in the extracted primary manuscript.",
    "empty-library-corpus": "No matching-model article-fulltext embeddings are available in the Library corpus.",
    "nli-unavailable": "Nearby Library passages were found, but the local stance model was unavailable; no stance was guessed.",
    "local-model-unavailable": "The configured local embedding or retrieval model was unavailable; method receipts remain inspectable.",
    "no-retrievable-passages": "Eligible embeddings existed, but no passage could be resolved for local comparison.",
  }[retrieval.status];
  const openOther = item => {
    if (!ctx.onOpenPaper) return;
    ctx.onOpenPaper(
      { id: item.other_paper_id, title: item.other_paper_title || "Library paper" },
      { id: `wip-critical:${run.id}:${item.other_paper_id}`, paperId: item.other_paper_id,
        attachmentId: item.attachment_id, page: item.page, precision: item.other_coordinate_precision }
    );
  };
  return <div className="wip-critical-result">
    <p className="eyebrow">Current-checkpoint method coverage</p>
    <div className="bayes-checklist">
      {methods.map(item => <div className="bayes-check-item" key={item.tool_id}>
        <div className="bayes-check-head">
          <span className="bayes-check-label">{item.label}</span>
          <span className={item.status === "available" ? "cite-status verified" : "bayes-check-muted"}>
            {item.status === "available" ? "current receipt" : "unavailable"}
          </span>
        </div>
        {item.status === "available"
          ? <div className="bayes-check-note">{item.result_summary}
              {item.unresolved_candidate_count > 0 && ` · ${item.unresolved_candidate_count} unresolved review prompt${item.unresolved_candidate_count === 1 ? "" : "s"}`}
            </div>
          : <div className="bayes-check-note">{item.detail}</div>}
      </div>)}
    </div>
    <p className="eyebrow">Claims compared locally</p>
    {retrievalMessage && <div className="tag-suggest-empty">{retrievalMessage}</div>}
    {!retrievalMessage && contested.length === 0 && <div className="tag-suggest-empty">
      No high-confidence contrasting stance surfaced within this run’s bounded Library comparison. That is not a
      clean bill of health or evidence that the claims are uncontested.
    </div>}
    {contested.map((item, index) => <div className="bayes-check-item" key={index}>
      <div className="bayes-check-note"><b>This manuscript:</b> “{item.claim}”</div>
      <button type="button" className="bayes-check-ev" onClick={() => openOther(item)}>
        <b>{item.other_paper_title || `Library paper ${item.other_paper_id}`}:</b> “{item.passage}”
      </button>
      <div className="lmm-basis">local NLI stance: contrast · confidence {Math.round(item.confidence * 100)}%</div>
    </div>)}
    <details className="evidence-trail">
      <summary>{claims.length} bounded manuscript claim sentence{claims.length === 1 ? "" : "s"} inspected</summary>
      {claims.map((claim, index) => <blockquote key={index}>{claim.text}</blockquote>)}
    </details>
    <div className="statcheck-caveat">
      Exact checkpoint {run.snapshot_id} · local models {run.parameters_json.embedding_model} / {run.parameters_json.stance_model}.
      Query embeddings are transient and never stored as paper embeddings. Only article-fulltext Library passages
      are eligible. This surfaces disagreement; it does not decide which claim is correct.
    </div>
    <button className="btn-link" onClick={onOpenSource}>Open primary manuscript file</button>
  </div>;
}

function CriticalReadWip({ manuscript, ctx }) {
  const manuscriptId = manuscript ? manuscript.id : null;
  const [latest, setLatest] = useState(null);
  const [state, setState] = useState({ status: "idle" });
  const pollRef = useRef(null);
  const reloadWipRef = useRef(ctx.onReloadWip);
  reloadWipRef.current = ctx.onReloadWip;
  const activeJobKey = manuscriptId == null ? null : `callosum.active-job.wip-critical-read.${manuscriptId}`;
  const pollJob = useCallback(jobId => {
    if (pollRef.current) pollRef.current();
    if (activeJobKey) rememberActiveJob(activeJobKey, jobId);
    pollRef.current = observeJobUntilTerminal(`/wip/critical-read/${jobId}`, {
      onProgress: () => setState({ status: "running", jobId }),
      onDone: data => {
        pollRef.current = null;
        if (activeJobKey) rememberActiveJob(activeJobKey, null);
        setLatest(data.run); setState({ status: "done", jobId });
        if (reloadWipRef.current) reloadWipRef.current();
      },
      onError: error => {
        pollRef.current = null;
        if (activeJobKey) rememberActiveJob(activeJobKey, null);
        setState({ status: "error", error: error || "Local critical read failed.", jobId });
      },
    });
  }, [activeJobKey]);
  useEffect(() => {
    setState({ status: "idle" }); setLatest(null);
    if (manuscriptId == null) return undefined;
    let live = true;
    api(`/wip/manuscripts/${manuscriptId}/checks`).then(r => {
      if (live && r.ok) setLatest((r.data.runs || []).find(run => run.tool_id === "critical-read") || null);
    });
    const activeJobId = recalledActiveJob(activeJobKey);
    if (activeJobId) {
      setState({ status: "running", jobId: activeJobId });
      pollJob(activeJobId);
    }
    return () => {
      live = false;
      if (pollRef.current) pollRef.current();
      pollRef.current = null;
    };
  }, [manuscriptId, ctx.wipRefresh, activeJobKey, pollJob]);
  const start = async () => {
    setState({ status: "running" });
    const response = await apiPost(`/wip/manuscripts/${manuscriptId}/critical-read`, {});
    if (!response.ok) return setState({ status: "error", error: response.error });
    pollJob(response.data.job_id);
  };
  const openSource = async () => {
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/files/${latest.file_id}/open`, {});
    if (!result.ok) setState({ status: "error", error: result.error || "Could not open the source file." });
  };
  if (manuscriptId == null) return <div className="tag-suggest-empty">Select a WIP manuscript to read it critically.</div>;
  return <div className="detail-statcheck">
    <span className="detail-cite-label">{manuscript.display_title || manuscript.derived_title || "This manuscript"}</span>
    <div className="settings-actions">
      <button className="btn btn-primary" disabled={state.status === "running"} onClick={start}>
        {state.status === "running" ? "Running…" : latest ? "Run local critical read again" : "Run local critical read"}
      </button>
    </div>
    {state.status === "running" && <ProgressBar label="Comparing bounded claims with local Library evidence…" managedBy="backend-job" />}
    {state.status === "error" && <div className="axis-err">Couldn’t complete the local critical read: {state.error}
      {latest && <span> The previous receipt remains below.</span>}
    </div>}
    {!latest && state.status !== "running" && <div className="tag-suggest-empty">
      No local critical-read receipt yet. An empty history says nothing about the manuscript.
    </div>}
    {latest && <div className="wip-tool-run">
      <div className="wip-tool-run-head">
        <strong>Local critical read</strong>
        <span className={`wip-identity-${latest.validity}`}>{latest.validity.replace(/-/g, " ")}</span>
        <time>{wipWhen(latest.executed_at)}</time>
      </div>
      <p>{latest.result_summary}</p>
      <small>v{latest.tool_version} · snapshot {latest.snapshot_id} · {latest.coverage}</small>
      <WipCriticalReadResult run={latest} ctx={ctx} onOpenSource={openSource} />
    </div>}
  </div>;
}

function CriticalReadSection({ ctx }) {
  if (ctx.researchContext.kind === "manuscript") return (
    <div className="statcheck-section ws-pad">
      <div className="settings-sub">
        A local critical read of the exact primary-manuscript checkpoint: current method receipts plus claims that
        receive a high-confidence contrasting stance from article-fulltext passages in your Library. It embeds draft
        claims transiently, sends nothing to a provider, and surfaces disagreement without deciding who is correct.
      </div>
      <CriticalReadWip manuscript={ctx.researchContext.entity} ctx={ctx} />
      <div className="statcheck-caveat">
        AI-suggested critique candidates are deliberately unavailable for WIP in this version. Sending unpublished
        text would require a separate exact transmission preview and explicit consent design.
      </div>
    </div>
  );
  return (
    <div className="statcheck-section ws-pad">
      <div className="settings-sub">
        A <b>critical read</b>: what to check before you cite — the paper’s method-check flags, claims the rest of
        your corpus contests, and (opt-in) AI-suggested critique candidates you confirm. A reading aid, never a
        verdict or a score.
      </div>
      <CriticalReadPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper} onFindingsChanged={ctx.onFindingsChanged} />
    </div>
  );
}

registerWorkspaceTab({ id: "synthesis" }, {
  id: "critique", label: "Critique", order: 20, hideInReadOnly: true, demoInspectable: true,
  render: (ctx) => <CriticalReadSection ctx={ctx} />,
});
