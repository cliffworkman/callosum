// WIP collection query state and manuscript-specific facets. Kept separate from the shared card/details renderer
// so the WIP browser can offer its own schema without inheriting irrelevant Library reference filters.
const WIP_EMPTY_FILTERS = {
  manuscriptType: "", targetJournal: "", deadline: "", modifiedDays: "",
  hasOpenTasks: false, hasUnresolvedFindings: false, hasStaleChecks: false, missingPrimary: false,
};

function useWipWorkspace({ enabled }) {
  const [state, setState] = useState({ status: "idle", manuscripts: [], roots: [], error: null });
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState("");
  const [workspaceState, setWorkspaceState] = useState("active");
  const [sort, setSort] = useState(() => _loadLayout("callosum.wip.sort", "activity"));
  const [filters, setFilters] = useState(WIP_EMPTY_FILTERS);
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
    if (filters.manuscriptType.trim()) params.set("manuscript_type", filters.manuscriptType.trim());
    if (filters.targetJournal.trim()) params.set("target_journal", filters.targetJournal.trim());
    if (filters.deadline) params.set("deadline", filters.deadline);
    if (filters.modifiedDays) params.set("modified_days", filters.modifiedDays);
    if (filters.hasOpenTasks) params.set("has_open_tasks", "true");
    if (filters.hasUnresolvedFindings) params.set("has_unresolved_findings", "true");
    if (filters.hasStaleChecks) params.set("has_stale_checks", "true");
    if (filters.missingPrimary) params.set("missing_primary", "true");
    params.set("sort", sort);
    const [items, roots] = await Promise.all([api("/wip/manuscripts?" + params), api("/wip/watch-roots")]);
    if (!items.ok || !roots.ok) {
      setState(prev => ({ ...prev, status: "error", error: items.error || roots.error || "Could not load WIP." }));
      return;
    }
    setState({ status: "ready", manuscripts: items.data || [], roots: roots.data || [], error: null });
  }, [enabled, query, stage, workspaceState, sort, filters, refresh]);

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

  const deleteManuscript = useCallback(async (id) => {
    const result = await apiDelete(`/wip/manuscripts/${id}`);
    if (result.ok) {
      setRefresh(n => n + 1);
      setSelectedId(current => (current === id ? null : current));
    }
    return result;
  }, []);

  const deleteRoot = useCallback(async (id) => {
    const result = await apiDelete(`/wip/watch-roots/${id}`);
    if (result.ok) setRefresh(n => n + 1);
    return result;
  }, []);

  const selected = state.manuscripts.find(item => item.id === selectedId) || null;
  return {
    ...state, enabled, query, setQuery, stage, setStage, workspaceState, setWorkspaceState, sort, filters, setFilters,
    setSort: value => { setSort(value); _saveLayout("callosum.wip.sort", value); },
    selectedId, setSelectedId, selected, scanning, rescan, addRoot, updateManuscript, deleteManuscript, deleteRoot,
    refresh, reload: () => setRefresh(n => n + 1),
  };
}

function WipFilterToggle({ active, label, onClick }) {
  return <button className={"lib-facet-toggle" + (active ? " on" : "")}
    aria-pressed={active} onClick={onClick}>{label}</button>;
}

function WipFilters({ wip }) {
  const patch = values => wip.setFilters(current => ({ ...current, ...values }));
  const active = Object.values(wip.filters).some(Boolean);
  return <div className="wip-query">
    <div className="searchbar">
      <input placeholder="Search manuscript title, type, journal, or notes…" value={wip.query}
        onChange={event => wip.setQuery(event.target.value)} spellCheck={false} />
      <select className="lib-sort" value={wip.stage} onChange={event => wip.setStage(event.target.value)}>
        <option value="">All stages</option>
        {WIP_STAGES.map(item => <option key={item[0]} value={item[0]}>{item[1]}</option>)}
      </select>
      <select className="lib-sort" value={wip.workspaceState}
        onChange={event => wip.setWorkspaceState(event.target.value)}>
        <option value="active">Active</option><option value="paused">Paused</option>
        <option value="archived">Archived</option><option value="missing">Missing folder</option>
        <option value="">All states</option>
      </select>
      <span className="lib-sort-label">Sort</span>
      <select className="lib-sort" value={wip.sort} onChange={event => wip.setSort(event.target.value)}>
        <option value="activity">Last modified</option><option value="title">Title</option>
        <option value="stage">Stage</option><option value="deadline">Deadline</option>
        <option value="created">Created</option><option value="open_tasks">Open tasks</option>
        <option value="unresolved_findings">Unresolved findings</option>
      </select>
    </div>
    <div className="wip-facets">
      <input aria-label="Filter by manuscript type" placeholder="Manuscript type" value={wip.filters.manuscriptType}
        onChange={event => patch({ manuscriptType: event.target.value })} />
      <input aria-label="Filter by target journal" placeholder="Target journal" value={wip.filters.targetJournal}
        onChange={event => patch({ targetJournal: event.target.value })} />
      <select aria-label="Filter by deadline" value={wip.filters.deadline}
        onChange={event => patch({ deadline: event.target.value })}>
        <option value="">Any deadline</option><option value="overdue">Overdue</option>
        <option value="next-30-days">Next 30 days</option><option value="none">No deadline</option>
      </select>
      <select aria-label="Filter by modified date" value={wip.filters.modifiedDays}
        onChange={event => patch({ modifiedDays: event.target.value })}>
        <option value="">Modified anytime</option><option value="7">Past 7 days</option>
        <option value="30">Past 30 days</option><option value="90">Past 90 days</option>
      </select>
      <WipFilterToggle label="Open tasks" active={wip.filters.hasOpenTasks}
        onClick={() => patch({ hasOpenTasks: !wip.filters.hasOpenTasks })} />
      <WipFilterToggle label="Unresolved findings" active={wip.filters.hasUnresolvedFindings}
        onClick={() => patch({ hasUnresolvedFindings: !wip.filters.hasUnresolvedFindings })} />
      <WipFilterToggle label="Stale checks" active={wip.filters.hasStaleChecks}
        onClick={() => patch({ hasStaleChecks: !wip.filters.hasStaleChecks })} />
      <WipFilterToggle label="Missing primary" active={wip.filters.missingPrimary}
        onClick={() => patch({ missingPrimary: !wip.filters.missingPrimary })} />
      {active && <button className="axis-link" onClick={() => wip.setFilters(WIP_EMPTY_FILTERS)}>Clear filters</button>}
    </div>
  </div>;
}
