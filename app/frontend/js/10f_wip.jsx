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

function useWipWorkspace({ enabled }) {
  const [state, setState] = useState({ status: "idle", manuscripts: [], roots: [], error: null });
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState("");
  const [workspaceState, setWorkspaceState] = useState("active");
  const [sort, setSort] = useState(() => _loadLayout("callosum.wip.sort", "activity"));
  const [selectedId, setSelectedId] = useState(null);
  const [refresh, setRefresh] = useState(0);
  const [scanning, setScanning] = useState(false);

  const load = useCallback(async () => {
    if (!enabled) return;
    setState(prev => ({ ...prev, status: prev.manuscripts.length ? "ready" : "loading", error: null }));
    const params = new URLSearchParams();
    if (query.trim()) params.set("query", query.trim());
    if (stage) params.set("stage", stage);
    if (workspaceState) params.set("state", workspaceState);
    params.set("sort", sort);
    const [items, roots] = await Promise.all([api("/wip/manuscripts?" + params), api("/wip/watch-roots")]);
    if (!items.ok || !roots.ok) {
      setState(prev => ({ ...prev, status: "error", error: items.error || roots.error || "Could not load WIP." }));
      return;
    }
    setState({ status: "ready", manuscripts: items.data || [], roots: roots.data || [], error: null });
  }, [enabled, query, stage, workspaceState, sort, refresh]);

  useEffect(() => { load(); }, [load]);

  const pollScan = useCallback(async (jobId) => {
    for (let attempt = 0; attempt < 80; attempt += 1) {
      const result = await api(`/wip/scan/${jobId}`);
      if (!result.ok || (result.data && ["done", "error"].includes(result.data.status))) {
        setScanning(false);
        setRefresh(n => n + 1);
        return result;
      }
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    setScanning(false);
    return { ok: false, error: "The WIP scan is still running." };
  }, []);

  const rescan = useCallback(async () => {
    if (!enabled || scanning) return;
    setScanning(true);
    const result = await apiPost("/wip/rescan", {});
    if (!result.ok) { setScanning(false); return result; }
    return pollScan(result.data.job_id);
  }, [enabled, scanning, pollScan]);

  useEffect(() => {
    if (!enabled) return undefined;
    rescan();
    const onFocus = () => rescan();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [enabled]); // one launch/focus scan; rescan identity is intentionally excluded

  const addRoot = useCallback(async (values) => {
    const result = await apiPost("/wip/watch-roots", values);
    if (!result.ok) return result;
    setRefresh(n => n + 1);
    setScanning(true);
    const scan = await apiPost(`/wip/watch-roots/${result.data.id}/scan`, {});
    if (!scan.ok) { setScanning(false); return scan; }
    return pollScan(scan.data.job_id);
  }, [pollScan]);

  const updateManuscript = useCallback(async (id, values) => {
    const result = await apiPatch(`/wip/manuscripts/${id}`, values);
    if (result.ok) setRefresh(n => n + 1);
    return result;
  }, []);

  const selected = state.manuscripts.find(item => item.id === selectedId) || null;
  return {
    ...state, enabled, query, setQuery, stage, setStage, workspaceState, setWorkspaceState, sort,
    setSort: value => { setSort(value); _saveLayout("callosum.wip.sort", value); },
    selectedId, setSelectedId, selected, scanning, rescan, addRoot, updateManuscript, reload: () => setRefresh(n => n + 1),
  };
}

function WipRootSetup({ roots, scanning, onAdd, onRescan }) {
  const [expanded, setExpanded] = useState(false);
  const [path, setPath] = useState("");
  const [mode, setMode] = useState("folder");
  const [error, setError] = useState("");
  const submit = async (event) => {
    event.preventDefault();
    setError("");
    const result = await onAdd({ path: path.trim(), discovery_mode: mode, excluded_children: [] });
    if (!result || !result.ok) { setError((result && result.error) || "Could not add this folder."); return; }
    setPath("");
    setExpanded(false);
  };
  return (
    <div className="wip-roots">
      <div className="wip-roots-summary">
        <span>{roots.length} watched {roots.length === 1 ? "location" : "locations"}</span>
        <button className="btn-ghost" onClick={() => setExpanded(value => !value)}>+ Add location</button>
        <button className="btn-ghost" disabled={scanning || roots.length === 0} onClick={onRescan}>
          {scanning ? "Scanning…" : "Rescan"}
        </button>
      </div>
      {expanded &&
        <form className="wip-root-form" onSubmit={submit}>
          <input value={path} onChange={event => setPath(event.target.value)}
            placeholder="Full path to a manuscript folder or a folder of WIPs" aria-label="WIP folder path" />
          <select className="lib-sort" value={mode} onChange={event => setMode(event.target.value)}>
            <option value="folder">This folder is one manuscript</option>
            <option value="children">Immediate subfolders are manuscripts</option>
          </select>
          <button className="axis-btn" disabled={!path.trim()}>Add</button>
          <button type="button" className="btn-ghost" onClick={() => setExpanded(false)}>Cancel</button>
          {error && <div className="wip-root-error">{error}</div>}
        </form>}
    </div>
  );
}

function WipCard({ manuscript, selected, onSelect, onOpen }) {
  return (
    <article className={"paper wip-card" + (selected ? " sel" : "")}
      data-wip-id={manuscript.id}
      onClick={() => onSelect(manuscript.id)}
      onDoubleClick={() => onOpen(manuscript)}
      title="Work in progress — double-click to open the manuscript workspace">
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
        {manuscript.missing_file_count > 0 &&
          <span className="wip-warning">{manuscript.missing_file_count} missing</span>}
        {manuscript.state === "missing" && <span className="wip-warning">folder missing</span>}
        <span className="wip-modified">{wipWhen(manuscript.last_filesystem_activity_at)}</span>
      </div>
    </article>
  );
}

function WipBrowser({ wip, onOpen }) {
  return (
    <div className="pane-list-body wip-browser">
      <div className="pane-head">
        <div className="lib-head">
          <p className="eyebrow">Work in progress</p>
          <span className="wip-mode-label"><span className="wip-badge">WIP</span> Unpublished manuscripts</span>
        </div>
        <WipRootSetup roots={wip.roots} scanning={wip.scanning} onAdd={wip.addRoot} onRescan={wip.rescan} />
        <div className="searchbar">
          <input placeholder="Search manuscript title, journal, or notes…" value={wip.query}
            onChange={event => wip.setQuery(event.target.value)} spellCheck={false} />
          <select className="lib-sort" value={wip.stage} onChange={event => wip.setStage(event.target.value)}>
            <option value="">All stages</option>
            {WIP_STAGES.map(item => <option key={item[0]} value={item[0]}>{item[1]}</option>)}
          </select>
          <select className="lib-sort" value={wip.workspaceState}
            onChange={event => wip.setWorkspaceState(event.target.value)}>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="archived">Archived</option>
            <option value="missing">Missing</option>
            <option value="">All states</option>
          </select>
          <span className="lib-sort-label">Sort</span>
          <select className="lib-sort" value={wip.sort} onChange={event => wip.setSort(event.target.value)}>
            <option value="activity">Last modified</option>
            <option value="title">Title</option>
            <option value="stage">Stage</option>
            <option value="deadline">Deadline</option>
            <option value="created">Created</option>
          </select>
        </div>
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
          onSelect={wip.setSelectedId} onOpen={onOpen} />)}
    </div>
  );
}

