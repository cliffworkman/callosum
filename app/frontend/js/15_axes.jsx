// Axes panel — create, browse, score, and correct user-defined axes (supervised lens).
// Honesty contract: an assignment is an embedding similarity, never a categorical truth. We
// always show the tier (assigned / uncertain / manual) + confidence, mark manual overrides
// distinctly from the scorer's calls, and surface staleness. The human can add/remove papers.

// Shown pinned at the top of the axes panel when My Publications hasn't been set up yet (inc 78).
function MyPubsPrompt() {
  return (
    <div className="axis-mypubs-prompt" title="Set your name / ORCID in Settings to auto-gather your own papers">
      📄 <b>My Publications</b> — set your name / ORCID in Settings (⚙) to auto-gather your own papers.
    </div>
  );
}

function AxesPanel({ onSelectPaper, selectedPaper, onOpenPaper, onEnterFocus, onFilterToAxis, onOpenMyPubsDashboard, axisRefresh, hideUncertainDefault, axisCutoffDefault }) {
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

  // A6 (inc 206): drag-and-drop a library paper onto a (non-My-Pubs) axis card → a manual override (the same
  // POST /axes/{id}/papers the ✓-confirm uses). Refreshes the open card + the badge counts; flashes on success.
  const dropPaper = useCallback((axisId, paperId) => {
    apiPost(`/axes/${axisId}/papers`, { paper_id: paperId }).then(r => {
      if (!r.ok) { flash(r.error); return; }
      const ax = (axes || []).find(a => a.id === axisId);
      flash(`Added to ${ax ? ax.label : "axis"}`);
      loadDetail(axisId);
      loadAxes();
    });
  }, [axes, loadDetail, loadAxes, flash]);

  // A7 SP2 (inc 212): drag-to-reorder a curated axis's members. Move `draggedId` to `targetId`'s slot in the
  // current (server position) order and PUT the full id list (the endpoint validates it == the member set).
  const reorderToIndex = useCallback((axisId, draggedId, targetId) => {
    const cur = (details[axisId] && details[axisId].papers) || [];
    const order = cur.map(p => p.id);
    const from = order.indexOf(draggedId);
    if (from < 0 || draggedId === targetId) return;
    order.splice(from, 1);
    const to = order.indexOf(targetId);
    order.splice(to < 0 ? order.length : to, 0, draggedId);
    apiPut(`/axes/${axisId}/order`, { paper_ids: order }).then(r => {
      if (!r.ok) { flash(r.error); return; }
      loadDetail(axisId);
    });
  }, [details, loadDetail, flash]);

  // A7: "freeze" a keyword axis to a curated set — snapshot the shown members (uncertain dropped) → manual+ordered.
  const freeze = useCallback((axisId) => {
    if (!window.confirm("Freeze this axis to a curated set? It snapshots the current members (uncertain ones are dropped) and unlocks manual ordering — you can convert it back later.")) return;
    apiPatch(`/axes/${axisId}`, { kind: "curated" }).then(r => {
      if (!r.ok) { flash(r.error); return; }
      loadAxes();
      if (expanded === axisId) loadDetail(axisId);
    });
  }, [loadAxes, loadDetail, flash, expanded]);

  // A7: convert a curated axis back to a keyword axis (warned — members kept, manual order lost, axis goes stale).
  const convertToKeyword = useCallback((axisId) => {
    if (!window.confirm("Convert to a keyword axis? It needs search terms and replaces your manual order with fit order — your members are kept. Re-score afterwards to populate it.")) return;
    apiPatch(`/axes/${axisId}`, { kind: "standard" }).then(r => {
      if (!r.ok) { flash(r.error); return; }
      loadAxes();
      if (expanded === axisId) loadDetail(axisId);
    });
  }, [loadAxes, loadDetail, flash, expanded]);

  // A7: create an empty curated axis by name (you then drag papers onto it). No terms/scoring — label only.
  const createCurated = useCallback(() => {
    const name = window.prompt("Name this curated axis (then drag papers from the library onto it):");
    if (!name || !name.trim()) return;
    apiPost("/axes", { label: name.trim(), kind: "curated" }).then(r => {
      if (!r.ok) { flash(r.error); return; }
      loadAxes();
      if (r.data && r.data.id) { setExpanded(r.data.id); loadDetail(r.data.id); }
    });
  }, [loadAxes, loadDetail, flash]);

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

  const filterToAxis = useCallback((axis, hideUncertain) => {
    // A10: carry the card's hide-uncertain state so the library view matches the card (shown == summarized).
    if (onFilterToAxis) onFilterToAxis({ id: axis.id, label: axis.label, hideUncertain: !!hideUncertain });
  }, [onFilterToAxis]);

  const openMyPubsDashboard = useCallback((axis) => {
    if (onOpenMyPubsDashboard) onOpenMyPubsDashboard(axis);
  }, [onOpenMyPubsDashboard]);

  const starPaper = useCallback((axisId, paperId, starred) => {
    apiPost("/my-publications/star", { paper_id: paperId, starred }).then(r => {
      if (r.ok) loadDetail(axisId);  // reflect the ★/☆ flip in the card
    });
  }, [loadDetail]);

  const handlers = {
    toggle, score, remove, removePaper, confirmPaper, dropPaper, dismissMyPubs, enterFocus, filterToAxis,
    openMyPubsDashboard, starPaper, toggleSelect, openEdit, openPaper,
    reorderToIndex, freeze, convertToKeyword,  // A7: curated-axis drag-reorder (SP2) + freeze/revert switch
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
      {/* inc 121: the "Axes" label is now the accordion section header (see 05_panes.jsx) — no inner eyebrow. */}
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
        <button className="axis-new" title="New curated axis (hand-picked, hand-ordered)" onClick={createCurated}>📌</button>
        <button className="axis-new" title={quickName != null ? "Cancel" : "New keyword axis"} onClick={() => { setQuickName(q => q == null ? "" : null); setNotice(null); }}>{quickName != null ? "×" : "+"}</button>
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
          key={axis.id + (hideUncertainDefault ? "-h" : "-s") + "-c" + axisCutoffDefault}
          hideUncertainDefault={hideUncertainDefault}
          axisCutoffDefault={axisCutoffDefault}
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

// inc 121 / inc 139: AXES is a THEORY-pane accordion section; the "Axes" view is its first tab (Tags is the
// second, registered in 10_pdf_layer.jsx — like-with-like, see 05_panes.jsx + DESIGN.md §5).
registerPaneTab(
  { id: "axes", label: "Axes", paneId: "theory", order: 10 },
  { id: "axes-tab", label: "Axes", order: 10,
    render: (ctx) => <AxesPanel onSelectPaper={ctx.onSelectPaper} selectedPaper={ctx.selectedPaper}
      onOpenPaper={ctx.onOpenPaper} onEnterFocus={ctx.onEnterFocus} onFilterToAxis={ctx.onFilterToAxis}
      onOpenMyPubsDashboard={ctx.onOpenMyPubsDashboard} axisRefresh={ctx.axisRefresh}
      hideUncertainDefault={ctx.hideUncertainDefault} axisCutoffDefault={ctx.axisCutoffDefault} /> },
);
