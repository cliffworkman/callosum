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
    // Seed from the current phase as well as listening (inc 574). The update check starts on app
    // setup and fires 30s later, but THIS window is only created once the backend is healthy — a
    // cold start the splash itself warns "can take a minute the first time". So update-downloading
    // and update-ready are routinely emitted before this listener exists, and Tauri never replays
    // an event: the toast simply never appeared and Status stayed empty, even though the update had
    // downloaded fine. Listening alone can only ever narrow that race; asking closes it.
    window.__TAURI__.core.invoke("current_update_state")
      .then(snapshot => {
        if (snapshot && snapshot.phase && snapshot.phase !== "idle") {
          setUpdate(current => (current.phase === "idle" ? snapshot : current)); // a live event always wins
        }
      })
      .catch(() => {}); // an older shell without the command: fall back to events-only, as before
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

// Settings > Account & sync > Desktop app. Hoisted here from 35_settings.jsx in inc 574 so every
// updater string lives beside the updater (and to keep that file under the 600-line cap).
//
// The copy here previously read "Update ready — vX. Restart to install." That was false, and a
// real user acted on it and lost the download: updater.rs holds the downloaded bytes in memory and
// installs them ONLY via install_update_now. Quitting and relaunching normally discards them. On
// Linux it was false twice over — nothing is downloaded there at all; the release page is the only
// path. So this now offers the action that actually installs, and says plainly what happens if you
// don't take it.
function DesktopUpdateSettings({ desktopUpdate }) {
  const [outcome, setOutcome] = useState(null); // the manual check's own one-shot result, or null
  const [checking, setChecking] = useState(false);
  // The running version, stated plainly rather than only in the logo's hover tooltip. This is the
  // first thing a bug report needs, and the update flow above is precisely where someone discovers
  // they are not on the version they expected. Read from /health (`app_version`, inc 417) — the
  // same source the feedback dialog uses, so a report and this label can never disagree.
  const [version, setVersion] = useState(null);
  useEffect(() => {
    let active = true;
    api("/health").then(response => {
      if (active && response.ok && response.data) setVersion(response.data.app_version || null);
    }).catch(() => {});
    return () => { active = false; };
  }, []);
  if (!("__TAURI__" in window)) return null;

  const check = async () => {
    setChecking(true); setOutcome(null);
    try {
      setOutcome(await window.__TAURI__.core.invoke("check_for_updates_now"));
    } catch (e) {
      setOutcome({ kind: "Failed", detail: String(e) });
    }
    setChecking(false);
  };

  const live = desktopUpdate && desktopUpdate.phase !== "idle" ? desktopUpdate : null;
  const ready = live && live.phase === "ready" ? live : null;
  // The one-shot outcome carries no `action`, so it can only ever be a version fallback — never the
  // basis for telling the user which action installs it.
  const readyVersion = ready ? ready.version : null;

  let statusText = null;
  if (live && live.phase === "downloading") statusText = `Downloading v${live.version}…`;
  else if (outcome && !ready) {
    if (outcome.kind === "UpToDate") statusText = "You're up to date.";
    else if (outcome.kind === "Downloading") statusText = `Found v${outcome.version} — downloading…`;
    else if (outcome.kind === "Ready") statusText = `Update v${outcome.version} is ready.`;
    else if (outcome.kind === "Failed") statusText = `Couldn't check for updates: ${outcome.detail}`;
  }

  const installable = ready && ready.action === "restart";
  return (
    <div className="settings-subsection">
      <p className="eyebrow">Desktop app</p>
      <span className="settings-sub">{version ? `Version ${version}` : "Version …"}</span>
      <div className="settings-row">
        <span className="settings-field-label">Updates</span>
        {readyVersion
          ? <button className="btn btn-primary" onClick={() => window.__TAURI__.core.invoke(
              installable ? "install_update_now" : "open_release_page")}>
              {installable ? `Install v${readyVersion} and restart` : `Get v${readyVersion}`}
            </button>
          : <button className="btn btn-ghost" disabled={checking} onClick={check}>
              {checking ? "Checking…" : "Check for updates"}
            </button>}
      </div>
      {readyVersion && (
        <span className="settings-sub">
          {installable
            ? "Downloaded and ready. Use this button to install it — quitting Callosum without installing discards the download, and it will be offered again next time."
            : "Linux updates are installed by hand: this opens the release page so you can download the .deb."}
        </span>
      )}
      {statusText && <span className="settings-sub">{statusText}</span>}
    </div>
  );
}
