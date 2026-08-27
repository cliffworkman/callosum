// WIP manuscript browser and details surfaces. Manuscripts share the Library interaction grammar, but keep a
// separate data model and teal/badged visual mode so unpublished work cannot be mistaken for a published paper.
const WIP_STAGES = [
  ["idea", "Idea"], ["planning", "Planning"], ["data-collection", "Data collection"], ["analysis", "Analysis"],
  ["drafting", "Drafting"], ["internal-review", "Internal review"], ["preprint", "Preprint"],
  ["submitted", "Submitted"], ["revise-and-resubmit", "Revise and resubmit"], ["accepted", "Accepted"],
  ["published", "Published"], ["paused", "Paused"], ["abandoned", "Abandoned"],
];

function wipStageLabel(value) {
  const found = WIP_STAGES.find(item => item[0] === value);
  return found ? found[1] : String(value || "Idea").replace(/-/g, " ");
}

function wipWhen(value) {
  if (!value) return "No filesystem activity yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString([], { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

function WipRootSetup({ roots, scanning, onAdd, onRescan, onDeleteRoot }) {
  const [expanded, setExpanded] = useState(false);
  const [rootsShown, setRootsShown] = useState(false);
  const [path, setPath] = useState("");
  const [mode, setMode] = useState("folder");
  const [error, setError] = useState("");
  const [browsing, setBrowsing] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    setError("");
    const result = await onAdd({ path: path.trim(), discovery_mode: mode, excluded_children: [] });
    if (!result || !result.ok) { setError((result && result.error) || "Could not add this folder."); return; }
    setPath("");
    setExpanded(false);
  };
  const removeRoot = async (root) => {
    if (!window.confirm(`Stop watching "${root.path}"? Manuscripts already found here are kept, just no longer tracked by this location.`)) return;
    await onDeleteRoot(root.id);
  };
  return (
    <div className="wip-roots">
      <div className="wip-roots-summary">
        <button className="wip-roots-toggle" disabled={roots.length === 0} onClick={() => setRootsShown(value => !value)}>
          {roots.length} watched {roots.length === 1 ? "location" : "locations"}
        </button>
        <button className="btn-ghost" onClick={() => setExpanded(value => !value)}>+ Add location</button>
        <button className="btn-ghost" disabled={scanning || roots.length === 0} onClick={onRescan}>
          {scanning ? "Scanning…" : "Rescan"}
        </button>
      </div>
      {rootsShown && roots.length > 0 &&
        <div className="wip-roots-list">
          {roots.map(root => (
            <div className="wip-roots-row" key={root.id}>
              <code title={root.path}>{root.path}</code>
              <span className="wip-roots-mode">{root.discovery_mode === "children" ? "subfolders" : "one manuscript"}</span>
              <button className="btn-icon" title="Stop watching this location" aria-label={`Stop watching ${root.path}`}
                onClick={() => removeRoot(root)}>🗑</button>
            </div>
          ))}
        </div>}
      {expanded &&
        <form className="wip-root-form" onSubmit={submit}>
          <input value={path} onChange={event => setPath(event.target.value)}
            placeholder="Full path to a manuscript folder or a folder of WIPs" aria-label="WIP folder path" />
          <button type="button" className="btn-ghost" onClick={() => setBrowsing(true)}>Browse…</button>
          <select className="lib-sort" value={mode} onChange={event => setMode(event.target.value)}>
            <option value="folder">This folder is one manuscript</option>
            <option value="children">Immediate subfolders are manuscripts</option>
          </select>
          <button className="axis-btn" disabled={!path.trim()}>Add</button>
          <button type="button" className="btn-ghost" onClick={() => setExpanded(false)}>Cancel</button>
          {error && <div className="wip-root-error">{error}</div>}
        </form>}
      {browsing &&
        <FolderBrowserModal initialPath={path.trim() || undefined}
          onCancel={() => setBrowsing(false)}
          onSelect={chosen => { setPath(chosen); setBrowsing(false); }} />}
    </div>
  );
}

