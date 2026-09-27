// Manual preview is a desktop privilege, never a remotely callable backend setup route.
function BrowserCaptureSettings() {
  const packaged = !!window.__TAURI__?.core?.invoke;
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [browser, setBrowser] = useState("Chrome");
  const invoke = (action) => window.__TAURI__.core.invoke("browser_preview", { action });
  useEffect(() => {
    if (!packaged) return;
    let live = true;
    invoke("status").then(s => { if (live) setState(s); }).catch(e => { if (live) setError(String(e)); });
    return () => { live = false; };
  }, [packaged]);
  useEffect(() => {
    if (state?.connection !== "waiting") return;
    let live = true;
    const timer = setInterval(() => invoke("status").then(s => { if (live) setState(s); })
      .catch(e => { if (live) { setError(String(e)); setState(s => ({ ...s, connection: "failed" })); } }), 1000);
    return () => { live = false; clearInterval(timer); };
  }, [state?.connection]);
  const act = async (action) => {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await invoke(action); setState(result);
      const messages = {
        enable: "Early access enabled. Prepare the extension next; it is not installed in your browser yet.",
        prepare: "Package verified and prepared. Load unpacked in your browser, or Reload it there after an update.",
        open_folder: "Folder opened. Browser installation and connection have not been verified.",
        disable: "Preview disabled. Remove Callosum Capture (early access) on your browser's Extensions page. Captured papers are kept.",
      };
      setNotice(result.cleanup_error ? `Preview disabled. ${result.cleanup_error}` : (messages[action] || ""));
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };
  return (
    <div className="browser-preview">
      <p className="eyebrow">Browser Capture — early access</p>
      <p className="settings-sub">Send a page or PDF you have open to Callosum for review. This opt-in preview requires manual installation using your browser's Developer mode. It is not a store installation and may be blocked by your organization's browser policy.</p>
      {!packaged ? <p className="settings-sub">Open the installed Callosum desktop app to prepare this integration. Remote access cannot install or manage local extension files.</p> : <>
        {!state?.enabled ? <button className="btn btn-primary" disabled={busy || !state} onClick={() => act("enable")}>Enable early access</button> : <>
          <div className="settings-actions">
            <button className="btn btn-primary" disabled={busy} onClick={() => act("prepare")}>Prepare extension</button>{" "}
            <button className="btn btn-ghost" disabled={busy || !state.prepared} onClick={() => act("open_folder")}>Open extension folder</button>{" "}
            <button className="btn btn-ghost" disabled={busy || !state.prepared || state.update_available} onClick={() => act("verify")}>Verify connection</button>{" "}
            <button className="btn btn-ghost" disabled={busy} onClick={() => act("disable")}>Turn off early access</button>
          </div>
          {state.update_available && <p className="settings-sub">An extension update is available. Prepare it, then Reload the extension in your browser. Your installation folder stays the same.</p>}
          {state.prepared && <>
            <p className="settings-sub">Prepared version {state.prepared_version}. Folder: <code>{state.folder}</code><br />Expected ID: <code>{state.extension_id}</code></p>
            <label className="settings-sub">Browser{" "}<select value={browser} onChange={e => setBrowser(e.target.value)}><option>Chrome</option><option>Edge</option></select></label>
            <ol className="settings-sub">
              <li>Open <code>{browser === "Chrome" ? "chrome://extensions" : "edge://extensions"}</code> in {browser}. Enable Developer mode.</li>
              <li>Click <b>Load unpacked</b> and choose the prepared folder above. Check that its ID matches. Pin <b>Callosum Capture (early access)</b> in your toolbar.</li>
              <li>Click <b>Verify connection</b> here, then open the extension's <b>Details → Extension options</b> and press <b>Verify connection</b> there within 60 seconds.</li>
              <li>After verification, open your paper/PDF and click the toolbar icon once. Return to Callosum to review its identity.</li>
            </ol>
          </>}
          {state.connection === "waiting" && <p role="status">Waiting for the browser. Open Extension options and click Verify connection there. No capture is sent.</p>}
          {state.connection === "verified" && <p role="status">Connection verified at {new Date(state.verified_at * 1000).toLocaleTimeString()}: the preview extension reached this Callosum app through its native host. This records that check; it does not monitor the connection continuously.</p>}
          {state.connection === "expired" && <p role="status">No current verification. Start Verify connection again. If it fails, check the browser profile, expected ID, extension Options message and that the installed desktop app is running.</p>}
        </>}
      </>}
      {notice && <p role="status" className="settings-sub">{notice}</p>}
      {error && <p role="alert" className="settings-sub">{error}</p>}
      <p className="settings-sub">Chrome Web Store and Microsoft Edge Add-ons installation is not available yet. To leave the preview, turn it off here and remove it in your browser. There is no automatic store migration.</p>
    </div>
  );
}
