function FundingRunHistory({ runs, currentRunId, loadState, onReload, onRefresh }) {
  if (!runs || !runs.length) return null;
  return (
    <details className="funding-run-history">
      <summary>
        <span>Recent runs</span>
        <button type="button" className="btn btn-ghost" onClick={(e) => { e.preventDefault(); onRefresh(); }}>
          Refresh
        </button>
      </summary>
      <div className="funding-run-list">
        {runs.map(run => {
          const counts = run.result_counts || {};
          const active = currentRunId === run.run_id;
          const loading = loadState.status === "running" && loadState.runId === run.run_id;
          const title = run.title || (run.source_kind === "manual" ? "Manual research description" : "Funding run");
          return (
            <div className={"funding-run-row" + (active ? " active" : "")} key={run.run_id}>
              <div>
                <b>{title}</b>
                <span>
                  Run {run.run_id}{run.created_at ? " - " + run.created_at : ""} ·
                  {" "}{counts.opportunities || 0} open · {counts.recurring_schemes || 0} recurring ·
                  {" "}{counts.prospects || 0} prospects
                </span>
                {run.llm_annotated_count > 0 && <small>{run.llm_annotated_count} persisted AI-fit label{run.llm_annotated_count === 1 ? "" : "s"}.</small>}
              </div>
              <button type="button" className="btn btn-sm" disabled={loading || active} onClick={() => onReload(run.run_id)}>
                {active ? "Loaded" : loading ? "Loading..." : "Reload"}
              </button>
            </div>
          );
        })}
      </div>
    </details>
  );
}

function FundingSaveButton({ kind, id, savedItem, onSaved }) {
  const [state, setState] = useState("idle");
  useEffect(() => {
    setState("idle");
  }, [kind, id, savedItem && savedItem.id]);
  const save = async () => {
    setState("saving");
    const r = await apiPost("/funding-discovery/save", { item_kind: kind, canonical_item_id: id });
    setState(r.ok ? "saved" : "error");
    if (r.ok && onSaved) onSaved();
  };
  const unsave = async () => {
    if (!savedItem) return;
    setState("unsaving");
    const r = await apiDelete(`/funding-discovery/saved/${savedItem.id}`);
    setState(r.ok ? "idle" : "error");
    if (r.ok && onSaved) onSaved();
  };
  if (savedItem) {
    return (
      <div className="funding-card-save">
        <span className="funding-card-saved">Saved</span>
        <button type="button" className="btn btn-ghost" onClick={unsave} disabled={state === "unsaving"}
          aria-label={`Unsave ${kind} from funding workflow`}>
          {state === "unsaving" ? "Removing..." : state === "error" ? "Remove failed" : "Unsave"}
        </button>
      </div>
    );
  }
  if (state === "saved") {
    return (
      <div className="funding-card-save">
        <span className="funding-card-saved">Saved</span>
      </div>
    );
  }
  return (
    <button type="button" className="btn btn-sm" onClick={save} disabled={state === "saving" || state === "saved"}>
      {state === "saved" ? "Saved" : state === "saving" ? "Saving..." : "Save"}
    </button>
  );
}

function FundingUnsaveButton({ item, onUnsaved }) {
  const [state, setState] = useState("idle");
  const unsave = async () => {
    setState("saving");
    const r = await apiDelete(`/funding-discovery/saved/${item.id}`);
    setState(r.ok ? "done" : "error");
    if (r.ok && onUnsaved) onUnsaved();
  };
  return (
    <button type="button" className="btn btn-ghost" onClick={unsave} disabled={state === "saving" || state === "done"}>
      {state === "saving" ? "Removing..." : state === "error" ? "Remove failed" : "Unsave"}
    </button>
  );
}

const FUNDING_WORKFLOW_STATES = ["saved", "reviewing", "considering", "planning", "applying", "submitted", "archived"];
const SAVED_FUNDING_FILTERS = [
  { key: "all", label: "All" },
  { key: "open_current", label: "Open / current" },
  { key: "prospects", label: "Prospects" },
  { key: "needs_review", label: "Needs review" },
  { key: "changed_since_saved", label: "Changed since saved" },
  { key: "provider_issue", label: "Provider issue" },
  { key: "no_current_window", label: "No current window" },
  { key: "applying_planning", label: "Applying / planning" },
  { key: "archived", label: "Archived" },
];

