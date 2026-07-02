// The "Extract" center-tab — the meta-analysis extraction workspace (workbench SP2a-1, inc 253).
// Assemble a dataset from your library: a project (template) -> rows (one effect, optionally linked to a paper) ->
// provenance-anchored cells -> convert each row via the SP1 converter -> export a metafor/JASP-ready CSV + a
// provenance audit. Extract/structure/convert/export only — it never pools/models (that's metafor/JASP/RevMan).
const WB_DESIGNS = [
  { key: "two_group_continuous", label: "Two-group continuous (means + SDs → Hedges' g)" },
  { key: "binary_2x2", label: "Binary 2×2 (→ log OR / RR / risk difference)" },
  { key: "correlation", label: "Correlation (→ Fisher's z)" },
];

function WorkbenchPane({ active, onOpenPdf }) {
  const [projects, setProjects] = useState([]);
  const [project, setProject] = useState(null); // the full view, or null on the picker
  const [newName, setNewName] = useState("");
  const [newDesign, setNewDesign] = useState("two_group_continuous");
  const [addQuery, setAddQuery] = useState("");
  const [addResults, setAddResults] = useState([]);
  const [anchor, setAnchor] = useState(null); // {rowId, key, page, quote} while the anchor popover is open
  const [err, setErr] = useState("");

  const loadProjects = async () => { const r = await api("/workbench/projects"); if (r.ok) setProjects(r.data); };
  const openProject = async (id) => { const r = await api("/workbench/projects/" + id); if (r.ok) setProject(r.data); };

  useEffect(() => { if (active && !project) loadProjects(); }, [active]);

  const fail = (r) => { if (!r.ok) setErr(r.error || "Something went wrong."); return r.ok; };

  const createProject = async () => {
    if (!newName.trim()) return;
    const r = await apiPost("/workbench/projects", { name: newName.trim(), design: newDesign });
    if (fail(r)) { setNewName(""); setProject(r.data); loadProjects(); }
  };
  const removeProject = async (id) => {
    if (!window.confirm("Delete this project and all its rows?")) return;
    const r = await apiDelete("/workbench/projects/" + id);
    if (fail(r)) { setProject(null); loadProjects(); }
  };

  // --- rows + cells (optimistic local updates; PUT replaces the whole cell, so we merge to preserve the anchor) ---
  const patchCellLocal = (rowId, key, patch) => setProject(p => ({
    ...p,
    rows: p.rows.map(r => r.id !== rowId ? r : { ...r, cells: { ...r.cells, [key]: { ...(r.cells[key] || {}), ...patch } } }),
  }));
  const putCell = async (rowId, key, patch) => {
    const row = project.rows.find(r => r.id === rowId);
    const cur = (row && row.cells[key]) || {};
    const merged = { value: cur.value ?? null, page: cur.page ?? null, quote: cur.quote ?? null, bbox_json: cur.bbox_json ?? null, ...patch };
    patchCellLocal(rowId, key, merged);
    fail(await apiPut(`/workbench/rows/${rowId}/cells/${key}`, merged));
  };
  const addRow = async (paperId) => {
    const r = await apiPost(`/workbench/projects/${project.id}/rows`, paperId ? { paper_id: paperId } : {});
    if (fail(r)) { setProject(r.data); setAddResults([]); setAddQuery(""); }
  };
  const removeRow = async (rowId) => {
    const r = await apiDelete("/workbench/rows/" + rowId);
    if (fail(r)) openProject(project.id);
  };
  const convertRow = async (rowId) => {
    const r = await apiPost(`/workbench/rows/${rowId}/convert`, {});
    if (r.ok) setProject(p => ({ ...p, rows: p.rows.map(x => x.id === rowId ? { ...x, converted: r.data } : x) }));
    else setErr(r.error || "Fill the required fields with valid numbers first.");
  };

  const searchPapers = async (q) => {
    setAddQuery(q);
    if (!q.trim()) { setAddResults([]); return; }
    const r = await api("/papers?q=" + encodeURIComponent(q.trim()) + "&limit=8");
    if (r.ok) setAddResults(r.data.items || r.data || []);
  };

  const saveAnchor = async () => {
    const page = anchor.page === "" ? null : Number(anchor.page);
    await putCell(anchor.rowId, anchor.key, { page: Number.isFinite(page) ? page : null, quote: anchor.quote || null });
    setAnchor(null);
  };
  const openAnchor = (row, key, cell) => {
    if (cell && cell.page != null && row.paper_id != null) {
      onOpenPdf({ id: row.paper_id, title: row.paper_title || ("Paper " + row.paper_id) },
        { id: `wb:${row.id}:${key}`, paperId: row.paper_id, page: cell.page, precision: "region" });
    } else {
      setAnchor({ rowId: row.id, key, page: (cell && cell.page) || "", quote: (cell && cell.quote) || "" });
    }
  };

  const addColumn = async () => {
    const label = window.prompt("New column label (a moderator / notes column):");
    if (!label || !label.trim()) return;
    const key = label.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 60) || ("c" + Date.now());
    const template = [...project.template, { key, label: label.trim(), type: "text", role: null }];
    fail(await apiPatch("/workbench/projects/" + project.id, { template }));
    openProject(project.id);
  };

  // --- render: picker -------------------------------------------------------------------------------------------
  if (!project) {
    return (
      <div className="wb-pane">
        <div className="wb-intro">Assemble a meta-analysis dataset from your library, anchor each value to its source, and convert + export it. It <b>extracts and converts one study at a time</b> — pooling, heterogeneity, and forest plots belong to your synthesis tool (metafor / JASP / RevMan).</div>
        {err && <div className="axis-err">{err}</div>}
        <div className="wb-newproj">
          <input className="wb-in" placeholder="New project name…" value={newName}
            onChange={e => setNewName(e.target.value)} onKeyDown={e => e.key === "Enter" && createProject()} />
          <select className="wb-in" value={newDesign} onChange={e => setNewDesign(e.target.value)}>
            {WB_DESIGNS.map(d => <option key={d.key} value={d.key}>{d.label}</option>)}
          </select>
          <button className="btn btn-primary" onClick={createProject}>Create project</button>
        </div>
        <ul className="wb-projects">
          {projects.length === 0 && <li className="wb-empty">No projects yet — create one above.</li>}
          {projects.map(p => (
            <li key={p.id} className="wb-project-row">
              <button className="btn-link wb-open" onClick={() => openProject(p.id)}>{p.name}</button>
              <span className="wb-meta">{p.design.replace(/_/g, " ")} · {p.row_count} row{p.row_count === 1 ? "" : "s"}</span>
              <button className="btn-link wb-del" onClick={() => removeProject(p.id)}>delete</button>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  // --- render: a project ----------------------------------------------------------------------------------------
  const fields = project.template;
  return (
    <div className="wb-pane">
      <div className="wb-head">
        <button className="btn-link" onClick={() => { setProject(null); loadProjects(); }}>← Projects</button>
        <input className="wb-name" defaultValue={project.name} key={"name" + project.id}
          onBlur={e => e.target.value.trim() && apiPatch("/workbench/projects/" + project.id, { name: e.target.value.trim() })} />
        <span className="wb-meta">{project.design.replace(/_/g, " ")}</span>
        <span className="wb-spacer" />
        <button className="btn-link" onClick={() => downloadAsset(`/workbench/projects/${project.id}/export?format=csv`, `extraction-${project.id}.csv`)}>Export CSV</button>
        <button className="btn-link" onClick={() => downloadAsset(`/workbench/projects/${project.id}/export?format=audit`, `extraction-${project.id}-provenance.json`)}>Provenance JSON</button>
      </div>
      <textarea className="wb-protocol" placeholder="Protocol note (question, inclusion criteria)…" defaultValue={project.protocol_note || ""}
        key={"proto" + project.id} onBlur={e => apiPatch("/workbench/projects/" + project.id, { protocol_note: e.target.value })} />
      {err && <div className="axis-err">{err}</div>}

      <div className="wb-gridwrap">
        <table className="wb-grid">
          <thead>
            <tr>
              <th className="wb-src">Source</th>
              {fields.map(f => <th key={f.key} title={f.role ? "converter input" : "moderator/notes"}>{f.label}</th>)}
              <th className="wb-eff">Effect size</th>
              <th className="wb-colbtn"><button className="btn-link" title="Add a moderator/notes column" onClick={addColumn}>+ col</button></th>
            </tr>
          </thead>
          <tbody>
            {project.rows.map(row => (
              <tr key={row.id}>
                <td className="wb-src">
                  {row.paper_id != null
                    ? <button className="btn-link" title="Open the PDF" onClick={() => onOpenPdf({ id: row.paper_id, title: row.paper_title })}>{row.paper_title || ("Paper " + row.paper_id)}</button>
                    : <input className="wb-label" defaultValue={row.label || ""} placeholder="(label)" key={"lbl" + row.id}
                        onBlur={e => apiPatch("/workbench/rows/" + row.id, { label: e.target.value })} />}
                </td>
                {fields.map(f => {
                  const cell = row.cells[f.key] || {};
                  return (
                    <td key={f.key} className="wb-cell">
                      {f.type === "choice"
                        ? <select className="wb-cellin" value={cell.value || (f.options && f.options[0]) || ""}
                            onChange={e => putCell(row.id, f.key, { value: e.target.value })}>
                            {(f.options || []).map(o => <option key={o} value={o}>{o}</option>)}
                          </select>
                        : <input className="wb-cellin" defaultValue={cell.value || ""} key={"c" + row.id + f.key + (cell.value || "")}
                            inputMode={f.type === "number" ? "decimal" : "text"}
                            onBlur={e => e.target.value !== (cell.value || "") && putCell(row.id, f.key, { value: e.target.value || null })} />}
                      {row.paper_id != null &&
                        <button className={"wb-anchor" + (cell.page != null ? " set" : "")}
                          title={cell.page != null ? `p. ${cell.page}${cell.quote ? " · " + cell.quote : ""} — open` : "Anchor to a page + quote"}
                          onClick={() => openAnchor(row, f.key, cell)}>📎</button>}
                    </td>
                  );
                })}
                <td className="wb-eff">
                  {row.converted
                    ? <span className="wb-conv" title={`Var ${row.converted.variance}`}>{row.converted.metric} = <b>{row.converted.value}</b></span>
                    : <button className="btn-link" onClick={() => convertRow(row.id)}>Convert →</button>}
                </td>
                <td className="wb-colbtn"><button className="wb-rowx" title="Remove row" onClick={() => removeRow(row.id)}>×</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="wb-add">
        <button className="btn-link" onClick={() => addRow(null)}>+ Add row (no paper)</button>
        <span className="wb-addpaper">
          <input className="wb-in" placeholder="+ Add paper — search your library…" value={addQuery} onChange={e => searchPapers(e.target.value)} />
          {addResults.length > 0 &&
            <div className="wb-addresults">
              {addResults.map(p => <button key={p.id} className="wb-addhit" onClick={() => addRow(p.id)}>{p.title}</button>)}
            </div>}
        </span>
      </div>
      <div className="wb-note">Every value is yours to enter and anchor to its source — the workspace converts and exports the dataset, it never pools or synthesizes.</div>

      {anchor &&
        <div className="wb-anchor-pop" onClick={() => setAnchor(null)}>
          <div className="wb-anchor-box" onClick={e => e.stopPropagation()}>
            <div className="wb-anchor-title">Anchor this value to its source</div>
            <label>Page <input className="wb-in" type="number" min="1" value={anchor.page} onChange={e => setAnchor(a => ({ ...a, page: e.target.value }))} /></label>
            <label>Quote <input className="wb-in" placeholder="the reported text…" value={anchor.quote} onChange={e => setAnchor(a => ({ ...a, quote: e.target.value }))} /></label>
            <div className="wb-anchor-actions">
              <button className="btn btn-primary" onClick={saveAnchor}>Save anchor</button>
              <button className="btn-link" onClick={() => setAnchor(null)}>Cancel</button>
            </div>
          </div>
        </div>}
    </div>
  );
}
