// Axes panel — create, browse, score, and correct user-defined axes (supervised lens).
// Honesty contract: an assignment is an embedding similarity, never a categorical truth. We
// always show the tier (assigned / uncertain / manual) + confidence, mark manual overrides
// distinctly from the scorer's calls, and surface staleness. The human can add/remove papers.

function axisConfidenceLabel(paper) {
  if (paper.manual || paper.confidence == null) return "manual";
  return paper.confidence.toFixed(2);
}

function AxisTierBadge({ status }) {
  // inc-50: no tag for scorer-assigned papers (de-clutter — the default good state). Tags flag only
  // the non-default states: amber "uncertain" (scorer unsure) and dashed "manual" (human override).
  if (status === "assigned") return null;
  const label = status === "uncertain" ? "uncertain" : "manual";
  return <span className={"axis-tier axis-tier-" + label}>{label}</span>;
}

function AxisPaperRow({ paper, selected, onOpen, onRemove, onConfirm }) {
  return (
    <div className={"axis-paper" + (selected ? " sel" : "")}>
      <span className="axis-paper-title" onClick={() => onOpen(paper)} title={"Open " + paper.title}>{paper.title}</span>
      <AxisTierBadge status={paper.status} />
      <span className="axis-paper-conf" title={paper.manual ? "Manually added by you" : "Embedding-similarity confidence"}>
        {axisConfidenceLabel(paper)}
      </span>
      {paper.status === "uncertain" &&
        <button className="axis-confirm" title="Confirm — keep this paper on the axis (a manual override)" onClick={() => onConfirm(paper.id)}>✓</button>}
      <button className="axis-x" title="Remove from this axis" onClick={() => onRemove(paper.id)}>×</button>
    </div>
  );
}

// Compact slider for the assigned cutoff ("gain"): assigned = similarity >= value; lower includes more.
function AxisCutoffFlipper({ value, onChange, disabled }) {
  return (
    <span className="axis-cutoff" title="Assigned = similarity at or above this cutoff (lower includes more)">
      <span className="axis-cutoff-name">Cutoff</span>
      <input className="axis-cutoff-range" type="range" min="0.2" max="0.6" step="0.01"
        value={value} disabled={disabled} onChange={e => onChange(parseFloat(e.target.value))} />
      <span className="axis-cutoff-val">{value.toFixed(2)}</span>
    </span>
  );
}

// Shown pinned at the top of the axes panel when My Publications hasn't been set up yet (inc 78).
function MyPubsPrompt() {
  return (
    <div className="axis-mypubs-prompt" title="Set your name / ORCID in Settings to auto-gather your own papers">
      📄 <b>My Publications</b> — set your name / ORCID in Settings (⚙) to auto-gather your own papers.
    </div>
  );
}

