// Watched-folders modal (inc 87 scan → inc 98 watching). Point Callosum at folders of PDFs; new files are
// ingested (extract + chunk + embed, Crossref-enriched), unchanged skipped, removed flagged. Scanning a folder
// **watches** it — watched folders are re-scanned automatically on launch (Settings toggle) + via "Re-scan all",
// so new PDFs appear without re-adding. Clones the poll lifecycle of the other async-job modals.

function ScanModal({ onClose, onScanned, onShowUnsorted }) {
  const [folder, setFolder] = useState(() => {
    try { return localStorage.getItem("callosum.scanFolder") || ""; } catch (e) { return ""; }
  });
  const [scan, setScan] = useState({ status: "idle" });   // idle | running | done | error
  const [watched, setWatched] = useState([]);
  const loadWatched = () => api("/library/watched").then(r => { if (r.ok) setWatched(r.data); });
  useEffect(() => { loadWatched(); }, []);

  const poll = (url, failMsg) => {
    const tick = (jobId) => api(`${url}/${jobId}`).then(r => {
      if (!r.ok) { setScan({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setScan({ status: "done", summary: d.summary }); loadWatched(); if (onScanned) onScanned(); }
      else if (d.status === "error") setScan({ status: "error", error: d.detail || failMsg });
      else { setScan({ status: "running", progress: d.progress }); setTimeout(() => tick(jobId), 1500); }
    });
    return tick;
  };

  const run = () => {
    const path = folder.trim();
    if (!path) return;
    try { localStorage.setItem("callosum.scanFolder", path); } catch (e) { /* ignore */ }
    setScan({ status: "running" });
    apiPost("/library/scan", { folder: path }).then(r => {
      if (!r.ok) { setScan({ status: "error", error: r.error }); return; }
      poll("/library/scan", "Scan failed.")(r.data.job_id);
    });
  };

  const rescanAll = () => {
    setScan({ status: "running" });
    apiPost("/library/watched/rescan", {}).then(r => {
      if (!r.ok) { setScan({ status: "error", error: r.error }); return; }
      poll("/library/watched/rescan", "Re-scan failed.")(r.data.job_id);
    });
  };

  const unwatch = async (id) => { await apiDelete(`/library/watched/${id}`); loadWatched(); };

  const s = scan.summary;
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Watched folders</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Point Callosum at folders of PDFs. New files are added (text extracted, chunked, embedded, with metadata
          from Crossref where possible); files already in your library are skipped. Watched folders are re-scanned
          automatically on launch, so new PDFs appear without re-adding — and the folder your library came from is
          already tracked once it's listed here. PDFs stay where they are; nothing is moved or copied.
        </div>
        {watched.length > 0 &&
          <div className="watched-list">
            {watched.map(w => (
              <div key={w.id} className="watched-row">
                <div className="watched-info">
                  <div className="watched-path" title={w.path}>{w.path}</div>
                  <div className="watched-meta">{w.last_scanned_at ? "last scanned " + w.last_scanned_at.slice(0, 10) : "not yet scanned"}</div>
                </div>
                <button className="axis-link" title="Stop watching (keeps the imported papers)" onClick={() => unwatch(w.id)}>remove</button>
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
        {scan.status === "running" && <ProgressBar label="Scanning + processing PDFs…" progress={scan.progress} />}
        {scan.status === "error" && <div className="axis-err">Scan failed: {scan.error}</div>}
        {scan.status === "done" && s &&
          <div className="scan-summary">
            <b>{s.added}</b> added · {s.unchanged} unchanged · {s.removed} missing
            {s.errors ? ` · ${s.errors} error${s.errors === 1 ? "" : "s"}` : ""}
            {s.added > 0 &&
              <div className="axis-hint">New papers are in your library — any whose DOI didn't resolve need a look.
                {onShowUnsorted && <> <button className="btn-link" onClick={() => { onShowUnsorted(); onClose(); }}>Review unsorted →</button></>}
              </div>}
          </div>}
        <div className="axis-form-actions">
          <button className="axis-link" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
