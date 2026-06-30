// inc 219: the Reading Queue — a personal, ordered to-read list shown as the third tab of the left-pane AXES
// section ([Axes | Tags | Queue]). A queue is NOT an axis (no scoring): a separate small table. Add by dragging a
// library card onto the panel (the inc-206 `application/x-callosum-paper` MIME) or via the Details "Reading queue"
// button; drag-to-reorder via a queue-only MIME (the inc-212 pattern); × removes, ✓ Done removes (a "finished it"
// gesture). Self-contained in this chunk so it never touches the at-cap 15_axes.jsx (rule #1). Hoisted in the IIFE.

const QUEUE_ITEM_MIME = "application/x-callosum-queueitem";
const PAPER_CARD_MIME = "application/x-callosum-paper";

function QueuePanel({ onOpenPaper, onSelectPaper, selectedPaper, queueRefresh, onQueueChanged }) {
  const [items, setItems] = useState([]);
  const [cardOver, setCardOver] = useState(false); // dragging a library card over the panel (add)
  const [rowOver, setRowOver] = useState(null); // reorder drop-target row id
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

  // Reorder: splice the current order, then PUT the full id list (the inc-211/212 curated-axis contract).
  const reorderToIndex = useCallback((draggedId, targetId) => {
    if (draggedId === targetId) return;
    const order = items.map((it) => it.id);
    const from = order.indexOf(draggedId);
    if (from < 0) return;
    order.splice(from, 1);
    const to = order.indexOf(targetId);
    order.splice(to < 0 ? order.length : to, 0, draggedId);
    apiPut("/reading-queue/order", { paper_ids: order }).then((r) => { if (!r.ok) setNotice(r.error); load(); });
  }, [items, load]);

  return (
    <div
      className={"queue-pane" + (cardOver ? " queue-drop" : "")}
      onDragOver={(e) => { if (e.dataTransfer.types.includes(PAPER_CARD_MIME)) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; setCardOver(true); } }}
      onDragLeave={(e) => { if (e.currentTarget === e.target) setCardOver(false); }}
      onDrop={(e) => {
        if (!e.dataTransfer.types.includes(PAPER_CARD_MIME)) return;
        e.preventDefault(); setCardOver(false);
        const pid = parseInt(e.dataTransfer.getData(PAPER_CARD_MIME), 10);
        if (pid) addPaper(pid);
      }}
    >
      <div className="queue-head">
        {items.length > 0 ? `${items.length} paper${items.length === 1 ? "" : "s"} · drag to reorder` : "Reading queue"}
      </div>
      {notice && <div className="axis-err" onClick={() => setNotice(null)}>{notice}</div>}
      {items.length === 0 ? (
        <div className="axis-hint">Your reading queue is empty — drag a paper here, or use <b>+ Reading queue</b> in a paper's details.</div>
      ) : (
        items.map((it) => (
          <div
            key={it.id}
            className={"queue-row" + (selectedPaper === it.id ? " sel" : "") + (rowOver === it.id ? " dragover" : "")}
            draggable
            onDragStart={(e) => { e.dataTransfer.setData(QUEUE_ITEM_MIME, String(it.id)); e.dataTransfer.effectAllowed = "move"; }}
            onDragOver={(e) => { if (e.dataTransfer.types.includes(QUEUE_ITEM_MIME)) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setRowOver(it.id); } }}
            onDragLeave={() => setRowOver((o) => (o === it.id ? null : o))}
            onDrop={(e) => {
              if (!e.dataTransfer.types.includes(QUEUE_ITEM_MIME)) return;
              e.preventDefault(); e.stopPropagation(); setRowOver(null);
              const dragged = parseInt(e.dataTransfer.getData(QUEUE_ITEM_MIME), 10);
              if (dragged) reorderToIndex(dragged, it.id);
            }}
          >
            <span className="axis-grip" title="Drag to reorder">⠿</span>
            <button className="queue-open" title="Open this paper"
              onClick={() => { if (onOpenPaper) onOpenPaper({ id: it.id, title: it.title }); if (onSelectPaper) onSelectPaper(it.id); }}>
              <span className="queue-title">{it.title}</span>
              <span className="queue-meta">{[(it.authors || []).slice(0, 2).join(", "), it.year].filter(Boolean).join(" · ")}</span>
            </button>
            <button className="queue-done" title="Mark as read — removes it from the queue" onClick={() => remove(it.id, "Marked done")}>✓</button>
            <button className="queue-x" title="Remove from the queue" onClick={() => remove(it.id, "Removed")}>×</button>
          </div>
        ))
      )}
    </div>
  );
}

registerPaneTab(
  { id: "axes", label: "Axes", paneId: "theory", order: 10 },
  {
    id: "queue-tab", label: "Queue", order: 30,
    render: (ctx) => <QueuePanel onOpenPaper={ctx.onOpenPaper} onSelectPaper={ctx.onSelectPaper}
      selectedPaper={ctx.selectedPaper} queueRefresh={ctx.queueRefresh} onQueueChanged={ctx.onQueueChanged} />,
  },
);
