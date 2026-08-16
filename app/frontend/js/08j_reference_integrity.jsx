// Meta Reference List: narrow negative reference signals, scoped to citation instances. It reuses the existing
// Semantic Scholar reference edge, Crossref/OpenAlex metadata resolution, retraction checkers, and local citation
// context classifier. Signals only; no positive reference-quality state and no composite score.

const REF_SIGNAL_LABELS = {
  bibliographic_verification: { label: "Could not verify", tone: "verify", icon: "?" },
  retraction: { label: "Known retraction signal", tone: "retraction", icon: "!" },
  own_library_propagation: { label: "Previously flagged in your library", tone: "propagation", icon: "↗" },
};

function RefSignalBadge({ signal }) {
  const cfg = REF_SIGNAL_LABELS[signal.detector_kind] || { label: signal.detector_status, tone: "verify", icon: "?" };
  return (
    <span className={"ref-signal-badge " + cfg.tone} title={signal.source + " · " + signal.snapshot_marker}>
      <span aria-hidden="true">{cfg.icon}</span> {cfg.label}
    </span>
  );
}

function RefEvidence({ signal, onOpenPaper }) {
  const e = signal.evidence || {};
  if (signal.detector_kind === "retraction") {
    return (
      <div className="ref-evidence">
        <b>Status evidence:</b> {e.nature || e.status || "retraction record"}
        {e.reason ? " · " + e.reason : ""}
        {e.sources && e.sources.length ? " · source: " + e.sources.join(", ") : ""}
        {e.notice_url && <> · <a href={e.notice_url} target="_blank" rel="noopener noreferrer">notice</a></>}
      </div>
    );
  }
  if (signal.detector_kind === "own_library_propagation") {
    const src = e.source_instances || [];
    return (
      <div className="ref-evidence">
        <b>Local evidence:</b> {e.reason || "The referenced entity has an active signal elsewhere."}
        {src.length > 0 && <div className="ref-mini-list">
          {src.slice(0, 3).map(s => (
            <button key={s.citation_instance_id} type="button" className="btn-link ref-source-link"
              title="Open the local paper with the earlier active reference signal"
              onClick={() => onOpenPaper && onOpenPaper({ id: s.citing_paper_id, title: s.title || ("Paper " + s.citing_paper_id) })}>
              {s.title || ("Paper " + s.citing_paper_id)}: {(s.detector_kinds || []).join(", ")}
            </button>
          ))}
        </div>}
      </div>
    );
  }
  const parsed = e.parsed || {};
  return (
    <div className="ref-evidence">
      <b>Reason:</b> {e.reason || "Could not verify with available sources."}
      {e.sources_queried && e.sources_queried.length ? <div>Sources queried: {e.sources_queried.join(", ")}</div> : null}
      {parsed.doi ? <div>DOI parsed: {parsed.doi}</div> : null}
      {e.candidate_matches && e.candidate_matches.length > 0 &&
        <div>Candidate considered: {e.candidate_matches.map(c => [c.source, c.title, c.match_basis].filter(Boolean).join(" · ")).join("; ")}</div>}
    </div>
  );
}

function RefReviewControls({ item, onReview }) {
  const dismissed = item.review_state === "dismissed";
  const confirmed = item.review_state === "confirmed_problem";
  return (
    <div className="ref-review-controls" role="group" aria-label="Reference signal review state">
      <button type="button" className={"ref-review-btn" + (dismissed ? " on dismissed" : "")}
        aria-pressed={dismissed} aria-label="Reviewed and dismissed" title="Reviewed and dismissed"
        disabled={isDemoMode()}
        onClick={() => onReview(item.id, "dismissed")}>✓</button>
      <button type="button" className={"ref-review-btn" + (confirmed ? " on confirmed" : "")}
        aria-pressed={confirmed} aria-label="Reviewed and confirmed as a concern" title="Reviewed and confirmed as a concern"
        disabled={isDemoMode()}
        onClick={() => onReview(item.id, "confirmed_problem")}>×</button>
    </div>
  );
}