function WipCard({ manuscript, selected, onSelect, onOpen, onMenu }) {
  return (
    <article className={"paper wip-card" + (selected ? " sel" : "")}
      data-wip-id={manuscript.id}
      role="button" tabIndex={0} aria-label={`WIP manuscript: ${manuscript.display_title}`}
      onClick={() => onSelect(manuscript.id)}
      onDoubleClick={() => onOpen(manuscript)}
      onContextMenu={event => onMenu(event, manuscript)}
      onKeyDown={event => {
        if (event.key === "Enter") { event.preventDefault(); onOpen(manuscript); }
        if (event.key === " ") { event.preventDefault(); onSelect(manuscript.id); }
        if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
          const rect = event.currentTarget.getBoundingClientRect();
          onMenu(event, manuscript, { x: rect.left + 24, y: rect.top + 24 });
        }
      }}
      title="Work in progress — double-click to open; right-click for manuscript actions">
      <div className="wip-card-heading">
        <span className="wip-badge">WIP</span>
        <p className="paper-title">{manuscript.display_title}</p>
      </div>
      <div className="paper-meta">
        <span>{wipStageLabel(manuscript.stage)}</span>
        {manuscript.manuscript_type && <span>· {manuscript.manuscript_type.replace(/-/g, " ")}</span>}
        {manuscript.target_journal && <span>· {manuscript.target_journal}</span>}
      </div>
      <div className="paper-foot">
        <span className="wip-stage">{wipStageLabel(manuscript.stage)}</span>
        <span className="chip">{manuscript.file_count} file{manuscript.file_count === 1 ? "" : "s"}</span>
        {manuscript.open_task_count > 0 &&
          <span className="chip">{manuscript.open_task_count} open task{manuscript.open_task_count === 1 ? "" : "s"}</span>}
        {manuscript.unresolved_finding_count > 0 &&
          <span className="wip-warning">{manuscript.unresolved_finding_count} finding{manuscript.unresolved_finding_count === 1 ? "" : "s"}</span>}
        {manuscript.stale_check_count > 0 &&
          <span className="wip-warning">{manuscript.stale_check_count} stale check{manuscript.stale_check_count === 1 ? "" : "s"}</span>}
        {manuscript.missing_file_count > 0 &&
          <span className="wip-warning">{manuscript.missing_file_count} missing</span>}
        {manuscript.missing_primary_file && <span className="wip-warning">primary file missing</span>}
        {manuscript.state === "missing" && <span className="wip-warning">folder missing</span>}
        <span className="wip-modified">{wipWhen(manuscript.last_filesystem_activity_at)}</span>
      </div>
    </article>
  );
}

