// Cross-device sync (accounts SP3c) — the Settings → Sync UI over the SP3a-c backend (app/backend/api/routers/sync.py):
// set up a passphrase-derived vault (a one-time recovery-code reveal, the inc-168 RemoteAccessSettings token pattern),
// enable against a server URL (lockout-safe — mirrors the backend's own setup→signed-in→url→enable gate order), run a
// sync (the passphrase is re-entered every run — never remembered), and review + resolve conflicts (a collapsible
// list, the 35b_providers.jsx ProviderRow pattern; the diff reuses 08y_critical_set.jsx's cr-matrix "facts, not a
// score" table). Split from 35_settings.jsx (at the 600-line cap) — the inc-256 35b_providers.jsx precedent.
// Opt-in, default-off throughout; PDFs never sync; no server-side passphrase reset; conflicts are surfaced, never
// auto-picked (value A4) — see .claude/security-audits/2026-07-19_sync-conflict-resolution.md.

function _fmtConflictValue(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

// One unresolved conflict — a collapsible card (closed by default; there's no "active" analogue to open one).
function ConflictCard({ c, busy, onResolve }) {
  const [open, setOpen] = useState(false);
  const mine = c.losing_payload || {};
  const current = c.current || {};
  const keys = Array.from(new Set([...Object.keys(mine), ...Object.keys(current)])).sort();
  return (
    <div className="provider-card">
      <div className="provider-card-head">
        <button className="provider-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
          <span className="provider-caret">{open ? "▾" : "▸"}</span>
          <span className="provider-name">{c.collection}</span>
          <span className="provider-badge">{new Date(c.detected_at).toLocaleString()}</span>
        </button>
      </div>
      {open &&
        <div className="provider-body">
          <div className="cr-matrix-wrap">
            <table className="cr-matrix">
              <thead><tr><th>Field</th><th>Mine</th><th>Current (theirs)</th></tr></thead>
              <tbody>
                {keys.map(k => (
                  <tr key={k}>
                    <td className="cr-matrix-title">{k}</td>
                    <td>{_fmtConflictValue(mine[k])}</td>
                    <td>{_fmtConflictValue(current[k])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="cr-matrix-caption">
              "Mine" is what you edited locally; "Current" is what's already applied (the other device's newer
              edit). Neither is picked for you.
            </div>
          </div>
          <div className="settings-actions">
            <button className="btn btn-ghost" disabled={busy} onClick={() => onResolve(c.id, "mine")}>Keep mine</button>
            <button className="btn btn-primary" disabled={busy} onClick={() => onResolve(c.id, "theirs")}>Keep theirs</button>
          </div>
        </div>}
    </div>
  );
}

function ConflictReviewPanel({ onClose, onResolved }) {
  const [conflicts, setConflicts] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const load = () => api("/sync/conflicts").then(r => { if (r.ok) setConflicts(r.data); });
  useEffect(() => { load(); }, []);

  const resolve = async (id, side) => {
    setBusy(true); setMsg("");
    const r = await apiPost(`/sync/conflicts/${id}/resolve`, { side });
    setBusy(false);
    if (r.ok) { await load(); if (onResolved) onResolved(); }
    else setMsg("Couldn't resolve: " + r.error);
  };

  return (
    <div className="settings-field">
      <label className="settings-field-label">Conflicts to review
        <span className="settings-sub">
          Two devices edited the same item since your last sync. Nothing is picked automatically — choose which
          version to keep for each.
        </span>
      </label>
      {conflicts === null && <div className="settings-sub">Loading…</div>}
      {conflicts && conflicts.length === 0 && <div className="settings-sub">No conflicts to review.</div>}
      {conflicts && conflicts.length > 0 &&
        <div className="provider-list">
          {conflicts.map(c => <ConflictCard key={c.id} c={c} busy={busy} onResolve={resolve} />)}
        </div>}
      {msg && <div className="settings-note settings-note-err">{msg}</div>}
      <div className="settings-actions"><button className="btn btn-ghost" onClick={onClose}>Close</button></div>
    </div>
  );
}

function SyncSettings() {
  const [status, setStatus] = useState(null);
  const [conflictCount, setConflictCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgErr, setMsgErr] = useState(false);

  const [passphrase, setPassphrase] = useState("");
  const [confirmPassphrase, setConfirmPassphrase] = useState("");
  const [settingUp, setSettingUp] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState("");  // shown once, right after setup — never re-fetchable

  const [serverUrl, setServerUrl] = useState("");
  const [runPassphrase, setRunPassphrase] = useState("");
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [reviewing, setReviewing] = useState(false);

  const loadConflictCount = () => api("/sync/conflicts").then(r => { if (r.ok) setConflictCount(r.data.length); });
  const load = () => {
    api("/sync/status").then(r => { if (r.ok) { setStatus(r.data); setServerUrl(r.data.server_url || ""); } });
    loadConflictCount();
  };
  useEffect(() => { load(); }, []);

  const note = (text, err) => { setMsg(text); setMsgErr(!!err); };

  const setup = async () => {
    if (!passphrase || passphrase !== confirmPassphrase) { note("Passphrases don't match.", true); return; }
    setSettingUp(true); note("");
    const r = await apiPost("/sync/setup", { passphrase });
    setSettingUp(false);
    setPassphrase(""); setConfirmPassphrase("");
    if (r.ok) { setRecoveryCode(r.data.recovery_code); await load(); }
    else note("Couldn't set up sync: " + r.error, true);
  };

  const saveServerUrl = async () => {
    setBusy(true); note("");
    const r = await apiPut("/sync/settings", { enabled: !!(status && status.enabled), server_url: serverUrl.trim() || null });
    setBusy(false);
    if (r.ok) { setStatus(r.data); note("Saved."); } else note("Couldn't save: " + r.error, true);
  };

  const toggleEnabled = async () => {
    setBusy(true); note("");
    const r = await apiPut("/sync/settings", { enabled: !status.enabled, server_url: serverUrl.trim() || null });
    setBusy(false);
    if (r.ok) { setStatus(r.data); note(r.data.enabled ? "Sync is on." : "Sync is off."); }
    else note("Couldn't toggle: " + r.error, true);
  };

  const run = async () => {
    if (!runPassphrase) return;
    setRunning(true); note(""); setRunResult(null);
    const r = await apiPost("/sync/run", { passphrase: runPassphrase });
    setRunning(false); setRunPassphrase("");
    if (r.ok) { setRunResult(r.data); await load(); }
    else note("Sync run failed: " + r.error, true);
  };

  if (!status) return <><p className="eyebrow">Cross-device sync</p><div className="settings-sub">Loading…</div></>;

  const step2 = status.configured;  // "sign in" — reuses AccountSettings below, not duplicated here
  const step3 = status.configured && status.signed_in;  // server URL + enable

  return (
    <>
      <p className="eyebrow">Cross-device sync</p>
      {conflictCount > 0 &&
        <div className="settings-note">
          <button className="btn-link" onClick={() => setReviewing(true)}>
            {conflictCount} conflict{conflictCount === 1 ? "" : "s"} to review →
          </button>
        </div>}

      {!status.configured &&
        <div className="settings-field">
          <label className="settings-field-label">1. Choose a passphrase
            <span className="settings-sub">
              Encrypts your synced data end-to-end — Callosum never sees or transmits the passphrase itself, only a
              key derived from it. <b>There is no server-side reset:</b> losing both the passphrase and the
              recovery code (shown once, next step) means the encrypted data can't be recovered.
            </span>
          </label>
          <input className="settings-input" type="password" autoComplete="new-password" placeholder="A strong passphrase"
            value={passphrase} onChange={e => setPassphrase(e.target.value)} />
          <div className="settings-keyrow">
            <input className="settings-input" type="password" autoComplete="new-password" placeholder="Confirm passphrase"
              value={confirmPassphrase} onChange={e => setConfirmPassphrase(e.target.value)} />
            <button className="btn btn-primary" disabled={settingUp || !passphrase || passphrase !== confirmPassphrase} onClick={setup}>
              {settingUp ? "Setting up…" : "Set up sync"}
            </button>
          </div>
          {settingUp && <ProgressBar label="Deriving your encryption key…" />}
        </div>}

      {recoveryCode &&
        <div className="settings-field">
          <label className="settings-field-label">Recovery code — shown once; save it now
            <span className="settings-sub">
              The only way to unlock your synced data if you forget your passphrase. <b>There is no server-side
              reset.</b> It will not be shown again.
            </span>
          </label>
          <input className="settings-input" readOnly value={recoveryCode} onFocus={e => e.target.select()} />
          <div className="settings-actions">
            <button className="btn btn-ghost" onClick={() => setRecoveryCode("")}>I've saved it</button>
          </div>
        </div>}

      {step2 && !status.signed_in &&
        <div className="settings-sub">2. <b>Sign in</b> (see Account, below) to continue setting up sync.</div>}

      {step3 &&
        <div className="settings-field settings-sync-enable">
          <div className="settings-row">
            <label className="settings-field-label">Enable sync
              <span className="settings-sub">
                Off by default. When on, your papers/tags/axes/notes/highlights sync as opaque, end-to-end-encrypted
                data to the server below.
              </span>
            </label>
            <button type="button" className={"settings-switch" + (status.enabled ? " on" : "")} role="switch"
              aria-checked={status.enabled} aria-label="Enable sync" disabled={busy || !serverUrl.trim()}
              onClick={toggleEnabled}><span className="settings-knob" /></button>
          </div>
        </div>}

      {step3 &&
        <div className="settings-field">
          <label className="settings-field-label">Sync server URL
            <span className="settings-sub">
              Where your encrypted data is stored — only opaque ciphertext ever reaches it. <b>PDFs stay local</b>{" "}
              (never synced); the server never sees your passphrase, key, or plaintext.
            </span>
          </label>
          <div className="settings-keyrow">
            <input className="settings-input" type="url" placeholder="https://your-sync-server.example.com"
              value={serverUrl} onChange={e => setServerUrl(e.target.value)} />
            <button className="btn btn-ghost" disabled={busy || !serverUrl.trim()} onClick={saveServerUrl}>Save</button>
          </div>
        </div>}

      {status.enabled &&
        <div className="settings-field">
          <label className="settings-field-label">Run sync now (Re-enter your passphrase each time — it's never remembered between runs.)</label>
          <div className="settings-keyrow">
            <input className="settings-input" type="password" autoComplete="off" placeholder="Passphrase"
              value={runPassphrase} onChange={e => setRunPassphrase(e.target.value)} />
            <button className="btn btn-primary" disabled={running || !runPassphrase} onClick={run}>
              {running ? "Syncing…" : "Run sync"}
            </button>
          </div>
          {running && <ProgressBar label="Syncing…" />}
          {runResult &&
            <div className="settings-note">
              Pushed {runResult.pushed}, applied {runResult.applied}.
              {runResult.conflicts > 0 &&
                <> {" "}<button className="btn-link" onClick={() => setReviewing(true)}>
                  {runResult.conflicts} new conflict{runResult.conflicts === 1 ? "" : "s"} →
                </button></>}
            </div>}
        </div>}

      {msg && <div className={"settings-note" + (msgErr ? " settings-note-err" : "")}>{msg}</div>}

      {reviewing &&
        <ConflictReviewPanel onClose={() => { setReviewing(false); loadConflictCount(); }} onResolved={loadConflictCount} />}
    </>
  );
}