function WipStructure({ manuscriptId, sections, onReload }) {
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
        <input value={name} onChange={event => setName(event.target.value)} placeholder="Add a custom section"
          onKeyDown={event => { if (event.key === "Enter") add(); }} />
        <button className="axis-btn" disabled={!name.trim()} onClick={add}>Add section</button>
      </div>
      {sections.map((section, index) =>
        <div className="wip-section-row" key={section.id}>
          <span className="wip-section-name">{section.name}</span>
          {section.content_detected && <span className="wip-detected">Content detected</span>}
          <select value={section.status} onChange={event => change(section, { status: event.target.value })}>
            {["not-started", "outlined", "drafting", "complete", "needs-revision", "under-review", "approved", "not-applicable"]
              .map(status => <option key={status} value={status}>{status.replace(/-/g, " ")}</option>)}
          </select>
          <button className="btn-icon" title="Move section up" disabled={index === 0} onClick={() => move(index, -1)}>↑</button>
          <button className="btn-icon" title="Move section down" disabled={index === sections.length - 1} onClick={() => move(index, 1)}>↓</button>
          {section.is_custom &&
            <button className="btn-icon danger" title="Delete custom section"
              onClick={async () => { const result = await apiDelete(`/wip/manuscripts/${manuscriptId}/sections/${section.id}`); if (result.ok) onReload(); }}>×</button>}
        </div>)}
    </section>
  );
}