const SAVED_FUNDING_SORTS = [
  { key: "recently_saved", label: "Recently saved" },
  { key: "deadline_soon", label: "Deadline soon" },
  { key: "changed_first", label: "Changed since saved first" },
  { key: "workflow_state", label: "Workflow state" },
  { key: "open_current_first", label: "Open/current first" },
  { key: "archived_last", label: "Archived last" },
];

function savedFundingStatusCue(item, latestRefresh) {
  if (item.linked_opportunity_title || item.linked_opportunity_id || latestRefresh.outcome === "current_opportunity_found") {
    return "Current opportunity found";
  }
  if (latestRefresh.outcome === "provider_unavailable") return "Provider issue";
  if (latestRefresh.outcome === "no_current_application_window_verified") return "No current window";
  if (item.item_kind === "prospect") return "Prospect";
  if (item.item_kind === "scheme") return "Recurring scheme";
  return (item.last_known_status || item.display_status || "Saved").replaceAll("_", " ");
}

function savedFundingNextCue(item, deadline, latestRefresh) {
  if (deadline) return `Next deadline: ${deadline}`;
  if (item.linked_opportunity_title) return `Linked opportunity: ${item.linked_opportunity_title}`;
  if (latestRefresh.outcome === "status_changed") return "Status changed since saved";
  if (latestRefresh.outcome === "deadline_changed") return "Deadline changed since saved";
  if ((latestRefresh.changes || []).length) return "Changed since saved";
  if (latestRefresh.outcome === "provider_unavailable") return "Existing saved evidence retained";
  return "Review saved evidence";
}

function SavedFundingQueueSummary({ item, deadline, latestRefresh }) {
  const workflow = (item.workflow_state || "saved").replaceAll("_", " ");
  const statusCue = savedFundingStatusCue(item, latestRefresh || {});
  const nextCue = savedFundingNextCue(item, deadline, latestRefresh || {});
  return (
    <div className="funding-saved-summary" aria-label="Saved funding queue summary">
      <small>{statusCue}</small>
      <small>Workflow: {workflow}</small>
      <small>{nextCue}</small>
    </div>
  );
}