function RefProviderStatusList({ statuses }) {
  if (!statuses || !statuses.length) return null;
  return (
    <details className="ref-provider-status">
      <summary>Source coverage for last run</summary>
      {statuses.map((s, i) => (
        <div className={"ref-provider-row " + (s.status || "unknown")} key={`${s.provider}:${i}`}>
          <b>{s.provider}</b> · {s.status || "unknown"}
          {s.result_count != null ? ` · ${s.result_count}` : ""}
          {s.detail ? <div>{s.detail}</div> : null}
        </div>
      ))}
    </details>
  );
}

function RefItem({ item, onReview, onOpenPaper }) {
  const title = item.title || "Untitled reference";
  const meta = [
    item.authors && item.authors.length ? item.authors.slice(0, 3).join(", ") : null,
    item.year,
    item.doi ? "doi:" + item.doi : null,
  ].filter(Boolean).join(" · ");
  return (
    <div className={"ref-card " + item.review_state}>
      <div className="ref-card-head">
        <div className="ref-title">{title}</div>
        <RefReviewControls item={item} onReview={onReview} />
      </div>
      {meta && <div className="ref-meta">{meta}</div>}
      <div className="ref-raw">{item.raw_text}</div>
      <div className="ref-signals">
        {item.signals.map(s => <RefSignalBadge key={s.id} signal={s} />)}
      </div>
      {item.signals.map(s => <RefEvidence key={"e" + s.id} signal={s} onOpenPaper={onOpenPaper} />)}
      {item.context && item.context.hint &&
        <div className="ref-context">
          {item.context.hint}
          {item.context.confidence != null ? ` · confidence ${Number(item.context.confidence).toFixed(2)}` : ""}
          {item.context.sentence ? <div className="ref-context-sentence">“{item.context.sentence}”</div> : null}
        </div>}
      <div className="ref-state">
        {item.reopened ? "Reopened after detector evidence changed"
          : item.review_state === "dismissed" ? "Reviewed and dismissed"
          : item.review_state === "confirmed_problem" ? "Reviewed and confirmed as a concern"
          : "Requires review"}
      </div>
    </div>
  );
}

