// Settings modal (inc 46) — the app-wide preferences surface. Appearance → Dark mode (theme + onTheme); Axes →
// hide-uncertain-by-default (hideUncertainDefault + onHideUncertainDefault). Controlled by App; toggles persist
// to localStorage. Reuses the .axis-modal overlay pattern.
// AI features — the unified LLM provider roster (`AiSettings`) lives in js/35b_providers.jsx (inc 256). It
// hoists across the shared IIFE, so SettingsModal below references it directly.

function LocalMaintenanceSettings({ onRetractionRan }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const repairSummaryCache = async () => {
    setBusy(true); setMsg("");
    const r = await apiPost("/settings/repair-summary-cache", {});
    setBusy(false);
    if (r.ok) setMsg(`Scanned ${r.data.scanned} summary cache row${r.data.scanned === 1 ? "" : "s"}; removed ${r.data.removed} malformed row${r.data.removed === 1 ? "" : "s"}.`);
    else setMsg("Couldn't repair summary cache: " + (r.error || "error"));
  };

  // Retraction Watch DB mirror (inc 132; moved from the old left-pane Review accordion — the library-wide
  // retraction check itself lives as a header button now, `10b_libmenus.jsx`'s RetractionCheckButton; this is
  // just the "how fresh is the local mirror" admin view + a refresh-only action).
  const [db, setDb] = useState(null);  // { count, retrieved_at } | null
  const [dbRun, setDbRun] = useState({ status: "idle" });
  const loadDb = () => api("/methods/retraction/database").then(r => { if (r.ok) setDb(r.data); });
  useEffect(() => { loadDb(); }, []);
  const refreshDb = async () => {
    setDbRun({ status: "running" });
    const poll = (jobId) => api(`/methods/retraction/database/refresh/${jobId}`).then(r => {
      if (!r.ok) { setDbRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setDbRun({ status: "done" }); loadDb(); if (onRetractionRan) onRetractionRan(); }
      else if (d.status === "error") setDbRun({ status: "error", error: d.detail || "Download failed." });
      else setTimeout(() => poll(jobId), 2000);
    });
    const r = await apiPost("/methods/retraction/database/refresh", {});
    if (!r.ok) { setDbRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  const ageDays = db && db.retrieved_at ? Math.floor((Date.now() - new Date(db.retrieved_at).getTime()) / 86400000) : null;
  const stale = ageDays != null && ageDays > 30;

  // Opt-in cadence auto-refresh (backlog #31): default off, decoupled via localStorage — 03_library.jsx's
  // triggerRetractionAutoRefresh reads the same key on launch/focus. Mirrors Feed's own opt-in auto-refresh
  // toggle (30e_feed.jsx) — visible + inspectable, never a silent standing timer (Principles gate, rule #9).
  const [autoRefresh, setAutoRefresh] = useState(() => {
    try { return localStorage.getItem("callosum.retractionAutoRefresh") === "1"; } catch (e) { return false; }
  });
  const toggleAutoRefresh = () => {
    setAutoRefresh(v => {
      const next = !v;
      try { localStorage.setItem("callosum.retractionAutoRefresh", next ? "1" : "0"); } catch (e) { /* ignore */ }
      return next;
    });
  };

  return (
    <>
      <p className="eyebrow">Local maintenance</p>
      <div className="settings-field">
        <div className="settings-row settings-maintenance-action">
          <span className="settings-field-label">Retraction Watch database</span>
          <button className="btn btn-ghost" disabled={dbRun.status === "running"} onClick={refreshDb}>
            {dbRun.status === "running" ? "Downloading…" : "Refresh database"}
          </button>
        </div>
        <span className="settings-sub">
          The local mirror of the Retraction Watch database (Crossref-hosted, CC0) — the richest source
          (reason/date/notice) the library's retraction check can draw on.
        </span>
        <div className={"settings-note" + (stale ? " settings-note-err" : "")}>
          {db && db.count > 0
            ? `${db.count.toLocaleString()} records${db.retrieved_at ? " · as of " + db.retrieved_at.slice(0, 10) : ""}`
            : "Not downloaded — refresh to enable the richest source"}
          {stale && ` · ${ageDays} days old — refresh recommended`}
        </div>
        <label className="auto-refresh-toggle" title="When enabled, refreshes the mirror and re-checks your library automatically on launch (and when you switch back to Callosum) if the mirror is more than 30 days old.">
          <input type="checkbox" checked={autoRefresh} onChange={toggleAutoRefresh} /> Auto-refresh when stale (checked on launch)
        </label>
      </div>
      {dbRun.status === "error" && <div className="settings-note settings-note-err">{dbRun.error}</div>}
      <div className="settings-field">
        <div className="settings-row settings-maintenance-action">
          <span className="settings-field-label">Synthesis cache</span>
          <button className="btn btn-ghost" disabled={busy} onClick={repairSummaryCache}>
            {busy ? "Scanning…" : "Repair synthesis cache"}
          </button>
        </div>
        <span className="settings-sub">
          Scans cached AI draft summaries and removes only malformed cache rows. Saved syntheses, verified citations, chunks, and evidence records are not changed.
        </span>
      </div>
      {msg && <div className="settings-note">{msg}</div>}
    </>
  );
}

// Metadata access (inc 158) — ONE contact email for the public metadata APIs' polite pool (Crossref, OpenAlex,
// Retraction Watch). Setting it here enables the Retraction Watch database download, instead of an env var. Not a
// secret (it is sent to those services as the polite-pool contact, exactly as the env var was) → GET /settings
// returns it, and it is stored in the local file (not the keychain).
function MetadataSettings() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => { api("/settings").then(r => { if (r.ok) setEmail(r.data.contact_email || ""); }); }, []);
  const save = async () => {
    setBusy(true); setMsg("");
    const r = await apiPut("/settings", { set_contact_email: true, contact_email: email.trim() });
    setBusy(false);
    if (r.ok) { setEmail(r.data.contact_email || ""); setMsg(email.trim() ? "Saved." : "Cleared."); }
    else setMsg("Couldn't save: " + (r.error || "error"));
  };
  return (
    <>
      <p className="eyebrow">Metadata access</p>
      <div className="settings-field">
        <label className="settings-field-label">Contact email (Enables the Retraction Watch database.)</label>
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

// Library access (inc 263) — the OpenURL institutional link-resolver hand-off. Set your library's official
// link-resolver base (from its off-campus-access page); when the OA cascade misses, "Get via my library" builds
// an OpenURL and opens THAT resolver in your own browser (your SSO does the auth). callosum never fetches the
// paper or handles credentials — a link-builder + your existing library-folder ingest. Opt-in: empty = dormant,
// the free-OA cascade stays the default (A8). Not a secret (a public URL) → GET /settings returns it.
const OPENURL_CSL = {  // credit-the-lineage: the OpenURL / SFX foundational paper, offered one-click to the library
  id: "vandesompel2001openurl",
  type: "article-journal",
  title: "Open Linking in the Scholarly Information Environment Using the OpenURL Framework",
  "container-title": "D-Lib Magazine",
  volume: "7", issue: "3",
  issued: { "date-parts": [[2001, 3]] },
  DOI: "10.1045/march2001-vandesompel",
  author: [{ given: "Herbert", family: "Van de Sompel" }, { given: "Oren", family: "Beit-Arie" }],
};
function AcquisitionSettings() {
  const [base, setBase] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => { api("/settings").then(r => { if (r.ok) setBase(r.data.openurl_resolver_base || ""); }); }, []);
  const save = async () => {
    setBusy(true); setMsg("");
    const r = await apiPut("/settings", { set_openurl_resolver_base: true, openurl_resolver_base: base.trim() });
    setBusy(false);
    if (r.ok) { setBase(r.data.openurl_resolver_base || ""); setMsg(base.trim() ? "Saved." : "Cleared."); }
    else setMsg("Couldn't save — must be an http(s) URL.");
  };
  return (
    <>
      <p className="eyebrow">Library access</p>
      <div className="settings-field">
        <div className="settings-openurl-row">
          <label className="settings-field-label">Institutional link resolver (OpenURL)</label>
          <input className="settings-input" type="url" autoComplete="off" placeholder="https://your-library.example.edu/openurl"
            value={base} onChange={e => setBase(e.target.value)} />
          <button className="btn btn-ghost" disabled={busy} onClick={save}>{busy ? "Saving…" : "Save"}</button>
        </div>
        <span className="settings-sub">
          Your library's link-resolver base URL (from its “off-campus access” / “get full text” help page). When no open-access copy is found, callosum builds an <b>OpenURL</b> and opens <b>this resolver in your browser</b> — you sign in as usual and download; callosum never fetches the paper or handles your login. Optional; the free open-access route stays the default. Not a secret.
        </span>
        <div className="settings-sub">Uses the NISO OpenURL standard (Van de Sompel &amp; Beit-Arie, 2001). <MethodCreditButton items={[OPENURL_CSL]} /></div>
      </div>
      {msg && <div className="settings-note">{msg}</div>}
    </>
  );
}

// Where to submit (#40 SP1b) — the two consequential publisher prefs, editable anytime (the panel's first-use gate
// forces them on first use; this is where they live thereafter). Reuses PubSegmented / PUB_WEIGHTS / PUB_BREADTHS
// (hoisted from 08e_methods_publishers.jsx). Local-only — never transmitted.
function PublishersSettings() {
  const [status, setStatus] = useState(null);
  useEffect(() => { api("/settings").then(r => { if (r.ok) setStatus(r.data); }); }, []);
  const put = async (body) => { const r = await apiPut("/settings", body); if (r.ok) setStatus(r.data); };
  const setW = (id) => put({ set_publisher_weighting: true, publisher_weighting: PUB_WEIGHTS.find(x => x.id === id).value });
  const setB = (id) => put({ set_publisher_breadth: true, publisher_breadth: id });
  const wId = status ? pubWeightId(status.publisher_weighting) : null;
  const bId = status ? status.publisher_breadth : null;
  return (
    <>
      <p className="eyebrow">Discover: Journals</p>
      <div className="settings-publisher-controls">
        <div className="settings-field">
          <label className="settings-field-label">Open-science weighting
            <span className="settings-sub">How much a journal's openness moves the ranking in Discover → Journals. Neither on nor off is a neutral default — you choose. Stored locally, never transmitted.</span>
          </label>
          <PubSegmented options={PUB_WEIGHTS} value={wId} onChange={setW} ariaLabel="Open-science weighting" />
        </div>
        <div className="settings-field">
          <label className="settings-field-label">Result breadth
            <span className="settings-sub">How many candidate journals to shortlist.</span>
          </label>
          <PubSegmented options={PUB_BREADTHS} value={bId} onChange={setB} ariaLabel="Result breadth" />
        </div>
      </div>
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
      <button className="btn btn-ghost settings-integration-action" disabled={busy} onClick={install}>{busy ? "Installing…" : "Install plugin"}</button>
      <div className="settings-sub">
        Installs the Callosum extension — a <b>Callosum</b> menu + toolbar in Writer (Add citation, Suggest, Refresh, Style, Flatten). Click Install, confirm in LibreOffice's Extension Manager, then restart Writer. The app must be running for the plugin to reach it. <button className="btn-link" onClick={() => downloadAsset("/integrations/libreoffice/plugin.oxt", "callosum.oxt")}>Download .oxt.</button>
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
      <button className="btn btn-ghost settings-integration-action" disabled={busy} onClick={openFolder}>{busy ? "Opening…" : "Open add-in folder"}</button>
      <div className="settings-sub">
        A task pane in <b>desktop</b> Word (Windows/Mac) that searches your library and inserts citations — everything stays on your machine. One-time setup: <b>1)</b> trust a local certificate, run <code>npx office-addin-dev-certs install</code>; <b>2)</b> run Callosum over HTTPS, <code>python tools/run_https.py</code>, then open <code>https://localhost:8443</code>; <b>3)</b> download the manifest and sideload it in Word (see the adapter README). Not supported in Word-on-the-web. <button className="btn-link" onClick={() => downloadAsset("/integrations/word/manifest.xml", "callosum-word-manifest.xml")}>Download manifest.</button>
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
      <p className="eyebrow">Google Docs (Remote access)</p>
      <div className="settings-row settings-integration-toggle">
        <span className="settings-field-label settings-integration-control-title">Allow citing from Google Docs</span>
        <button type="button" className={"settings-switch" + (on ? " on" : "")} role="switch" aria-checked={on}
          aria-label="Allow remote access" disabled={busy} onClick={on ? disable : enable}><span className="settings-knob" /></button>
      </div>
      <span className="settings-sub">
        <b>Off by default.</b> When on, your library is reachable through a tunnel you run (the next setup step) — protected by an access token only you hold. This is the opt-in that lets cited-paper metadata leave your machine; local use is unaffected.
      </span>
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
      <div className="settings-sub">Locked out after losing the token? Just reload — callosum shows a recovery panel that lets you paste the token or turn Remote access back off (a code written to a local file proves you're at this machine). Or restart with <code>CALLOSUM_DISABLE_REMOTE_ACCESS=1</code> set.</div>
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
      <div className="settings-row settings-ai-control">
        <span className="eyebrow settings-ai-control-title">Let an AI agent edit your library</span>
        <button type="button" className={"settings-switch" + (on ? " on" : "")} role="switch" aria-checked={on}
          aria-label="Allow agent writes" disabled={busy} onClick={toggle}><span className="settings-knob" /></button>
        <span className="settings-sub">
          <b>Off by default.</b> When on, an MCP agent (e.g. Claude Desktop, via the callosum MCP server) can tag papers, add them to axes, save verified references, and add notes — each marked <b>ai-agent</b> and reversible below. It can't delete or overwrite anything. Restart your agent host after enabling so the write tools appear.
        </span>
      </div>
      {msg && <div className="settings-note settings-ai-agent-details">{msg}</div>}
      {writes.length > 0 &&
        <div className="settings-field settings-ai-agent-details">
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
        <label className="settings-field-label">Account sign in (Optional.)
          <span className="settings-sub">
            Callosum works fully offline with no account. Requires an <b>ORCID iD</b> — signing in verifies your identity and enables cross-device sync. <b>Identity only</b> — your library, PDFs, and notes never leave your machine.
          </span>
        </label>
        {signedIn
          ? <div className="settings-account-row">
              <button className="btn btn-ghost" disabled={busy} onClick={signOut}>{busy ? "Signing out…" : "Sign out"}</button>
              <div className="settings-note">Signed in{acct.display_name ? " as " + acct.display_name : (acct.email ? " as " + acct.email : "")}{acct.orcid ? " · ORCID " + acct.orcid : ""}{acct.is_superuser ? " · superuser" : ""}.</div>
            </div>
          : acct && acct.configured
            ? <div className="settings-keyrow"><button className="btn btn-primary" disabled={busy} onClick={signIn}>{busy ? "Starting…" : "Sign in"}</button></div>
            : <div className="settings-sub">Sign-in isn't set up on this Callosum yet — the account service is configured by whoever runs this instance.</div>}
      </div>
      {msg && <div className="settings-note">{msg}</div>}
    </>
  );
}

function SettingsCard({ title, children, id }) {
  return (
    <section className="settings-card" id={id}>
      <h2 className="settings-card-title">{title}</h2>
      {children}
    </section>
  );
}

// inc 280 (stage 3): the Settings center view (the menu-bar "Settings" utility workspace) — formerly a modal.
function SettingsView({ theme, onTheme, hideUncertainDefault, onHideUncertainDefault, axisCutoffDefault, onAxisCutoffDefault, onMyPubsRefreshed, onRetractionRan }) {
  const dark = theme === "dark";
  return (
    <div className="workspace-view scroll settings-view">
      <div className="settings-grid">
        <SettingsCard title="Account & sync">
          <div className="settings-sections-grid">
            <div className="settings-section">
              <AccountSettings />
              <div className="settings-subsection">
                <p className="eyebrow">My Publications</p>
                <MyPubsSettings onRefreshed={onMyPubsRefreshed} />
              </div>
              <div className="settings-subsection"><MetadataSettings /></div>
            </div>
            <div className="settings-section">
              <SyncSettings />
              <div className="settings-subsection">
                <p className="eyebrow">Appearance</p>
                <div className="settings-row">
                  <span className="settings-sub">Dark mode</span>
                  <button
                    type="button"
                    className={"settings-switch" + (dark ? " on" : "")}
                    role="switch" aria-checked={dark} aria-label="Dark mode"
                    onClick={() => onTheme(dark ? "light" : "dark")}
                  ><span className="settings-knob" /></button>
                </div>
              </div>
            </div>
          </div>
        </SettingsCard>

        <SettingsCard title="AI features">
          <AiSettings agentSettings={<AgentSettings />} />
        </SettingsCard>

        <SettingsCard title="Library behavior">
          <div className="settings-sections-grid">
            <div className="settings-section settings-section-wide">
              <div className="settings-axis-controls">
                <div className="settings-row settings-axis-control">
                  <span className="eyebrow settings-axis-title">Hide uncertain papers by default</span>
                  <button
                    type="button"
                    className={"settings-switch" + (hideUncertainDefault ? " on" : "")}
                    role="switch" aria-checked={!!hideUncertainDefault} aria-label="Hide uncertain axis papers by default"
                    onClick={() => onHideUncertainDefault(!hideUncertainDefault)}
                  ><span className="settings-knob" /></button>
                  <span className="settings-sub">New axis cards start in the assigned/manual-only view (the 👁 toggle).</span>
                </div>
                <div className="settings-row settings-axis-control">
                  <span className="eyebrow settings-axis-title">Default axis cutoff</span>
                  <span className="settings-cutoff">
                    <input type="range" min="0.2" max="0.6" step="0.01" value={axisCutoffDefault}
                      onChange={e => onAxisCutoffDefault(Number(e.target.value))} aria-label="Default axis cutoff" />
                    <span className="settings-cutoff-val">{Number(axisCutoffDefault).toFixed(2)}</span>
                  </span>
                  <span className="settings-sub">The assigned-vs-uncertain threshold a new axis's re-score starts at (you can still adjust it per axis). Higher = stricter.</span>
                </div>
              </div>
            </div>
            <div className="settings-section"><AcquisitionSettings /></div>
            <div className="settings-section"><LocalMaintenanceSettings onRetractionRan={onRetractionRan} /></div>
            <div className="settings-section settings-section-wide"><PublishersSettings /></div>
          </div>
        </SettingsCard>

        <SettingsCard title="Citation styles" id="citation-styles">
          <CitationStylesSettings />
        </SettingsCard>

        <SettingsCard title="Integrations">
          <div className="settings-sections-grid settings-sections-grid-3">
            <div className="settings-section"><LibreOfficeSettings /></div>
            <div className="settings-section"><WordSettings /></div>
            <div className="settings-section"><RemoteAccessSettings /></div>
          </div>
        </SettingsCard>

      </div>
    </div>
  );
}
