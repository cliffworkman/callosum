// Entity-specific manuscript context actions. Every item delegates to an existing WIP operation; actions that
// require evidence/result feedback stay in the full workspace rather than becoming silent card shortcuts.
function WipContextMenu({ menu, onClose, onOpen, onUpdate, onRescan, onDelete }) {
  useEffect(() => {
    if (!menu) return undefined;
    const close = () => onClose();
    const onKey = event => { if (event.key === "Escape") close(); };
    window.addEventListener("mousedown", close);
    window.addEventListener("contextmenu", close);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", close);
      window.removeEventListener("contextmenu", close);
      window.removeEventListener("keydown", onKey);
    };
  }, [menu, onClose]);
  if (!menu) return null;
  const manuscript = menu.manuscript;
  const left = Math.max(8, Math.min(menu.x, window.innerWidth - 218));
  const top = Math.max(8, Math.min(menu.y, window.innerHeight - 285));
  const update = async values => {
    const result = await onUpdate(manuscript.id, values);
    if (result && result.ok) onClose();
  };
  const rescan = async () => {
    onClose();
    await onRescan();
  };
  const remove = async () => {
    onClose();
    if (!window.confirm(`Remove "${manuscript.display_title}" from WIP? This deletes its tasks, notes, checks, and activity history, and cannot be undone. The manuscript's own files on disk are untouched.`)) return;
    await onDelete(manuscript.id);
  };
  return <div className="wip-context-menu" role="menu" aria-label="Manuscript actions"
    style={{ left, top }} onMouseDown={event => event.stopPropagation()}
    onContextMenu={event => event.stopPropagation()}>
    <button role="menuitem" onClick={() => { onClose(); onOpen(manuscript); }}>Open workspace</button>
    <label>Stage
      <select value={manuscript.stage} onChange={event => update({ stage: event.target.value })}>
        {WIP_STAGES.map(item => <option key={item[0]} value={item[0]}>{item[1]}</option>)}
      </select>
    </label>
    {["active", "paused"].includes(manuscript.state) &&
      <button role="menuitem" onClick={() => update({ state: manuscript.state === "paused" ? "active" : "paused" })}>
        {manuscript.state === "paused" ? "Resume tracking" : "Pause tracking"}
      </button>}
    <button role="menuitem" onClick={() => update({ state: manuscript.state === "archived" ? "active" : "archived" })}>
      {manuscript.state === "archived" ? "Restore to active" : "Archive manuscript"}
    </button>
    <button role="menuitem" onClick={rescan}>Rescan files</button>
    <hr className="wip-context-menu-divider" />
    <button role="menuitem" className="wip-context-menu-danger" onClick={remove}>Remove manuscript</button>
  </div>;
}