function WipTasks({ manuscriptId, tasks, sections, onReload }) {
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
        <input value={title} onChange={event => setTitle(event.target.value)} placeholder="Add a manuscript task"
          onKeyDown={event => { if (event.key === "Enter") add(); }} />
        <select value={sectionId} onChange={event => setSectionId(event.target.value)}>
          <option value="">Whole manuscript</option>
          {sections.map(section => <option key={section.id} value={section.id}>{section.name}</option>)}
        </select>
        <button className="axis-btn" disabled={!title.trim()} onClick={add}>Add task</button>
      </div>
      {tasks.length === 0 && <p className="axis-hint">No manuscript tasks.</p>}
      {tasks.map(task =>
        <div className={"wip-task-row" + (task.status === "complete" ? " complete" : "")} key={task.id}>
          <input type="checkbox" checked={task.status === "complete"}
            onChange={async event => {
              const result = await apiPatch(`/wip/manuscripts/${manuscriptId}/tasks/${task.id}`,
                { status: event.target.checked ? "complete" : "open" });
              if (result.ok) onReload();
            }} />
          <span>{task.title}</span>
          <select value={task.status} onChange={async event => {
            const result = await apiPatch(`/wip/manuscripts/${manuscriptId}/tasks/${task.id}`, { status: event.target.value });
            if (result.ok) onReload();
          }}>
            {["open", "in-progress", "blocked", "complete", "deferred", "cancelled"]
              .map(status => <option key={status} value={status}>{status.replace(/-/g, " ")}</option>)}
          </select>
          <button className="btn-icon danger" title="Delete task"
            onClick={async () => { const result = await apiDelete(`/wip/manuscripts/${manuscriptId}/tasks/${task.id}`); if (result.ok) onReload(); }}>×</button>
        </div>)}
    </section>
  );
}

function WipReferences({ manuscriptId, references, onReload, onOpenPaper }) {
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
        <input inputMode="numeric" value={paperId} onChange={event => setPaperId(event.target.value)}
          placeholder="Library paper ID" />
        <select value={relationship} onChange={event => setRelationship(event.target.value)}>
          {["cited", "possibly-cited", "background-reading", "to-cite", "rejected-for-use", "needs-verification"]
            .map(state => <option key={state} value={state}>{state.replace(/-/g, " ")}</option>)}
        </select>
        <button className="axis-btn" disabled={!paperId} onClick={add}>Link paper</button>
      </div>
      {error && <div className="wip-root-error">{error}</div>}
      {references.length === 0 && <p className="axis-hint">No Library references linked yet.</p>}
      {references.map(reference =>
        <div className="wip-reference-row" key={reference.id}>
          <button className="btn-link" onClick={() => onOpenPaper && onOpenPaper({
            id: reference.paper_id, title: reference.paper_title,
          })}>{reference.paper_title}</button>
          <span>{reference.paper_year || ""}</span>
          <select value={reference.relationship_state} onChange={async event => {
            const result = await apiPost(`/wip/manuscripts/${manuscriptId}/references`, {
              paper_id: reference.paper_id, relationship_state: event.target.value, notes: reference.notes,
            });
            if (result.ok) onReload();
          }}>
            {["cited", "possibly-cited", "background-reading", "to-cite", "rejected-for-use", "needs-verification"]
              .map(state => <option key={state} value={state}>{state.replace(/-/g, " ")}</option>)}
          </select>
          <button className="btn-icon danger" title="Unlink paper"
            onClick={async () => { const result = await apiDelete(`/wip/manuscripts/${manuscriptId}/references/${reference.paper_id}`); if (result.ok) onReload(); }}>×</button>
        </div>)}
    </section>
  );
}

