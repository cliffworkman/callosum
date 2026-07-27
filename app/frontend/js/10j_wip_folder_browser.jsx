// A generic server-driven local-folder picker -- the in-app browser a plain browser tab needs since it has no
// native OS file-dialog access (uvicorn on 127.0.0.1 and the packaged Tauri shell both hit this same server
// endpoint, GET /wip/browse-dirs). Currently wired only from WipRootSetup + WipRelink's "Browse…" buttons
// (10f_wip.jsx / 10g_wip_relink.jsx), but intentionally generic -- no Wip-specific state -- for any future
// "paste a folder path" control to adopt the same way.
function FolderBrowserModal({ title = "Choose a folder", initialPath, onCancel, onSelect }) {
  const [path, setPath] = useState(null);
  const [parent, setParent] = useState(null);
  const [entries, setEntries] = useState([]);
  const [truncated, setTruncated] = useState(false);
  const [listError, setListError] = useState("");   // this folder's own contents couldn't be listed (Up still works)
  const [navError, setNavError] = useState("");     // navigating away failed; last-good folder stays shown
  const [fatalError, setFatalError] = useState(""); // only possible on the very first load
  const [loading, setLoading] = useState(true);

  const load = (target) => {
    setLoading(true);
    const query = target ? `?path=${encodeURIComponent(target)}` : "";
    api(`/wip/browse-dirs${query}`).then(r => {
      setLoading(false);
      if (!r.ok) {
        if (path === null) setFatalError(r.error || "Could not open this folder.");
        else setNavError(r.error || "Could not open that folder.");
        return;
      }
      setPath(r.data.path); setParent(r.data.parent); setEntries(r.data.entries || []);
      setTruncated(!!r.data.truncated); setListError(r.data.error || ""); setNavError("");
    });
  };
  useEffect(() => { load(initialPath || undefined); }, []);  // eslint-disable-line react-hooks/exhaustive-deps -- mount-only

  return (
    <div className="axis-modal-overlay" onClick={onCancel}>
      <div className="axis-modal folder-browser-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head"><span>{title}</span><button className="axis-link" onClick={onCancel}>×</button></div>
        {fatalError && <div className="axis-err">{fatalError}</div>}
        {!fatalError && <React.Fragment>
          <div className="folder-browser-path" title={path || ""}>{path || "Loading…"}</div>
          {navError && <div className="axis-err">{navError}</div>}
          <div className="folder-browser-list">
            <button className="folder-browser-row folder-browser-up" disabled={!parent || loading}
              onClick={() => load(parent)}>⬆ Up one level</button>
            {listError && <div className="axis-err">{listError}</div>}
            {!listError && !loading && entries.length === 0 && <div className="axis-hint">No subfolders here.</div>}
            {entries.map(entry =>
              <button key={entry.path} className="folder-browser-row" disabled={loading}
                onClick={() => load(entry.path)}>📁 {entry.name}</button>)}
          </div>
          {truncated && <div className="axis-hint">Showing the first {entries.length} folders only.</div>}
        </React.Fragment>}
        <div className="axis-form-actions">
          <button className="axis-link" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" disabled={!path || loading} onClick={() => onSelect(path)}>
            Select this folder
          </button>
        </div>
      </div>
    </div>
  );
}
