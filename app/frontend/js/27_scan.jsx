// Watched-folders modal (inc 87 scan → inc 98 watching). Point Callosum at folders of PDFs; new files are
// ingested (extract + chunk + embed, Crossref-enriched), unchanged skipped, removed flagged. Scanning a folder
// **watches** it — watched folders are re-scanned automatically on launch (Settings toggle) + via "Re-scan all",
// so new PDFs appear without re-adding. Clones the poll lifecycle of the other async-job modals.

const SCAN_JOB_KEY = "callosum.scanJob";  // { url, jobId } for whichever scan is currently in flight, if any

function ScanModal({ onClose, onScanned, onShowUnsorted }) {
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <ScanModalBody onClose={onClose} onScanned={onScanned} onShowUnsorted={onShowUnsorted} />
      </div>
    </div>
  );
}

// inc 416: the bare body, split out so the onboarding wizard can embed it without nesting a second
// .axis-modal-overlay inside its own — ScanModal above is now a thin wrapper adding that chrome. Every
// hook/handler below is unchanged from before the split.
function ScanModalBody({ onClose, onScanned, onShowUnsorted }) {
  const [folder, setFolder] = useState(() => {
    try { return localStorage.getItem("callosum.scanFolder") || ""; } catch (e) { return ""; }
  });
  const [scan, setScan] = useState({ status: "idle" });   // idle | running | done | error
  const [watched, setWatched] = useState([]);
  const loadWatched = () => api("/library/watched").then(r => { if (r.ok) setWatched(r.data); });
  useEffect(() => { loadWatched(); }, []);

  // QA re-triage, 2026-07-21: a running scan's {url, jobId} is persisted so closing + reopening this modal (the
  // job keeps running server-side regardless) resumes polling instead of silently forgetting it happened.
  const _clearScanJob = () => { try { localStorage.removeItem(SCAN_JOB_KEY); } catch (e) { /* ignore */ } };

  const poll = (url, failMsg) => {
    const tick = (jobId) => api(`${url}/${jobId}`).then(r => {
      if (!r.ok) { setScan({ status: "error", error: r.error }); _clearScanJob(); return; }
      const d = r.data;
      if (d.status === "done") { setScan({ status: "done", summary: d.summary }); _clearScanJob(); loadWatched(); if (onScanned) onScanned(); }
      else if (d.status === "error") { setScan({ status: "error", error: d.detail || failMsg }); _clearScanJob(); }
      else { setScan({ status: "running", progress: d.progress }); setTimeout(() => tick(jobId), 1500); }
    });
    return tick;
  };

  useEffect(() => {
    let job = null;
    try { job = JSON.parse(localStorage.getItem(SCAN_JOB_KEY) || "null"); } catch (e) { /* ignore */ }
    if (job && job.url && job.jobId) {
      setScan({ status: "running" });
      poll(job.url, "Scan failed.")(job.jobId);
    }
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps -- mount-only resume check

  const run = () => {
    const path = folder.trim();
    if (!path) return;
    try { localStorage.setItem("callosum.scanFolder", path); } catch (e) { /* ignore */ }
    setScan({ status: "running" });
    apiPost("/library/scan", { folder: path }).then(r => {
      if (!r.ok) { setScan({ status: "error", error: r.error }); return; }
      try { localStorage.setItem(SCAN_JOB_KEY, JSON.stringify({ url: "/library/scan", jobId: r.data.job_id })); } catch (e) { /* ignore */ }
      poll("/library/scan", "Scan failed.")(r.data.job_id);
    });
  };

  const rescanAll = () => {
    setScan({ status: "running" });
    apiPost("/library/watched/rescan", {}).then(r => {
      if (!r.ok) { setScan({ status: "error", error: r.error }); return; }
      try { localStorage.setItem(SCAN_JOB_KEY, JSON.stringify({ url: "/library/watched/rescan", jobId: r.data.job_id })); } catch (e) { /* ignore */ }
      poll("/library/watched/rescan", "Re-scan failed.")(r.data.job_id);
    });
  };

  const unwatch = async (id) => { await apiDelete(`/library/watched/${id}`); loadWatched(); };

  const s = scan.summary;
  return (
    <>
      <div className="axis-modal-head">
        <span>Watched folders</span>
        <button className="axis-link" onClick={onClose}>×</button>
      </div>
      <div className="axis-modal-note">
        Your <b>library folder</b> is watched by default (shown below) — drop a PDF into it and it's picked up
        automatically on launch (and when you switch back to Callosum). Add more folders to watch them the same
        way. New files are added (text extracted, chunked, embedded, Crossref-enriched); files already in your
        library are skipped. PDFs stay where they are; nothing is moved or copied.
      </div>
      {watched.length > 0 &&
        <div className="watched-list">
          {watched.map(w => (
            <div key={w.id} className={"watched-row" + (w.is_default ? " is-default" : "")}>
              <div className="watched-info">
                <div className="watched-path" title={w.path}>{w.path}</div>
                <div className="watched-meta">{w.is_default ? "your library folder · always watched" : (w.last_scanned_at ? "last scanned " + w.last_scanned_at.slice(0, 10) : "not yet scanned")}</div>
              </div>
              {w.is_default
                ? <span className="watched-default-note" title="Your library folder is always watched — it can't be removed">default</span>
                : <button className="axis-link" title="Stop watching (keeps the imported papers)" onClick={() => unwatch(w.id)}>remove</button>}
            </div>
          ))}
          <button className="btn btn-ghost" disabled={scan.status === "running"} onClick={rescanAll}>
            {scan.status === "running" ? "Working…" : "Re-scan all"}
          </button>
        </div>}
      <div className="scan-row">
        <input className="wanted-add" placeholder="/path/to/your/pdfs" value={folder}
          onChange={e => setFolder(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") run(); }} />
        <button className="btn btn-primary" disabled={scan.status === "running" || !folder.trim()} onClick={run}>
          {scan.status === "running" ? "Scanning…" : "Add + scan"}
        </button>
      </div>
      {scan.status === "running" && <ProgressBar label="Scanning + processing PDFs…" progress={scan.progress} managedBy="backend-job" />}
      {scan.status === "error" && <div className="axis-err">Scan failed: {scan.error}</div>}
      {scan.status === "done" && s &&
        <div className="scan-summary">
          <b>{s.added}</b> added · {s.unchanged} unchanged · {s.removed} missing
          {s.errors ? ` · ${s.errors} error${s.errors === 1 ? "" : "s"}` : ""}
          {s.error_details && s.error_details.length > 0 &&
            <details className="scan-errors">
              <summary>{s.errors} file{s.errors === 1 ? "" : "s"} couldn't be read</summary>
              <ul>{s.error_details.map((e, i) => (
                <li key={i}><span className="scan-err-path" title={e.path}>{e.path.split(/[\\/]/).pop()}</span> — {e.error}</li>
              ))}</ul>
              {s.errors > s.error_details.length && <div className="axis-hint">…and {s.errors - s.error_details.length} more.</div>}
            </details>}
          {s.added > 0 &&
            <div className="axis-hint">New papers are in your library — any whose DOI didn't resolve need a look.
              {onShowUnsorted && <> <button className="btn-link" onClick={() => { onShowUnsorted(); onClose(); }}>Review unsorted →</button></>}
            </div>}
        </div>}
      <div className="axis-form-actions">
        <button className="axis-link" onClick={onClose}>Close</button>
      </div>
    </>
  );
}