function SavedFundingRow({ item, onChanged }) {
  const [open, setOpen] = useState(false);
  const [workflow, setWorkflow] = useState(item.workflow_state || "saved");
  const [notes, setNotes] = useState(item.notes || "");
  const [state, setState] = useState("idle");
  useEffect(() => {
    setWorkflow(item.workflow_state || "saved");
    setNotes(item.notes || "");
  }, [item.id, item.workflow_state, item.notes]);
  const label = (item.item_kind || "item").replaceAll("_", " ");
  const status = (item.last_known_status || item.display_status || "saved").replaceAll("_", " ");
  const deadline = item.last_known_deadline || item.next_deadline;
  const latestRefresh = (item.refresh_events || [])[0] || null;
  const saveChanges = async () => {
    setState("saving");
    const r = await apiPatch(`/funding-discovery/saved/${item.id}`, { workflow_state: workflow, notes });
    setState(r.ok ? "saved" : "error");
    if (r.ok && onChanged) onChanged();
  };
  return (
    <div className="funding-saved-item">
      <button type="button" className="funding-saved-main" onClick={() => setOpen(v => !v)}
        aria-expanded={open} aria-label={`Review saved funding item ${item.title || item.id}`}>
        <div>
          <b>{item.title || "Saved funding item"}</b>
          <span>{label}{item.organization_name ? " - " + item.organization_name : ""}</span>
          <SavedFundingQueueSummary item={item} deadline={deadline} latestRefresh={latestRefresh} />
        </div>
        <small>
          {status}{deadline ? " - deadline " + deadline : ""} - {item.workflow_state || "saved"}
        </small>
        {latestRefresh && <SavedFundingRefreshPill event={latestRefresh} />}
      </button>
      {open &&
        <div className="funding-saved-detail">
          <div className="funding-saved-facts">
            <span>Kind: {label}</span>
            <span>Status snapshot: {status}</span>
            {deadline && <span>Deadline snapshot: {deadline}</span>}
            {item.linked_opportunity_title && <span>Linked opportunity: {item.linked_opportunity_title}</span>}
            {item.last_checked_at && <span>Last checked: {item.last_checked_at}</span>}
            {item.source_url && <a href={item.source_url} target="_blank" rel="noopener noreferrer">Source</a>}
          </div>
          <SavedFundingRefreshHistory events={item.refresh_events || []} />
          <label>
            <span>Workflow</span>
            <select value={workflow} onChange={e => setWorkflow(e.target.value)}>
              {FUNDING_WORKFLOW_STATES.map(s => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}
            </select>
          </label>
          <label>
            <span>Notes</span>
            <textarea rows={3} value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="What needs review next?" />
          </label>
          <div className="funding-saved-actions">
            <button type="button" className="btn btn-sm" onClick={saveChanges} disabled={state === "saving"}>
              {state === "saving" ? "Saving..." : state === "error" ? "Save failed" : "Save changes"}
            </button>
            <FundingUnsaveButton item={item} onUnsaved={onChanged} />
          </div>
        </div>}
    </div>
  );
}

function SavedFundingRefreshHistory({ events }) {
  if (!events.length) return null;
  return (
    <div className="funding-refresh-history">
      <b>Refresh history</b>
      {events.slice(0, 5).map(event => (
        <div className="funding-refresh-history-row" key={event.id}>
          <SavedFundingRefreshPill event={event} />
          <small>
            {savedRefreshEventLabel(event)}
            {event.checked_at ? ` - ${event.checked_at}` : ""}
          </small>
        </div>
      ))}
    </div>
  );
}

function savedRefreshTone(eventOrChange) {
  const outcome = eventOrChange.outcome || "";
  const provider = eventOrChange.provider_status || "";
  const changes = eventOrChange.changes || [];
  if (outcome === "provider_unavailable" || provider === "provider_unavailable") return "issue";
  if (outcome === "current_opportunity_found" || provider.startsWith("application_surface_refreshed")) return "found";
  if (outcome === "status_changed" || changes.some(x => x.field === "status")) return "changed";
  if (outcome === "deadline_changed" || changes.some(x => x.field === "deadline")) return "changed";
  if (outcome === "no_current_application_window_verified" || provider === "no_current_application_window_verified") return "unresolved";
  return "neutral";
}

function SavedFundingRefreshPill({ event }) {
  const tone = savedRefreshTone(event);
  const labels = {
    found: "current opportunity",
    changed: "changed",
    issue: "provider issue",
    unresolved: "no current window",
    neutral: "checked",
  };
  return <span className={"funding-refresh-pill " + tone}>{labels[tone]}</span>;
}

function savedRefreshEventLabel(event) {
  const labels = {
    current_opportunity_found: "Current opportunity found",
    status_changed: "Status changed",
    deadline_changed: "Deadline changed",
    no_current_application_window_verified: "No current application window verified",
    provider_unavailable: "Provider unavailable",
    saved_item_unavailable: "Saved item unavailable",
    unchanged: "No saved status or deadline changes detected",
  };
  const base = labels[event.outcome] || "Refresh checked";
  const changes = event.changes || [];
  if (!changes.length) return base;
  return `${base}: ${changes.map(x => `${x.field} ${x.before || "none"} -> ${x.after || "none"}`).join("; ")}`;
}

function SavedFundingRefreshSummary({ result }) {
  if (!result || !result.changes || !result.changes.length) return null;
  const changed = result.changes.filter(c => c.status === "changed");
  const itemsById = new Map((result.items || []).map(item => [item.id, item]));
  return (
    <div className="funding-saved-refresh">
      <b>Saved funding refresh</b>
      <span>
        {changed.length
          ? `${changed.length} saved item${changed.length === 1 ? "" : "s"} changed.`
          : "No saved status or deadline changes detected."}
      </span>
      {result.refreshed_at && <small>Checked {result.refreshed_at}</small>}
      {result.changes.slice(0, 5).map(c => {
        const item = itemsById.get(c.saved_item_id) || {};
        return (
          <div className="funding-refresh-row" key={c.saved_item_id}>
            <SavedFundingRefreshPill event={c} />
            <small>{savedRefreshOutcome(c, item)}</small>
            {savedRefreshChangeLine(c) && <small>{savedRefreshChangeLine(c)}</small>}
            {item.linked_opportunity_title &&
              <small>Current opportunity found: {item.linked_opportunity_title}{item.next_deadline ? ` - deadline ${item.next_deadline}` : ""}</small>}
            {item.source_url && <a href={item.source_url} target="_blank" rel="noopener noreferrer">Open source</a>}
          </div>
        );
      })}
    </div>
  );
}

function savedRefreshOutcome(change, item) {
  const label = (change.item_kind || "item").replaceAll("_", " ");
  const title = item.title || `${label} ${change.canonical_item_id || ""}`.trim();
  if ((change.provider_status || "").startsWith("application_surface_refreshed")) {
    return `${title}: Current opportunity found.`;
  }
  if (change.provider_status === "provider_unavailable") {
    return `${title}: Provider unavailable. Existing saved evidence was retained.`;
  }
  if (change.provider_status === "no_current_application_window_verified") {
    return `${title}: No current application window verified.`;
  }
  if (change.status === "unavailable") {
    return `${title}: Saved item unavailable.`;
  }
  if ((change.changes || []).some(x => x.field === "status")) {
    return `${title}: Status changed.`;
  }
  if ((change.changes || []).some(x => x.field === "deadline")) {
    return `${title}: Deadline changed.`;
  }
  return `${title}: No current application window verified.`;
}

function savedRefreshChangeLine(change) {
  const changes = change.changes || [];
  if (!changes.length) return "";
  return changes.map(x => `${x.field} ${x.before || "none"} -> ${x.after || "none"}`).join("; ");
}

function SavedFundingItems({ items, onChanged }) {
  const [refreshState, setRefreshState] = useState({ status: "idle" });
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("recently_saved");
  const [bulkState, setBulkState] = useState({ status: "idle" });
  const refresh = async () => {
    setRefreshState({ status: "running" });
    const r = await apiPost("/funding-discovery/saved/refresh", {});
    if (!r.ok) { setRefreshState({ status: "error", error: r.error }); return; }
    setRefreshState({ status: "done", result: r.data });
    if (onChanged) onChanged();
  };
  if (!items || !items.length) return null;
  const counts = savedFundingFilterCounts(items);
  const filteredItems = items.filter(item => savedFundingMatchesFilter(item, filter));
  const sortedItems = savedFundingSortResults(filteredItems, sort);
  const visibleItems = sortedItems.slice(0, 6);
  return (
    <div className="funding-saved">
      <div className="funding-saved-head">
        <div className="funding-subhead">Saved funding</div>
        <button type="button" className="btn btn-sm" onClick={refresh} disabled={refreshState.status === "running"}>
          {refreshState.status === "running" ? "Refreshing..." : "Refresh saved funding"}
        </button>
      </div>
      {refreshState.status === "error" && <div className="axis-err">Refresh failed: {refreshState.error}</div>}
      <SavedFundingRefreshSummary result={refreshState.result} />
      <div className="funding-saved-filters" role="group" aria-label="Saved funding filters">
        {SAVED_FUNDING_FILTERS.map(f => (
          <button key={f.key} type="button" className={"tags-srcfilter-btn" + (filter === f.key ? " on" : "")}
            onClick={() => setFilter(f.key)}>
            {f.label} <span>{counts[f.key] || 0}</span>
          </button>
        ))}
      </div>
      <SavedFundingSort sort={sort} setSort={setSort} />
      <SavedFundingBulkActions items={visibleItems} state={bulkState} setState={setBulkState} onChanged={onChanged} />
      <div className="funding-saved-list">
        {visibleItems.length
          ? visibleItems.map(item => <SavedFundingRow key={item.id} item={item} onChanged={onChanged} />)
          : <div className="funding-fact">No saved funding items match this filter.</div>}
      </div>
    </div>
  );
}

function SavedFundingBulkActions({ items, state, setState, onChanged }) {
  const count = (items || []).length;
  const running = state.status === "running";
  const applyWorkflow = async (workflowState) => {
    setState({ status: "running", workflowState });
    for (const item of items || []) {
      const r = await apiPatch(`/funding-discovery/saved/${item.id}`, { workflow_state: workflowState });
      if (!r.ok) {
        setState({ status: "error", error: r.error || "Bulk workflow update failed." });
        return;
      }
    }
    setState({ status: "done", workflowState, count });
    if (onChanged) onChanged();
  };
  return (
    <div className="funding-saved-bulk">
      <small>Applies to {count} visible saved item{count === 1 ? "" : "s"}.</small>
      <div>
        <button type="button" className="btn btn-ghost" disabled={!count || running}
          onClick={() => applyWorkflow("reviewing")}>
          {running && state.workflowState === "reviewing" ? "Updating..." : "Mark visible reviewing"}
        </button>
        <button type="button" className="btn btn-ghost" disabled={!count || running}
          onClick={() => applyWorkflow("archived")}>
          {running && state.workflowState === "archived" ? "Updating..." : "Archive visible"}
        </button>
      </div>
      {state.status === "done" &&
        <small>Updated {state.count || count} visible saved item{(state.count || count) === 1 ? "" : "s"} to {state.workflowState}.</small>}
      {state.status === "error" && <small className="funding-bulk-error">Bulk update failed: {state.error}</small>}
    </div>
  );
}

function SavedFundingSort({ sort, setSort }) {
  return (
    <label className="funding-result-sort">
      <span>Sort saved funding</span>
      <select value={sort} onChange={e => setSort(e.target.value)} aria-label="Sort saved funding">
        {SAVED_FUNDING_SORTS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
      </select>
      <small>Sorting changes display order only; saved records and workflow states are unchanged.</small>
    </label>
  );
}

function savedFundingFilterCounts(items) {
  const counts = Object.fromEntries(SAVED_FUNDING_FILTERS.map(f => [f.key, 0]));
  (items || []).forEach(item => {
    SAVED_FUNDING_FILTERS.forEach(f => {
      if (savedFundingMatchesFilter(item, f.key)) counts[f.key] += 1;
    });
  });
  return counts;
}

function savedFundingMatchesFilter(item, filter) {
  const latest = (item.refresh_events || [])[0] || {};
  const workflow = item.workflow_state || "saved";
  if (filter === "all") return true;
  if (filter === "open_current") return item.linked_opportunity_id
    || item.display_status === "open_opportunity"
    || item.last_known_status === "open"
    || latest.outcome === "current_opportunity_found";
  if (filter === "prospects") return item.item_kind === "prospect";
  if (filter === "needs_review") return !["archived", "submitted"].includes(workflow);
  if (filter === "changed_since_saved") return latest.outcome === "current_opportunity_found"
    || latest.outcome === "status_changed"
    || latest.outcome === "deadline_changed"
    || (latest.changes || []).length > 0;
  if (filter === "provider_issue") return latest.outcome === "provider_unavailable";
  if (filter === "no_current_window") return latest.outcome === "no_current_application_window_verified";
  if (filter === "applying_planning") return ["planning", "applying"].includes(workflow);
  if (filter === "archived") return workflow === "archived";
  return true;
}

function savedFundingTime(value) {
  const time = Date.parse(value || "");
  return Number.isFinite(time) ? time : 0;
}

function savedFundingDeadlineTime(item) {
  const time = savedFundingTime(item.last_known_deadline || item.next_deadline);
  return time || Number.POSITIVE_INFINITY;
}

function savedFundingChangedRank(item) {
  const latest = (item.refresh_events || [])[0] || {};
  return savedFundingMatchesFilter(item, "changed_since_saved") ? savedFundingTime(latest.checked_at) || 1 : 0;
}

function savedFundingWorkflowRank(item) {
  const workflow = item.workflow_state || "saved";
  const ranks = { reviewing: 0, considering: 1, planning: 2, applying: 3, saved: 4, submitted: 5, archived: 6 };
  return ranks[workflow] == null ? 4 : ranks[workflow];
}

function savedFundingSortResults(items, sort) {
  return [...(items || [])].sort((a, b) => {
    if (sort === "deadline_soon") {
      return savedFundingDeadlineTime(a) - savedFundingDeadlineTime(b) || savedFundingTime(b.saved_at) - savedFundingTime(a.saved_at);
    }
    if (sort === "changed_first") {
      return savedFundingChangedRank(b) - savedFundingChangedRank(a) || savedFundingTime(b.saved_at) - savedFundingTime(a.saved_at);
    }
    if (sort === "workflow_state") {
      return savedFundingWorkflowRank(a) - savedFundingWorkflowRank(b) || savedFundingTime(b.saved_at) - savedFundingTime(a.saved_at);
    }
    if (sort === "open_current_first") {
      return Number(savedFundingMatchesFilter(b, "open_current")) - Number(savedFundingMatchesFilter(a, "open_current"))
        || savedFundingTime(b.saved_at) - savedFundingTime(a.saved_at);
    }
    if (sort === "archived_last") {
      return Number((a.workflow_state || "saved") === "archived") - Number((b.workflow_state || "saved") === "archived")
        || savedFundingTime(b.saved_at) - savedFundingTime(a.saved_at);
    }
    return savedFundingTime(b.saved_at) - savedFundingTime(a.saved_at) || (b.id || 0) - (a.id || 0);
  });
}
