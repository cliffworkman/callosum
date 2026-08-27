// inc 406: the "Status" menu item — a click-toggle popover of active + recently-finished async processes
// (Synthesize > Ask, a Meta-Analysis checklist refresh, a cited-by refresh, ...), each with a progress bar +
// ETA when the underlying job reports real progress, or an honest indeterminate spinner when it doesn't (most
// of the ~30 job kinds only go pending->running->done today — Phase 1 never fakes a percentage for those).
// Mirrors AddMenu/SavedSearchMenu's click-toggle-popover pattern (10b_libmenus.jsx) rather than inventing a
// new interaction; reuses ProgressBar (10_pdf_layer.jsx) unmodified for each row.

// inc 436: local/provider AI calls that complete inside one HTTP request do not have a backend JobStore. The small
// client registry gives those operations the same popover contract. ProgressBar also registers itself here unless a
// backend/tracked request already owns the row, structurally covering every visible running bar.
const StatusNavContext = React.createContext(null);
const _clientStatusJobs = new Map();
const _clientStatusListeners = new Set();
let _statusFallbackNav = { workspace: "library" };
let _clientStatusSequence = 0;

function StatusScope({ nav, children }) {
  return <StatusNavContext.Provider value={nav}>{children}</StatusNavContext.Provider>;
}

function setStatusFallbackNav(nav) { _statusFallbackNav = nav || { workspace: "library" }; }
function _emitClientStatus() { _clientStatusListeners.forEach(fn => fn()); }
function _clientStatusSnapshot() {
  const cutoff = Date.now() - (60 * 60 * 1000);
  for (const [id, job] of _clientStatusJobs) if (job.status !== "running" && job.updated_at < cutoff) _clientStatusJobs.delete(id);
  return [..._clientStatusJobs.values()].sort((a, b) => (a.status === "running" ? -1 : 1) - (b.status === "running" ? -1 : 1) || b.updated_at - a.updated_at);
}
function _startClientStatus({ id, label, nav, computeKind, progress }) {
  const jobId = id || `client-${++_clientStatusSequence}`;
  const previous = _clientStatusJobs.get(jobId);
  _clientStatusJobs.set(jobId, {
    store: "client_operations", job_id: jobId, label: label || "Working", status: "running",
    detail: null, progress: progress || null, nav: nav || _statusFallbackNav,
    compute_kind: computeKind || "Local operation", started_at: previous?.started_at || Date.now(), updated_at: Date.now(),
  });
  _emitClientStatus();
  return jobId;
}
function _updateClientStatus(jobId, patch) {
  const previous = _clientStatusJobs.get(jobId);
  if (!previous) return;
  const progress = patch.progress ? { ...patch.progress } : previous.progress ? { ...previous.progress } : null;
  if (progress && progress.total > 0 && progress.current > 0 && progress.eta_seconds == null) {
    const elapsed = (Date.now() - previous.started_at) / 1000;
    const remaining = Math.max(0, progress.total - progress.current);
    progress.eta_seconds = remaining ? Math.round(elapsed / progress.current * remaining) : 0;
  }
  _clientStatusJobs.set(jobId, { ...previous, ...patch, progress, updated_at: Date.now() });
  _emitClientStatus();
}
function _finishClientStatus(jobId, ok = true, detail = null) {
  _updateClientStatus(jobId, { status: ok ? "done" : "error", detail, finished_at: Date.now() });
}
function _dismissClientStatus(jobId) { _clientStatusJobs.delete(jobId); _emitClientStatus(); }
function _clearFinishedClientStatus() {
  for (const [id, job] of _clientStatusJobs) if (job.status === "done" || job.status === "error") _clientStatusJobs.delete(id);
  _emitClientStatus();
}
function useClientStatusJobs() {
  const [, refresh] = useState(0);
  useEffect(() => { const fn = () => refresh(n => n + 1); _clientStatusListeners.add(fn); return () => _clientStatusListeners.delete(fn); }, []);
  return _clientStatusSnapshot();
}