function WipChecks({ manuscriptId, snapshots, checks, onReload }) {
  const [creating, setCreating] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const createCheckpoint = async () => {
    setCreating(true);
    setError("");
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/snapshots`, {});
    setCreating(false);
    if (result.ok) onReload();
    else setError(result.error || "Could not create checkpoint.");
  };
  const runStatcheck = async () => {
    setRunning(true);
    setError("");
    const result = await apiPost(`/wip/manuscripts/${manuscriptId}/checks/statcheck`, {});
    setRunning(false);
    if (result.ok) onReload();
    else setError(result.error || "Statcheck could not run.");
  };
  return <section className="wip-work-view">
    <div className="wip-check-head">
      <div>
        <h3>Deterministic checks</h3>
        <p>Each run names its exact checkpoint, tool version, coverage, and reviewable findings.</p>
      </div>
      <div className="wip-check-actions">
        <button className="btn-ghost" disabled={creating} onClick={createCheckpoint}>
          {creating ? "Creating…" : "Create checkpoint"}
        </button>
        <button className="axis-btn" disabled={running} onClick={runStatcheck}>
          {running ? "Running…" : "Run statcheck"}
        </button>
      </div>
    </div>
    {running && <ProgressBar />}
    {error && <div className="wip-root-error">{error}</div>}
    {(checks.runs || []).length === 0 ? <p className="axis-hint">
      No checks run yet. An empty history is not a clean manuscript.
    </p> : checks.runs.map(run => <div className="wip-tool-run" key={run.id}>
      <div className="wip-tool-run-head">
        <strong>{run.tool_id}</strong>
        <span className={`wip-identity-${run.validity}`}>{run.validity.replace(/-/g, " ")}</span>
        <time>{wipWhen(run.executed_at)}</time>
      </div>
      <p>{run.result_summary}</p>
      <small>v{run.tool_version} · snapshot {run.snapshot_id} · {run.coverage}</small>
      {(run.findings || []).map(finding => <div className="wip-finding-row" key={finding.id}>
        <div>
          <strong>Candidate</strong> <span>{finding.summary}</span>
          <button className="btn-link" onClick={async () => {
            const result = await apiPost(
              `/wip/manuscripts/${manuscriptId}/files/${finding.file_id}/open`, {},
            );
            if (!result.ok) setError(result.error || "Could not open the source file.");
          }}>Open source file</button>
        </div>
        <select value={finding.disposition || "open"} onChange={async event => {
          const result = await apiPatch(`/wip/findings/${finding.id}`, { disposition: event.target.value });
          if (result.ok) onReload();
          else setError(result.error || "Could not update the finding.");
        }}>
          {["open", "acknowledged", "resolved", "dismissed", "false-positive", "deferred", "superseded"]
            .map(value => <option key={value} value={value}>{value.replace(/-/g, " ")}</option>)}
        </select>
        <blockquote>{finding.quote}</blockquote>
        <p>{finding.context}</p>
        <small>Reported {finding.details_json.reported_p}; recomputed p = {finding.details_json.computed_p}</small>
      </div>)}
    </div>)}
    <div className="wip-checkpoint-heading">
      <h3>Content checkpoints</h3>
      <p>Exact local hashes and bounded context; never a copy of the manuscript file.</p>
    </div>
    {snapshots.length === 0 ? <p className="axis-hint">No content checkpoints yet.</p> :
      snapshots.map(snapshot => <div className="wip-checkpoint-row" key={snapshot.id}>
        <div>
          <strong>{snapshot.reason.replace(/-/g, " ")}</strong>
          {snapshot.reason_detail && <span>{snapshot.reason_detail}</span>}
          <small>{snapshot.extraction_provider} {snapshot.extraction_version} · {snapshot.extracted_char_count.toLocaleString()} extracted characters</small>
        </div>
        <div className="wip-checkpoint-state">
          <span className={`wip-identity-${snapshot.identity_status}`}>{snapshot.identity_status.replace(/-/g, " ")}</span>
          <time>{wipWhen(snapshot.created_at)}</time>
        </div>
        <p>{snapshot.status_detail}</p>
      </div>)}
    <p className="axis-hint">No tool result is implied by a content checkpoint. Deterministic checks will appear here after they run.</p>
  </section>;
}

function WipDetails({ manuscript, onUpdate, onOpenPaper, workspace = false }) {
  const [files, setFiles] = useState([]);
  const [activity, setActivity] = useState([]);
  const [sections, setSections] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [references, setReferences] = useState([]);
  const [snapshots, setSnapshots] = useState([]);
  const [checks, setChecks] = useState({ tools: [], runs: [] });
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
    ]).then(([fileResult, activityResult, sectionResult, taskResult, referenceResult, snapshotResult, checkResult]) => {
      if (fileResult.ok) setFiles(fileResult.data || []);
      if (activityResult.ok) setActivity(activityResult.data || []);
      if (sectionResult.ok) setSections(sectionResult.data || []);
      if (taskResult.ok) setTasks(taskResult.data || []);
      if (referenceResult.ok) setReferences(referenceResult.data || []);
      if (snapshotResult.ok) setSnapshots(snapshotResult.data || []);
      if (checkResult.ok) setChecks(checkResult.data || { tools: [], runs: [] });
    });
  }, [manuscript && manuscript.id, manuscript && manuscript.updated_at, nonce]);
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
  const reload = () => setNonce(value => value + 1);
  const overview = <>
    <div className="wip-detail-grid">
      <label>Display title<input value={draft.title_override || ""} placeholder={manuscript.derived_title}
        onChange={event => setDraft({ ...draft, title_override: event.target.value })} /></label>
      <label>Stage<select value={draft.stage || "idea"} onChange={event => setDraft({ ...draft, stage: event.target.value })}>
        {WIP_STAGES.map(item => <option key={item[0]} value={item[0]}>{item[1]}</option>)}
      </select></label>
      <label>Manuscript type<input value={draft.manuscript_type || ""}
        onChange={event => setDraft({ ...draft, manuscript_type: event.target.value })} /></label>
      <label>Target journal<input value={draft.target_journal || ""}
        onChange={event => setDraft({ ...draft, target_journal: event.target.value })} /></label>
      <label>Deadline<input type="date" value={draft.deadline || ""}
        onChange={event => setDraft({ ...draft, deadline: event.target.value })} /></label>
      <label className="wip-detail-wide">Notes<textarea rows={workspace ? 4 : 3} value={draft.notes || ""}
        onChange={event => setDraft({ ...draft, notes: event.target.value })} /></label>
    </div>
    <button className="axis-btn" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save manuscript"}</button>
  </>;
  const fileView = <section className="wip-work-view">
    {files.length === 0 ? <p className="axis-hint">No files discovered.</p> :
      files.map(file => <div className="wip-file-row" key={file.id}>
        <span>{file.relative_path}</span>
        <select value={file.role} onChange={async event => {
          const result = await apiPatch(`/wip/manuscripts/${manuscript.id}/files/${file.id}`, { role: event.target.value });
          if (result.ok) reload();
        }}>
          {["manuscript-candidate", "supplement", "cover-letter", "response-to-reviewers", "reporting-checklist",
            "figure", "table", "analysis-output", "other"].map(role =>
            <option key={role} value={role}>{role.replace(/-/g, " ")}</option>)}
          {file.is_primary && <option value="primary-manuscript">primary manuscript</option>}
        </select>
        <button className={"btn-ghost" + (file.is_primary ? " wip-primary" : "")}
          disabled={file.existence_state !== "available"}
          onClick={async () => {
            const result = await apiPatch(`/wip/manuscripts/${manuscript.id}/files/${file.id}`, { is_primary: true });
            if (result.ok) reload();
          }}>{file.is_primary ? "Primary" : "Make primary"}</button>
        <button className="btn-icon" title="Open file"
          onClick={() => apiPost(`/wip/manuscripts/${manuscript.id}/files/${file.id}/open`, {})}>↗</button>
        <button className="btn-icon" title="Reveal file in its folder"
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
        <div className="tags-srcfilter wip-work-tabs" role="tablist">
          {["overview", "structure", "tasks", "files", "references", "checks", "activity"].map(value =>
            <button key={value} className={"tags-srcfilter-btn" + (tab === value ? " on" : "")}
              onClick={() => setTab(value)}>{value[0].toUpperCase() + value.slice(1)}</button>)}
        </div>
        {tab === "overview" && overview}
        {tab === "structure" && <WipStructure manuscriptId={manuscript.id} sections={sections} onReload={reload} />}
        {tab === "tasks" && <WipTasks manuscriptId={manuscript.id} tasks={tasks} sections={sections} onReload={reload} />}
        {tab === "files" && fileView}
        {tab === "references" && <WipReferences manuscriptId={manuscript.id} references={references}
          onReload={reload} onOpenPaper={onOpenPaper} />}
        {tab === "checks" && <WipChecks manuscriptId={manuscript.id} snapshots={snapshots}
          checks={checks} onReload={reload} />}
        {tab === "activity" && activityView}
      </> : <>
        {overview}
        <section className="wip-detail-section"><h3>Files</h3>{fileView}</section>
        <section className="wip-detail-section"><h3>Recent activity</h3>{activityView}</section>
      </>}
    </div>
  );
}
