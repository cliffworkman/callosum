// inc 406: the "Status" menu item — a click-toggle popover of active + recently-finished async processes
// (Synthesize > Ask, a Meta-Analysis checklist refresh, a cited-by refresh, ...), each with a progress bar +
// ETA when the underlying job reports real progress, or an honest indeterminate spinner when it doesn't (most
// of the ~30 job kinds only go pending->running->done today — Phase 1 never fakes a percentage for those).
// Mirrors AddMenu/SavedSearchMenu's click-toggle-popover pattern (10b_libmenus.jsx) rather than inventing a
// new interaction; reuses ProgressBar (10_pdf_layer.jsx) unmodified for each row.

function StatusJobRow({ job, onDismiss }) {
  const finished = job.status === "done" || job.status === "error";
  return (
    <div className={"status-row" + (job.status === "error" ? " status-row-error" : "")}>
      <div className="status-row-head">
        <span className="status-row-label">{job.label}</span>
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

function StatusMenu() {
  const [open, setOpen] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [pos, setPos] = useState(null);  // {top, right} in viewport px, computed from the toggle button
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
    setJobs(js => js.filter(j => j.job_id !== job.job_id));  // optimistic — the next poll reconciles either way
    apiPost(`/status/jobs/${job.store}/${job.job_id}/dismiss`, {});
  };
  const clearFinished = () => {
    setJobs(js => js.filter(j => j.status !== "done" && j.status !== "error"));
    apiPost("/status/jobs/clear-finished", {});
  };

  const hasFinished = jobs.some(j => j.status === "done" || j.status === "error");

  return (
    <span className="status-menu">
      <button ref={toggleRef} className={"menubar-item status-menu-toggle" + (open ? " active" : "")}
        onClick={toggle} title="Active and recently-finished processes">
        Status
        {jobs.length > 0 && <span className="status-badge">{jobs.length}</span>}
      </button>
      {open && pos && ReactDOM.createPortal(
        <div className="status-menu-pop" ref={popRef} style={{ position: "fixed", top: pos.top, right: pos.right }}>
          {jobs.length === 0
            ? <div className="status-empty">Nothing running.</div>
            : jobs.map(j => <StatusJobRow key={j.store + ":" + j.job_id} job={j} onDismiss={dismiss} />)}
          {hasFinished &&
            <button className="status-clear-finished" onClick={clearFinished}>Clear all finished</button>}
        </div>,
        document.body
      )}
    </span>
  );
}
