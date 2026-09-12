// Add-by-DOI modal (backlog #58). Paste a DOI (bare, doi:, or https://doi.org/…) → the backend resolves it
// to authoritative metadata, dedups against the library, and creates a metadata-only record; open-access
// full-text acquisition then runs as a SEPARATE step (the backend starts it and returns a distinct job id),
// so a failed PDF fetch never masquerades as a failed DOI import. Mirrors ImportModal's structure/chrome.

function AddDoiModal({ onClose, onImported }) {
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <AddDoiModalBody onClose={onClose} onImported={onImported} />
      </div>
    </div>
  );
}

function AddDoiModalBody({ onClose, onImported }) {
  const [doi, setDoi] = useState("");
  const [meta, setMeta] = useState({ status: "idle" });  // idle | running | created | existing | error
  const [oa, setOa] = useState(null);                    // null | {status:"running"|"done", found, detail}

  const pollOa = (jobId) => api(`/papers/acquire-oa/${jobId}`).then(r => {
    if (!r.ok) { setOa({ status: "done", found: false, reasonCode: "error", detail: "Could not check OA status." }); return; }
    const d = r.data;
    // Capture the STRUCTURED reason_code (inc 588) so the "why" is human-readable, not the raw "HTTP 403" string.
    if (d.status === "done") setOa({ status: "done", found: !!d.found, reasonCode: d.reason_code, detail: d.detail });
    else if (d.status === "error") setOa({ status: "done", found: false, reasonCode: "error", detail: d.detail || "OA fetch failed." });
    else { setOa({ status: "running" }); setTimeout(() => pollOa(jobId), 1500); }
  });

  const run = () => {
    const value = doi.trim();
    if (!value) return;
    setMeta({ status: "running" }); setOa(null);
    apiPost("/papers/by-doi", { doi: value, acquire_oa: true }).then(r => {
      if (!r.ok) { setMeta({ status: "error", error: r.error || "Could not add that DOI." }); return; }
      const d = r.data;
      setMeta({ status: d.status, title: d.title, doi: d.doi });
      if (onImported) onImported();               // refresh the library (the record now exists)
      if (d.acquire_job_id) { setOa({ status: "running" }); pollOa(d.acquire_job_id); }
    });
  };

  const onKey = (e) => { if (e.key === "Enter" && meta.status !== "running") { e.preventDefault(); run(); } };

  return (
    <>
      <div className="axis-modal-head">
        <span>Add with DOI</span>
        <button className="axis-link" onClick={onClose}>×</button>
      </div>
      <div className="axis-modal-note">
        Paste a <b>DOI</b> — bare (<code>10.1037/a0033242</code>), <code>doi:</code> form, or a
        {" "}<code>https://doi.org/…</code> link. Callosum resolves it to authoritative metadata and adds it to your
        library; if a legal open-access PDF exists, it's fetched automatically afterward. Nothing is invented — an
        unrecognised DOI is reported, not saved.
      </div>
      <div className="scan-row">
        <input type="text" className="axis-input" style={{ flex: 1 }} placeholder="10.1037/a0033242"
          aria-label="DOI to add" value={doi} disabled={meta.status === "running"}
          onChange={e => setDoi(e.target.value)} onKeyDown={onKey} />
        <button className="btn btn-primary" disabled={meta.status === "running" || !doi.trim()} onClick={run}>
          {meta.status === "running" ? "Adding…" : "Add"}
        </button>
      </div>
      {meta.status === "error" && <div className="axis-err">{meta.error}</div>}
      {meta.status === "created" &&
        <div className="scan-summary"><b>Added.</b> {meta.title || meta.doi} is now in your library.</div>}
      {meta.status === "existing" &&
        <div className="scan-summary"><b>Already in your library.</b> {meta.title || meta.doi} — surfaced, not duplicated.</div>}
      {/* OA full-text acquisition — a DISTINCT step from the metadata import above. inc 588: on failure, say WHY
          in plain language (from the structured reason_code), offer the article page so the user can get it
          themselves, and keep the raw provenance under a "Technical details" disclosure. */}
      {oa && oa.status === "running" && <ProgressBar label="Fetching open-access PDF…" managedBy="backend-job" />}
      {oa && oa.status === "done" && oa.found &&
        <div className="axis-hint">Open-access PDF added.</div>}
      {oa && oa.status === "done" && !oa.found &&
        <div className="axis-hint">
          {_acquireFriendlyMessage(oa.reasonCode)}
          {meta.doi &&
            <> <button className="axis-link"
                 title="Open this article's page (via its DOI) in your browser — if it's freely readable, download the PDF yourself and attach it here."
                 onClick={() => window.open("https://doi.org/" + meta.doi, "_blank", "noopener,noreferrer")}>Open article ↗</button></>}
          {oa.detail &&
            <details className="detail-acquire-tech"><summary>Technical details</summary><span>{oa.detail}</span></details>}
        </div>}
      <div className="axis-form-actions">
        <button className="axis-link" onClick={onClose}>Close</button>
      </div>
    </>
  );
}
