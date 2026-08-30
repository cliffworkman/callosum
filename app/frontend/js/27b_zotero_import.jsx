// Native Zotero library importer (backlog #57 Phase 1). Reads Zotero's own zotero.sqlite directly (copied,
// never the live file — integrations/zotero/adapter.py): full fidelity vs. the generic BibTeX/RIS/CSL-JSON
// path (28_import.jsx, metadata-only) — PDFs are extracted + chunked, collections/tags/notes/annotations carry
// over. Supported Zotero PDF highlight/underline positions are translated locally into Callosum's exact
// PDF-space coordinates; raw Zotero position JSON remains preserved for unsupported/ambiguous cases.
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
  const [folderAxes, setFolderAxes] = useState({ status: "loading", collections: [] });
  const [scoreFolders, setScoreFolders] = useState(false);

  const _clearJob = () => { try { localStorage.removeItem(ZOTERO_IMPORT_JOB_KEY); } catch (e) { /* ignore */ } };

  const loadFolderAxes = () => {
    api("/library/imported-collections/axes?import_source=zotero").then(r => {
      if (!r.ok) { setFolderAxes({ status: "error", error: r.error, collections: [] }); return; }
      setFolderAxes({ status: "ready", collections: r.data.collections || [] });
    });
  };

  const poll = (jobId) => {
    api(`/library/zotero/import/${jobId}`).then(r => {
      if (!r.ok) { setImp({ status: "error", error: r.error }); _clearJob(); return; }
      const d = r.data;
      if (d.status === "done") {
        setImp({ status: "done", summary: d.summary }); _clearJob(); loadFolderAxes();
        if (onImported) onImported();
      }
      else if (d.status === "error") { setImp({ status: "error", error: d.detail || "Zotero import failed." }); _clearJob(); }
      else { setImp({ status: "running", progress: d.progress }); setTimeout(() => poll(jobId), 1500); }
    });
  };

  useEffect(() => {
    let job = null;
    try { job = JSON.parse(localStorage.getItem(ZOTERO_IMPORT_JOB_KEY) || "null"); } catch (e) { /* ignore */ }
    if (job && job.jobId) { setImp({ status: "running" }); poll(job.jobId); }
    else loadFolderAxes();
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

  const createFolderAxes = () => {
    const available = folderAxes.collections.filter(c => !c.axis_id && c.paper_count > 0);
    if (!available.length) return;
    setFolderAxes(v => ({ ...v, status: "creating" }));
    apiPost("/library/imported-collections/axes", {
      import_source: "zotero", axis_kind: scoreFolders ? "standard" : "curated",
    }).then(r => {
      if (!r.ok) { setFolderAxes(v => ({ ...v, status: "error", error: r.error })); return; }
      setFolderAxes(v => ({ ...v, status: "created", result: r.data }));
      loadFolderAxes();
      if (onImported) onImported();
    });
  };

  const s = imp.summary;
  const importedFolders = folderAxes.collections || [];
  const availableFolders = importedFolders.filter(c => !c.axis_id && c.paper_count > 0);
  const linkedFolders = importedFolders.filter(c => c.axis_id);
  const folderPaperCount = availableFolders.reduce((total, c) => total + c.paper_count, 0);
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
        collections, tags, and notes carry over. Zotero PDF highlights and underlines are also placed on the
        matching local PDF when their stored position can be translated exactly; unsupported or ambiguous
        positions stay unmarked rather than being drawn at a guessed location. <b>Moving from Mendeley?</b> In
        current Zotero Desktop, first choose <b>File → Import → Mendeley Reference Manager (online import)</b> and
        let it finish, then enter that Zotero data directory here. That bridge requires your Mendeley data/files
        online and signs in through Zotero; Callosum never receives your Mendeley credentials.
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
      {folderAxes.status === "error" && importedFolders.length === 0 &&
        <div className="axis-err">Imported folders could not be loaded: {folderAxes.error}</div>}
      {imp.status === "done" && s &&
        <div className="scan-summary">
          <b>{s.papers_created}</b> new · {s.papers_matched} already in your library
          {s.attachments_created ? ` · ${s.attachments_created} attachment${s.attachments_created === 1 ? "" : "s"}` : ""}
          {s.chunks_created ? ` · ${s.chunks_created} chunk${s.chunks_created === 1 ? "" : "s"} extracted` : ""}
          {s.attachment_errors ? ` · ${s.attachment_errors} attachment${s.attachment_errors === 1 ? "" : "s"} couldn't be read` : ""}
          {s.papers_created > 0 &&
            <div className="axis-hint">New papers are in your library — full fidelity wherever a local PDF was found.</div>}
        </div>}
      {folderAxes.status !== "loading" && importedFolders.length > 0 &&
        <div className="scan-summary">
          <b>Imported Zotero folders</b>
          <div className="axis-hint">
            {importedFolders.length} top-level folder{importedFolders.length === 1 ? "" : "s"}; nested-folder
            papers roll up into their parent. Creating axes is an explicit one-time snapshot—later Zotero reads
            never overwrite an axis you own.
          </div>
          {availableFolders.length > 0 && <>
            <div className="axis-hint">
              {availableFolders.slice(0, 5).map(c => `${c.name} (${c.paper_count})`).join(" · ")}
              {availableFolders.length > 5 ? ` · +${availableFolders.length - 5} more` : ""}
            </div>
            <label className="settings-check">
              <input type="checkbox" checked={scoreFolders} onChange={e => setScoreFolders(e.target.checked)} />
              Create keyword axes instead: keep the exact {folderPaperCount} folder-paper memberships as manual
              anchors, then score the rest of the library locally by each folder name (may take a while).
            </label>
            <button className="btn btn-secondary" disabled={folderAxes.status === "creating"}
              onClick={createFolderAxes}>
              {folderAxes.status === "creating" ? "Creating axes…"
                : `Create ${availableFolders.length} ${scoreFolders ? "keyword" : "curated"} ${availableFolders.length === 1 ? "axis" : "axes"}`}
            </button>
          </>}
          {!availableFolders.length && linkedFolders.length > 0 &&
            <div className="axis-hint">All non-empty top-level folders already have axes.</div>}
          {folderAxes.error && <div className="axis-err">Folder axes failed: {folderAxes.error}</div>}
          <div className="axis-hint">
            Imported before this feature? Read the Zotero library once more before creating axes to restore its
            nested folder relationships.
          </div>
        </div>}
      <div className="axis-form-actions">
        <button className="axis-link" onClick={onClose}>Close</button>
      </div>
    </>
  );
}
