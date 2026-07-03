// The "Extract" center-tab — the meta-analysis extraction workspace (workbench SP2a-1, inc 253).
// Assemble a dataset from your library: a project (template) -> rows (one effect, optionally linked to a paper) ->
// provenance-anchored cells -> convert each row via the SP1 converter -> export a metafor/JASP-ready CSV + a
// provenance audit. Extract/structure/convert/export only — it never pools/models (that's metafor/JASP/RevMan).
const WB_DESIGNS = [
  { key: "two_group_continuous", label: "Two-group continuous (means + SDs → Hedges' g)" },
  { key: "binary_2x2", label: "Binary 2×2 (→ log OR / RR / risk difference)" },
  { key: "correlation", label: "Correlation (→ Fisher's z)" },
];

function WorkbenchPane({ active, onOpenPdf, capture, onArmCapture, onCaptureApplied }) {
  const [projects, setProjects] = useState([]);
  const [project, setProject] = useState(null); // the full view, or null on the picker
  const [newName, setNewName] = useState("");
  const [newDesign, setNewDesign] = useState("two_group_continuous");
  const [addQuery, setAddQuery] = useState("");
  const [addResults, setAddResults] = useState([]);
  const [anchor, setAnchor] = useState(null); // {rowId, key, page, quote} while the anchor popover is open
  const [err, setErr] = useState("");
  const [convMsg, setConvMsg] = useState(""); // transient "Converted k of N" summary after Convert-all
  const [aiStatus, setAiStatus] = useState(null); // GET /settings — gates the Draft button
  const [aiErr, setAiErr] = useState("");
  const [draftingRow, setDraftingRow] = useState(null);

  const loadProjects = async () => { const r = await api("/workbench/projects"); if (r.ok) setProjects(r.data); };
  const openProject = async (id) => { const r = await api("/workbench/projects/" + id); if (r.ok) { setConvMsg(""); setAiErr(""); setProject(r.data); } };

  useEffect(() => { if (active && !project) loadProjects(); }, [active]);
  // AI readiness for the "Draft from PDF" funnel (the existing AI-surface pattern — 20_synthesis.jsx). A cloud
  // provider needs egress consent + a key; the builtin `local` (loopback) needs neither.
  useEffect(() => { if (active) api("/settings").then(r => { if (r.ok && r.data) setAiStatus(r.data); }); }, [active]);

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

  // --- rows + cells (optimistic local updates; PUT replaces the whole cell, so we merge to preserve the anchor).
  // A cell edit also drops the row's stored effect size (the server clears it too) — never a silently-stale g. ---
  const putCell = async (rowId, key, patch) => {
    setConvMsg("");  // editing a cell clears that row's effect → the batch note no longer reflects reality
    const row = project.rows.find(r => r.id === rowId);
    const cur = (row && row.cells[key]) || {};
    const merged = { value: cur.value ?? null, page: cur.page ?? null, quote: cur.quote ?? null, bbox_json: cur.bbox_json ?? null, ...patch };
    setProject(p => ({
      ...p,
      rows: p.rows.map(r => r.id !== rowId ? r : { ...r, converted: null, cells: { ...r.cells, [key]: { ...(r.cells[key] || {}), ...merged } } }),
    }));
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
    setConvMsg("");  // a single-row convert changes the coverage — drop the batch note so it can't go stale
    const r = await apiPost(`/workbench/rows/${rowId}/convert`, {});
    if (r.ok) setProject(p => ({ ...p, rows: p.rows.map(x => x.id === rowId ? { ...x, converted: r.data } : x) }));
    else setErr(r.error || "Fill the required fields with valid numbers first.");
  };
  // Convert-all: run the SP1 converter across the whole dataset in one click. Rows lacking valid inputs are left
  // honestly un-converted (named, never fabricated); nothing is pooled. Re-open to refresh, then show the summary.
  const convertAll = async () => {
    const r = await apiPost(`/workbench/projects/${project.id}/convert-all`, {});
    if (!r.ok) { setErr(r.error || "Couldn't convert the dataset."); return; }
    await openProject(project.id);
    const incs = r.data.incomplete || [];
    setErr("");
    let msg = `Converted ${r.data.converted} of ${r.data.total} row${r.data.total === 1 ? "" : "s"}.`;
    if (incs.length) {
      // name the rows that still need inputs (the data's already here) — a count alone leaves you hunting.
      const names = incs.slice(0, 6).map(it => it.label || "untitled row");
      const more = incs.length > 6 ? ` +${incs.length - 6} more` : "";
      msg += ` Still need valid inputs: ${names.join(", ")}${more}.`;
    }
    setConvMsg(msg);
  };

  const aiReady = !!aiStatus && (aiStatus.provider === "local" || (aiStatus.data_egress_enabled && aiStatus.api_key_set));

  // Draft candidates for a row's empty structured cells (one blocking egress-gated call). The proposals ride back on
  // the row; nothing enters a trusted cell until the human accepts (facts ≠ candidates).
  const draftRow = async (row) => {
    setAiErr(""); setDraftingRow(row.id);
    const r = await apiPost(`/workbench/rows/${row.id}/propose`, {});
    setDraftingRow(null);
    if (!r.ok) { setAiErr(r.error || "Couldn't draft from the PDF."); return; }
    const props = r.data.proposals || [];
    setProject(p => ({ ...p, rows: p.rows.map(x => x.id === row.id ? { ...x, proposals: props } : x) }));
    if (!props.length) setAiErr("No empty structured cells to draft — clear or add a cell first.");
    else if (r.data.truncated) setAiErr("Note: this PDF is long, so only its first part was sent to the AI.");
  };
  const acceptProposal = async (proposal, value) => {
    const r = await apiPost(`/workbench/proposals/${proposal.id}/accept`, value === undefined ? {} : { value });
    if (r.ok) { setConvMsg(""); setProject(r.data); } else setAiErr(r.error || "Couldn't accept the candidate.");
  };
  const rejectProposal = async (proposal) => {
    const r = await apiPost(`/workbench/proposals/${proposal.id}/reject`, {});
    if (r.ok) setProject(r.data); else setAiErr(r.error || "Couldn't reject the candidate.");
  };
  // Verify a candidate against the source BEFORE accepting: exact draws the rect; region/unanchored scroll only.
  const openProposalAnchor = (row, proposal) => {
    onOpenPdf({ id: row.paper_id, title: row.paper_title || ("Paper " + row.paper_id) },
      { id: `wbp:${proposal.id}`, paperId: row.paper_id, page: proposal.page,
        precision: proposal.anchor_state === "exact" ? "exact" : "region",
        bboxJson: proposal.anchor_state === "exact" ? proposal.bbox_json : null, quote: proposal.quote || null });
  };

  const searchPapers = async (q) => {
    setAddQuery(q);
    if (!q.trim()) { setAddResults([]); return; }
    const r = await api("/papers?q=" + encodeURIComponent(q.trim()) + "&limit=8");
    if (r.ok) setAddResults(r.data.items || r.data || []);
  };

  const saveAnchor = async () => {
    const page = anchor.page === "" ? null : Number(anchor.page);
    // a hand-entered anchor has no bbox → clear any stale bbox so precision honestly falls back to region.
    await putCell(anchor.rowId, anchor.key, { page: Number.isFinite(page) ? page : null, quote: anchor.quote || null, bbox_json: null });
    setAnchor(null);
  };
  // 📎 opens the cell's anchor hub: select-in-PDF (the primary capture), manual page+quote, and — once anchored —
  // "Open at anchor" (exact if a bbox was captured, else region — invariant #2, derived from what provenance exists).
  const openAnchor = (row, key, cell) => {
    setAnchor({ rowId: row.id, key, page: (cell && cell.page) || "", quote: (cell && cell.quote) || "",
      hasCell: !!(cell && (cell.page != null || cell.value)) });
  };
  // Arm "select in PDF" for a cell: the parent opens the paper; the next text selection there flows back to putCell.
  const armCapture = (row, key) => {
    if (row.paper_id == null) return;
    setAnchor(null);
    const f = (project.template || []).find(x => x.key === key) || {};
    onArmCapture({
      paper: { id: row.paper_id, title: row.paper_title || ("Paper " + row.paper_id) },
      paperId: row.paper_id, projectId: project.id, rowId: row.id, fieldKey: key,
      fieldLabel: f.label || key, page: (row.cells[key] && row.cells[key].page) || null,
    });
  };
  const armFromPopover = () => {
    const row = project.rows.find(r => r.id === anchor.rowId);
    if (row) armCapture(row, anchor.key);
  };
  const openAtAnchor = () => {
    const row = project.rows.find(r => r.id === anchor.rowId);
    if (!row || row.paper_id == null) return;
    const cell = row.cells[anchor.key] || {};
    onOpenPdf({ id: row.paper_id, title: row.paper_title || ("Paper " + row.paper_id) },
      { id: `wb:${row.id}:${anchor.key}`, paperId: row.paper_id, page: cell.page,
        precision: cell.bbox_json ? "exact" : "region", bboxJson: cell.bbox_json || null, quote: cell.quote || null });
    setAnchor(null);
  };
  // A captured selection arrived for this project → write it into the cell: value = the verbatim selected text
  // (capped + human-editable, never parsed/inferred), its page + quote, and the union bbox as bbox_json → an EXACT
  // anchor. onCaptureApplied clears the shared state (→ this fires once; the guard no-ops on the clear).
  useEffect(() => {
    if (!capture || !capture.result || !project || capture.projectId !== project.id) return;
    const { rowId, fieldKey, result } = capture;
    putCell(rowId, fieldKey, {
      value: (result.quote || "").slice(0, 500) || null,
      page: result.page ?? null,
      quote: (result.quote || "").slice(0, 4000) || null,
      bbox_json: result.bbox ? JSON.stringify([result.bbox]) : null,
    });
    onCaptureApplied();
  }, [capture]);

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
  const convertedCount = project.rows.filter(r => r.converted).length;
  const exportUrl = (fmt) => `/workbench/projects/${project.id}/export?format=${fmt}`;
  return (
    <div className="wb-pane">
      <div className="wb-head">
        <button className="btn-link" onClick={() => { setProject(null); loadProjects(); }}>← Projects</button>
        <input className="wb-name" defaultValue={project.name} key={"name" + project.id}
          onBlur={e => e.target.value.trim() && apiPatch("/workbench/projects/" + project.id, { name: e.target.value.trim() })} />
        <span className="wb-meta">{project.design.replace(/_/g, " ")}</span>
        {project.rows.length > 0 &&
          <button className="btn-link" title="Convert every row that has valid inputs" onClick={convertAll}>Convert all →</button>}
        {project.rows.length > 0 &&
          <span className="wb-meta">{convertedCount} of {project.rows.length} converted</span>}
        <span className="wb-spacer" />
        <span className="wb-meta">Export</span>
        <button className="btn-link" title="The general dataset: your columns + the converted effect size + variance"
          onClick={() => downloadAsset(exportUrl("csv"), `extraction-${project.id}.csv`)}>CSV</button>
        <button className="btn-link" title="Clean yi/vi table — in R: read.csv(...) then rma(yi, vi, data=dat)"
          onClick={() => downloadAsset(exportUrl("metafor"), `extraction-${project.id}-metafor.csv`)}>metafor</button>
        <button className="btn-link" title="Raw per-group study data in RevMan's import columns for this design (RevMan computes the effect)"
          onClick={() => downloadAsset(exportUrl("revman"), `extraction-${project.id}-revman.csv`)}>RevMan</button>
        <button className="btn-link" title="Provenance audit (JSON): every cell's page + quote — your source trail"
          onClick={() => downloadAsset(exportUrl("audit"), `extraction-${project.id}-provenance.json`)}>provenance</button>
      </div>
      <textarea className="wb-protocol" placeholder="Protocol note (question, inclusion criteria)…" defaultValue={project.protocol_note || ""}
        key={"proto" + project.id} onBlur={e => apiPatch("/workbench/projects/" + project.id, { protocol_note: e.target.value })} />
      {convMsg && <div className="wb-note">{convMsg}</div>}
      {err && <div className="axis-err">{err}</div>}
      {aiErr && <div className="wb-note wb-ai-note">{aiErr}</div>}
      {draftingRow && <ProgressBar />}

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
                    ? <div className="wb-src-linked">
                        <button className="btn-link" title="Open the PDF" onClick={() => onOpenPdf({ id: row.paper_id, title: row.paper_title })}>{row.paper_title || ("Paper " + row.paper_id)}</button>
                        <WbDraftButton row={row} aiReady={aiReady} busy={draftingRow === row.id} onDraft={() => draftRow(row)} />
                      </div>
                    : <input className="wb-label" defaultValue={row.label || ""} placeholder="(label)" key={"lbl" + row.id}
                        onBlur={e => apiPatch("/workbench/rows/" + row.id, { label: e.target.value })} />}
                </td>
                {fields.map(f => {
                  const cell = row.cells[f.key] || {};
                  const armed = capture && !capture.result && capture.rowId === row.id && capture.fieldKey === f.key;
                  const cand = (row.proposals || []).find(p => p.field_key === f.key);
                  const showCand = cand && !(cell.value && String(cell.value).trim());
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
                        <button className={"wb-anchor" + (cell.page != null ? " set" : "") + (armed ? " arming" : "")}
                          title={armed ? "Selecting in the PDF…"
                            : cell.page != null ? `p. ${cell.page} · ${cell.bbox_json ? "exact" : "region"}${cell.quote ? " · " + cell.quote : ""} — anchor`
                            : "Anchor: select in the PDF, or enter a page"}
                          onClick={() => openAnchor(row, f.key, cell)}>📎</button>}
                      {showCand &&
                        <WbCandidate proposal={cand}
                          onAccept={(v) => acceptProposal(cand, v)}
                          onReject={() => rejectProposal(cand)}
                          onOpen={() => openProposalAnchor(row, cand)} />}
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
            <button className="btn btn-primary wb-anchor-select" onClick={armFromPopover}>◎ Select the value in the PDF</button>
            <div className="wb-anchor-or">— or enter it by hand (page-level) —</div>
            <label>Page <input className="wb-in" type="number" min="1" value={anchor.page} onChange={e => setAnchor(a => ({ ...a, page: e.target.value }))} /></label>
            <label>Quote <input className="wb-in" placeholder="the reported text…" value={anchor.quote} onChange={e => setAnchor(a => ({ ...a, quote: e.target.value }))} /></label>
            <div className="wb-anchor-actions">
              <button className="btn btn-primary" onClick={saveAnchor}>Save anchor</button>
              {anchor.hasCell && <button className="btn-link" onClick={openAtAnchor}>Open at anchor →</button>}
              <button className="btn-link" onClick={() => setAnchor(null)}>Cancel</button>
            </div>
          </div>
        </div>}
    </div>
  );
}
