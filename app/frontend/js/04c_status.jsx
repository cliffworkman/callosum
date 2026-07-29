// inc 406: the "Status" menu item — a click-toggle popover of active + recently-finished async processes
// (Synthesize > Ask, a Meta-Analysis checklist refresh, a cited-by refresh, ...), each with a progress bar +
// ETA when the underlying job reports real progress, or an honest indeterminate spinner when it doesn't (most
// of the ~30 job kinds only go pending->running->done today — Phase 1 never fakes a percentage for those).
// Mirrors AddMenu/SavedSearchMenu's click-toggle-popover pattern (10b_libmenus.jsx) rather than inventing a
// new interaction; reuses ProgressBar (10_pdf_layer.jsx) unmodified for each row.

// inc 415: which job stores' rows get a clickable destination at all — App owns what "navigate" actually
// means per store (onStatusNavigate, 40_app.jsx); this is only the allowlist deciding whether a row gets the
// affordance, so a job kind nobody's wired a destination for yet renders an honest, non-clickable label
// instead of a dead click.
const STATUS_NAVIGABLE_STORES = new Set(["meta_jobs", "citation_count_jobs", "summary_jobs"]);

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
      status: "running", detail: null, progress, nav: null,
    };
  }
  // "ready" — the download finished; the toast already offers Restart now / Open release page.
  return {
    store: DESKTOP_UPDATE_STORE, job_id: "desktop-update", label: `Update ready — v${update.version}`,
    status: "done", detail: null, progress: null, nav: null,
  };
}

function StatusJobRow({ job, onDismiss, onNavigate }) {
  const finished = job.status === "done" || job.status === "error";
  const navigable = STATUS_NAVIGABLE_STORES.has(job.store);
  return (
    <div className={"status-row" + (job.status === "error" ? " status-row-error" : "")}>
      <div className="status-row-head">
        {navigable
          ? <button className="status-row-label status-row-label-link" onClick={() => onNavigate(job)}
              title={`Open ${job.label}`}>{job.label}</button>
          : <span className="status-row-label">{job.label}</span>}
        {finished &&
          <button className="status-row-dismiss" title="Dismiss" aria-label={`Dismiss ${job.label}`}
            onClick={() => onDismiss(job)}>×</button>}
      </div>
      {job.status === "error"
        ? <div className="status-row-error-detail">{job.detail || "Failed."}</div>
        : job.status === "done"
          // A finished row never uses ProgressBar's animated sweep (misleading — it would still look "working").
          ? <div className="status-row-done">
              {job.progress ? `${job.progress.label} — ${job.progress.current} / ${job.progress.total}` : "Done"}
            </div>
          : <ProgressBar label="Working…" progress={job.progress} />}
    </div>
  );
}

function StatusMenu({ onNavigate, desktopUpdate }) {
  const [open, setOpen] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [pos, setPos] = useState(null);  // {top, right} in viewport px, computed from the toggle button
  // The synthetic desktop-update row's own dismiss state (component-local — there's no backend job to
  // dismiss). Keyed by phase, not just a bool: dismissing "downloading" hides only that phase, so the
  // later "ready" transition (genuinely new information) still surfaces once.
  const [updateDismissedPhase, setUpdateDismissedPhase] = useState(null);
  const toggleRef = useRef(null);
  const popRef = useRef(null);

  const load = useCallback(() => {
    api("/status/jobs").then(r => { if (r.ok) setJobs(r.data.jobs); });
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, open ? 2000 : 12000);
    return () => clearInterval(id);
  }, [open, load]);

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
    setJobs(js => js.filter(j => j.job_id !== job.job_id));  // optimistic — the next poll reconciles either way
    apiPost(`/status/jobs/${job.store}/${job.job_id}/dismiss`, {});
  };
  const clearFinished = () => {
    if (updateJob && updateJob.status === "done") setUpdateDismissedPhase(desktopUpdate.phase);
    setJobs(js => js.filter(j => j.status !== "done" && j.status !== "error"));
    apiPost("/status/jobs/clear-finished", {});
  };
  const navigate = (job) => {
    setOpen(false);
    if (onNavigate) onNavigate(job);
  };

  const updateJob = desktopUpdate && desktopUpdate.phase !== updateDismissedPhase
    ? desktopUpdateStatusJob(desktopUpdate) : null;
  const displayJobs = updateJob ? [updateJob, ...jobs] : jobs;
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
            : displayJobs.map(j => <StatusJobRow key={j.store + ":" + j.job_id} job={j} onDismiss={dismiss} onNavigate={navigate} />)}
          {hasFinished &&
            <button className="status-clear-finished" onClick={clearFinished}>Clear all finished</button>}
        </div>,
        document.body
      )}
    </span>
  );
}
