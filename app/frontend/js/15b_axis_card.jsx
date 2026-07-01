// Axis card — renders one axis card (AxisItem) + its presentational helpers (split from 15_axes.jsx,
// inc 222, which was over the 600-line cap). These are top-level function declarations in the shared
// IIFE, so they hoist — AxesPanel (15_axes.jsx) renders <AxisItem/> regardless of chunk order. Honesty
// contract: an assignment is an embedding similarity, never a categorical truth — the tier
// (assigned/uncertain/manual) + confidence are always shown, manual overrides marked distinctly.

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

function AxisPaperRow({ paper, selected, onOpen, onRemove, onConfirm, onStar, curated, readOnly }) {
  // A7: a curated row shows a drag grip (inc 212 — reorder by dragging) + title + remove — no tier/confidence
  // (every member is a hand-pick by definition, so the "manual" badge would be noise). Keyword rows keep the tiers.
  return (
    <div className={"axis-paper" + (selected ? " sel" : "")}>
      {curated && !readOnly && <span className="axis-grip" title="Drag to reorder">⠿</span>}
      {onStar && !readOnly &&
        <button className={"axis-star" + (paper.starred ? " on" : "")}
          title={paper.starred ? "Starred — click to unstar" : "Star this key publication (scopes the AI summary)"}
          onClick={() => onStar(paper.id, !paper.starred)}>{paper.starred ? "★" : "☆"}</button>}
      <span className="axis-paper-title" onClick={() => onOpen(paper)} title={"Open " + paper.title}>{paper.title}</span>
      {!curated && <AxisTierBadge status={paper.status} />}
      {!curated &&
        <span className="axis-paper-conf" title={paper.manual ? "Manually added by you" : "Embedding-similarity confidence"}>
          {axisConfidenceLabel(paper)}
        </span>}
      {!readOnly && !curated && paper.status === "uncertain" &&
        <button className="axis-confirm" title="Confirm — keep this paper on the axis (a manual override)" onClick={() => onConfirm(paper.id)}>✓</button>}
      {!readOnly && <button className="axis-x" title="Remove from this axis" onClick={() => onRemove(paper.id)}>×</button>}
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

function AxisItem({ axis, detail, job, expanded, selected, selectedPaper, handlers, hideUncertainDefault, axisCutoffDefault = 0.35, readOnly }) {
  const scoring = job && job.status === "running";
  const isMyPubs = axis.kind === "my_publications";  // inc 78: the pinned own-papers axis (variant UI, no scoring)
  const isCurated = axis.kind === "curated";  // A7 (inc 211): hand-populated + hand-ordered (no scoring UI; drag-droppable)
  // inc-105: an unscored axis's flipper starts at the Settings default cutoff; a stored per-axis gain still wins.
  const [cutoff, setCutoff] = useState(axis.scoring_gain != null ? axis.scoring_gain : axisCutoffDefault);
  // B′: eye toggle — show assigned/manual only. Starts from the Settings default (re-keyed on change → remount).
  const [hideUncertain, setHideUncertain] = useState(!!hideUncertainDefault);
  // inc 118 (SP2 #16): My Publications card — collapsible research-domain subheadings.
  const [collapsedDomains, setCollapsedDomains] = useState(() => new Set());
  // A6 (inc 206): a library card dragged onto a (non-My-Pubs) axis card manually adds it. My-Pubs is authorship-
  // resolved (✓/✕ only), so it's never a drop target. The drag payload rides the native dataTransfer (cross-pane).
  const [dragOver, setDragOver] = useState(false);
  const [dragMemberOver, setDragMemberOver] = useState(null);  // A7 SP2 (inc 212): the member row a drag is hovering
  const canDrop = !isMyPubs && !readOnly;  // B5 SP2: no drop-to-add on a read-only companion
  const stop = (fn) => (e) => { e.stopPropagation(); fn(); };
  const readyPapers = detail && detail.status === "ready" ? detail.papers : [];
  const uncertainCount = readyPapers.filter(p => p.status === "uncertain").length;
  // inc 79: when uncertain papers are hidden, the count badge shows the visible (assigned + manual) count.
  const total = axis.assignment_count || 0;
  const badgeCount = hideUncertain ? Math.max(0, total - (axis.uncertain_count || 0)) : total;

  const renderRow = (p) => (
    <AxisPaperRow key={p.id} paper={p} selected={selectedPaper === p.id} readOnly={readOnly}
      onOpen={handlers.openPaper}
      onConfirm={(pid) => handlers.confirmPaper(axis.id, pid)}
      onRemove={(pid) => handlers.removePaper(axis.id, pid)}
      onStar={isMyPubs ? ((pid, starred) => handlers.starPaper(axis.id, pid, starred)) : undefined} />
  );
  const toggleCollapse = (label) =>
    setCollapsedDomains(s => { const n = new Set(s); if (n.has(label)) n.delete(label); else n.add(label); return n; });
  // inc 118 (SP2 #16/#17): filter + sort (starred-first for My-Pubs), then group My-Pubs rows by domain ("Other" last).
  const renderPapers = (allPapers) => {
    if (isCurated) {
      // A7 SP2 (inc 212): render in the server's manual (position) order, drag-to-reorder. Each row is a drag
      // source + drop target via a member-only MIME (distinct from A6's "…-paper" so the card-level drop-to-add
      // never fires); dropping moves the dragged member to the target row's position → PUT /axes/{id}/order.
      const MEMBER_MIME = "application/x-callosum-axismember";
      return allPapers.map((p) => (
        <div key={p.id}
          className={"axis-member-drag" + (dragMemberOver === p.id ? " dragover" : "")}
          draggable={!readOnly}
          onDragStart={readOnly ? undefined : (e => { e.stopPropagation(); e.dataTransfer.setData(MEMBER_MIME, String(p.id)); e.dataTransfer.effectAllowed = "move"; })}
          onDragOver={readOnly ? undefined : (e => { if (e.dataTransfer.types.includes(MEMBER_MIME)) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setDragMemberOver(p.id); } })}
          onDragLeave={readOnly ? undefined : (() => setDragMemberOver(o => (o === p.id ? null : o)))}
          onDrop={readOnly ? undefined : (e => {
            setDragMemberOver(null);
            const dragged = parseInt(e.dataTransfer.getData(MEMBER_MIME), 10);
            if (dragged && dragged !== p.id) { e.preventDefault(); e.stopPropagation(); handlers.reorderToIndex(axis.id, dragged, p.id); }
          })}>
          <AxisPaperRow paper={p} selected={selectedPaper === p.id} curated readOnly={readOnly}
            onOpen={handlers.openPaper}
            onRemove={(pid) => handlers.removePaper(axis.id, pid)} />
        </div>
      ));
    }
    const sorted = [...allPapers]
      .filter(p => !hideUncertain || p.status !== "uncertain")
      .sort((a, b) =>
        (isMyPubs ? (b.starred ? 1 : 0) - (a.starred ? 1 : 0) : 0)
        || _tierRank(a) - _tierRank(b)
        || (b.confidence || 0) - (a.confidence || 0));
    if (!(isMyPubs && sorted.some(p => p.domain))) return sorted.map(renderRow);
    const groupsMap = new Map();
    for (const p of sorted) {
      const k = p.domain || "Other";
      if (!groupsMap.has(k)) groupsMap.set(k, []);
      groupsMap.get(k).push(p);
    }
    const ordered = [...groupsMap.entries()].sort(
      (a, b) => (a[0] === "Other") - (b[0] === "Other") || b[1].length - a[1].length
    );
    return ordered.map(([label, rows]) => (
      <div key={label} className="axis-domain-group">
        <button className="axis-domain-subhead" onClick={() => toggleCollapse(label)}>
          {collapsedDomains.has(label) ? "▸" : "▾"} {label} <span className="axis-domain-count">{rows.length}</span>
        </button>
        {!collapsedDomains.has(label) && rows.map(renderRow)}
      </div>
    ));
  };
  return (
    <div className={"axis-item" + (isMyPubs ? " axis-mypubs" : "")}>
      <div className={"axis" + (expanded ? " active" : "") + (dragOver ? " drag-over" : "")} onClick={() => handlers.toggle(axis.id)}
        onDragOver={canDrop ? (e => { if (e.dataTransfer.types.includes("application/x-callosum-paper")) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; setDragOver(true); } }) : undefined}
        onDragLeave={canDrop ? (() => setDragOver(false)) : undefined}
        onDrop={canDrop ? (e => {
          setDragOver(false);
          const pid = parseInt(e.dataTransfer.getData("application/x-callosum-paper"), 10);
          if (pid) { e.preventDefault(); handlers.dropPaper(axis.id, pid); }
        }) : undefined}>
        <div className="axis-row-head">
          {!readOnly && !isMyPubs &&
            <input
              type="checkbox" className="axis-select" checked={selected}
              title="Select for bulk delete / merge"
              onClick={e => e.stopPropagation()}
              onChange={() => handlers.toggleSelect(axis.id)}
            />}
          <span className="axis-label">{isMyPubs ? "📄 " + axis.label : isCurated ? "📌 " + axis.label : axis.label}</span>
          <span className="axis-card-actions">
            {!readOnly && !isMyPubs && <button className="axis-icon-btn" title="Edit axis" onClick={stop(() => handlers.openEdit(axis))}>✎</button>}
            {!readOnly && !isMyPubs && <button className="axis-icon-btn" title="Add papers from the library" onClick={stop(() => handlers.enterFocus(axis))}>＋</button>}
            {!readOnly && !isMyPubs && !isCurated &&
              <button className="axis-icon-btn" title="Freeze to a curated set — snapshot the current members + unlock manual ordering"
                onClick={stop(() => handlers.freeze(axis.id))}>❄</button>}
            {!readOnly && isCurated &&
              <button className="axis-icon-btn" title="Convert to a keyword axis — needs search terms and replaces your manual order with fit order; members are kept"
                onClick={stop(() => handlers.convertToKeyword(axis.id))}>↩</button>}
            {isMyPubs && <button className="axis-icon-btn" title="Open the impact dashboard" onClick={stop(() => handlers.openMyPubsDashboard(axis))}>📊</button>}
            {!readOnly && <button className="axis-icon-btn axis-icon-danger"
              title={isMyPubs ? "Dismiss My Publications (keeps your profile)" : "Delete axis"}
              onClick={stop(() => (isMyPubs ? handlers.dismissMyPubs() : handlers.remove(axis.id)))}>🗑</button>}
            <button
              className={"axis-count-badge" + (isMyPubs ? " is-scored" : isCurated ? " is-curated" : axis.scored ? (axis.stale ? " is-stale" : " is-scored") : "")}
              title={isMyPubs
                ? `Show your ${axis.assignment_count || 0} papers in the library`
                : isCurated
                  ? `Show these ${axis.assignment_count || 0} hand-picked papers in the library`
                  : (hideUncertain && (axis.uncertain_count || 0) > 0
                      ? `${badgeCount} assigned · ${axis.uncertain_count} uncertain hidden — click to show this axis in the library`
                      : `Show these ${axis.assignment_count || 0} papers in the library` + (axis.scored ? (axis.stale ? " · edited since scoring" : " · scored & up to date") : " · not scored yet"))}
              onClick={stop(() => handlers.filterToAxis(axis, hideUncertain))}
            >{badgeCount}</button>
          </span>
        </div>
      </div>

      {expanded &&
        <div className="axis-body">
          {!readOnly && isCurated &&
            <div className="axis-curated-hint">Hand-picked set — drag papers from the library onto this card to add them; reorder with ↑/↓.</div>}
          {!readOnly && !isMyPubs && !isCurated &&
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
              ? <div className="axis-hint">{isMyPubs ? "No publications matched yet — set your name/ORCID in Settings (⚙) and Refresh." : isCurated ? "Empty — drag papers from the library onto this card to add them." : axis.scored ? "No papers were close enough to this axis. Add one manually if the scorer missed it." : "Score this axis to assign papers, or add one manually."}</div>
              : <div className="axis-papers">
                  {renderPapers(detail.papers)}
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
