// Literature gap-finder modal (inc 135 backward; inc 137 forward + axis-scoped + persistent cache).
// Two directions: works your papers CITE that you're missing ("cited by N of your papers"), or works that CITE
// your papers ("cites N of your papers"). An axis dropdown scopes the scan. Results are cached per (direction,
// axis): opening / toggling reads the cache instantly (GET /gaps); Refresh recomputes (POST /gaps/refresh). The
// count is a fact about YOUR library, never a quality/importance rank; Add imports metadata-only into the general
// library (the PDF stays the separate OA-acquire lane). Clones the WantedModal shell.

function GapsModal({ onClose, onChanged }) {
  const [direction, setDirection] = useState("backward");  // backward | forward
  const [axisId, setAxisId] = useState("");                // "" = whole library
  const [axes, setAxes] = useState([]);
  const [rows, setRows] = useState([]);                    // cached candidates (read-time filtered server-side)
  const [computedAt, setComputedAt] = useState(null);
  const [refresh, setRefresh] = useState({ status: "idle" });  // idle | running | done | error
  const [lastScan, setLastScan] = useState(null);          // {checked, total, note} from the last refresh

  useEffect(() => { api("/axes").then(r => setAxes(r.ok ? r.data.filter(a => a.kind !== "my_publications") : [])); }, []);

  const scopeQS = () => `direction=${direction}${axisId ? `&axis_id=${axisId}` : ""}`;

  const load = React.useCallback(() => {
    api(`/gaps?${scopeQS()}`).then(r => {
      if (r.ok) { setRows(r.data.candidates || []); setComputedAt(r.data.computed_at); }
    });
  }, [direction, axisId]);

  useEffect(() => { setLastScan(null); load(); }, [load]);  // re-read the cache when the scope changes

  const runRefresh = async () => {
    setRefresh({ status: "running" }); setLastScan(null);
    const poll = (jobId) => api(`/gaps/refresh/${jobId}`).then(r => {
      if (!r.ok) { setRefresh({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") {
        setRefresh({ status: "done" });
        setLastScan({ checked: d.result.checked, total: d.result.total, note: d.result.note });
        load();
      } else if (d.status === "error") setRefresh({ status: "error", error: d.detail || "Gap-finder failed." });
      else setTimeout(() => poll(jobId), 2000);
    });
    const r = await apiPost("/gaps/refresh", { direction, axis_id: axisId ? Number(axisId) : null });
    if (!r.ok) { setRefresh({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };

  const add = async (row) => {
    const r = await apiPost("/gaps/add", { doi: row.doi, openalex_work_id: row.openalex_work_id, title: row.title });
    if (r.ok) { load(); if (onChanged) onChanged(); }  // re-GET: read-time filter drops the now-in-library row
  };
  const dismiss = async (row) => {
    const r = await apiPost("/gaps/dismiss", { openalex_work_id: row.openalex_work_id, doi: row.doi });
    if (r.ok) load();  // re-GET: read-time filter drops the dismissed row
  };

  const countLabel = (n) => direction === "forward" ? `cites ${n} of your papers` : `cited by ${n} of your papers`;
  const running = refresh.status === "running";
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Gaps in your library</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          {direction === "forward"
            ? <>Works that <b>cite several of your papers</b> but aren't in your library — newer work building on yours. The count is how many of <i>your</i> papers each one cites, not a measure of importance.</>
            : <>Works that <b>several of your papers cite</b> but aren't in your library yet — likely references worth adding. The count is how many of <i>your</i> papers cite each one, not a measure of importance.</>}
          {" "}<b>Add</b> imports the metadata; <b>Dismiss</b> hides it for good.
        </div>

        <div className="gaps-controls">
          <div className="tags-srcfilter">
            <button className={`tags-srcfilter-btn${direction === "backward" ? " on" : ""}`} onClick={() => setDirection("backward")}>Works you cite</button>
            <button className={`tags-srcfilter-btn${direction === "forward" ? " on" : ""}`} onClick={() => setDirection("forward")}>Works citing you</button>
          </div>
          <select className="lib-sort" value={axisId} onChange={e => setAxisId(e.target.value)} title="Scope to an axis">
            <option value="">All papers</option>
            {axes.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}
          </select>
          <button className="btn btn-primary" disabled={running} onClick={runRefresh}>{running ? "Scanning…" : "Refresh"}</button>
        </div>

        <div className="gaps-coverage">
          {computedAt
            ? `Last refreshed ${new Date(computedAt).toLocaleString()}.`
            : "Not computed yet for this scope — Refresh to scan."}
          {lastScan && ` Scanned ${lastScan.checked} of ${lastScan.total} papers (the rest have no DOI). ${lastScan.note}`}
        </div>

        {running && <ProgressBar label="Scanning your library against OpenAlex…" managedBy="backend-job" />}
        {refresh.status === "error" && <div className="axis-err">{refresh.error}</div>}
        {!running && computedAt && rows.length === 0 &&
          <div className="axis-hint">No gaps in this scope — everything related to several of your papers is already in your library.</div>}

        {rows.map(row => (
          <div key={row.openalex_work_id} className="gap-row">
            <div className="gap-row-info">
              <div className="gap-row-title">{row.title || row.doi}</div>
              <div className="gap-row-meta">
                <span className="gap-count">{countLabel(row.cited_by_in_library)}</span>
                {row.authors && row.authors.length > 0 && <> · {row.authors.slice(0, 3).join(", ")}{row.authors.length > 3 ? " et al." : ""}</>}
                {row.year ? ` · ${row.year}` : ""}
              </div>
            </div>
            <div className="gap-row-actions">
              <button className="axis-link" onClick={() => add(row)}>Add</button>
              <button className="axis-link" onClick={() => dismiss(row)}>Dismiss</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
