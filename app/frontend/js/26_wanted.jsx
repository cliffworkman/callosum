// Wanted-list modal (inc 76). The OA acquisition "track" loop: a persistent list of papers you want an
// open-access copy of (library-linked or external), a manual "Re-check OA" job that runs the resolver
// cascade over the list and auto-acquires hits, plus a coverage readout. Clones DuplicatesModal's poll
// lifecycle; reuses the inc-74 .oa-chip recipe for the acquired summary.

function _wantedTitle(it) {
  return it.paper_title || it.title || it.doi || "Untitled";
}

function WantedModal({ onClose, onOpenPaper, onChanged }) {
  const [items, setItems] = useState([]);
  const [coverage, setCoverage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [addDoi, setAddDoi] = useState("");
  const [busy, setBusy] = useState(false);
  const [recheck, setRecheck] = useState({ status: "idle" });  // idle | running | done | error

  const refresh = useCallback(() => {
    return Promise.all([api("/wanted"), api("/wanted/coverage")]).then(([li, cov]) => {
      if (li.ok) setItems(li.data.items || []);
      if (cov.ok) setCoverage(cov.data);
      setLoading(false);
    });
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const syncLibrary = async () => {
    setBusy(true);
    await apiPost("/wanted/sync-library", {});
    setBusy(false);
    refresh();
  };

  const addExternal = async () => {
    const doi = addDoi.trim();
    if (!doi) return;
    setBusy(true);
    const r = await apiPost("/wanted", { doi });
    setBusy(false);
    if (r.ok) { setAddDoi(""); refresh(); }
  };

  const removeItem = async (id) => {
    const r = await apiDelete(`/wanted/${id}`);
    if (r.ok) refresh();
  };

  const runRecheck = () => {
    setRecheck({ status: "running" });
    const poll = (jobId) => {
      api(`/wanted/recheck/${jobId}`).then(r => {
        if (!r.ok) { setRecheck({ status: "error", error: r.error }); return; }
        const d = r.data;
        if (d.status === "done") {
          setRecheck({ status: "done", summary: d.summary });
          refresh();
          if (onChanged) onChanged();  // acquired PDFs → refresh the main library
        } else if (d.status === "error") {
          setRecheck({ status: "error", error: d.detail || "Re-check failed." });
        } else {
          setTimeout(() => poll(jobId), 1500);
        }
      });
    };
    apiPost("/wanted/recheck", {}).then(r => {
      if (!r.ok) { setRecheck({ status: "error", error: r.error }); return; }
      poll(r.data.job_id);
    });
  };

  const cov = coverage;
  const summary = recheck.summary;
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Wanted list</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Papers you want an open-access copy of. <b>Sync from Library</b> adds your PDF-less papers;{" "}
          <b>Re-check OA</b> searches the open-access sources and imports any authorized copy it finds
          (bronze = unstable). Add an external paper by DOI.
        </div>

        {cov &&
          <div className="wanted-coverage">
            {cov.with_pdf} of {cov.library_total} papers have PDFs · acquired{" "}
            {cov.acquired_oa.gold} gold / {cov.acquired_oa.green} green / {cov.acquired_oa.bronze} bronze ·{" "}
            {cov.wanted_open} wanted
          </div>}

        <div className="wanted-actions">
          <button className="axis-link" disabled={busy} onClick={syncLibrary}>Sync from Library</button>
          <button className="btn btn-primary" disabled={recheck.status === "running"} onClick={runRecheck}>
            {recheck.status === "running" ? "Re-checking…" : "Re-check OA"}
          </button>
          <input className="wanted-add" placeholder="Add by DOI…" value={addDoi}
            onChange={e => setAddDoi(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") addExternal(); }} />
          <button className="axis-link" disabled={busy || !addDoi.trim()} onClick={addExternal}>Add</button>
        </div>
        {recheck.status === "running" && <ProgressBar label="Searching open-access sources…" managedBy="backend-job" />}

        {recheck.status === "error" && <div className="axis-err">Re-check failed: {recheck.error}</div>}
        {recheck.status === "done" && summary &&
          <div className="wanted-summary">
            Acquired {summary.acquired.length} · {summary.still_wanted} still wanted
            {summary.skipped ? ` · ${summary.skipped} need an identifier` : ""}
            {summary.errors ? ` · ${summary.errors} error${summary.errors === 1 ? "" : "s"}` : ""}
            {summary.acquired.length > 0 &&
              <div className="oa-meta wanted-acquired">
                {summary.acquired.map((a, i) =>
                  <span key={i} className={"oa-chip " + (a.oa_color === "bronze" ? "oa-bronze" : "oa-durable")}>
                    {a.oa_color}/{a.oa_version}
                  </span>)}
              </div>}
          </div>}

        {loading && <div className="axis-hint">Loading…</div>}
        {!loading && items.length === 0 &&
          <div className="axis-hint">Your wanted list is empty. Sync from library or add a DOI.</div>}
        {items.map(it => (
          <div key={it.id} className="wanted-row">
            <div className="wanted-row-info">
              <div className="wanted-row-title">{_wantedTitle(it)}</div>
              <div className="wanted-row-meta">
                {it.paper_id ? "library" : "external"}
                {it.paper_year ? " · " + it.paper_year : ""}
                {it.last_result ? " · " + it.last_result : ""}
              </div>
            </div>
            <span className={"wanted-status" + (it.status === "fulfilled" ? " fulfilled" : "")}>{it.status}</span>
            {it.paper_id && it.status === "fulfilled" &&
              <button className="axis-link"
                onClick={() => onOpenPaper && onOpenPaper({ id: it.paper_id, title: _wantedTitle(it) })}>Open</button>}
            <button className="axis-link" title="Remove from the wanted list" onClick={() => removeItem(it.id)}>×</button>
          </div>
        ))}

        <div className="axis-form-actions">
          <button className="axis-link" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