function AxisItem({ axis, detail, job, expanded, selected, selectedPaper, handlers, hideUncertainDefault }) {
  const scoring = job && job.status === "running";
  const isMyPubs = axis.kind === "my_publications";  // inc 78: the pinned own-papers axis (variant UI, no scoring)
  const [cutoff, setCutoff] = useState(axis.scoring_gain != null ? axis.scoring_gain : 0.35);
  // B′: eye toggle — show assigned/manual only. Starts from the Settings default (re-keyed on change → remount).
  const [hideUncertain, setHideUncertain] = useState(!!hideUncertainDefault);
  const stop = (fn) => (e) => { e.stopPropagation(); fn(); };
  const readyPapers = detail && detail.status === "ready" ? detail.papers : [];
  const uncertainCount = readyPapers.filter(p => p.status === "uncertain").length;
  // inc 79: when uncertain papers are hidden, the count badge shows the visible (assigned + manual) count.
  const total = axis.assignment_count || 0;
  const badgeCount = hideUncertain ? Math.max(0, total - (axis.uncertain_count || 0)) : total;
  return (
    <div className={"axis-item" + (isMyPubs ? " axis-mypubs" : "")}>
      <div className={"axis" + (expanded ? " active" : "")} onClick={() => handlers.toggle(axis.id)}>
        <div className="axis-row-head">
          {!isMyPubs &&
            <input
              type="checkbox" className="axis-select" checked={selected}
              title="Select for bulk delete / merge"
              onClick={e => e.stopPropagation()}
              onChange={() => handlers.toggleSelect(axis.id)}
            />}
          <span className="axis-label">{isMyPubs ? "📄 " + axis.label : axis.label}</span>
          <span className="axis-card-actions">
            {!isMyPubs && <button className="axis-icon-btn" title="Edit axis" onClick={stop(() => handlers.openEdit(axis))}>✎</button>}
            {!isMyPubs && <button className="axis-icon-btn" title="Add papers from the library" onClick={stop(() => handlers.enterFocus(axis))}>＋</button>}
            {isMyPubs && <button className="axis-icon-btn" title="Open the impact dashboard" onClick={stop(() => handlers.openMyPubsDashboard(axis))}>📊</button>}
            <button className="axis-icon-btn axis-icon-danger"
              title={isMyPubs ? "Dismiss My Publications (keeps your profile)" : "Delete axis"}
              onClick={stop(() => (isMyPubs ? handlers.dismissMyPubs() : handlers.remove(axis.id)))}>🗑</button>
            <button
              className={"axis-count-badge" + (isMyPubs ? " is-scored" : axis.scored ? (axis.stale ? " is-stale" : " is-scored") : "")}
              title={isMyPubs
                ? `Show your ${axis.assignment_count || 0} papers in the library`
                : (hideUncertain && (axis.uncertain_count || 0) > 0
                    ? `${badgeCount} assigned · ${axis.uncertain_count} uncertain hidden — click to show this axis in the library`
                    : `Show these ${axis.assignment_count || 0} papers in the library` + (axis.scored ? (axis.stale ? " · edited since scoring" : " · scored & up to date") : " · not scored yet"))}
              onClick={stop(() => handlers.filterToAxis(axis))}
            >{badgeCount}</button>
          </span>
        </div>
      </div>

      {expanded &&
        <div className="axis-body">
          {!isMyPubs &&
            <div className="axis-rescore-row">
              <span className="axis-rescore-label">Re-score:</span>
              <AxisCutoffFlipper value={cutoff} onChange={setCutoff} disabled={scoring} />
              <button className="axis-btn axis-rescore-btn" disabled={scoring} onClick={() => handlers.score(axis.id, cutoff)}>
                {scoring ? "Scoring…" : axis.scored ? "Re-score" : "Score"}
              </button>
              {uncertainCount > 0 &&
                <button className={"axis-icon-btn axis-eye" + (hideUncertain ? " off" : "")}
                  title={hideUncertain ? `Show ${uncertainCount} uncertain paper${uncertainCount > 1 ? "s" : ""}` : "Hide uncertain papers (assigned-only view)"}
                  onClick={() => setHideUncertain(h => !h)}>👁</button>}
            </div>}
          {isMyPubs && uncertainCount > 0 &&
            <div className="axis-mypubs-hint">Name-only matches are candidates — <b>✓</b> confirm the ones that are yours, <b>✕</b> reject the rest. (Confirmed papers match by DOI/ORCID.)</div>}

          {scoring && <ProgressBar label={job.message || "Scoring the library…"} />}
          {job && job.status === "error" && <div className="axis-err">Scoring failed: {job.message}</div>}

          {detail && detail.status === "loading" && <div className="axis-hint">Loading…</div>}
          {detail && detail.status === "error" && <div className="axis-err">Couldn't load assignments.</div>}
          {detail && detail.status === "ready" &&
            (detail.papers.length === 0
              ? <div className="axis-hint">{isMyPubs ? "No publications matched yet — set your name/ORCID in Settings (⚙) and Refresh." : axis.scored ? "No papers were close enough to this axis. Add one manually if the scorer missed it." : "Score this axis to assign papers, or add one manually."}</div>
              : <div className="axis-papers">
                  {[...detail.papers]
                    .filter(p => !hideUncertain || p.status !== "uncertain")
                    .sort((a, b) => _tierRank(a) - _tierRank(b) || (b.confidence || 0) - (a.confidence || 0))
                    .map(p => (
                      <AxisPaperRow key={p.id} paper={p} selected={selectedPaper === p.id}
                        onOpen={handlers.openPaper}
                        onConfirm={(pid) => handlers.confirmPaper(axis.id, pid)}
                        onRemove={(pid) => handlers.removePaper(axis.id, pid)} />
                    ))}
                  {hideUncertain && uncertainCount > 0 &&
                    <button className="axis-eye-hint" onClick={() => setHideUncertain(false)}>
                      {uncertainCount} uncertain hidden — show
                    </button>}
                </div>)}
        </div>}
    </div>
  );
}

function _tierRank(p) {
  return p.status === "assigned" ? 0 : p.status === "uncertain" ? 1 : 2;
}

function AxesPanel({ onSelectPaper, selectedPaper, onOpenPaper, onEnterFocus, onFilterToAxis, onOpenMyPubsDashboard, axisRefresh, hideUncertainDefault }) {
  const [axes, setAxes] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [details, setDetails] = useState({});     // { axisId: {status, papers} }
  const [jobs, setJobs] = useState({});           // { axisId: {status, message} }
  const [quickName, setQuickName] = useState(null);    // inline new-axis name input (null = hidden)
  const [editor, setEditor] = useState(null);          // {mode, axisId?, title, description, terms} → AxisEditModal
  const [notice, setNotice] = useState(null);
  const [sortBy, setSortBy] = useState("name");                  // name | count | recent
  const [filter, setFilter] = useState("");                      // quick filter over the visible axes
  const [selectedIds, setSelectedIds] = useState(() => new Set()); // axes checked for bulk delete / merge
  const [merging, setMerging] = useState(null);                  // selected axis objects when the merge modal is open
  const [suggesting, setSuggesting] = useState(false);           // suggest-optimal-axes modal open?
  const pollRef = useRef({});

  const flash = useCallback((msg) => setNotice(msg), []);

  const loadAxes = useCallback(() => {
    api("/axes").then(r => setAxes(r.ok ? r.data : []));
  }, []);

  const loadDetail = useCallback((id) => {
    setDetails(d => ({ ...d, [id]: { status: "loading", papers: [] } }));
    api(`/axes/${id}/clusters`).then(r => {
      if (r.ok) {
        const papers = (r.data || []).flatMap(node => node.papers || []);
        setDetails(d => ({ ...d, [id]: { status: "ready", papers } }));
      } else {
        setDetails(d => ({ ...d, [id]: { status: "error", papers: [] } }));
      }
    });
  }, []);

  useEffect(() => { loadAxes(); }, [loadAxes]);
  useEffect(() => () => { Object.values(pollRef.current).forEach(clearTimeout); }, []);

  // Refresh after a library focus-mode Save (App bumps axisRefresh): update the counts + the open
  // axis's paper list. expandedRef avoids re-running this on every expand/collapse.
  const expandedRef = useRef(null);
  expandedRef.current = expanded;
  const skipFirstRefresh = useRef(true);
  useEffect(() => {
    if (skipFirstRefresh.current) { skipFirstRefresh.current = false; return; }
    loadAxes();
    if (expandedRef.current != null) loadDetail(expandedRef.current);
  }, [axisRefresh, loadAxes, loadDetail]);

  const toggle = useCallback((id) => {
    setExpanded(prev => {
      const next = prev === id ? null : id;
      if (next === id) loadDetail(id);
      return next;
    });
  }, [loadDetail]);

  const pollScore = useCallback((id, jobId) => {
    api(`/axes/score/${jobId}`).then(r => {
      if (!r.ok) { setJobs(j => ({ ...j, [id]: { status: "error", message: r.error } })); return; }
      const d = r.data;
      if (d.status === "done") {
        setJobs(j => { const n = { ...j }; delete n[id]; return n; });
        loadAxes();
        loadDetail(id);
      } else if (d.status === "error") {
        setJobs(j => ({ ...j, [id]: { status: "error", message: d.detail || "Scoring failed." } }));
      } else {
        setJobs(j => ({ ...j, [id]: { status: "running", message: "Scoring the library…" } }));
        pollRef.current[id] = setTimeout(() => pollScore(id, jobId), 1200);
      }
    });
  }, [loadAxes, loadDetail]);

  const score = useCallback((id, gain) => {
    setJobs(j => ({ ...j, [id]: { status: "running", message: "Starting…" } }));
    apiPost(`/axes/${id}/score`, gain != null ? { gain } : {}).then(r => {
      if (!r.ok) { setJobs(j => ({ ...j, [id]: { status: "error", message: r.error } })); return; }
      pollScore(id, r.data.job_id);
    });
  }, [pollScore]);

  // Create + edit both flow through the AxisEditModal. "+ new" reveals a quick name input; submitting it
  // opens the modal in create mode seeded with that name (title + first selected term). "edit" opens it
  // prefilled from the axis (title = label; prose + terms parsed from the description's Related: block).
  const openCreate = useCallback((name) => {
    const t = (name || "").trim();
    setQuickName(null);
    setEditor({ mode: "create", title: t, description: "", terms: t ? [{ term: t, selected: true }] : [] });
  }, []);

  const openEdit = useCallback((axis) => {
    setEditor({
      mode: "edit", axisId: axis.id, title: axis.label || "",
      description: _axisBase(axis.description),
      terms: _axisRelatedTerms(axis.description).map(t => ({ term: t, selected: true })),
    });
  }, []);

  const onEditorSaved = useCallback((id) => {
    setEditor(null);
    loadAxes();
    if (expanded === id) loadDetail(id);
  }, [loadAxes, loadDetail, expanded]);

  // Clicking an article under an axis opens its PDF (axes panel = a clickable library overview) and also
  // selects it so the Detail pane follows along.
  const openPaper = useCallback((paper) => {
    if (onOpenPaper) onOpenPaper(paper);
    if (onSelectPaper) onSelectPaper(paper.id);
  }, [onOpenPaper, onSelectPaper]);

  const remove = useCallback((id) => {
    if (!window.confirm("Delete this axis? This removes the axis and all its paper assignments (your manual ones too).")) return;
    apiDelete(`/axes/${id}`).then(r => {
      if (!r.ok) { flash(r.error); return; }
      setExpanded(prev => prev === id ? null : prev);
      loadAxes();
    });
  }, [loadAxes, flash]);

  // ✕ on a paper: a standard axis removes the assignment; the My Publications axis persists a "rejected"
  // decision (so it's never re-proposed) via /my-publications/decide.
  const removePaper = useCallback((axisId, paperId) => {
    const ax = (axes || []).find(a => a.id === axisId);
    const req = ax && ax.kind === "my_publications"
      ? apiPost("/my-publications/decide", { paper_id: paperId, decision: "rejected" })
      : apiDelete(`/axes/${axisId}/papers/${paperId}`);
    req.then(r => {
      if (!r.ok) { flash(r.error); return; }
      loadDetail(axisId);
      loadAxes();
    });
  }, [axes, loadDetail, loadAxes, flash]);

  // ✓-confirm: a standard axis upserts a manual override; the My Publications axis persists a "confirmed"
  // decision (survives every re-match) via /my-publications/decide.
  const confirmPaper = useCallback((axisId, paperId) => {
    const ax = (axes || []).find(a => a.id === axisId);
    const req = ax && ax.kind === "my_publications"
      ? apiPost("/my-publications/decide", { paper_id: paperId, decision: "confirmed" })
      : apiPost(`/axes/${axisId}/papers`, { paper_id: paperId });
    req.then(r => {
      if (!r.ok) { flash(r.error); return; }
      loadDetail(axisId);
      loadAxes();
    });
  }, [axes, loadDetail, loadAxes, flash]);

  // 🗑 on the My Publications card dismisses it (keeps the profile + decisions); Refresh rebuilds it.
  const dismissMyPubs = useCallback(() => {
    if (!window.confirm("Dismiss the My Publications card? Your profile and confirm/reject choices are kept — Refresh in Settings rebuilds it.")) return;
    apiDelete("/my-publications").then(r => { if (r.ok) loadAxes(); });
  }, [loadAxes]);

  const toggleSelect = useCallback((id) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const bulkDelete = useCallback(() => {
    const ids = [...selectedIds];
    if (!ids.length) return;
    if (!window.confirm(`Delete ${ids.length} ${ids.length === 1 ? "axis" : "axes"}? This removes them and all their paper assignments (your manual ones too).`)) return;
    Promise.all(ids.map(id => apiDelete(`/axes/${id}`))).then(results => {
      const failed = results.filter(r => !r.ok).length;
      setSelectedIds(new Set());
      setExpanded(prev => ids.includes(prev) ? null : prev);
      loadAxes();
      if (failed) flash(`${failed} of ${ids.length} could not be deleted.`);
    });
  }, [selectedIds, loadAxes, flash]);

  const openMerge = useCallback(() => {
    const chosen = (axes || []).filter(a => selectedIds.has(a.id));
    if (chosen.length >= 2) setMerging(chosen);
  }, [axes, selectedIds]);

  // The card "＋" puts the library panel into focus mode for this axis (add the papers the scorer missed).
  const enterFocus = useCallback((axis) => {
    if (onEnterFocus) onEnterFocus({ id: axis.id, label: axis.label });
  }, [onEnterFocus]);

  const filterToAxis = useCallback((axis) => {
    if (onFilterToAxis) onFilterToAxis({ id: axis.id, label: axis.label });
  }, [onFilterToAxis]);

  const openMyPubsDashboard = useCallback((axis) => {
    if (onOpenMyPubsDashboard) onOpenMyPubsDashboard(axis);
  }, [onOpenMyPubsDashboard]);

  const handlers = {
    toggle, score, remove, removePaper, confirmPaper, dismissMyPubs, enterFocus, filterToAxis,
    openMyPubsDashboard, toggleSelect, openEdit, openPaper,
  };

  // Sorted copy for display (small list — no memo needed). Selection/merge act on real ids, not order.
  const sortedAxes = axes ? [...axes].sort((a, b) => {
    if (sortBy === "count") return (b.assignment_count || 0) - (a.assignment_count || 0) || a.label.localeCompare(b.label);
    if (sortBy === "recent") return String(b.created_at || "").localeCompare(String(a.created_at || "")) || (b.id - a.id);
    return a.label.localeCompare(b.label);
  }) : axes;

  // quick filter over the sorted axes — matches the title or its terms/description
  const visibleAxes = sortedAxes && filter.trim()
    ? sortedAxes.filter(a => ((a.label || "") + " " + (a.description || "")).toLowerCase().includes(filter.trim().toLowerCase()))
    : sortedAxes;
  const myPubsAxis = (axes || []).find(a => a.kind === "my_publications") || null;
  // The My Publications card is pinned (rendered first, orthogonal to sort/filter); keep it out of the list.
  const standardVisible = visibleAxes ? visibleAxes.filter(a => a.kind !== "my_publications") : visibleAxes;

  return (
    <div className="axis-group">
      <div className="axis-group-head">
        <p className="eyebrow">Axes</p>
      </div>
      <div className="axis-controls">
        {axes && axes.length > 1 &&
          <input className="axis-filter" placeholder="Filter axes…" value={filter} onChange={e => setFilter(e.target.value)} />}
        {axes && axes.length > 1 &&
          <select className="axis-sort" value={sortBy} onChange={e => setSortBy(e.target.value)} title="Sort axes">
            <option value="name">A–Z</option>
            <option value="count">most papers</option>
            <option value="recent">newest</option>
          </select>}
        <button className="axis-suggest" title="Suggest axes from your library" onClick={() => setSuggesting(true)}>✨</button>
        <button className="axis-new" title={quickName != null ? "Cancel" : "New axis"} onClick={() => { setQuickName(q => q == null ? "" : null); setNotice(null); }}>{quickName != null ? "×" : "+"}</button>
      </div>

      {quickName != null &&
        <div className="axis-quickname">
          <input className="axis-add-input" autoFocus placeholder="New axis name…" value={quickName}
            onChange={e => setQuickName(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && quickName.trim()) { e.preventDefault(); openCreate(quickName); } else if (e.key === "Escape") setQuickName(null); }} />
          <button className="axis-btn" disabled={!quickName.trim()} onClick={() => openCreate(quickName)}>next →</button>
        </div>}
      {notice && <div className="axis-err" onClick={() => setNotice(null)}>{notice}</div>}

      {selectedIds.size > 0 &&
        <div className="axis-bulk-bar">
          <span className="axis-bulk-count">{selectedIds.size} selected</span>
          <button className="axis-link" disabled={selectedIds.size < 2} onClick={openMerge}
            title={selectedIds.size < 2 ? "Select 2+ axes to merge" : "Merge selected axes into one"}>merge</button>
          <button className="axis-link axis-danger" onClick={bulkDelete}>delete</button>
          <button className="axis-link" onClick={() => setSelectedIds(new Set())}>clear</button>
        </div>}

      {axes === null && <div className="axis-hint">—</div>}
      {axes && axes.length === 0 && quickName == null &&
        <div className="axis-hint">No axes yet. An axis is a lens: name it + describe the construct, and Callosum scores each paper's similarity to it.</div>}
      {axes && axes.length > 0 && visibleAxes && visibleAxes.length === 0 && filter.trim() &&
        <div className="axis-hint">No axes match “{filter.trim()}”.</div>}

      {/* My Publications hangs at the top of the axis list (below the filter/sort controls), styled distinct. */}
      {axes && (myPubsAxis
        ? <AxisItem key="mypubs" axis={myPubsAxis} detail={details[myPubsAxis.id]} job={jobs[myPubsAxis.id]}
            expanded={expanded === myPubsAxis.id} selected={false} selectedPaper={selectedPaper}
            handlers={handlers} hideUncertainDefault={false} />
        : <MyPubsPrompt />)}
      {standardVisible && standardVisible.map(axis => (
        <AxisItem
          key={axis.id + (hideUncertainDefault ? "-h" : "-s")}
          hideUncertainDefault={hideUncertainDefault}
          axis={axis}
          detail={details[axis.id]}
          job={jobs[axis.id]}
          expanded={expanded === axis.id}
          selected={selectedIds.has(axis.id)}
          selectedPaper={selectedPaper}
          handlers={handlers}
        />
      ))}

      {editor &&
        <AxisEditModal
          mode={editor.mode}
          axisId={editor.axisId}
          initialTitle={editor.title}
          initialDescription={editor.description}
          initialTerms={editor.terms}
          onClose={() => setEditor(null)}
          onSaved={onEditorSaved}
        />}

      {merging &&
        <MergeAxesModal
          axes={merging}
          onClose={() => setMerging(null)}
          onMerged={(keepId) => {
            setMerging(null);
            setSelectedIds(new Set());
            loadAxes();
            loadDetail(keepId);
            score(keepId);   // re-score the survivor so matching reflects the merged text
          }}
        />}

      {suggesting &&
        <SuggestAxesModal onClose={() => { setSuggesting(false); loadAxes(); }} />}
    </div>
  );
}