function WipBrowser({ wip, onOpen }) {
  const [menu, setMenu] = useState(null);
  const openMenu = (event, manuscript, position) => {
    event.preventDefault();
    event.stopPropagation();
    wip.setSelectedId(manuscript.id);
    if (wip.readOnly) return;
    setMenu({ manuscript, x: position ? position.x : event.clientX, y: position ? position.y : event.clientY });
  };
  return (
    <div className="pane-list-body wip-browser">
      <div className="pane-head">
        <div className="lib-head">
          <p className="eyebrow">Work in progress</p>
          <span className="wip-mode-label"><span className="wip-badge">WIP</span> Unpublished manuscripts</span>
        </div>
        {wip.readOnly ? <div className="axis-hint demo-wip-note">
          Saved synthetic manuscripts · browse, inspect sources, and open genuine saved check results. Changes and reruns require the local app.
        </div> : <WipRootSetup roots={wip.roots} scanning={wip.scanning} onAdd={wip.addRoot} onRescan={wip.rescan}
          onDeleteRoot={wip.deleteRoot} />}
        <WipFilters wip={wip} />
        {wip.status === "ready" && <div className="list-meta">{wip.manuscripts.length} shown</div>}
      </div>
      {wip.status === "loading" && <div className="state">Loading work in progress…</div>}
      {wip.status === "error" && <div className="errbox"><b>Can't load WIP.</b><br />{wip.error}</div>}
      {wip.status === "ready" && wip.manuscripts.length === 0 &&
        <div className="state">
          <div className="big">{wip.roots.length ? "No manuscripts match this view." : "Add a manuscript location."}</div>
          {wip.roots.length
            ? "Change the stage or state filters, or rescan the watched locations."
            : "Choose one manuscript folder, or a parent whose immediate subfolders are manuscripts."}
        </div>}
      {wip.status === "ready" && wip.manuscripts.map(item =>
        <WipCard key={item.id} manuscript={item} selected={wip.selectedId === item.id}
          onSelect={wip.setSelectedId} onOpen={onOpen} onMenu={openMenu} />)}
      {!wip.readOnly && <WipContextMenu menu={menu} onClose={() => setMenu(null)} onOpen={onOpen}
        onUpdate={wip.updateManuscript} onRescan={wip.rescan} onDelete={wip.deleteManuscript} />}
    </div>
  );
}

function WipStructure({ manuscriptId, sections, onReload, readOnly }) {
  const [name, setName] = useState("");
  const change = async (section, values) => {
    const result = await apiPatch(`/wip/manuscripts/${manuscriptId}/sections/${section.id}`, values);
    if (result.ok) onReload();
  };
  const move = async (index, delta) => {
    const next = sections.map(section => section.id);
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    const result = await apiPut(`/wip/manuscripts/${manuscriptId}/sections/order`, { section_ids: next });
    if (result.ok) onReload();
  };
  const add = async () => {
    if (!name.trim()) return;
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/sections`, { name: name.trim() });
    if (result.ok) { setName(""); onReload(); }
  };
  return (
    <section className="wip-work-view">
      <div className="wip-section-add">
        <input value={name} disabled={readOnly} onChange={event => setName(event.target.value)} placeholder="Add a custom section"
          onKeyDown={event => { if (event.key === "Enter") add(); }} />
        <button className="axis-btn" disabled={readOnly || !name.trim()} onClick={add}>Add Section</button>
      </div>
      {sections.map((section, index) =>
        <div className="wip-section-row" key={section.id}>
          <span className="wip-section-name">{section.name}</span>
          {section.content_detected && <span className="wip-detected">Content detected</span>}
          <select value={section.status} disabled={readOnly} onChange={event => change(section, { status: event.target.value })}>
            {["not-started", "outlined", "drafting", "complete", "needs-revision", "under-review", "approved", "not-applicable"]
              .map(status => <option key={status} value={status}>{status.replace(/-/g, " ")}</option>)}
          </select>
          <button className="btn-icon" title="Move section up" disabled={readOnly || index === 0} onClick={() => move(index, -1)}>↑</button>
          <button className="btn-icon" title="Move section down" disabled={readOnly || index === sections.length - 1} onClick={() => move(index, 1)}>↓</button>
          {section.is_custom &&
            <button className="btn-icon danger" title="Delete custom section"
              disabled={readOnly} onClick={async () => { const result = await apiDelete(`/wip/manuscripts/${manuscriptId}/sections/${section.id}`); if (result.ok) onReload(); }}>×</button>}
        </div>)}
    </section>
  );
}

function WipTasks({ manuscriptId, tasks, sections, onReload, readOnly }) {
  const [title, setTitle] = useState("");
  const [sectionId, setSectionId] = useState("");
  const add = async () => {
    if (!title.trim()) return;
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/tasks`, {
      title: title.trim(), section_id: sectionId ? Number(sectionId) : null,
    });
    if (result.ok) { setTitle(""); onReload(); }
  };
  return (
    <section className="wip-work-view">
      <div className="wip-task-add">
        <input value={title} disabled={readOnly} onChange={event => setTitle(event.target.value)} placeholder="Add a manuscript task"
          onKeyDown={event => { if (event.key === "Enter") add(); }} />
        <select value={sectionId} disabled={readOnly} onChange={event => setSectionId(event.target.value)}>
          <option value="">Whole Manuscript</option>
          {sections.map(section => <option key={section.id} value={section.id}>{section.name}</option>)}
        </select>
        <button className="axis-btn" disabled={readOnly || !title.trim()} onClick={add}>Add Task</button>
      </div>
      {tasks.length === 0 && <p className="axis-hint">No manuscript tasks.</p>}
      {tasks.map(task =>
        <div className={"wip-task-row" + (task.status === "complete" ? " complete" : "")} key={task.id}>
          <input type="checkbox" checked={task.status === "complete"} disabled={readOnly}
            onChange={async event => {
              const result = await apiPatch(`/wip/manuscripts/${manuscriptId}/tasks/${task.id}`,
                { status: event.target.checked ? "complete" : "open" });
              if (result.ok) onReload();
            }} />
          <span>{task.title}</span>
          <select value={task.status} disabled={readOnly} onChange={async event => {
            const result = await apiPatch(`/wip/manuscripts/${manuscriptId}/tasks/${task.id}`, { status: event.target.value });
            if (result.ok) onReload();
          }}>
            {["open", "in-progress", "blocked", "complete", "deferred", "cancelled"]
              .map(status => <option key={status} value={status}>{status.replace(/-/g, " ")}</option>)}
          </select>
          <button className="btn-icon danger" title="Delete task" disabled={readOnly}
            onClick={async () => { const result = await apiDelete(`/wip/manuscripts/${manuscriptId}/tasks/${task.id}`); if (result.ok) onReload(); }}>×</button>
        </div>)}
    </section>
  );
}

