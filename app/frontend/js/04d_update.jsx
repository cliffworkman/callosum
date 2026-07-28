// Desktop-shell auto-updater notice — Rust (updater.rs) drives the whole check/download/ready
// lifecycle; this component only ever listens for one Tauri event and invokes one command of its
// own. Windows/macOS: the update is ALREADY silently downloaded by the time this fires (action =
// "restart") — clicking just installs + relaunches. Linux (no silent-update support — see
// updater.rs's header comment): action = "open-page", pointing at the GitHub release for a manual
// download. No new frontend npm dependency: uses the already-enabled `window.__TAURI__` global
// (`withGlobalTauri: true` in tauri.conf.json) rather than an import the build pipeline can't
// resolve (esbuild here runs in transform-only mode, no bundler — see 04d_update's sibling note
// in the increment notes).

function UpdateNotice() {
  const [ready, setReady] = useState(null); // {version, notes, action: "restart" | "open-page"}
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!("__TAURI__" in window)) return; // no-op in a plain browser / the remote-access tunnel
    let unlisten;
    window.__TAURI__.event.listen("update-ready", (e) => setReady(e.payload)).then(f => { unlisten = f; });
    return () => { if (unlisten) unlisten(); };
  }, []);

  if (!ready) return null;

  const act = () => window.__TAURI__.core.invoke(
    ready.action === "restart" ? "install_update_now" : "open_release_page"
  );
  const label = ready.action === "restart" ? "Restart now" : "Open release page";

  if (dismissed) {
    return (
      <button className="update-pill" onClick={() => setDismissed(false)} title={`Update ready — v${ready.version}`}>
        Update ready
      </button>
    );
  }
  return (
    <div className="update-toast" role="status">
      <span className="update-toast-text">Update ready — v{ready.version}</span>
      <button className="btn btn-primary" onClick={act}>{label}</button>
      <button className="btn btn-ghost" onClick={() => setDismissed(true)}>Later</button>
    </div>
  );
}