const TRACKED_AI_REQUESTS = [
  { method: "POST", re: /^\/axes\/suggest-terms$/, label: "Suggesting axis terms", kind: "Provider AI", nav: { pane: "theory", section: "axes", tab: "axes" } },
  { method: "GET", re: /^\/papers\/\d+\/suggested-tags$/, label: "Suggesting tags", kind: "Local AI", nav: { pane: "theory", section: "axes", tab: "tags" } },
  { method: "POST", re: /^\/citations\/suggest$/, label: "Finding citation evidence", kind: "Local AI", nav: { workspace: "work", tab: "cite" } },
  { method: "POST", re: /^\/papers\/\d+\/critical-read\/candidates\/generate$/, label: "Suggesting grounded critiques", kind: "Provider AI + local verification", nav: { workspace: "synthesis", tab: "critique" } },
  { method: "POST", re: /^\/discovery\/relevance$/, label: "Scoring literature relevance", kind: "Local AI", nav: { workspace: "discover", tab: "search" } },
  { method: "POST", re: /^\/funding-discovery\/llm-triage$/, label: "Triaging funding results", kind: "Provider AI", nav: { workspace: "discover", tab: "funding" } },
  { method: "POST", re: /^\/help\/ask$/, label: "Drafting a Help answer", kind: "Provider AI", nav: { workspace: "help" } },
  { method: "POST", re: /^\/my-publications\/summary\/generate$/, label: "Drafting research summary", kind: "Provider AI", nav: { workspace: "profile" } },
  { method: "POST", re: /^\/papers\/\d+\/registration-comparisons\/\d+\/llm-triage$/, label: "Triaging registration comparison", kind: "Provider AI", nav: { workspace: "synthesis", tab: "meta-preregistration" } },
  { method: "POST", re: /^\/papers\/\d+\/registration-evidence\/retrieve$/, label: "Retrieving publication evidence", kind: "Local AI", nav: { workspace: "synthesis", tab: "meta-preregistration" } },
  { method: "POST", re: /^\/papers\/\d+\/reprocess-pdf$/, label: "Reprocessing and embedding PDF", kind: "Local AI", nav: { pane: "methods", section: "details" } },
  { method: "POST", re: /^\/settings\/test-key$/, label: "Testing AI provider", kind: "Provider AI", nav: { workspace: "settings" } },
  { method: "POST", re: /^\/summaries\/\d+\/reverify$/, label: "Re-verifying synthesis evidence", kind: "Local AI", nav: { workspace: "synthesis", tab: "ask" } },
  { method: "POST", re: /^\/workbench\/rows\/\d+\/propose$/, label: "Drafting extraction candidates", kind: "Provider AI + local retrieval", nav: { workspace: "work", tab: "meta-analyze" } },
  { method: "POST", re: /^\/papers\/\d+\/analytic-flexibility$/, label: "Surfacing analytic decision points", kind: "Provider AI + local anchoring", nav: { pane: "methods", section: "checklists" } },
  { method: "POST", re: /^\/wip\/manuscripts\/\d+\/checks\/analytic-flexibility$/, label: "Surfacing analytic decision points", kind: "Provider AI + local anchoring", nav: { workspace: "library" } },
];

