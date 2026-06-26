// Literature gap-finder modal (inc 135). "Find gaps" runs an async job that surfaces works MANY of your library
// papers cite but that you don't have ("cited by N of your papers") — discovery candidates to Add or Dismiss.
// The count is a fact about YOUR library's citing, never a quality/importance rank; Add imports metadata-only
// into the general library (the PDF stays the separate OA-acquire lane). Clones the WantedModal shell.

function GapsModal({ onClose, onChanged }) {
  const [run, setRun] = useState({ status: "idle" });  // idle | running | done | error
  const [rows, setRows] = useState([]);                // candidates, each with a local _state: null|"added"|"dismissed"
  const [coverage, setCoverage] = useState(null);

  const find = async () => {
    setRun({ status: "running" }); setRows([]); setCoverage(null);
    const poll = (jobId) => api(`/gaps/find/${jobId}`).then(r => {
      if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") {
        setRun({ status: "done" });
        setRows((d.result.candidates || []).map(c => ({ ...c, _state: null })));
        setCoverage({ checked: d.result.checked, total: d.result.total, note: d.result.note });
      } else if (d.status === "error") setRun({ status: "error", error: d.detail || "Gap-finder failed." });
      else setTimeout(() => poll(jobId), 2000);
    });
    const r = await apiPost("/gaps/find", {});
    if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };

  const mark = (id, state) => setRows(rs => rs.map(x => x.openalex_work_id === id ? { ...x, _state: state } : x));
  const add = async (row) => {
    const r = await apiPost("/gaps/add", { doi: row.doi, openalex_work_id: row.openalex_work_id, title: row.title });
    if (r.ok) { mark(row.openalex_work_id, "added"); if (onChanged) onChanged(); }
  };
  const dismiss = async (row) => {
    const r = await apiPost("/gaps/dismiss", { openalex_work_id: row.openalex_work_id, doi: row.doi });
    if (r.ok) mark(row.openalex_work_id, "dismissed");
  };

  const visible = rows.filter(r => r._state !== "dismissed");
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Gaps in your library</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Works that <b>several of your papers cite</b> but that aren't in your library yet — likely references worth adding. The count is how many of <i>your</i> papers cite each one, not a measure of importance. <b>Add</b> imports the metadata; <b>Dismiss</b> hides it for good.
        </div>
        <div className="gaps-actions">
          <button className="btn btn-primary" disabled={run.status === "running"} onClick={find}>
            {run.status === "running" ? "Finding…" : "Find gaps"}
          </button>
        </div>
        {run.status === "running" && <ProgressBar label="Scanning your library's references (OpenAlex)…" />}
        {run.status === "error" && <div className="axis-err">{run.error}</div>}
        {coverage &&
          <div className="gaps-coverage">Scanned {coverage.checked} of {coverage.total} papers (the rest have no DOI). {coverage.note}</div>}
        {run.status === "done" && visible.length === 0 &&
          <div className="axis-hint">No gaps found — every work cited by several of your papers is already in your library.</div>}
        {visible.map(row => (
          <div key={row.openalex_work_id} className="gap-row">
            <div className="gap-row-info">
              <div className="gap-row-title">{row.title || row.doi}</div>
              <div className="gap-row-meta">
                <span className="gap-count">cited by {row.cited_by_in_library} of your papers</span>
                {row.authors && row.authors.length > 0 && <> · {row.authors.slice(0, 3).join(", ")}{row.authors.length > 3 ? " et al." : ""}</>}
                {row.year ? ` · ${row.year}` : ""}
              </div>
            </div>
            <div className="gap-row-actions">
              {row._state === "added"
                ? <span className="gap-added">✓ in library</span>
                : <>
                    <button className="axis-link" onClick={() => add(row)}>Add</button>
                    <button className="axis-link" onClick={() => dismiss(row)}>Dismiss</button>
                  </>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
