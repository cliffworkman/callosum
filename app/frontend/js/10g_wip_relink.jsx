function WipRelink({ manuscript, onRelinked }) {
  const [editing, setEditing] = useState(false);
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event) => {
    event.preventDefault();
    if (!path.trim()) return;
    setBusy(true);
    setError("");
    const result = await apiPost(`/wip/manuscripts/${manuscript.id}/relink`, { path: path.trim() });
    setBusy(false);
    if (!result.ok) {
      setError(result.error || "Could not relink this manuscript.");
      return;
    }
    setEditing(false);
    setPath("");
    if (onRelinked) onRelinked(result.data);
  };
  return <div className="wip-location">
    <div>
      <span>Manuscript location</span>
      <code title={manuscript.root_path}>{manuscript.root_path}</code>
    </div>
    <button className="btn-ghost" onClick={() => { setEditing(value => !value); setError(""); }}>
      {editing ? "Cancel" : "Relink folder"}
    </button>
    {editing && <form onSubmit={submit}>
      <input aria-label="New manuscript folder" placeholder="Full path to the relocated manuscript folder"
        value={path} onChange={event => setPath(event.target.value)} />
      <button className="btn-primary" disabled={busy || !path.trim()}>{busy ? "Relinking…" : "Relink"}</button>
    </form>}
    {error && <div className="wip-root-error">{error}</div>}
  </div>;
}
