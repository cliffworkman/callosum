// Desktop-shell auto-updater notice — Rust (updater.rs) drives the whole check/download/ready
// lifecycle; the frontend only ever listens for its events + invokes its commands. Windows/macOS:
// the update is ALREADY silently downloaded by the time the "ready" phase fires — clicking just
// installs + relaunches. Linux (no silent-update support — see updater.rs's header comment): the
// "ready" phase points at the GitHub release for a manual download instead. No new frontend npm
// dependency: uses the already-enabled `window.__TAURI__` global (`withGlobalTauri: true` in
// tauri.conf.json) rather than an import the build pipeline can't resolve (esbuild here runs in
// transform-only mode, no bundler — see 04d_update's sibling note in the increment notes).

// Shared across the toast below AND the Status popover (04c_status.jsx) — a single source of truth
// for "what is the desktop update doing right now" so both surfaces read the same live state
// instead of each keeping its own duplicate Tauri event listener.
function useDesktopUpdate() {
  const [update, setUpdate] = useState({ phase: "idle" });

  useEffect(() => {
    if (!("__TAURI__" in window)) return; // no-op in a plain browser / the remote-access tunnel
    const unlisten = [];
    const on = (name, fn) => window.__TAURI__.event.listen(name, fn).then(f => unlisten.push(f));
    on("update-downloading", (e) => setUpdate({ phase: "downloading", version: e.payload.version, downloaded: 0, total: null }));
    on("update-progress", (e) => setUpdate({
      phase: "downloading", version: e.payload.version, downloaded: e.payload.downloaded, total: e.payload.total,
    }));
    on("update-ready", (e) => setUpdate({ phase: "ready", version: e.payload.version, notes: e.payload.notes, action: e.payload.action }));
    return () => unlisten.forEach(f => f());
  }, []);

  return update;
}

function UpdateNotice({ update }) {
  const [dismissed, setDismissed] = useState(false);

  if (!update || update.phase !== "ready") return null;

  const act = () => window.__TAURI__.core.invoke(
    update.action === "restart" ? "install_update_now" : "open_release_page"
  );
  const label = update.action === "restart" ? "Restart now" : "Open release page";

  if (dismissed) {
    return (
      <button className="update-pill" onClick={() => setDismissed(false)} title={`Update ready — v${update.version}`}>
        Update ready
      </button>
    );
  }
  return (
    <div className="update-toast" role="status">
      <span className="update-toast-text">Update ready — v{update.version}</span>
      <button className="btn btn-primary" onClick={act}>{label}</button>
      <button className="btn btn-ghost" onClick={() => setDismissed(true)}>Later</button>
    </div>
  );
}