function MetaReferenceList({ ctx }) {
  const pid = ctx.selectedPaper;
  const [state, setState] = useState({ status: "idle", data: null });
  const hasPartialCoverage = !!(state.data && (state.data.provider_statuses || []).some(s => ["failed", "partial"].includes(s.status)));
  const load = () => {
    if (pid == null) { setState({ status: "idle", data: null }); return; }
    setState(s => ({ ...s, status: s.data ? "ready" : "loading" }));
    api(`/papers/${pid}/reference-integrity`).then(r => setState(r.ok ? { status: "ready", data: r.data } : { status: "error", error: r.error, data: null }));
  };
  useEffect(load, [pid]);
  const run = async () => {
    if (pid == null) return;
    setState({ status: "running", data: state.data, progress: null });
    const start = await apiPost(`/papers/${pid}/reference-integrity/run`, {});
    if (!start.ok) { setState({ status: "error", error: start.error, data: state.data }); return; }
    const poll = (jid) => api(`/reference-integrity/run/${jid}`).then(r => {
      if (!r.ok) { setState({ status: "error", error: r.error, data: state.data }); return; }
      if (r.data.status === "done") {
        setState({ status: "ready", data: r.data.report });
        if (ctx.onReferenceWarningsChanged) ctx.onReferenceWarningsChanged();
      } else if (r.data.status === "error") setState({ status: "error", error: r.data.detail || "Check failed.", data: state.data });
      else {
        setState(s => ({ ...s, status: "running", progress: r.data.progress || null }));
        setTimeout(() => poll(jid), 1400);
      }
    });
    poll(start.data.job_id);
  };
  const review = async (instanceId, reviewState) => {
    const r = await apiPost(`/reference-integrity/instances/${instanceId}/review`, { state: reviewState });
    if (r.ok) {
      setState({ status: "ready", data: r.data });
      if (ctx.onReferenceWarningsChanged) ctx.onReferenceWarningsChanged();
    }
  };
  if (pid == null) return <div className="tag-suggest-empty">Select a paper to inspect reference signals.</div>;
  const data = state.data;
  return (
    <div className="ref-panel">
      <div className="meta-ref-action-row">
        <div className="meta-ref-action-copy ref-intro">
          Surfaces only three negative signals for review: could not verify, known retraction signal, and prior local
          flag propagation. Search misses are not conclusions, and clearing signals is not positive verification.
        </div>
        <div className="meta-ref-action-slot">
          {state.status !== "running" &&
            <button className="btn btn-primary" onClick={run} disabled={isDemoMode()}
              title={isDemoMode() ? "Reference refresh is unavailable in the read-only online demo" : "Check references"}>
              {state.status === "error" || hasPartialCoverage ? "Retry reference check" : "Check references"}
            </button>}
        </div>
      </div>
      {state.status === "running" && <ProgressBar progress={state.progress} label="Checking reference list…" managedBy="backend-job" />}
      {state.status === "error" && <div className="axis-err">Reference check failed: {state.error}</div>}
      {state.status === "loading" && <div className="tag-suggest-empty">Loading reference signals…</div>}
      {data && <div className="ref-summary">
        Checked {data.checked_count || 0} linked reference{(data.checked_count || 0) === 1 ? "" : "s"} ·{" "}
        {data.active_count} active reference signal{data.active_count === 1 ? "" : "s"}.
        {data.last_checked_at ? <> Last checked {data.last_checked_at}.</> : null}
        Dismissed items do not count; confirmed concerns and unreviewed signals do.
      </div>}
      {data && <RefProviderStatusList statuses={data.provider_statuses} />}
      {data && data.items.length === 0 && (data.checked_count || 0) === 0 &&
        <div className="tag-suggest-empty">No linked reference records were available from Semantic Scholar or OpenAlex for this DOI.</div>}
      {data && data.items.length === 0 && (data.checked_count || 0) > 0 &&
        <div className="tag-suggest-empty">No active reference signals from these checks. This is not positive verification of the references.</div>}
      {data && data.items.map(item => <RefItem key={item.id} item={item} onReview={review} onOpenPaper={ctx.onOpenPaper} />)}
    </div>
  );
}

// backlog #48 (inc 447): the WIP-manuscript variant. A WIP reference is a direct link to an already-known,
// DOI'd Library paper (not a raw discovered citation string), so its item card is its own thin component —
// reusing RefSignalBadge/RefEvidence/RefReviewControls (the truly reusable atoms) rather than forcing the
// backend response to fake RefItem's title/authors/raw_text shape.
function WipRefItem({ item, onReview, onOpenPaper }) {
  const title = item.paper_title || "Untitled reference";
  const meta = [item.paper_year, item.doi ? "doi:" + item.doi : null].filter(Boolean).join(" · ");
  return (
    <div className={"ref-card " + item.review_state}>
      <div className="ref-card-head">
        <button type="button" className="btn-link ref-title" onClick={() => onOpenPaper && onOpenPaper({ id: item.paper_id, title })}>
          {title}
        </button>
        <RefReviewControls item={item} onReview={onReview} />
      </div>
      {meta && <div className="ref-meta">{meta}</div>}
      <div className="ref-signals">
        {item.signals.map(s => <RefSignalBadge key={s.id} signal={s} />)}
      </div>
      {item.signals.map(s => <RefEvidence key={"e" + s.id} signal={s} onOpenPaper={onOpenPaper} />)}
      <div className="ref-state">
        {item.review_state === "dismissed" ? "Reviewed and dismissed"
          : item.review_state === "confirmed_problem" ? "Reviewed and confirmed as a concern"
          : "Requires review"}
      </div>
    </div>
  );
}

