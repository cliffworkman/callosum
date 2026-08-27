// inc 254: the remote-access LOCKOUT recovery overlay. App-wide (rendered by 40_app) when any data call 401s
// because Remote access (inc 168) is on and this browser isn't authorized. It replaces the old, misleading
// "start the backend / uvicorn" error box (the server is fine — it's the token that's missing). Two honest,
// testable recovery paths: (1) paste the access token → stored client-side → reload; (2) a local-possession
// reset → POST /access/recover writes a one-time code to a file only someone AT the machine can read, then
// disables Remote access (the safe local-only default). Never reveals the token; never blames a dead server.
function AccessLockOverlay() {
  const [tab, setTab] = useState("token");          // "token" | "reset"
  const [tokenInput, setTokenInput] = useState("");
  const [codePath, setCodePath] = useState("");     // set once the code file is written
  const [codeInput, setCodeInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [ok, setOk] = useState(false);          // success (green) vs error (amber) styling for the msg line
  const [copied, setCopied] = useState(false);  // "Copy path" button feedback

  const applyToken = () => {
    const t = tokenInput.trim();
    if (!t) { setMsg("Paste the access token first."); return; }
    setAccessToken(t);
    window.location.reload();   // reload so every pane refetches, now with the token attached
  };

  const startReset = async () => {
    setBusy(true); setMsg("");
    const r = await startAccessRecovery();
    setBusy(false);
    if (r.ok && r.data) { setCodePath(r.data.code_path || ""); setCodeInput(""); }
    else setMsg("Couldn't start recovery: " + (r.error || "unknown error"));
  };

  const submitReset = async () => {
    const c = codeInput.trim();
    if (!c) { setMsg("Enter the code from the file first."); return; }
    setBusy(true); setMsg("");
    const r = await submitAccessRecovery(c);
    if (r.ok && r.data && r.data.status === "recovered") {
      clearAccessToken();            // any stale token is now irrelevant — the gate is off
      setOk(true);
      setMsg((r.data && r.data.detail) || "Remote access is off — your library is available locally again.");
      setTimeout(() => window.location.reload(), 1400);   // let the confirmation land; buttons stay disabled
    } else {
      setBusy(false);
      setMsg((r.data && r.data.detail) || r.error || "That code didn't work. Get a new code and try again.");
    }
  };

  const copyPath = () => {
    // navigator.clipboard is fine on the 127.0.0.1 secure context (cf. the inc-70 citation copy).
    navigator.clipboard.writeText(codePath).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); });
  };

  return (
    <div className="axis-modal-overlay" role="dialog" aria-modal="true" aria-label="Remote access locked">
      <div className="axis-modal lockout-card">
        <div className="lockout-head">
          <span className="lockout-icon" aria-hidden="true">🔒</span>
          <div>
            <h2 className="lockout-title">Remote access is on — this browser isn't authorized</h2>
            <p className="lockout-sub">Your library and the server are fine. callosum is holding back every request
              because of the <b>Allow citing from Google Docs</b> (Remote access) setting you turned on — and this
              browser isn't sending the access token it now expects, so nothing loads. Pick a way back in:</p>
          </div>
        </div>

        <div className="lockout-tabs">
          <button className={"lockout-tab" + (tab === "token" ? " active" : "")} onClick={() => { setTab("token"); setMsg(""); setOk(false); }}>I have the token</button>
          <button className={"lockout-tab" + (tab === "reset" ? " active" : "")} onClick={() => { setTab("reset"); setMsg(""); setOk(false); }}>I lost it — turn remote access off</button>
        </div>

        {tab === "token" &&
          <div className="lockout-body">
            <p>Paste the access token you copied when you turned Remote access on. It's kept only in this browser
              and sent securely with each request.</p>
            <input className="settings-input" type="password" placeholder="Access token" value={tokenInput} autoFocus
              onChange={e => setTokenInput(e.target.value)} onKeyDown={e => { if (e.key === "Enter") applyToken(); }} />
            <div className="lockout-actions">
              <button className="btn-primary" onClick={applyToken}>Unlock</button>
            </div>
          </div>}

        {tab === "reset" &&
          <div className="lockout-body">
            <p>This turns Remote access <b>off</b> and returns callosum to local-only — its default. To prove you're
              at the computer running callosum (not reaching it remotely), you'll copy a one-time code from a file
              only you can open.</p>
            {!codePath &&
              <div className="lockout-actions">
                <button className="btn-primary" disabled={busy} onClick={startReset}>{busy ? "Working…" : "Get My Recovery Code"}</button>
              </div>}
            {codePath &&
              <React.Fragment>
                <div className="lockout-step">On the computer running callosum, open this file — it's a plain text
                  file, so Notepad (Windows) or TextEdit (Mac) will open it — and copy the code inside:
                  <code className="lockout-path">{codePath}</code>
                  <div className="lockout-hint">
                    <button className="btn-link" onClick={copyPath}>{copied ? "Copied ✓" : "Copy Path"}</button>
                    <span> — paste it into your File Explorer / Finder address bar to jump straight to the file.</span>
                  </div>
                </div>
                <input className="settings-input" placeholder="Paste the code from the file" value={codeInput} autoFocus
                  onChange={e => setCodeInput(e.target.value)} onKeyDown={e => { if (e.key === "Enter") submitReset(); }} />
                <div className="lockout-actions">
                  <button className="btn-primary" disabled={busy} onClick={submitReset}>{busy ? "Working…" : "Turn Off Remote Access"}</button>
                  <button className="btn-ghost" disabled={busy} onClick={startReset}>New Code</button>
                </div>
              </React.Fragment>}
          </div>}

        {msg && <div className={"lockout-msg" + (ok ? " ok" : "")}>{msg}</div>}
        <div className="lockout-foot">Still stuck? Ask whoever helped you set up remote access — or, on the callosum
          machine, restart it with <code>CALLOSUM_DISABLE_REMOTE_ACCESS=1</code> set.</div>
      </div>
    </div>
  );
}
