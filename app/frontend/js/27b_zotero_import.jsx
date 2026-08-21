// Native Zotero library importer (backlog #57 Phase 1). Reads Zotero's own zotero.sqlite directly (copied,
// never the live file — integrations/zotero/adapter.py): full fidelity vs. the generic BibTeX/RIS/CSL-JSON
// path (28_import.jsx, metadata-only) — PDFs are extracted + chunked, collections/tags/notes/annotations carry
// over. Known, disclosed gap: imported highlight POSITIONS stay in raw Zotero-reader-JSON form (unfixed by
// this increment) — they show their quoted text/comment but can't be jumped-to or drawn on the PDF yet.
// Mirrors ScanModalBody's exact resume-on-remount poll lifecycle (27_scan.jsx).

const ZOTERO_IMPORT_JOB_KEY = "callosum.zoteroImportJob";

function ZoteroImportModal({ onClose, onImported }) {
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <ZoteroImportModalBody onClose={onClose} onImported={onImported} />
      </div>
    </div>
  );
}

function ZoteroImportModalBody({ onClose, onImported }) {
  const [dir, setDir] = useState(() => {
    try { return localStorage.getItem("callosum.zoteroDataDir") || ""; } catch (e) { return ""; }
  });
  const [imp, setImp] = useState({ status: "idle" });

  const _clearJob = () => { try { localStorage.removeItem(ZOTERO_IMPORT_JOB_KEY); } catch (e) { /* ignore */ } };

  const poll = (jobId) => {
    api(`/library/zotero/import/${jobId}`).then(r => {
      if (!r.ok) { setImp({ status: "error", error: r.error }); _clearJob(); return; }
      const d = r.data;
      if (d.status === "done") { setImp({ status: "done", summary: d.summary }); _clearJob(); if (onImported) onImported(); }
      else if (d.status === "error") { setImp({ status: "error", error: d.detail || "Zotero import failed." }); _clearJob(); }
      else { setImp({ status: "running", progress: d.progress }); setTimeout(() => poll(jobId), 1500); }
    });
  };

  useEffect(() => {
    let job = null;
    try { job = JSON.parse(localStorage.getItem(ZOTERO_IMPORT_JOB_KEY) || "null"); } catch (e) { /* ignore */ }
    if (job && job.jobId) { setImp({ status: "running" }); poll(job.jobId); }
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps -- mount-only resume check

  const run = () => {
    const path = dir.trim();
    if (!path) return;
    try { localStorage.setItem("callosum.zoteroDataDir", path); } catch (e) { /* ignore */ }
    setImp({ status: "running" });
    apiPost("/library/zotero/import", { zotero_data_dir: path }).then(r => {
      if (!r.ok) { setImp({ status: "error", error: r.error }); return; }
      try { localStorage.setItem(ZOTERO_IMPORT_JOB_KEY, JSON.stringify({ jobId: r.data.job_id })); } catch (e) { /* ignore */ }
      poll(r.data.job_id);
    });
  };

  const s = imp.summary;
  return (
    <>
      <div className="axis-modal-head">
        <span>Read my Zotero library</span>
        <button className="axis-link" onClick={onClose}>×</button>
      </div>
      <div className="axis-modal-note">
        Point this at your <b>Zotero data directory</b> — the folder containing <code>zotero.sqlite</code>{" "}
        (commonly <code>~/Zotero</code> on Mac/Linux, or under <code>Documents\Zotero</code> on Windows).
        Callosum copies that file before reading it — your live Zotero database is never opened or modified, so
        this is safe to run while Zotero itself is open. Full fidelity: local PDFs are extracted and chunked,
        collections, tags, and notes carry over. One known gap: imported highlight positions can't yet be
        jumped-to or drawn on the PDF (they still show their quoted text and any comment).
      </div>
      <div className="scan-row">
        <input className="wanted-add" placeholder="/path/to/Zotero" value={dir}
          onChange={e => setDir(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") run(); }} />
        <button className="btn btn-primary" disabled={imp.status === "running" || !dir.trim()} onClick={run}>
          {imp.status === "running" ? "Importing…" : "Read library"}
        </button>
      </div>
      {imp.status === "running" && <ProgressBar label="Reading your Zotero library…" progress={imp.progress} managedBy="backend-job" />}
      {imp.status === "error" && <div className="axis-err">Import failed: {imp.error}</div>}
      {imp.status === "done" && s &&
        <div className="scan-summary">
          <b>{s.papers_created}</b> new · {s.papers_matched} already in your library
          {s.attachments_created ? ` · ${s.attachments_created} attachment${s.attachments_created === 1 ? "" : "s"}` : ""}
          {s.chunks_created ? ` · ${s.chunks_created} chunk${s.chunks_created === 1 ? "" : "s"} extracted` : ""}
          {s.attachment_errors ? ` · ${s.attachment_errors} attachment${s.attachment_errors === 1 ? "" : "s"} couldn't be read` : ""}
          {s.papers_created > 0 &&
            <div className="axis-hint">New papers are in your library — full fidelity wherever a local PDF was found.</div>}
        </div>}
      <div className="axis-form-actions">
        <button className="axis-link" onClick={onClose}>Close</button>
      </div>
    </>
  );
}
