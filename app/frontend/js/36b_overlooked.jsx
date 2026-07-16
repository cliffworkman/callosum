// Overlooked-work lens (backlog #37) — a sibling of the gap-finder. Per axis, surfaces external works highly
// relevant to that axis but under-cited for their vintage ("the Matthew effect, inverted"). Distinct from the
// citation-equity per-paper "Overlooked work" card (08b): this is a library-level DISCOVERY lens, keyed on an axis.
//
// Honesty posture: two SEPARABLE visible inputs per row — axis `relevance` (local cosine similarity) and citations
// vs. a same-vintage percentile — shown side by side and NEVER fused into one score. Framed honestly: relevant +
// low-cited-for-its-year = possibly overlooked, possibly just low-impact; your call (silence-not-a-certificate).
// Pull-not-push (you open it, per axis); Add/Dismiss are the user's (augment-never-filter) and reuse the gap flow.
// Cached per axis (GET /overlooked?axis_id=); Refresh recomputes (POST /overlooked/refresh). Clones the GapsModal shell.

function OverlookedLensModal({ onClose, onChanged }) {
  const [axisId, setAxisId] = useState("");                // required — the lens is per-axis
  const [axes, setAxes] = useState([]);
  const [rows, setRows] = useState([]);                    // cached candidates (read-time filtered server-side)
  const [computedAt, setComputedAt] = useState(null);
  const [refresh, setRefresh] = useState({ status: "idle" });  // idle | running | done | error

  useEffect(() => { api("/axes").then(r => setAxes(r.ok ? r.data.filter(a => a.kind !== "my_publications") : [])); }, []);

  const load = React.useCallback(() => {
    if (!axisId) { setRows([]); setComputedAt(null); return; }
    api(`/overlooked?axis_id=${axisId}`).then(r => {
      if (r.ok) { setRows(r.data.candidates || []); setComputedAt(r.data.computed_at); }
    });
  }, [axisId]);

  useEffect(() => { load(); }, [load]);  // re-read the cache when the axis changes

  const runRefresh = async () => {
    if (!axisId) return;
    setRefresh({ status: "running" });
    const poll = (jobId) => api(`/overlooked/refresh/${jobId}`).then(r => {
      if (!r.ok) { setRefresh({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setRefresh({ status: "done" }); load(); }
      else if (d.status === "error") setRefresh({ status: "error", error: d.detail || "Overlooked-work scan failed." });
      else setTimeout(() => poll(jobId), 2000);
    });
    const r = await apiPost("/overlooked/refresh", { axis_id: Number(axisId) });
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

  const axisLabel = (axes.find(a => String(a.id) === String(axisId)) || {}).label || "this axis";
  const pct = (p) => (p === null || p === undefined) ? null : Math.round(p * 100);
  const running = refresh.status === "running";
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Possibly overlooked work</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          External works <b>relevant to {axisId ? <i>{axisLabel}</i> : "an axis"}</b> that are <b>under-cited for their
          year</b> — work the field may have overlooked. Each row shows two <b>separate</b> signals: how relevant it is
          to the axis, and how its citations compare to same-year work on the topic. Low citations can mean the field
          overlooked it — or that it's simply low-impact; <b>your call</b>. <b>Add</b> imports the metadata;
          {" "}<b>Dismiss</b> hides it for good. Inspired by the <i>Matthew effect in science</i> (Merton, 1968).
        </div>

        <div className="gaps-controls">
          <select className="lib-sort" value={axisId} onChange={e => setAxisId(e.target.value)} title="Choose an axis">
            <option value="">Choose an axis…</option>
            {axes.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}
          </select>
          <button className="btn btn-primary" disabled={running || !axisId} onClick={runRefresh}>{running ? "Scanning…" : "Refresh"}</button>
        </div>

        <div className="gaps-coverage">
          {!axisId
            ? "Choose an axis to look for overlooked work relevant to it."
            : computedAt
              ? `Last refreshed ${new Date(computedAt).toLocaleString()}.`
              : "Not computed yet for this axis — Refresh to scan OpenAlex for this topic's works."}
        </div>

        {running && <ProgressBar label="Scanning this topic's works against OpenAlex…" />}
        {refresh.status === "error" && <div className="axis-err">{refresh.error}</div>}
        {!running && axisId && computedAt && rows.length === 0 &&
          <div className="axis-hint">Nothing surfaced for this axis — that isn't evidence none exists; low citations can just mean low-impact, and only works with enough same-year peers to rank are shown.</div>}

        {rows.map(row => (
          <div key={row.openalex_work_id} className="gap-row">
            <div className="gap-row-info">
              <div className="gap-row-title">
                {row.doi ? <a className="ref-source-link" href={`https://doi.org/${row.doi}`} target="_blank" rel="noopener noreferrer">{row.title || row.doi}</a> : (row.title || row.openalex_work_id)}
              </div>
              <div className="gap-row-meta">
                <span className="gap-count" title={`Local cosine similarity of this work's abstract to ${axisLabel} — a checkable relevance signal, not a verdict`}>relevance {Number(row.relevance).toFixed(2)}</span>
                {" "}
                <span className="gap-count" title="Citations vs. same-year works on this topic — low = under-cited for its vintage">
                  cited {row.cited_by_count}{pct(row.year_percentile) !== null && row.year ? ` · ${pct(row.year_percentile)}th percentile for ${row.year}` : ""}
                </span>
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
