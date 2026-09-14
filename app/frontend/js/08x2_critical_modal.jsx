// Reaccessible single-paper critique modal (inc 601). The reader-launched critique (inc 598) used to be trapped
// in the reference-finder modal; now the result is PERSISTED per paper (GET .../critical-read/snapshot) and this
// modal reopens it on demand — from the reference finder ("View critique"), from the Status popover (the
// critical_review_jobs entry now navigates here with the job's own paper_id, not the globally-selected paper),
// or anywhere with a paper id. Reuses the SAME renderer as the Synthesize -> Critique tab (ScrutinyBackboneView,
// hoisted from 08x_methods_critical.jsx). Computes nothing on open; Run/Refresh uses the canonical
// POST /papers/{id}/critical-read. Honors the inc-598 fulltext gate: Run/Refresh is offered ONLY when the paper
// is authoritatively fulltext-ready (chunk_count > 0) — never a path that critiques metadata/abstract.

// Self-hosted controller (the FeedbackLauncher pattern): listens for `callosum:open-critical-read`
// (detail.paperId) so the reader's "View critique" and the Status popover both reopen the modal without 40_app
// prop-threading. Rendered once at the app root.
function CriticalReadModalHost({ onOpenPaper }) {
  const [paperId, setPaperId] = useState(null);
  useEffect(() => {
    const open = (e) => {
      const pid = e && e.detail && Number(e.detail.paperId);
      if (Number.isInteger(pid) && pid > 0) setPaperId(pid);
    };
    window.addEventListener("callosum:open-critical-read", open);
    return () => window.removeEventListener("callosum:open-critical-read", open);
  }, []);
  if (paperId == null) return null;
  return <CriticalReadModal paperId={paperId} onClose={() => setPaperId(null)} onOpenPaper={onOpenPaper} />;
}

function CriticalReadModal({ paperId, onClose, onOpenPaper }) {
  const [meta, setMeta] = useState(null);      // { title, hasText } | null (hasText = chunk_count > 0)
  const [snap, setSnap] = useState(null);      // the GET .../snapshot payload | null while loading
  const [phase, setPhase] = useState("loading");  // loading | ready | running | error
  const [live, setLive] = useState(null);      // { backbone } once a Run/Refresh completes (authoritative over snap)
  const [runErr, setRunErr] = useState("");
  const pollRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => () => { mountedRef.current = false; if (pollRef.current) pollRef.current(); }, []);

  const load = useCallback(() => {
    if (paperId == null) return;
    setPhase("loading"); setLive(null); setRunErr("");
    Promise.all([api(`/papers/${paperId}`), api(`/papers/${paperId}/critical-read/snapshot`)]).then(([p, s]) => {
      if (!mountedRef.current) return;
      setMeta(p.ok ? { title: p.data.title, hasText: (p.data.chunk_count || 0) > 0 } : { title: null, hasText: false });
      const snapshot = s.ok ? s.data : { backbone: null };
      setSnap(snapshot);
      // c5: a Refresh already running (e.g. kicked off from the reader) stays visibly running rather than
      // presenting the older snapshot as the active result.
      if (snapshot.running_job_id) { setPhase("running"); poll(snapshot.running_job_id); }
      else setPhase("ready");
    });
  }, [paperId]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load]);

  function poll(jobId) {
    if (pollRef.current) pollRef.current();
    pollRef.current = observeJobUntilTerminal(`/critical-read/${jobId}`, {
      onProgress: () => { if (mountedRef.current) setPhase("running"); },
      onDone: data => { pollRef.current = null; if (mountedRef.current) { setLive({ backbone: data.backbone }); setPhase("ready"); } },
      onError: err => { pollRef.current = null; if (mountedRef.current) { setRunErr(err || "Critique failed."); setPhase("error"); } },
    });
  }

  const run = useCallback(() => {
    setPhase("running"); setRunErr("");
    apiPost(`/papers/${paperId}/critical-read`, {}).then(r => {
      if (!r.ok || !r.data || !r.data.job_id) { if (mountedRef.current) { setRunErr(r.error || "Couldn't start the critique."); setPhase("error"); } return; }
      poll(r.data.job_id);  // the job's own result is authoritative — we do NOT re-fetch the snapshot after (c2)
    });
  }, [paperId]);

  const open = (pid, page) => { if (onOpenPaper && page != null) onOpenPaper({ id: pid }, { page, precision: "region" }); };

  // The backbone to show: a completed Run/Refresh wins; else the persisted snapshot.
  const backbone = (live && live.backbone) || (snap && snap.backbone) || null;
  const canRun = !!(meta && meta.hasText);          // c1: fulltext gate — never offer Run/Refresh otherwise
  const computedAt = snap && !live ? snap.computed_at : null;

  return (
    <div className="axis-modal-overlay" onMouseDown={onClose}>
      <div className="axis-modal cr-modal" role="dialog" aria-label="Paper critique" onMouseDown={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Critique{meta && meta.title ? `: ${meta.title}` : ""}</span>
          <button className="axis-link" aria-label="Close" onClick={onClose}>×</button>
        </div>
        <div className="statcheck-caveat">
          What a skeptical reader should check before citing — a <b>signal, not a verdict</b>. Local method-check
          facts + corpus-contested claims; never a score, and the critique is of the work, never the authors.
        </div>

        {phase === "loading" && <div className="axis-hint">Loading…</div>}
        {phase === "running" && <ProgressBar label="Assembling the scrutiny surface…" managedBy="backend-job" />}
        {phase === "error" && <div className="axis-err">Couldn’t assemble: {runErr}</div>}

        {phase === "ready" && backbone &&
          <>
            {computedAt &&
              <div className="cr-modal-meta">
                Critiqued {new Date(computedAt).toLocaleString()}.
                {snap && snap.stale && <span className="cr-modal-stale"> The paper’s full text has changed since this was computed.</span>}
                {canRun && <button className="btn btn-link" onClick={run}>Refresh</button>}
              </div>}
            <ScrutinyBackboneView backbone={backbone} onOpen={open} triageOnly={false} />
          </>}

        {phase === "ready" && !backbone && snap && snap.refresh_required &&
          <div className="cr-modal-empty">
            This saved critique was produced by an older version of Callosum and can’t be shown safely.
            {canRun
              ? <> <button className="btn btn-primary" onClick={run}>Refresh critique</button></>
              : <> Open the full text to re-run it.</>}
          </div>}

        {phase === "ready" && !backbone && (!snap || !snap.refresh_required) &&
          (canRun
            ? <div className="cr-modal-empty">
                No critique yet for this paper.
                <button className="btn btn-primary" onClick={run}>Critique this paper</button>
              </div>
            : <div className="cr-modal-empty">
                Critique needs the full paper — no usable full text is available yet. Acquire or attach a PDF,
                then critique it from here or in <b>Synthesize → Critique</b>.
              </div>)}
      </div>
    </div>
  );
}
