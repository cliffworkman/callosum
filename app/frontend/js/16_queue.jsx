// inc 219: the Reading Queue — a personal, ordered to-read list shown as the third tab of the left-pane AXES
// section ([Axes | Tags | Queue]). A queue is NOT an axis (no scoring): a separate small table. Add by dragging a
// library card onto the panel (the inc-206 `application/x-callosum-paper` MIME) or via the Details "Reading queue"
// button; × removes, ✓ Done removes (a "finished it" gesture). Self-contained in this chunk so it never touches the
// at-cap 15_axes.jsx (rule #1). Hoisted in the IIFE.
//
// inc 294: stratified by the user's hand-set priority (High / Normal / Low / Unprioritized). Rows stay draggable —
// reorder WITHIN a group, or drag ACROSS groups to re-prioritise (reuses POST /papers/{id}/priority; dropping into
// Unprioritized clears it to null). Priority is the user's own triage label, never an AI score — grouping their own
// labels makes no claim about the literature (PRINCIPLES: the label is theirs). Order is the global manual order
// (PUT /reading-queue/order); grouping is a display layer on top of it.

const QUEUE_ITEM_MIME = "application/x-callosum-queueitem";
const PAPER_CARD_MIME = "application/x-callosum-paper";
const QUEUE_GROUPS = [
  { key: "high", label: "High" },
  { key: "normal", label: "Normal" },
  { key: "low", label: "Low" },
  { key: "unprioritized", label: "Unprioritized" },
];
const queueGroupOf = (it) =>
  it.priority === "high" || it.priority === "normal" || it.priority === "low" ? it.priority : "unprioritized";

