// Settings modal (inc 46) — the app-wide preferences surface. Appearance → Dark mode (theme + onTheme); Axes →
// hide-uncertain-by-default (hideUncertainDefault + onHideUncertainDefault). Controlled by App; toggles persist
// to localStorage. Reuses the .axis-modal overlay pattern.
// My Publications profile + refresh (inc 78). Set your name/variants/ORCID; "Refresh my papers" resolves
// via OpenAlex and (re)builds the pinned axis. Calls onRefreshed() so the axes panel reloads.
function MyPubsSettings({ onRefreshed }) {
  const [name, setName] = useState("");
  const [variants, setVariants] = useState("");  // newline-separated published-name variants
  const [orcid, setOrcid] = useState("");
  const [saving, setSaving] = useState(false);
  const [refresh, setRefresh] = useState({ status: "idle" });

  useEffect(() => {
    api("/my-publications/profile").then(r => {
      if (!r.ok) return;
      const p = r.data;
      setName(p.display_name || "");
      setVariants((p.name_variants || []).join("\n"));
      setOrcid(p.orcid || "");
    });
  }, []);

  const save = async () => {
    setSaving(true);
    await apiPut("/my-publications/profile", {
      display_name: name.trim() || null,
      name_variants: variants.split("\n").map(s => s.trim()).filter(Boolean),
      orcid: orcid.trim() || null,
    });
    setSaving(false);
  };

  const runRefresh = async () => {
    await save();  // persist the latest edits first
    setRefresh({ status: "running" });
    const poll = (jobId) => api(`/my-publications/refresh/${jobId}`).then(r => {
      if (!r.ok) { setRefresh({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setRefresh({ status: "done", summary: d.summary }); if (onRefreshed) onRefreshed(); }
      else if (d.status === "error") setRefresh({ status: "error", error: d.detail || "Refresh failed." });
      else setTimeout(() => poll(jobId), 1500);
    });
    const r = await apiPost("/my-publications/refresh", {});
    if (!r.ok) { setRefresh({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };

  const s = refresh.summary;
  const summaryText = !s ? "" :
    s.status === "ok" ? `Found ${s.confirmed || 0} confirmed + ${s.candidates || 0} candidate${(s.candidates || 0) === 1 ? "" : "s"} (of ${s.indexed_works || 0} indexed works; ${s.in_library || 0} in your library).` :
    s.status === "no-identity" ? "Add your name or ORCID first." :
    s.status === "no-match" ? `No OpenAlex author found for ${s.name || "that identity"} — check the name / ORCID.` :
    "Done.";

  return (
    <>
      <p className="eyebrow">My Publications</p>
      <div className="settings-field">
        <label className="settings-field-label">Your name</label>
        <input className="settings-input" placeholder="e.g. Ada Lovelace" value={name} onChange={e => setName(e.target.value)} />
      </div>
      <div className="settings-field">
        <label className="settings-field-label">Other published names (one per line)</label>
        <textarea className="settings-input" rows={2} placeholder={"A. Lovelace\nAugusta Ada King"} value={variants} onChange={e => setVariants(e.target.value)} />
      </div>
      <div className="settings-field">
        <label className="settings-field-label">ORCID (recommended — gives an exact match)</label>
        <input className="settings-input" placeholder="0000-0002-1825-0097" value={orcid} onChange={e => setOrcid(e.target.value)} />
      </div>
      <div className="settings-actions">
        <button className="btn btn-ghost" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save"}</button>
        <button className="btn btn-primary" disabled={refresh.status === "running" || (!name.trim() && !orcid.trim())} onClick={runRefresh}>
          {refresh.status === "running" ? "Gathering…" : "Refresh my papers"}
        </button>
      </div>
      {refresh.status === "running" && <ProgressBar label="Resolving via OpenAlex…" />}
      {refresh.status === "error" && <div className="settings-note settings-note-err">Refresh failed: {refresh.error}</div>}
      {refresh.status === "done" && <div className="settings-note">{summaryText}</div>}
      <div className="settings-sub">Resolved via OpenAlex (public metadata — not the Gemini gate); never uses an LLM.</div>
    </>
  );
}

// AI features (inc 146/149/150 — multi-provider BYOK). Pick a provider, set its key (or a local endpoint) +
// turn on data egress, instead of env vars. Keys are write-only: GET /settings returns status only (never the
// value); egress is default-OFF. A LOCAL (loopback) provider needs no egress consent — nothing leaves the machine.
const AI_PROVIDERS = [
  { id: "gemini", label: "Google Gemini", keyUrl: "https://aistudio.google.com/apikey" },
  { id: "openai", label: "OpenAI", keyUrl: "https://platform.openai.com/api-keys" },
  { id: "anthropic", label: "Anthropic (Claude)", keyUrl: "https://console.anthropic.com/settings/keys" },
  { id: "local", label: "Local model (no data leaves)", keyUrl: null },
];

function AiSettings() {
  const [status, setStatus] = useState(null);
  const [keyInput, setKeyInput] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [test, setTest] = useState(null);  // {ok, detail} from POST /settings/test-key
  const [testing, setTesting] = useState(false);

  const refresh = (data) => { setStatus(data); setUrlInput(data.local_base_url || ""); };
  useEffect(() => { api("/settings").then(r => { if (r.ok) refresh(r.data); }); }, []);

  const provider = status ? status.provider : "gemini";
  const meta = AI_PROVIDERS.find(p => p.id === provider) || AI_PROVIDERS[0];
  const isLocal = provider === "local";

  const put = async (body, doneMsg) => {
    setBusy(true); setMsg(""); setTest(null);
    const r = await apiPut("/settings", body);
    setBusy(false);
    if (r.ok) { refresh(r.data); if (doneMsg) setMsg(doneMsg); return true; }
    setMsg("Couldn't save: " + (r.error || "error")); return false;
  };

  const changeProvider = async (p) => { setKeyInput(""); await put({ provider: p }); };
  const saveKey = async () => {
    const val = keyInput;
    if (await put({ set_api_key: true, api_key: val, api_key_provider: provider }, val.trim() ? "Key saved." : "Key cleared.")) setKeyInput("");
  };
  const clearKey = () => put({ set_api_key: true, api_key: "", api_key_provider: provider }, "Key cleared.");
  const saveUrl = () => put({ set_local_base_url: true, local_base_url: urlInput }, "Endpoint saved.");
  const toggleEgress = () => status && put({ data_egress_enabled: !status.data_egress_enabled });
  const toggleHelp = () => status && put({ help_assistant_enabled: !status.help_assistant_enabled });

  const testActive = async () => {
    setTesting(true); setTest(null);
    const r = await apiPost("/settings/test-key", {});
    setTesting(false);
    setTest(r.ok ? r.data : { ok: false, detail: r.error || "Test failed." });
  };

  const egressOn = !!(status && status.data_egress_enabled);
  const helpOn = !!(status && status.help_assistant_enabled);
  const keySet = !!(status && status.api_key_set);
  const fromEnv = status && status.api_key_source === "env";
  return (
    <>
      <p className="eyebrow">AI features</p>
      <div className="settings-field">
        <label className="settings-field-label">Model provider</label>
        <select className="settings-input" value={provider} disabled={busy} onChange={e => changeProvider(e.target.value)}>
          {AI_PROVIDERS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
      </div>

      {isLocal ? (
        <div className="settings-field">
          <label className="settings-field-label">Local endpoint (OpenAI-compatible)
            <span className="settings-sub">e.g. Ollama / LM Studio at <code>http://127.0.0.1:11434</code>. Must be a loopback address — <b>nothing leaves your machine</b>, so no data-egress consent is needed.</span>
          </label>
          <div className="settings-keyrow">
            <input className="settings-input" placeholder="http://127.0.0.1:11434" value={urlInput} onChange={e => setUrlInput(e.target.value)} />
            <button className="btn btn-ghost" disabled={busy || !urlInput.trim()} onClick={saveUrl}>{busy ? "Saving…" : "Save"}</button>
          </div>
          {status && status.local_base_url &&
            <div className="settings-keytest">
              <button className="btn btn-ghost" disabled={testing} onClick={testActive}>{testing ? "Testing…" : "Test connection"}</button>
              {test && <span className={"settings-keytest-result " + (test.ok ? "ok" : "err")}>{test.detail}</span>}
            </div>}
        </div>
      ) : (
        <>
          <div className="settings-field">
            <label className="settings-field-label">{meta.label} API key
              <span className="settings-sub">
                {keySet
                  ? (fromEnv ? "Set via an environment variable."
                    : (status && status.key_storage === "keychain" ? "A key is saved in your OS keychain." : "A key is saved in a local file on this machine."))
                  : "Not set. AI features need a key — stored locally (your OS keychain if available), sent only to the provider."}
                {meta.keyUrl ? <>{" "}<a href={meta.keyUrl} target="_blank" rel="noopener noreferrer">Get a key →</a></> : null}
              </span>
            </label>
            <div className="settings-keyrow">
              <input className="settings-input" type="password" autoComplete="off"
                placeholder={keySet && !fromEnv ? "•••••••• (saved) — type to replace" : "Paste your key"}
                value={keyInput} onChange={e => setKeyInput(e.target.value)} />
              <button className="btn btn-ghost" disabled={busy || !keyInput.trim()} onClick={saveKey}>{busy ? "Saving…" : "Save"}</button>
              {keySet && !fromEnv &&
                <button className="btn btn-ghost" disabled={busy} onClick={clearKey}>Clear</button>}
            </div>
            {keySet &&
              <div className="settings-keytest">
                <button className="btn btn-ghost" disabled={testing} onClick={testActive}>{testing ? "Testing…" : "Test key"}</button>
                {test && <span className={"settings-keytest-result " + (test.ok ? "ok" : "err")}>{test.detail}</span>}
              </div>}
          </div>
          <div className="settings-row">
            <span className="settings-label">Allow AI features (sends text to {meta.label})
              <span className="settings-sub">
                Off by default. When on, generating a summary sends the relevant library text to {meta.label}; every sentence is still verified locally against your PDFs.
                {status && status.egress_source === "env" ? " Currently set by the CALLOSUM_ALLOW_DATA_EGRESS environment variable." : ""}
              </span>
            </span>
            <button type="button" className={"settings-switch" + (egressOn ? " on" : "")}
              role="switch" aria-checked={egressOn} aria-label="Allow AI features"
              onClick={toggleEgress}><span className="settings-knob" /></button>
          </div>
        </>
      )}
      <div className="settings-row">
        <span className="settings-label">AI help assistant
          <span className="settings-sub">
            Answers questions about using Callosum (the “Ask…” box in Help). Its <b>own</b> switch — it sends only your question + the public help docs, never your library, so it works with any provider and is independent of the egress toggle above.
            {status && status.help_source === "env" ? " Currently set by the CALLOSUM_HELP_ASSISTANT_ENABLED environment variable." : ""}
          </span>
        </span>
        <button type="button" className={"settings-switch" + (helpOn ? " on" : "")}
          role="switch" aria-checked={helpOn} aria-label="AI help assistant"
          onClick={toggleHelp}><span className="settings-knob" /></button>
      </div>
      <div className="settings-ai-note">Whichever provider you choose, every summary sentence is still <b>verified locally</b> against your PDFs — your model choice affects draft quality + coverage, never which citations are accepted.</div>
      {msg && <div className="settings-note">{msg}</div>}
    </>
  );
}

// Metadata access (inc 158) — ONE contact email for the public metadata APIs' polite pool (Crossref, OpenAlex,
// Retraction Watch). Setting it here enables the Retraction Watch database download, instead of an env var. Not a
// secret (it is sent to those services as the polite-pool contact, exactly as the env var was) → GET /settings
// returns it, and it is stored in the local file (not the keychain).
function MetadataSettings() {
  const [status, setStatus] = useState(null);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => { api("/settings").then(r => { if (r.ok) { setStatus(r.data); setEmail(r.data.contact_email || ""); } }); }, []);
  const save = async () => {
    setBusy(true); setMsg("");
    const r = await apiPut("/settings", { set_contact_email: true, contact_email: email.trim() });
    setBusy(false);
    if (r.ok) { setStatus(r.data); setEmail(r.data.contact_email || ""); setMsg(email.trim() ? "Saved." : "Cleared."); }
    else setMsg("Couldn't save: " + (r.error || "error"));
  };
  const fromEnv = status && status.contact_email_source === "env";
  return (
    <>
      <p className="eyebrow">Metadata access</p>
      <div className="settings-field">
        <label className="settings-field-label">Contact email
          <span className="settings-sub">
            Sent as the polite-pool contact for public metadata services (Crossref, OpenAlex, Retraction Watch) so they can reach you about heavy use. Setting it here enables the <b>Retraction Watch database</b> download (Methods → Data consistency). Not an AI feature — no library text is sent.
            {fromEnv ? " Currently set by the CALLOSUM_CROSSREF_MAILTO environment variable." : ""}
          </span>
        </label>
        <div className="settings-keyrow">
          <input className="settings-input" type="email" autoComplete="off" placeholder="you@example.com"
            value={email} onChange={e => setEmail(e.target.value)} />
          <button className="btn btn-ghost" disabled={busy} onClick={save}>{busy ? "Saving…" : "Save"}</button>
        </div>
      </div>
      {msg && <div className="settings-note">{msg}</div>}
    </>
  );
}

function LibreOfficeSettings() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const install = async () => {
    setBusy(true); setMsg("");
    const r = await apiPost("/integrations/libreoffice/install", {});
    setBusy(false);
    setMsg(r.ok ? (r.data.detail || "Opening LibreOffice…") : ("Couldn't install: " + (r.error || "error")));
  };
  return (
    <>
      <p className="eyebrow">LibreOffice plugin</p>
      <div className="settings-field">
        <label className="settings-field-label">Cite while you write in LibreOffice Writer
          <span className="settings-sub">
            Installs the Callosum extension — a <b>Callosum</b> menu + toolbar in Writer (Add citation, Suggest, Refresh, Style, Flatten). Click Install, confirm in LibreOffice's Extension Manager, then restart Writer. The app must be running for the plugin to reach it.
          </span>
        </label>
        <div className="settings-keyrow">
          <button className="btn btn-ghost" disabled={busy} onClick={install}>{busy ? "Installing…" : "Install plugin"}</button>
          <button className="btn-link" onClick={() => downloadAsset("/integrations/libreoffice/plugin.oxt", "callosum.oxt")}>Download .oxt</button>
        </div>
      </div>
      {msg && <div className="settings-note">{msg}</div>}
    </>
  );
}

// Microsoft Word add-in (inc 164, SP1). Architecture A: callosum serves the task pane over HTTPS, same-origin with
// the API — desktop Word only, zero egress. "Install" can't auto-sideload on desktop, so it opens the add-in
// folder; the manifest is also downloadable. The 3-step one-time setup (cert + HTTPS run + sideload) is spelled out.
function WordSettings() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const openFolder = async () => {
    setBusy(true); setMsg("");
    const r = await apiPost("/integrations/word/install", {});
    setBusy(false);
    setMsg(r.ok ? (r.data.detail || "Opened the add-in folder.") : ("Couldn't open: " + (r.error || "error")));
  };
  return (
    <>
      <p className="eyebrow">Microsoft Word add-in (desktop)</p>
      <div className="settings-field">
        <label className="settings-field-label">Cite while you write in Word
          <span className="settings-sub">
            A task pane in <b>desktop</b> Word (Windows/Mac) that searches your library and inserts citations — everything stays on your machine. One-time setup: <b>1)</b> trust a local certificate, run <code>npx office-addin-dev-certs install</code>; <b>2)</b> run Callosum over HTTPS, <code>python tools/run_https.py</code>, then open <code>https://localhost:8443</code>; <b>3)</b> download the manifest below and sideload it in Word (see the adapter README). Not supported in Word-on-the-web.
          </span>
        </label>
        <div className="settings-keyrow">
          <button className="btn-link" onClick={() => downloadAsset("/integrations/word/manifest.xml", "callosum-word-manifest.xml")}>Download manifest</button>
          <button className="btn btn-ghost" disabled={busy} onClick={openFolder}>{busy ? "Opening…" : "Open add-in folder"}</button>
        </div>
      </div>
      {msg && <div className="settings-note">{msg}</div>}
    </>
  );
}

// Remote access (inc 168) — the opt-in, default-OFF gate that lets the Google Docs add-on reach your library through
// a tunnel you run. Enabling mints an access token (shown once → copy into the add-on) + saves it locally so the
// local UI keeps working under the gate. Off by default; local-only use is unaffected.
function RemoteAccessSettings() {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState("");  // shown once, right after minting
  const [msg, setMsg] = useState("");
  const refresh = () => api("/settings").then(r => { if (r.ok) setStatus(r.data); });
  useEffect(() => { refresh(); }, []);
  const on = !!(status && status.remote_access_enabled);

  const enable = async () => {
    setBusy(true); setMsg(""); setToken("");
    const m = await apiPost("/settings/access-token", {});  // mint while still OFF (ungated)
    if (!m.ok) { setBusy(false); setMsg("Couldn't generate a token: " + (m.error || "error")); return; }
    setAccessToken(m.data.token);  // the local browser now authenticates to the gate
    setToken(m.data.token);        // show once
    const r = await apiPut("/settings", { remote_access_enabled: true });
    setBusy(false);
    if (r.ok) { setStatus(r.data); setMsg("Remote access is on. Copy the token into the add-on — it won't be shown again."); }
    else setMsg("Couldn't enable: " + (r.error || "error"));
  };
  const disable = async () => {
    setBusy(true); setMsg(""); setToken("");
    const r = await apiPut("/settings", { remote_access_enabled: false });
    setBusy(false);
    if (r.ok) { setStatus(r.data); setMsg("Remote access is off."); }
    else setMsg("Couldn't disable: " + (r.error || "error"));
  };
  const regenerate = async () => {
    setBusy(true); setMsg(""); setToken("");
    const m = await apiPost("/settings/access-token", {});
    setBusy(false);
    if (m.ok) { setAccessToken(m.data.token); setToken(m.data.token); setMsg("New token — update the add-on; the old one no longer works."); }
    else setMsg("Couldn't regenerate: " + (m.error || "error"));
  };

  return (
    <>
      <p className="eyebrow">Remote access (Google Docs)</p>
      <div className="settings-row">
        <span className="settings-label">Allow citing from Google Docs
          <span className="settings-sub">
            <b>Off by default.</b> When on, your library is reachable through a tunnel you run (the next setup step) — protected by an access token only you hold. This is the opt-in that lets cited-paper metadata leave your machine; local use is unaffected.
          </span>
        </span>
        <button type="button" className={"settings-switch" + (on ? " on" : "")} role="switch" aria-checked={on}
          aria-label="Allow remote access" disabled={busy} onClick={on ? disable : enable}><span className="settings-knob" /></button>
      </div>
      {on &&
        <div className="settings-keyrow">
          <button className="btn btn-ghost" disabled={busy} onClick={regenerate}>Regenerate token</button>
        </div>}
      {token &&
        <div className="settings-field">
          <label className="settings-field-label">Access token — shown once; copy it into the add-on
            <span className="settings-sub">Stored on this machine; sent to your tunnel as a Bearer token. It is never shown again or returned by the app.</span>
          </label>
          <input className="settings-input" readOnly value={token} onFocus={e => e.target.select()} />
        </div>}
      {msg && <div className="settings-note">{msg}</div>}
      <div className="settings-sub">Locked out locally after losing the token? Set <code>CALLOSUM_DISABLE_REMOTE_ACCESS=1</code> and restart, or remove the token from <code>~/.callosum/app-settings.json</code>.</div>
    </>
  );
}

// AI agent (MCP writes), B1 SP2 — opt-in (default off); when on, an MCP agent can tag / add-to-axis / save a
// verified reference / annotate, each stamped "ai-agent" and reversible here. No destructive tool exists.
function AgentSettings() {
  const [on, setOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [writes, setWrites] = useState([]);
  const [msg, setMsg] = useState("");
  const refresh = () => {
    api("/settings").then(r => { if (r.ok) setOn(!!r.data.agent_writes_enabled); });
    api("/agent/writes").then(r => { if (r.ok) setWrites(r.data); });
  };
  useEffect(() => { refresh(); }, []);

  const toggle = async () => {
    setBusy(true); setMsg("");
    const r = await apiPut("/settings", { agent_writes_enabled: !on });
    setBusy(false);
    if (r.ok) { setOn(!!r.data.agent_writes_enabled); refresh(); }
    else setMsg("Couldn't toggle: " + (r.error || "error"));
  };
  const revert = async (id) => { const r = await apiPost(`/agent/writes/${id}/revert`, {}); if (r.ok) refresh(); };
  const revertAll = async () => {
    for (const w of writes) if (!w.reverted_at) await apiPost(`/agent/writes/${w.id}/revert`, {});
    refresh();
  };
  const pending = writes.filter(w => !w.reverted_at);

  return (
    <>
      <p className="eyebrow">AI agent (MCP writes)</p>
      <div className="settings-row">
        <span className="settings-label">Let an AI agent edit your library
          <span className="settings-sub">
            <b>Off by default.</b> When on, an MCP agent (e.g. Claude Desktop, via the callosum MCP server) can tag papers, add them to axes, save verified references, and add notes — each marked <b>ai-agent</b> and reversible below. It can't delete or overwrite anything. Restart your agent host after enabling so the write tools appear.
          </span>
        </span>
        <button type="button" className={"settings-switch" + (on ? " on" : "")} role="switch" aria-checked={on}
          aria-label="Allow agent writes" disabled={busy} onClick={toggle}><span className="settings-knob" /></button>
      </div>
      {msg && <div className="settings-note">{msg}</div>}
      {writes.length > 0 &&
        <div className="settings-field">
          <label className="settings-field-label">Agent activity
            {pending.length > 0 &&
              <button type="button" className="btn-link" onClick={revertAll}>Revert all ({pending.length})</button>}
          </label>
          <div className="agent-activity">
            {writes.map(w => (
              <div key={w.id} className={"agent-activity-row" + (w.reverted_at ? " reverted" : "")}>
                <span className="agent-activity-what">{w.action} · {w.target_title || ("#" + w.target_paper_id)}</span>
                {w.reverted_at
                  ? <span className="settings-sub">reverted</span>
                  : <button type="button" className="btn-link" onClick={() => revert(w.id)}>Revert</button>}
              </div>
            ))}
          </div>
        </div>}
    </>
  );
}

// Optional account (SP1) — "Sign in with ORCID" via the callosum account platform (OIDC). Opt-in + additive: the app
// works fully offline with no account. Signing in verifies your identity and populates My Publications; identity
// only — the library never leaves the machine. The Sign-in button shows only when the account service is configured
// (account.configured); the callback redirect (/oauth/callback) reloads the app, so signed-in state re-fetches then.
function AccountSettings() {
  const [acct, setAcct] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const load = () => api("/settings").then(r => { if (r.ok) setAcct(r.data.account); });
  useEffect(() => { load(); }, []);

  const signIn = async () => {
    setBusy(true); setMsg("");
    const r = await api("/auth/login?origin=" + encodeURIComponent(window.location.origin));
    setBusy(false);
    if (r.ok && r.data && r.data.authorize_url) window.location.href = r.data.authorize_url;  // navigate to the IdP
    else setMsg("Couldn't start sign-in: " + (r.error || "error"));
  };
  const signOut = async () => {
    setBusy(true); setMsg("");
    const r = await apiPost("/auth/logout", {});
    setBusy(false);
    if (r.ok) { await load(); setMsg("Signed out."); } else setMsg("Couldn't sign out: " + (r.error || "error"));
  };

  const signedIn = !!(acct && acct.signed_in);
  return (
    <>
      <p className="eyebrow">Account</p>
      <div className="settings-field">
        <label className="settings-field-label">Optional account — sign in
          <span className="settings-sub">
            Callosum works fully offline with <b>no account</b>. Signing in verifies your identity (<b>ORCID, Google, or email</b> — you pick on the next page); signing in with <b>ORCID</b> also pre-fills <b>My Publications</b> with your authoritative author record. <b>Identity only</b> — your library, PDFs, and notes never leave your machine.
          </span>
        </label>
        {signedIn
          ? <>
              <div className="settings-note">Signed in{acct.display_name ? " as " + acct.display_name : (acct.email ? " as " + acct.email : "")}{acct.orcid ? " · ORCID " + acct.orcid : ""}{acct.is_superuser ? " · superuser" : ""}.</div>
              <div className="settings-keyrow"><button className="btn btn-ghost" disabled={busy} onClick={signOut}>{busy ? "Signing out…" : "Sign out"}</button></div>
            </>
          : acct && acct.configured
            ? <div className="settings-keyrow"><button className="btn btn-primary" disabled={busy} onClick={signIn}>{busy ? "Starting…" : "Sign in"}</button></div>
            : <div className="settings-sub">Sign-in isn't set up on this Callosum yet — the account service is configured by whoever runs this instance.</div>}
      </div>
      {msg && <div className="settings-note">{msg}</div>}
    </>
  );
}

function SettingsModal({ theme, onTheme, hideUncertainDefault, onHideUncertainDefault, axisCutoffDefault, onAxisCutoffDefault, onMyPubsRefreshed, autoScanWatched, onAutoScanWatched, onClose }) {
  const dark = theme === "dark";
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal settings-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Settings</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>

        <p className="eyebrow">Appearance</p>
        <div className="settings-row">
          <span className="settings-label">Dark mode</span>
          <button
            type="button"
            className={"settings-switch" + (dark ? " on" : "")}
            role="switch" aria-checked={dark} aria-label="Dark mode"
            onClick={() => onTheme(dark ? "light" : "dark")}
          ><span className="settings-knob" /></button>
        </div>

        <AiSettings />

        <p className="eyebrow">Axes</p>
        <div className="settings-row">
          <span className="settings-label">Hide uncertain papers by default
            <span className="settings-sub">New axis cards start in the assigned/manual-only view (the 👁 toggle).</span>
          </span>
          <button
            type="button"
            className={"settings-switch" + (hideUncertainDefault ? " on" : "")}
            role="switch" aria-checked={!!hideUncertainDefault} aria-label="Hide uncertain axis papers by default"
            onClick={() => onHideUncertainDefault(!hideUncertainDefault)}
          ><span className="settings-knob" /></button>
        </div>
        <div className="settings-row">
          <span className="settings-label">Default axis cutoff
            <span className="settings-sub">The assigned-vs-uncertain threshold a new axis's re-score starts at (you can still adjust it per axis). Higher = stricter.</span>
          </span>
          <span className="settings-cutoff">
            <input type="range" min="0.2" max="0.6" step="0.01" value={axisCutoffDefault}
              onChange={e => onAxisCutoffDefault(Number(e.target.value))} aria-label="Default axis cutoff" />
            <span className="settings-cutoff-val">{Number(axisCutoffDefault).toFixed(2)}</span>
          </span>
        </div>

        <p className="eyebrow">Library</p>
        <div className="settings-row">
          <span className="settings-label">Auto-scan watched folders on launch
            <span className="settings-sub">Re-scan the folders you've added (under + Add → Watched folders) each time the app starts, to pick up new PDFs.</span>
          </span>
          <button
            type="button"
            className={"settings-switch" + (autoScanWatched ? " on" : "")}
            role="switch" aria-checked={!!autoScanWatched} aria-label="Auto-scan watched folders on launch"
            onClick={() => onAutoScanWatched(!autoScanWatched)}
          ><span className="settings-knob" /></button>
        </div>

        <MetadataSettings />

        <LibreOfficeSettings />

        <WordSettings />

        <RemoteAccessSettings />

        <AgentSettings />

        <AccountSettings />

        <MyPubsSettings onRefreshed={onMyPubsRefreshed} />

        <div className="axis-modal-note">More settings will live here — this is just the start.</div>
      </div>
    </div>
  );
}
