// inc 130: the findings subsystem UI — the FACT-vs-CANDIDATE review surface. FACTs render as neutral persistent
// marks (FactMark); CANDIDATEs as reviewable cards (FindingCard) with Confirmed / Accepted(needs reason) / Noted.
// Badges describe the user's WORK STATE ("N to review"), never paper quality. Anchors reuse the existing
// page-open (ctx.onOpenPaper) — no new highlighter.

function findingText(f) {
  const p = f.payload || {};
  return p.desc || p.label || p.text || p.title || JSON.stringify(p);
}

const RETRACTION_LABEL = { retracted: "Retracted", correction: "Correction", concern: "Expression of Concern" };

function FactMark({ finding }) {
  const p = finding.payload || {};
  // inc 131: retraction FACTs render a status label + a link to the notice (the registry record — verify before
  // citing, never an accusation). The notice URL is only ever a derived https://doi.org/<doi>.
  if (finding.source === "retraction") {
    const label = RETRACTION_LABEL[p.status] || "Retracted";
    const severe = p.status === "retracted";
    return (
      <span className={"fact-mark retraction" + (severe ? " retraction-severe" : "")}
        title={"Source(s): " + (p.sources || []).join(", ") + (p.reason ? " · Reason: " + p.reason : "")}>
        ⚠ {label}
        {p.notice_url && <> · <a className="btn-link" href={p.notice_url} target="_blank" rel="noopener noreferrer">notice</a></>}
      </span>
    );
  }
  return <span className="fact-mark" title={finding.source}>◆ {findingText(finding)}</span>;
}

// inc 131: the library-wide retraction check (mirrors the statcheck batch). Public DOI metadata (Crossref +
// OpenAlex), no AI. On completion it refreshes the header "N retracted" chip via ctx.onRetractionRan.
function RetractionBatch({ ctx }) {
  const [run, setRun] = useState({ status: "idle" });
  const start = async () => {
    setRun({ status: "running" });
    const poll = (jobId) => api(`/methods/retraction/run/${jobId}`).then(r => {
      if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setRun({ status: "done", summary: d.summary }); if (ctx.onRetractionRan) ctx.onRetractionRan(); }
      else if (d.status === "error") setRun({ status: "error", error: d.detail || "Check failed." });
      else setTimeout(() => poll(jobId), 1500);
    });
    const r = await apiPost("/methods/retraction/run", {});
    if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  const s = run.summary;
  return (
    <div className="retraction-batch">
      <p className="eyebrow">Retraction check</p>
      <div className="settings-sub">Check every paper's DOI against Crossref + OpenAlex for retractions, corrections, or expressions of concern — public metadata, no AI. A registry record to verify before citing, never an accusation.</div>
      <div className="settings-actions">
        <button className="btn btn-primary" disabled={run.status === "running"} onClick={start}>
          {run.status === "running" ? "Checking…" : "Check all papers for retractions"}
        </button>
      </div>
      {run.status === "running" && <ProgressBar label="Checking retraction registries…" />}
      {run.status === "error" && <div className="settings-note settings-note-err">Check failed: {run.error}</div>}
      {run.status === "done" && s &&
        <div className="settings-note">
          {s.checked} paper{s.checked === 1 ? "" : "s"} checked · <b>{s.flagged}</b> retracted.
          {s.flagged > 0 && ctx.onShowRetractionFlagged && <> <button className="btn-link" onClick={ctx.onShowRetractionFlagged}>Show retracted papers</button></>}
        </div>}
      <RetractionDatabasePanel ctx={ctx} />
    </div>
  );
}