function WipMetaReferenceList({ manuscriptId, onOpenPaper, onReload, refreshKey }) {
  const [state, setState] = useState({ status: "idle", data: null });
  const hasPartialCoverage = !!(state.data && (state.data.provider_statuses || []).some(s => ["failed", "partial"].includes(s.status)));
  const load = () => {
    if (manuscriptId == null) { setState({ status: "idle", data: null }); return; }
    setState(s => ({ ...s, status: s.data ? "ready" : "loading" }));
    api(`/wip/manuscripts/${manuscriptId}/reference-integrity`).then(r => setState(r.ok ? { status: "ready", data: r.data } : { status: "error", error: r.error, data: null }));
  };
  useEffect(load, [manuscriptId, refreshKey]);
  const run = async () => {
    if (manuscriptId == null) return;
    setState({ status: "running", data: state.data, progress: null });
    const start = await apiPost(`/wip/manuscripts/${manuscriptId}/reference-integrity/run`, {});
    if (!start.ok) { setState({ status: "error", error: start.error, data: state.data }); return; }
    const poll = (jid) => api(`/wip/reference-integrity/run/${jid}`).then(r => {
      if (!r.ok) { setState({ status: "error", error: r.error, data: state.data }); return; }
      if (r.data.status === "done") {
        setState({ status: "ready", data: r.data.report });
        if (onReload) onReload();
      } else if (r.data.status === "error") setState({ status: "error", error: r.data.detail || "Check failed.", data: state.data });
      else {
        setState(s => ({ ...s, status: "running", progress: r.data.progress || null }));
        setTimeout(() => poll(jid), 1400);
      }
    });
    poll(start.data.job_id);
  };
  const review = async (referenceId, reviewState) => {
    const r = await apiPost(`/wip/reference-integrity/${referenceId}/review`, { state: reviewState });
    if (r.ok) {
      setState({ status: "ready", data: r.data });
      if (onReload) onReload();
    }
  };
  if (manuscriptId == null) return null;
  const data = state.data;
  return (
    <div className="ref-panel">
      <div className="meta-ref-action-row">
        <div className="meta-ref-action-copy ref-intro">
          Checks this manuscript's "cited" Library references for the same three negative signals as a published
          paper: could not verify, known retraction signal, and prior local flag propagation. Search misses are not
          conclusions, and clearing signals is not positive verification.
        </div>
        <div className="meta-ref-action-slot">
          {state.status !== "running" &&
            <button className="btn btn-primary" onClick={run} disabled={isDemoMode()}
              title={isDemoMode() ? "Refreshing manuscript references requires the local app and metadata providers." : undefined}>
              {state.status === "error" || hasPartialCoverage ? "Retry reference check" : "Check references"}
            </button>}
        </div>
      </div>
      {state.status === "running" && <ProgressBar progress={state.progress} label="Checking reference list…" managedBy="backend-job" />}
      {state.status === "error" && <div className="axis-err">Reference check failed: {state.error}</div>}
      {state.status === "loading" && <div className="tag-suggest-empty">Loading reference signals…</div>}
      {data && <div className="ref-summary">
        Checked {data.checked_count || 0} cited reference{(data.checked_count || 0) === 1 ? "" : "s"} ·{" "}
        {data.active_count} active reference signal{data.active_count === 1 ? "" : "s"}.
        {data.last_checked_at ? <> Last checked {data.last_checked_at}.</> : null}
        Dismissed items do not count; confirmed concerns and unreviewed signals do.
      </div>}
      {data && <RefProviderStatusList statuses={data.provider_statuses} />}
      {data && (data.checked_count || 0) === 0 &&
        <div className="tag-suggest-empty">No Library references are marked "cited" for this manuscript yet — link one from the References tab first.</div>}
      {data && data.items.length === 0 && (data.checked_count || 0) > 0 &&
        <div className="tag-suggest-empty">No active reference signals from these checks. This is not positive verification of the references.</div>}
      {data && data.items.map(item => <WipRefItem key={item.id} item={item} onReview={review} onOpenPaper={onOpenPaper} />)}
    </div>
  );
}

// Rendered directly by MetaReferencePane (37b_meta_reference.jsx) as Work → Meta-Reference's first subsection.
