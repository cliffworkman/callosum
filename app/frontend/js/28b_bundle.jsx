// Import-bundle modal (B2 SP1). Choose a callosum library bundle (.json) → merge its papers + tags + annotations
// + axis definitions into the library (additive & non-destructive; NO PDFs). The browser reads the file and POSTs
// its text; nothing is sent off-machine. Clones the ImportModal poll lifecycle.

function BundleImportModal({ onClose, onImported }) {
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <BundleImportModalBody onClose={onClose} onImported={onImported} />
      </div>
    </div>
  );
}

// inc 416: bare body split out so the onboarding wizard can embed it without a nested overlay —
// BundleImportModal above is now a thin wrapper adding that chrome. Every hook/handler below is unchanged.
function BundleImportModalBody({ onClose, onImported }) {
  const [file, setFile] = useState(null);   // {name, content}
  const [imp, setImp] = useState({ status: "idle" });   // idle | running | done | error

  const onPick = async (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    try {
      setFile({ name: f.name || "bundle.json", content: await f.text() });
      setImp({ status: "idle" });
    } catch (err) {
      setImp({ status: "error", error: "Couldn't read that file." });
    }
  };

  const run = () => {
    if (!file || !file.content.trim()) return;
    setImp({ status: "running" });
    const poll = (jobId) => api(`/library/bundle/import/${jobId}`).then(r => {
      if (!r.ok) { setImp({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setImp({ status: "done", summary: d.summary }); if (onImported) onImported(); }
      else if (d.status === "error") setImp({ status: "error", error: d.detail || "Import failed." });
      else { setImp({ status: "running", progress: d.progress }); setTimeout(() => poll(jobId), 1500); }
    });
    apiPost("/library/bundle/import", { content: file.content }).then(r => {
      if (!r.ok) { setImp({ status: "error", error: r.error }); return; }
      poll(r.data.job_id);
    });
  };

  const s = imp.summary;
  return (
    <>
      <div className="axis-modal-head">
        <span>Import library bundle</span>
        <button className="axis-link" onClick={onClose}>×</button>
      </div>
      <div className="axis-modal-note">
        Choose a <b>callosum library bundle</b> (.json) exported from another library. Its papers, tags,
        annotations, axis definitions, and syntheses merge into yours — existing papers keep their own metadata and
        just gain the bundle's tags + notes. An imported synthesis is shown as <b>the sender's assessment</b> (not
        re-verified in your library). <b>No PDFs</b> travel in a bundle; a highlight's box re-appears once you have
        the same PDF. Everything stays on your machine.
      </div>
      <div className="scan-row">
        <input type="file" accept=".json" onChange={onPick} />
        <button className="btn btn-primary" disabled={imp.status === "running" || !file} onClick={run}>
          {imp.status === "running" ? "Importing…" : "Import"}
        </button>
      </div>
      {file && imp.status === "idle" && <div className="axis-hint">{file.name} — ready to import.</div>}
      {imp.status === "running" && <ProgressBar label="Merging + embedding…" progress={imp.progress} />}
      {imp.status === "error" && <div className="axis-err">Import failed: {imp.error}</div>}
      {imp.status === "done" && s &&
        <div className="scan-summary">
          <b>{s.papers_created}</b> new · {s.papers_merged} merged
          {s.tags_applied ? ` · ${s.tags_applied} tags` : ""}
          {s.annotations_added ? ` · ${s.annotations_added} highlights` : ""}
          {s.axes_created ? ` · ${s.axes_created} axes` : ""}
          {s.axes_members_added ? ` · ${s.axes_members_added} axis members` : ""}
          {s.syntheses_imported ? ` · ${s.syntheses_imported} syntheses` : ""}
          {s.skipped ? ` · ${s.skipped} skipped` : ""}
          <div className="axis-hint">Merged papers keep your own metadata; new papers are filterable by type. Imported syntheses are the sender's — not re-verified here.</div>
        </div>}
      <div className="axis-form-actions">
        <button className="axis-link" onClick={onClose}>Close</button>
      </div>
    </>
  );
}