function QueuePanel({ onOpenPaper, onSelectPaper, selectedPaper, queueRefresh, onQueueChanged, readOnly }) {
  const [items, setItems] = useState([]);
  const [cardOver, setCardOver] = useState(false); // dragging a library card over the panel (add)
  const [rowOver, setRowOver] = useState(null); // reorder drop-target row id
  const [groupOver, setGroupOver] = useState(null); // cross-group drop-target group key
  const [notice, setNotice] = useState(null);

  const load = useCallback(() => {
    api("/reading-queue").then((r) => { if (r.ok) setItems(r.data || []); });
  }, []);
  useEffect(() => { load(); }, [load, queueRefresh]);

  const changed = useCallback(() => { load(); if (onQueueChanged) onQueueChanged(); }, [load, onQueueChanged]);

  const remove = useCallback((id, doneMsg) => {
    apiDelete("/reading-queue/" + id).then((r) => {
      if (!r.ok) { setNotice(r.error); return; }
      setNotice(doneMsg);
      changed();
    });
  }, [changed]);

  const addPaper = useCallback((pid) => {
    apiPost("/reading-queue", { paper_id: pid }).then((r) => {
      if (!r.ok) { setNotice(r.error); return; }
      setNotice(r.data && r.data.added ? "Added to the queue" : "Already in the queue");
      changed();
    });
  }, [changed]);

  // Move a dragged paper. If its group changes, set the new priority first (Unprioritized → null clears it), then
  // splice the global order next to `targetId` (or to the END of `targetGroup` when dropping on the group itself),
  // then PUT the full id list (the inc-211/212 reorder contract). A same-group drop skips the priority write → a
  // plain reorder. onQueueChanged() lets the Library list + paper-card priority control reflect the new label.
  const moveTo = useCallback(async (draggedId, targetGroup, targetId) => {
    const dragged = items.find((it) => it.id === draggedId);
    if (!dragged || draggedId === targetId) return;
    if (queueGroupOf(dragged) !== targetGroup) {
      const priority = targetGroup === "unprioritized" ? null : targetGroup;
      const pr = await apiPost(`/papers/${draggedId}/priority`, { priority });
      if (!pr.ok) { setNotice(pr.error); return; }
    }
    const order = items.map((it) => it.id);
    const from = order.indexOf(draggedId);
    if (from >= 0) order.splice(from, 1);
    if (targetId != null) {
      const to = order.indexOf(targetId);
      order.splice(to < 0 ? order.length : to, 0, draggedId);
    } else {
      // dropped on the group (not a row): insert after the last existing member of that group in the global order
      let insertAt = order.length;
      for (let i = order.length - 1; i >= 0; i--) {
        const it = items.find((x) => x.id === order[i]);
        if (it && queueGroupOf(it) === targetGroup) { insertAt = i + 1; break; }
      }
      order.splice(insertAt, 0, draggedId);
    }
    const ord = await apiPut("/reading-queue/order", { paper_ids: order });
    if (!ord.ok) setNotice(ord.error);
    changed();
  }, [items, changed]);

  const rowDragProps = (it) => readOnly ? {} : {
    draggable: true,
    onDragStart: (e) => { e.dataTransfer.setData(QUEUE_ITEM_MIME, String(it.id)); e.dataTransfer.effectAllowed = "move"; },
    onDragOver: (e) => { if (e.dataTransfer.types.includes(QUEUE_ITEM_MIME)) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setRowOver(it.id); } },
    onDragLeave: () => setRowOver((o) => (o === it.id ? null : o)),
    onDrop: (e) => {
      if (!e.dataTransfer.types.includes(QUEUE_ITEM_MIME)) return;
      e.preventDefault(); e.stopPropagation(); setRowOver(null); setGroupOver(null);
      const dragged = parseInt(e.dataTransfer.getData(QUEUE_ITEM_MIME), 10);
      if (dragged) moveTo(dragged, queueGroupOf(it), it.id);
    },
  };

  const groupDropProps = (g) => readOnly ? {} : {
    onDragOver: (e) => { if (e.dataTransfer.types.includes(QUEUE_ITEM_MIME)) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setGroupOver(g.key); } },
    onDragLeave: (e) => { if (e.currentTarget === e.target) setGroupOver((o) => (o === g.key ? null : o)); },
    onDrop: (e) => {
      if (!e.dataTransfer.types.includes(QUEUE_ITEM_MIME)) return;
      e.preventDefault(); setGroupOver(null); setRowOver(null);
      const dragged = parseInt(e.dataTransfer.getData(QUEUE_ITEM_MIME), 10);
      if (dragged) moveTo(dragged, g.key, null);
    },
  };

  return (
    <div
      className={"queue-pane" + (cardOver ? " queue-drop" : "")}
      onDragOver={readOnly ? undefined : ((e) => { if (e.dataTransfer.types.includes(PAPER_CARD_MIME)) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; setCardOver(true); } })}
      onDragLeave={readOnly ? undefined : ((e) => { if (e.currentTarget === e.target) setCardOver(false); })}
      onDrop={readOnly ? undefined : ((e) => {
        if (!e.dataTransfer.types.includes(PAPER_CARD_MIME)) return;
        e.preventDefault(); setCardOver(false);
        const pid = parseInt(e.dataTransfer.getData(PAPER_CARD_MIME), 10);
        if (pid) addPaper(pid);
      })}
    >
      <div className="queue-head">
        {items.length > 0 ? `${items.length} paper${items.length === 1 ? "" : "s"}${readOnly ? "" : " · drag to reorder or re-prioritise"}` : "Reading queue"}
      </div>
      {notice && <div className="axis-err" onClick={() => setNotice(null)}>{notice}</div>}
      {items.length === 0 ? (
        <div className="axis-hint">Your reading queue is empty — drag a paper here, or use <b>+ Reading queue</b> in a paper's details.</div>
      ) : (
        QUEUE_GROUPS.map((g) => {
          const groupItems = items.filter((it) => queueGroupOf(it) === g.key);
          return (
            <div key={g.key} className={"queue-group" + (groupOver === g.key ? " drop" : "")} {...groupDropProps(g)}>
              <div className={"queue-group-head pr-" + (g.key === "unprioritized" ? "none" : g.key)}>
                {g.label} <span className="queue-group-count">{groupItems.length}</span>
              </div>
              {groupItems.length === 0
                ? (!readOnly && <div className="queue-group-empty">Drag a paper here to mark it {g.label.toLowerCase()}.</div>)
                : groupItems.map((it) => (
                  <div
                    key={it.id}
                    className={"queue-row" + (selectedPaper === it.id ? " sel" : "") + (rowOver === it.id ? " dragover" : "")}
                    {...rowDragProps(it)}
                  >
                    {!readOnly && <span className="axis-grip" title="Drag to reorder or move to another priority">⠿</span>}
                    <button className="queue-open" title="Open this paper"
                      onClick={() => { if (onOpenPaper) onOpenPaper({ id: it.id, title: it.title }); if (onSelectPaper) onSelectPaper(it.id); }}>
                      <span className="queue-title">{it.title}</span>
                      <span className="queue-meta">{[(it.authors || []).slice(0, 2).join(", "), it.year].filter(Boolean).join(" · ")}</span>
                    </button>
                    {!readOnly && <button className="queue-done" title="Mark as read — removes it from the queue" onClick={() => remove(it.id, "Marked done")}>✓</button>}
                    {!readOnly && <button className="queue-x" title="Remove from the queue" onClick={() => remove(it.id, "Removed")}>×</button>}
                  </div>
                ))}
            </div>
          );
        })
      )}
    </div>
  );
}

registerPaneTab(
  { id: "axes", label: "Axes", paneId: "theory", order: 10 },
  {
    id: "queue-tab", label: "Queue", order: 30,
    render: (ctx) => <QueuePanel onOpenPaper={ctx.onOpenPaper} onSelectPaper={ctx.onSelectPaper} readOnly={ctx.readOnly}
      selectedPaper={ctx.selectedPaper} queueRefresh={ctx.queueRefresh} onQueueChanged={ctx.onQueueChanged} />,
  },
);