function _startTrackedApiOperation(method, path) {
  const cleanPath = path.split("?")[0];
  const route = TRACKED_AI_REQUESTS.find(item => item.method === method && item.re.test(cleanPath));
  if (!route) return null;
  const paperMatch = cleanPath.match(/^\/papers\/(\d+)\//);
  const manuscriptMatch = cleanPath.match(/^\/wip\/manuscripts\/(\d+)\//);
  const nav = paperMatch
    ? { ...route.nav, paper_id: Number(paperMatch[1]) }
    : manuscriptMatch
      ? { ...route.nav, manuscript_id: Number(manuscriptMatch[1]) }
      : route.nav;
  return _startClientStatus({ label: route.label, nav, computeKind: route.kind });
}
function _finishTrackedApiOperation(jobId, result) {
  if (!jobId) return;
  _finishClientStatus(jobId, !!result?.ok, result?.ok ? null : result?.error || "Operation failed.");
}

function _statusDestinationKey(nav) {
  if (!nav) return "";
  const keys = ["workspace", "tab", "pane", "section", "modal", "view"];
  return keys.map(key => `${key}:${nav[key] || ""}`).join("|");
}

function useProgressStatus({ label, progress, managedBy }) {
  const nav = useContext(StatusNavContext) || _statusFallbackNav;
  const idRef = useRef(null);
  useEffect(() => {
    if (managedBy) return undefined;
    idRef.current = _startClientStatus({ label: label || progress?.label || "Working", nav, progress });
    return () => { if (idRef.current) _finishClientStatus(idRef.current, true); };
  }, [managedBy]);
  useEffect(() => {
    if (idRef.current) _updateClientStatus(idRef.current, { label: label || progress?.label || "Working", progress: progress || null, nav });
  }, [label, progress?.current, progress?.total, progress?.label, progress?.eta_seconds, nav]);
}

// The desktop auto-updater (updater.rs) is NOT a backend JobStore — it lives entirely in the Tauri/Rust
// process, so it can never appear via GET /status/jobs. Instead this shapes the shared `desktopUpdate`
// state (04d_update.jsx's useDesktopUpdate, also read by the toast) into the same row shape a real
// StatusJob has, purely for display — a synthetic entry, never sent to or dismissed via the backend.
// Not in STATUS_NAVIGABLE_STORES: the "ready" state already has its own dedicated toast with the
// restart action; duplicating that trigger here would be a second path that could drift out of sync.
const DESKTOP_UPDATE_STORE = "desktop_update";

function desktopUpdateStatusJob(update) {
  if (!update || update.phase === "idle") return null;
  if (update.phase === "downloading") {
    const total = update.total;
    const progress = total
      ? { current: Math.round((update.downloaded / 1e5)) / 10, total: Math.round(total / 1e5) / 10, label: "MB downloaded", eta_seconds: null }
      : null;
    return {
      store: DESKTOP_UPDATE_STORE, job_id: "desktop-update", label: `Downloading update v${update.version}`,
      status: "running", detail: null, progress, nav: null, compute_kind: "Desktop updater",
    };
  }
  // "ready" — the download finished; the toast already offers Restart now / Open release page.
  return {
    store: DESKTOP_UPDATE_STORE, job_id: "desktop-update", label: `Update ready — v${update.version}`,
    status: "done", detail: null, progress: null, nav: null, compute_kind: "Desktop updater",
  };
}

function _statusElapsed(job, now) {
  if (job.store === "client_operations") {
    const end = job.finished_at || now;
    return Math.max(0, (end - job.started_at) / 1000);
  }
  const base = Math.max(0, Number(job.elapsed_seconds) || 0);
  return job.status === "running" ? base + Math.max(0, (now - (job.observed_at || now)) / 1000) : base;
}

function StatusJobRow({ job, onDismiss, onNavigate, now }) {
  const finished = job.status === "done" || job.status === "error";
  const navigable = !!job.nav;
  const elapsed = _statusElapsed(job, now);
  const stageLabel = job.stage?.label || job.progress?.label || (job.store === "client_operations" ? job.label : "Working");
  // The learned-history comparison must be checked against how long the CURRENT stage has run, not the
  // whole job (job.elapsed_seconds sums every prior stage too) -- see 04bb_status_timing.jsx's
  // _statusStageElapsed. A job with no stage at all falls back to the job-level `elapsed` exactly as
  // before: _statusTimingWording never reads its `elapsed` argument unless a stage estimate exists.
  const stageElapsed = job.stage ? _statusStageElapsed(job, now) : elapsed;
  const estimateText = !finished ? _statusTimingWording(job.stage, stageElapsed, job.compute_kind) : null;
  return (
    <div className={"status-row" + (job.status === "error" ? " status-row-error" : "")}>
      <div className="status-row-head">
        {navigable
          ? <button className="status-row-label status-row-label-link" onClick={() => onNavigate(job)}
              title={`Open ${job.label}`}>{job.label}</button>
          : <span className="status-row-label">{job.label}</span>}
        {finished && !isDemoMode() &&
          <button className="status-row-dismiss" title="Dismiss" aria-label={`Dismiss ${job.label}`}
            onClick={() => onDismiss(job)}>×</button>}
      </div>
      {job.compute_kind && <div className="status-row-kind">{job.compute_kind}</div>}
      {job.status === "error"
        ? <React.Fragment>
            <div className="status-row-error-detail">{job.detail || "Failed."}</div>
            <div className="status-row-eta">Stopped after {_formatTimingDuration(elapsed)}</div>
          </React.Fragment>
        : job.status === "done"
          // A finished row never uses ProgressBar's animated sweep (misleading — it would still look "working").
          ? <div className="status-row-done">
              {job.progress && !job.completed_stages?.length
                ? `${job.progress.label} — ${job.progress.current} / ${job.progress.total} · ${_formatTimingDuration(elapsed)}`
                : `Done in ${_formatTimingDuration(elapsed)}`}
            </div>
          : <React.Fragment>
              <ProgressBar label={stageLabel} progress={job.stage ? null : job.progress} managedBy="status-popover" />
              <div className="status-row-eta">
                {_formatTimingDuration(elapsed)} elapsed{estimateText ? ` · ${estimateText}` : ""}
              </div>
            </React.Fragment>}
    </div>
  );
}

function StatusMenu({ onNavigate, desktopUpdate }) {
  const [open, setOpen] = useState(false);
  const [jobs, setJobs] = useState([]);
  const jobsRef = useRef([]);
  const [pos, setPos] = useState(null);  // {top, right} in viewport px, computed from the toggle button
  const [now, setNow] = useState(Date.now());
  const clientJobs = useClientStatusJobs();
  const hasRunningTimer = [...clientJobs, ...jobs].some(job => job.status === "running");
  // The synthetic desktop-update row's own dismiss state (component-local — there's no backend job to
  // dismiss). Keyed by phase, not just a bool: dismissing "downloading" hides only that phase, so the
  // later "ready" transition (genuinely new information) still surfaces once.
  const [updateDismissedPhase, setUpdateDismissedPhase] = useState(null);
  const toggleRef = useRef(null);
  const popRef = useRef(null);

  const load = useCallback(() => {
    api("/status/jobs").then(r => {
      if (!r.ok) return;
      const observedAt = Date.now();
      const previous = new Map(jobsRef.current.map(job => [`${job.store}:${job.job_id}`, job]));
      const next = r.data.jobs.map(job => {
        const prior = previous.get(`${job.store}:${job.job_id}`);
        const priorElapsed = prior?.status === "running"
          ? Number(prior.elapsed_seconds || 0) + Math.max(0, (observedAt - prior.observed_at) / 1000)
          : 0;
        return {
          ...job,
          observed_at: observedAt,
          elapsed_seconds: job.status === "running"
            ? Math.max(Number(job.elapsed_seconds) || 0, priorElapsed)
            : job.elapsed_seconds,
        };
      });
      next.forEach(job => _recordStatusReceipts(job));
      jobsRef.current = next;
      setJobs(next);
    });
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, open ? 2000 : 12000);
    return () => clearInterval(id);
  }, [open, load]);

  useEffect(() => {
    if (!open || !hasRunningTimer) return undefined;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [open, hasRunningTimer]);

  useEffect(() => {
    if (!open) return;
    // The popover is portaled to document.body (see the CSS comment above), so it sits OUTSIDE toggleRef's DOM
    // subtree — a click inside it (e.g. a row's × or "Clear all finished") must not count as "outside."
    const onDoc = (e) => {
      if (toggleRef.current && toggleRef.current.contains(e.target)) return;
      if (popRef.current && popRef.current.contains(e.target)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const toggle = () => {
    if (!open && toggleRef.current) {
      const r = toggleRef.current.getBoundingClientRect();
      setPos({ top: r.bottom + 5, right: Math.max(8, window.innerWidth - r.right) });
    }
    setOpen(o => !o);
  };

  const dismiss = (job) => {
    if (job.store === DESKTOP_UPDATE_STORE) { setUpdateDismissedPhase(desktopUpdate.phase); return; }
    if (job.store === "client_operations") { _dismissClientStatus(job.job_id); return; }
    setJobs(js => js.filter(j => j.job_id !== job.job_id));  // optimistic — the next poll reconciles either way
    apiPost(`/status/jobs/${job.store}/${job.job_id}/dismiss`, {});
  };
  const clearFinished = () => {
    if (updateJob && updateJob.status === "done") setUpdateDismissedPhase(desktopUpdate.phase);
    setJobs(js => js.filter(j => j.status !== "done" && j.status !== "error"));
    apiPost("/status/jobs/clear-finished", {});
    _clearFinishedClientStatus();
  };
  const navigate = (job) => {
    setOpen(false);
    if (onNavigate) onNavigate(job);
  };

  const updateJob = desktopUpdate && desktopUpdate.phase !== updateDismissedPhase
    ? desktopUpdateStatusJob(desktopUpdate) : null;
  const backendDestinations = new Set(jobs.filter(j => j.status === "running" && j.nav).map(j => _statusDestinationKey(j.nav)));
  const uniqueClientJobs = clientJobs.filter(j => !(j.status === "running" && j.nav && backendDestinations.has(_statusDestinationKey(j.nav))));
  const allJobs = [...uniqueClientJobs, ...jobs];
  const displayJobs = updateJob ? [updateJob, ...allJobs] : allJobs;
  const hasFinished = displayJobs.some(j => j.status === "done" || j.status === "error");

  return (
    <span className="status-menu">
      <button ref={toggleRef} className={"menubar-item status-menu-toggle" + (open ? " active" : "")}
        onClick={toggle} title="Active and recently-finished processes">
        Status
        {displayJobs.length > 0 && <span className="status-badge">{displayJobs.length}</span>}
      </button>
      {open && pos && ReactDOM.createPortal(
        <div className="status-menu-pop" ref={popRef} style={{ position: "fixed", top: pos.top, right: pos.right }}>
          {displayJobs.length === 0
            ? <div className="status-empty">Nothing running.</div>
            : displayJobs.map(j => <StatusJobRow key={j.store + ":" + j.job_id} job={j} now={now}
                onDismiss={dismiss} onNavigate={navigate} />)}
          {hasFinished && !isDemoMode() &&
            <button className="status-clear-finished" onClick={clearFinished}>Clear All Finished</button>}
        </div>,
        document.body
      )}
    </span>
  );
}
