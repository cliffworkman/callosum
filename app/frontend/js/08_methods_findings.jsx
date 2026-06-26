// inc 130: the findings subsystem UI — the FACT-vs-CANDIDATE review surface. FACTs render as neutral persistent
// marks (FactMark); CANDIDATEs as reviewable cards (FindingCard) with Confirmed / Accepted(needs reason) / Noted.
// Badges describe the user's WORK STATE ("N to review"), never paper quality. Anchors reuse the existing
// page-open (ctx.onOpenPaper) — no new highlighter.

function findingText(f) {
  const p = f.payload || {};
  return p.desc || p.label || p.text || p.title || JSON.stringify(p);
}

function FactMark({ finding }) {
  return <span className="fact-mark" title={finding.source}>◆ {findingText(finding)}</span>;
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
        <button className="btn-link finding-anchor" onClick={() => onOpenPaper({ id: finding.paper_id, title: "" }, { page, precision: "region" })}>show in paper · p.{page}</button>}
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

function FindingsSection({ ctx }) {
  const [state, setState] = useState({ status: "idle" });
  const pid = ctx.selectedPaper;
  const load = () => {
    if (pid == null) { setState({ status: "idle" }); return; }
    setState({ status: "loading" });
    api(`/papers/${pid}/findings`).then(r => setState(r.ok ? { status: "ready", data: r.data } : { status: "error", error: r.error }));
  };
  useEffect(load, [pid]);
  const onReviewed = () => { load(); if (ctx.onFindingsChanged) ctx.onFindingsChanged(); };
  if (pid == null) return <div className="axis-hint">Select a paper to review its findings.</div>;
  if (state.status !== "ready") return <div className="tag-suggest-empty">{state.status === "error" ? state.error : "Loading…"}</div>;
  const { facts, candidates } = state.data;
  if (!facts.length && !candidates.length) return <div className="tag-suggest-empty">No findings for this paper yet.</div>;
  return (
    <div className="findings-section">
      {facts.length > 0 && <div className="findings-facts">{facts.map(f => <FactMark key={f.id} finding={f} />)}</div>}
      {candidates.map(c => <FindingCard key={c.id} finding={c} onReviewed={onReviewed} onOpenPaper={ctx.onOpenPaper} />)}
    </div>
  );
}

registerPaneSection({ id: "findings", label: "Review", paneId: "methods", order: 40, render: (ctx) => <FindingsSection ctx={ctx} /> });