function WipReferences({ manuscriptId, references, onReload, onOpenPaper, readOnly }) {
  const [paperId, setPaperId] = useState("");
  const [relationship, setRelationship] = useState("possibly-cited");
  const [error, setError] = useState("");
  const add = async () => {
    const id = Number(paperId);
    if (!Number.isInteger(id) || id < 1) return;
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/references`,
      { paper_id: id, relationship_state: relationship });
    if (!result.ok) { setError(result.error || "Library paper not found."); return; }
    setPaperId(""); setError(""); onReload();
  };
  return (
    <section className="wip-work-view">
      <div className="wip-reference-add">
        <input inputMode="numeric" value={paperId} disabled={readOnly} onChange={event => setPaperId(event.target.value)}
          placeholder="Library paper ID" />
        <select value={relationship} disabled={readOnly} onChange={event => setRelationship(event.target.value)}>
          {["cited", "possibly-cited", "background-reading", "to-cite", "rejected-for-use", "needs-verification"]
            .map(state => <option key={state} value={state}>{state.replace(/-/g, " ")}</option>)}
        </select>
        <button className="axis-btn" disabled={readOnly || !paperId} onClick={add}>Link Paper</button>
      </div>
      {error && <div className="wip-root-error">{error}</div>}
      {references.length === 0 && <p className="axis-hint">No Library references linked yet.</p>}
      {references.map(reference =>
        <div className="wip-reference-row" key={reference.id}>
          <button className="btn-link" onClick={() => onOpenPaper && onOpenPaper({
            id: reference.paper_id, title: reference.paper_title,
          })}>{reference.paper_title}</button>
          <span>{reference.paper_year || ""}</span>
          <select value={reference.relationship_state} disabled={readOnly} onChange={async event => {
            const result = await apiPost(`/wip/manuscripts/${manuscriptId}/references`, {
              paper_id: reference.paper_id, relationship_state: event.target.value, notes: reference.notes,
            });
            if (result.ok) onReload();
          }}>
            {["cited", "possibly-cited", "background-reading", "to-cite", "rejected-for-use", "needs-verification"]
              .map(state => <option key={state} value={state}>{state.replace(/-/g, " ")}</option>)}
          </select>
          <button className="btn-icon danger" title="Unlink paper" disabled={readOnly}
            onClick={async () => { const result = await apiDelete(`/wip/manuscripts/${manuscriptId}/references/${reference.paper_id}`); if (result.ok) onReload(); }}>×</button>
        </div>)}
    </section>
  );
}

// inc 403: a compact, read-only history of Discover > Funding runs made against this manuscript (tagged via
// research_funding_profiles.source_kind/source_id -- see funding.py's _run_funding_job). Reuses the same
// .wip-checkpoint-* recipe WipChecks' "Content checkpoints" list already uses -- one visual language, no new CSS.
// Full results/reload live in Discover > Funding itself (its own "Recent runs" history already lists every run,
// WIP-sourced or not); this is a scoped view for "what has been searched for this manuscript," not a duplicate UI.
function WipFundingRuns({ runs }) {
  if (!runs || runs.length === 0) return null;
  return <section className="wip-work-view">
    <div className="wip-checkpoint-heading">
      <h3>Funding searches</h3>
      <p>Run from Discover → Funding while this manuscript was active. Open Discover → Funding's Recent runs for full results.</p>
    </div>
    {runs.map(run => {
      const counts = run.result_counts || {};
      return <div className="wip-checkpoint-row" key={run.run_id}>
        <div>
          <strong>{run.title || "Funding search"}</strong>
          <small>{counts.opportunities || 0} open · {counts.recurring_schemes || 0} recurring · {counts.prospects || 0} prospects</small>
        </div>
        <div className="wip-checkpoint-state">
          <time>{wipWhen(run.created_at)}</time>
        </div>
      </div>;
    })}
  </section>;
}

// inc 404: a compact, read-only history of Discover > Journals runs made against this manuscript -- a receipt
// only (topic/weighting/counts), never the full ranked profile list (re-run in Discover > Journals for that).
// Reuses the same .wip-checkpoint-* recipe as WipChecks/WipFundingRuns -- one visual language, no new CSS.
function WipJournalRuns({ runs }) {
  if (!runs || runs.length === 0) return null;
  return <section className="wip-work-view">
    <div className="wip-checkpoint-heading">
      <h3>Journal searches</h3>
      <p>Run from Discover → Journals while this manuscript was active. Re-run there to see the full ranked list.</p>
    </div>
    {runs.map(run => <div className="wip-checkpoint-row" key={run.id}>
      <div>
        <strong>{run.topic_id || "Journal search"}</strong>
        <small>{run.shown} of {run.considered} candidates shown · weighting {run.weighting}</small>
      </div>
      <div className="wip-checkpoint-state">
        <time>{wipWhen(run.created_at)}</time>
      </div>
    </div>)}
  </section>;
}

function WipDetails({ manuscript, onUpdate, onRelinked, onOpenPaper, workspace = false, externalRefresh }) {
  const readOnly = React.useContext(AppReadOnly);
  const [files, setFiles] = useState([]);
  const [activity, setActivity] = useState([]);
  const [sections, setSections] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [references, setReferences] = useState([]);
  const [snapshots, setSnapshots] = useState([]);
  const [checks, setChecks] = useState({ tools: [], runs: [] });
  const [fundingRuns, setFundingRuns] = useState([]);
  const [journalRuns, setJournalRuns] = useState([]);
  const [tab, setTab] = useState("overview");
  const [nonce, setNonce] = useState(0);
  const [draft, setDraft] = useState(manuscript || {});
  const [saving, setSaving] = useState(false);
  useEffect(() => { setDraft(manuscript || {}); }, [manuscript && manuscript.id, manuscript && manuscript.updated_at]);
  useEffect(() => {
    if (!manuscript) return;
    Promise.all([
      api(`/wip/manuscripts/${manuscript.id}/files`),
      api(`/wip/manuscripts/${manuscript.id}/activity`),
      api(`/wip/manuscripts/${manuscript.id}/sections`),
      api(`/wip/manuscripts/${manuscript.id}/tasks`),
      api(`/wip/manuscripts/${manuscript.id}/references`),
      api(`/wip/manuscripts/${manuscript.id}/snapshots`),
      api(`/wip/manuscripts/${manuscript.id}/checks`),
      api(`/wip/manuscripts/${manuscript.id}/funding-runs`),
      api(`/wip/manuscripts/${manuscript.id}/journal-runs`),
    ]).then(([fileResult, activityResult, sectionResult, taskResult, referenceResult, snapshotResult, checkResult, fundingResult, journalResult]) => {
      if (fileResult.ok) setFiles(fileResult.data || []);
      if (activityResult.ok) setActivity(activityResult.data || []);
      if (sectionResult.ok) setSections(sectionResult.data || []);
      if (taskResult.ok) setTasks(taskResult.data || []);
      if (referenceResult.ok) setReferences(referenceResult.data || []);
      if (snapshotResult.ok) setSnapshots(snapshotResult.data || []);
      if (checkResult.ok) setChecks(checkResult.data || { tools: [], runs: [] });
      if (fundingResult.ok) setFundingRuns(fundingResult.data.runs || []);
      if (journalResult.ok) setJournalRuns(journalResult.data.runs || []);
    });
    // externalRefresh (the shared wip.refresh counter) picks up a run/disposition change made from a concurrently
    // mounted sibling view of the same manuscript (e.g. the Methods-panel Statistics section, inc 402) -- both
    // sides bump it via ctx.onReloadWip/onRelinked, so either one triggers the other to refetch.
  }, [manuscript && manuscript.id, manuscript && manuscript.updated_at, nonce, externalRefresh]);
  if (!manuscript) return <div className="axis-hint">Select a WIP manuscript to see its details.</div>;
  const save = async () => {
    setSaving(true);
    await onUpdate(manuscript.id, {
      title_override: (draft.title_override || "").trim() || null,
      stage: draft.stage,
      manuscript_type: draft.manuscript_type,
      target_journal: (draft.target_journal || "").trim() || null,
      deadline: draft.deadline || null,
      notes: draft.notes || null,
    });
    setSaving(false);
  };
  // Structure/Tasks/References/Checks/file-role mutations only need this component's own sub-fetch effect to
  // re-run (setNonce) -- but the WIP browser's card list (file/task/finding/check counts) reads from a separate,
  // higher-level refresh counter (wip.refresh) that only the overview form's save() and WipRelink previously
  // bumped. Call onRelinked here too so every WIP mutation, not just those two, keeps the card list in sync.
  const reload = () => { setNonce(value => value + 1); if (onRelinked) onRelinked(); };
  const overview = <>
    <WipRelink manuscript={draft} onRelinked={row => {
      setDraft(row);
      if (onRelinked) onRelinked();
      reload();
    }} />
    <div className="wip-detail-grid">
      <label>Display title<input value={draft.title_override || ""} disabled={readOnly} placeholder={manuscript.derived_title}
        onChange={event => setDraft({ ...draft, title_override: event.target.value })} /></label>
      <label>Stage<select value={draft.stage || "idea"} disabled={readOnly} onChange={event => setDraft({ ...draft, stage: event.target.value })}>
        {WIP_STAGES.map(item => <option key={item[0]} value={item[0]}>{item[1]}</option>)}
      </select></label>
      <label>Manuscript type<input value={draft.manuscript_type || ""} disabled={readOnly}
        onChange={event => setDraft({ ...draft, manuscript_type: event.target.value })} /></label>
      <label>Target journal<input value={draft.target_journal || ""} disabled={readOnly}
        onChange={event => setDraft({ ...draft, target_journal: event.target.value })} /></label>
      <label>Deadline<input type="date" value={draft.deadline || ""} disabled={readOnly}
        onChange={event => setDraft({ ...draft, deadline: event.target.value })} /></label>
      <label className="wip-detail-wide">Notes<textarea rows={workspace ? 4 : 3} value={draft.notes || ""} disabled={readOnly}
        onChange={event => setDraft({ ...draft, notes: event.target.value })} /></label>
    </div>
    <button className="axis-btn" disabled={saving || readOnly} onClick={save}
      title={isDemoMode() ? "Manuscript changes require the local app." : undefined}>{saving ? "Saving…" : "Save Manuscript"}</button>
  </>;
  const fileView = <section className="wip-work-view">
    {files.length === 0 ? <p className="axis-hint">No files discovered.</p> :
      files.map(file => <div className="wip-file-row" key={file.id}>
        <span>{file.relative_path}</span>
        <select value={file.role} disabled={readOnly} onChange={async event => {
          const result = await apiPatch(`/wip/manuscripts/${manuscript.id}/files/${file.id}`, { role: event.target.value });
          if (result.ok) reload();
        }}>
          {["manuscript-candidate", "supplement", "cover-letter", "response-to-reviewers", "reporting-checklist",
            "figure", "table", "analysis-output", "other"].map(role =>
            <option key={role} value={role}>{role.replace(/-/g, " ")}</option>)}
          {file.is_primary && <option value="primary-manuscript">Primary Manuscript</option>}
        </select>
        <button className={"btn-ghost" + (file.is_primary ? " wip-primary" : "")}
          disabled={readOnly || file.existence_state !== "available"}
          onClick={async () => {
            const result = await apiPatch(`/wip/manuscripts/${manuscript.id}/files/${file.id}`, { is_primary: true });
            if (result.ok) reload();
          }}>{file.is_primary ? "Primary" : "Make Primary"}</button>
        <button className="btn-icon" title={readOnly ? "Opening the local manuscript file requires the local app." : "Open file"} disabled={readOnly}
          onClick={() => apiPost(`/wip/manuscripts/${manuscript.id}/files/${file.id}/open`, {})}>↗</button>
        <button className="btn-icon" title={readOnly ? "Revealing local files requires the local app." : "Reveal file in its folder"} disabled={readOnly}
          onClick={() => apiPost(`/wip/manuscripts/${manuscript.id}/files/${file.id}/reveal`, {})}>⌖</button>
      </div>)}
  </section>;
  const activityView = <section className="wip-work-view">
    {activity.length === 0 ? <p className="axis-hint">No activity recorded.</p> :
      activity.slice(0, workspace ? 100 : 6).map(event => <div className="wip-activity-row" key={event.id}>
        <span>{event.summary}</span><time>{wipWhen(event.created_at)}</time>
      </div>)}
  </section>;
  return (
    <div className={"wip-details" + (workspace ? " wip-workspace" : "")}>
      <header className="wip-detail-head">
        <span className="wip-badge">WIP</span>
        <div><h2>{manuscript.display_title}</h2><p>Unpublished manuscript workspace</p></div>
      </header>
      {workspace ? <>
        {isDemoMode() && <div className="settings-note">
          Synthetic public-demo manuscript. Its structure, tasks, linked sources, detector receipts, and provenance
          are genuine saved Callosum state; editing, rerunning, and local file actions require the installed app.
        </div>}
        <div className="tags-srcfilter wip-work-tabs" role="tablist">
          {["overview", "structure", "tasks", "files", "references", "checks", "activity"].map(value =>
            <button key={value} className={"tags-srcfilter-btn" + (tab === value ? " on" : "")}
              onClick={() => setTab(value)}>{value[0].toUpperCase() + value.slice(1)}</button>)}
        </div>
        {tab === "overview" && overview}
        {tab === "structure" && <WipStructure manuscriptId={manuscript.id} sections={sections} onReload={reload} readOnly={readOnly} />}
        {tab === "tasks" && <WipTasks manuscriptId={manuscript.id} tasks={tasks} sections={sections} onReload={reload} readOnly={readOnly} />}
        {tab === "files" && fileView}
        {tab === "references" && <WipReferences manuscriptId={manuscript.id} references={references}
          onReload={reload} onOpenPaper={onOpenPaper} readOnly={readOnly} />}
        {tab === "checks" && <>
          <WipChecks manuscriptId={manuscript.id} snapshots={snapshots} checks={checks} onReload={reload} />
          <WipFundingRuns runs={fundingRuns} />
          <WipJournalRuns runs={journalRuns} />
          <WipMetaReferenceList manuscriptId={manuscript.id} onOpenPaper={onOpenPaper} onReload={reload} refreshKey={nonce} />
        </>}
        {tab === "activity" && activityView}
      </> : <>
        {overview}
        <section className="wip-detail-section"><h3>Files</h3>{fileView}</section>
        <section className="wip-detail-section"><h3>Recent activity</h3>{activityView}</section>
      </>}
    </div>
  );
}
