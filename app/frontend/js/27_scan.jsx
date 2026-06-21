// Scan-a-folder modal (inc 87). Point Callosum at a folder of PDFs → ingest new ones (extract + chunk + embed,
// Crossref-enriched), skip unchanged, flag removed. Manual scan/refresh; the folder path is remembered locally.
// Clones the WantedModal poll lifecycle.

function ScanModal({ onClose, onScanned }) {
  const [folder, setFolder] = useState(() => {
    try { return localStorage.getItem("callosum.scanFolder") || ""; } catch (e) { return ""; }
  });
  const [scan, setScan] = useState({ status: "idle" });  // idle | running | done | error

  const run = () => {
    const path = folder.trim();
    if (!path) return;
    try { localStorage.setItem("callosum.scanFolder", path); } catch (e) { /* ignore */ }
    setScan({ status: "running" });
    const poll = (jobId) => api(`/library/scan/${jobId}`).then(r => {
      if (!r.ok) { setScan({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setScan({ status: "done", summary: d.summary }); if (onScanned) onScanned(); }
      else if (d.status === "error") setScan({ status: "error", error: d.detail || "Scan failed." });
      else setTimeout(() => poll(jobId), 1500);
    });
    apiPost("/library/scan", { folder: path }).then(r => {
      if (!r.ok) { setScan({ status: "error", error: r.error }); return; }
      poll(r.data.job_id);
    });
  };

  const s = scan.summary;
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Scan a folder for PDFs</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Enter a folder path on this computer. New PDFs are added to your library (text extracted + chunked +
          embedded, with metadata fetched from Crossref where possible); files already in the library are skipped;
          a previously-scanned file that's now gone is flagged. PDFs stay where they are — nothing is moved or copied.
        </div>
        <div className="scan-row">
          <input className="wanted-add" placeholder="/path/to/your/pdfs" value={folder}
            onChange={e => setFolder(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") run(); }} />
          <button className="btn btn-primary" disabled={scan.status === "running" || !folder.trim()} onClick={run}>
            {scan.status === "running" ? "Scanning…" : "Scan"}
          </button>
        </div>
        {scan.status === "running" && <ProgressBar label="Scanning + processing PDFs…" />}
        {scan.status === "error" && <div className="axis-err">Scan failed: {scan.error}</div>}
        {scan.status === "done" && s &&
          <div className="scan-summary">
            <b>{s.added}</b> added · {s.unchanged} unchanged · {s.removed} missing
            {s.errors ? ` · ${s.errors} error${s.errors === 1 ? "" : "s"}` : ""}
            {s.added > 0 &&
              <div className="axis-hint">New papers are in your library — any whose DOI didn't resolve are under <b>Unsorted</b>.</div>}
          </div>}
        <div className="axis-form-actions">
          <button className="axis-link" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
