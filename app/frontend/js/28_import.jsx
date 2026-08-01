// Import-citations modal (inc 93). Choose a BibTeX / RIS / CSL-JSON file → each entry becomes a metadata-only
// library paper (deduped). The inverse of the inc-70 export. Entirely local — the browser reads the file and
// POSTs its text; nothing is sent off-machine. Clones the ScanModal poll lifecycle.

function ImportModal({ onClose, onImported }) {
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <ImportModalBody onClose={onClose} onImported={onImported} />
      </div>
    </div>
  );
}

// inc 416: bare body split out so the onboarding wizard can embed it without a nested overlay — ImportModal
// above is now a thin wrapper adding that chrome. Every hook/handler below is unchanged from before the split.
function ImportModalBody({ onClose, onImported }) {
  const [file, setFile] = useState(null);   // {name, content, format}
  const [imp, setImp] = useState({ status: "idle" });   // idle | running | done | error

  const onPick = async (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    const ext = (f.name || "").toLowerCase().split(".").pop();
    const format = ext === "bib" ? "bibtex" : ext === "ris" ? "ris" : ext === "json" ? "csl-json" : "auto";
    try {
      setFile({ name: f.name || "file", content: await f.text(), format });
      setImp({ status: "idle" });
    } catch (err) {
      setImp({ status: "error", error: "Couldn't read that file." });
    }
  };

  const run = () => {
    if (!file || !file.content.trim()) return;
    setImp({ status: "running" });
    const poll = (jobId) => api(`/library/import/${jobId}`).then(r => {
      if (!r.ok) { setImp({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setImp({ status: "done", summary: d.summary }); if (onImported) onImported(); }
      else if (d.status === "error") setImp({ status: "error", error: d.detail || "Import failed." });
      else { setImp({ status: "running", progress: d.progress }); setTimeout(() => poll(jobId), 1500); }
    });
    apiPost("/library/import", { content: file.content, format: file.format }).then(r => {
      if (!r.ok) { setImp({ status: "error", error: r.error }); return; }
      poll(r.data.job_id);
    });
  };

  const s = imp.summary;
  return (
    <>
      <div className="axis-modal-head">
        <span>Import citations</span>
        <button className="axis-link" onClick={onClose}>×</button>
      </div>
      <div className="axis-modal-note">
        Choose a <b>BibTeX</b> (.bib), <b>RIS</b> (.ris), or <b>CSL-JSON</b> (.json) file exported from Zotero,
        Mendeley, EndNote, or callosum. Each entry becomes a metadata-only library paper (no PDF attached);
        entries already in your library are skipped. Everything stays on your machine — nothing is sent anywhere.
      </div>
      <div className="scan-row">
        <input type="file" accept=".bib,.ris,.json,.txt" onChange={onPick} />
        <button className="btn btn-primary" disabled={imp.status === "running" || !file} onClick={run}>
          {imp.status === "running" ? "Importing…" : "Import"}
        </button>
      </div>
      {file && imp.status === "idle" && <div className="axis-hint">{file.name} — ready to import.</div>}
      {imp.status === "running" && <ProgressBar label="Parsing + embedding…" progress={imp.progress} managedBy="backend-job" />}
      {imp.status === "error" && <div className="axis-err">Import failed: {imp.error}</div>}
      {imp.status === "done" && s &&
        <div className="scan-summary">
          <b>{s.imported}</b> imported · {s.duplicate} already in library
          {s.failed ? ` · ${s.failed} failed` : ""}
          {s.skipped ? ` · ${s.skipped} skipped (no title or DOI)` : ""}
          {s.format == null
            ? <div className="axis-err">Couldn't recognise the file — is it BibTeX, RIS, or CSL-JSON?</div>
            : s.imported > 0
              ? <div className="axis-hint">New papers are in your library, filterable by type.</div>
              : null}
        </div>}
      <div className="axis-form-actions">
        <button className="axis-link" onClick={onClose}>Close</button>
      </div>
    </>
  );
}