// inc 132: the Retraction Watch DB mirror — an as-of line + a Refresh button (downloads the Crossref-hosted RW
// database, CC0, into the local mirror so the batch above gains the richest source: reason / date / notice).
function RetractionDatabasePanel({ ctx }) {
  const [db, setDb] = useState(null);  // { count, retrieved_at }
  const [run, setRun] = useState({ status: "idle" });
  const load = () => api("/methods/retraction/database").then(r => { if (r.ok) setDb(r.data); });
  useEffect(() => { load(); }, []);  // call load() (its Promise must NOT become the effect's cleanup return)
  const refresh = async () => {
    setRun({ status: "running" });
    const poll = (jobId) => api(`/methods/retraction/database/refresh/${jobId}`).then(r => {
      if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setRun({ status: "done", count: d.count }); load(); if (ctx.onRetractionRan) ctx.onRetractionRan(); }
      else if (d.status === "error") setRun({ status: "error", error: d.detail || "Download failed." });
      else setTimeout(() => poll(jobId), 2000);
    });
    const r = await apiPost("/methods/retraction/database/refresh", {});
    if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  // inc 134: world-state staleness — a registry snapshot ages, so nudge a refresh past 30 days (the data isn't
  // wrong, just old). Browser Date is fine here (the script-sandbox Date restriction is workflow-only).
  const ageDays = db && db.retrieved_at ? Math.floor((Date.now() - new Date(db.retrieved_at).getTime()) / 86400000) : null;
  const stale = ageDays != null && ageDays > 30;
  return (
    <div className="retraction-db">
      <span className="retraction-db-line">
        {db && db.count > 0
          ? `Retraction Watch database: ${db.count.toLocaleString()} records${db.retrieved_at ? " · as of " + db.retrieved_at.slice(0, 10) : ""}`
          : "Retraction Watch database: not downloaded — refresh to enable the richest source"}
        {stale && <span className="retraction-db-stale"> · {ageDays} days old — refresh recommended</span>}
      </span>
      <button className="btn-link" disabled={run.status === "running"} onClick={refresh}>
        {run.status === "running" ? "Downloading…" : "Refresh database"}
      </button>
      {run.status === "error" && <div className="settings-note settings-note-err">{run.error}</div>}
    </div>
  );
}

// inc 131: the per-paper retraction CHECK status (silence != clean). Shows "checked — none found" / "unchecked —
// no DOI" / "not yet checked"; a retracted paper's FactMark already carries the verdict, so this stays quiet then.
function RetractionStatusLine({ paperId }) {
  const [st, setSt] = useState(null);
  useEffect(() => {
    setSt(null);
    if (paperId == null) return;
    let live = true;
    api(`/papers/${paperId}/retraction`).then(r => { if (live && r.ok) setSt(r.data); });
    return () => { live = false; };
  }, [paperId]);
  if (!st || st.status === "retracted" || st.status === "correction" || st.status === "concern") return null;
  if (!st.checked) return <div className="retraction-status">Retraction: not yet checked — run the retraction check above.</div>;
  if (st.status === "unchecked") return <div className="retraction-status">Retraction: unchecked — no DOI to look up.</div>;
  return <div className="retraction-status">Retraction: checked — none found{st.sources && st.sources.length ? ` (${st.sources.join(", ")})` : ""}.</div>;
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
  const facts = state.status === "ready" ? state.data.facts : [];
  const candidates = state.status === "ready" ? state.data.candidates : [];
  return (
    <div className="findings-section">
      <RetractionBatch ctx={ctx} />
      <p className="eyebrow">This paper</p>
      {pid == null
        ? <div className="axis-hint">Select a paper to review its findings.</div>
        : <>
            <RetractionStatusLine paperId={pid} />
            {state.status !== "ready"
              ? <div className="tag-suggest-empty">{state.status === "error" ? state.error : "Loading…"}</div>
              : facts.length || candidates.length
                ? <>
                    {facts.length > 0 && <div className="findings-facts">{facts.map(f => <FactMark key={f.id} finding={f} />)}</div>}
                    {candidates.map(c => <FindingCard key={c.id} finding={c} onReviewed={onReviewed} onOpenPaper={ctx.onOpenPaper} />)}
                  </>
                : <div className="tag-suggest-empty">No findings for this paper yet.</div>}
          </>}
    </div>
  );
}

registerPaneSection({ id: "findings", label: "Review", paneId: "methods", order: 40, render: (ctx) => <FindingsSection ctx={ctx} /> });
