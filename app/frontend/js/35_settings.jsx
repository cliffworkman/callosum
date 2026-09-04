// Settings modal (inc 46) — the app-wide preferences surface. Appearance → Dark mode (theme + onTheme); Axes →
// hide-uncertain-by-default (hideUncertainDefault + onHideUncertainDefault). Controlled by App; toggles persist
// to localStorage. Reuses the .axis-modal overlay pattern.
// AI features — the unified LLM provider roster (`AiSettings`) lives in js/35b_providers.jsx (inc 256). It
// hoists across the shared IIFE, so SettingsModal below references it directly.
// Local maintenance (`LocalMaintenanceSettings`, incl. the Retraction Watch + TOP Factor mirrors) lives in
// js/35e_maintenance.jsx (backlog #40) — split out to stay under the 600-line cap, same hoist pattern.
// GROBID document structure (`GrobidSettings`, URL + Test connection + bulk "Parse structure for library") also
// lives in js/35e_maintenance.jsx (backlog #30 Stage 2, task 11) — same hoist pattern.

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

// WordSettings + LibreOfficeSettings live in js/35e_maintenance.jsx (split out to preserve this file's
// 600-line budget). Both hoist across the shared IIFE and are called here unchanged.

// Remote access (inc 168) — the opt-in, default-OFF gate that lets the Google Docs add-on reach your library through
// a tunnel you run. Enabling mints an access token (shown once → copy into the add-on) + saves it locally so the
// local UI keeps working under the gate. Off by default; local-only use is unaffected.
function RemoteAccessSettings() {
  const packaged = "__TAURI__" in window;
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState("");  // shown once, right after minting
  const [msg, setMsg] = useState("");
  const [tunnel, setTunnel] = useState(null);
  const [tunnelBusy, setTunnelBusy] = useState(false);
  const [tunnelMsg, setTunnelMsg] = useState("");
  const refresh = () => api("/settings").then(r => { if (r.ok) setStatus(r.data); });
  const refreshTunnel = () => packaged && window.__TAURI__.core.invoke("quick_tunnel_status")
    .then(setTunnel).catch(e => setTunnelMsg("Couldn't check Quick Tunnel: " + String(e)));
  useEffect(() => { refresh(); refreshTunnel(); }, []);
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
    if (packaged) {
      try {
        const stopped = await window.__TAURI__.core.invoke("stop_quick_tunnel");
        setTunnel(stopped); setTunnelMsg("");
      } catch (e) {
        setBusy(false); setMsg("Couldn't stop the Quick Tunnel, so Remote access stayed on: " + String(e)); return;
      }
    }
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
  const changeTunnel = async (start) => {
    setTunnelBusy(true); setTunnelMsg("");
    try {
      const result = await window.__TAURI__.core.invoke(start ? "start_quick_tunnel" : "stop_quick_tunnel");
      setTunnel(result);
      setTunnelMsg(result.detail || (start ? "Quick Tunnel started." : "Quick Tunnel stopped."));
    } catch (e) {
      setTunnelMsg("Couldn't change Quick Tunnel: " + String(e));
    }
    setTunnelBusy(false);
  };
  const copyTunnelUrl = () => tunnel && tunnel.url && navigator.clipboard.writeText(tunnel.url)
    .then(() => setTunnelMsg("Tunnel URL copied. Paste it into the add-on with your bearer token."));

  return (
    <>
      <p className="eyebrow">Google Docs (Remote access)</p>
      <div className="settings-row settings-integration-toggle">
        <span className="settings-field-label settings-integration-control-title">Allow Citing from Google Docs</span>
        <button type="button" className={"settings-switch" + (on ? " on" : "")} role="switch" aria-checked={on}
          aria-label="Allow remote access" disabled={busy || tunnelBusy} onClick={on ? disable : enable}><span className="settings-knob" /></button>
      </div>
      <span className="settings-sub">
        <b>Off by default.</b> When on, your library is reachable through a tunnel you run (the next setup step) — protected by an access token only you hold. This is the opt-in that lets cited-paper metadata leave your machine; local use is unaffected.
      </span>
      {on &&
        <div className="settings-keyrow">
          <button className="btn btn-ghost" disabled={busy} onClick={regenerate}>Regenerate Token</button>
        </div>}
      {token &&
        <div className="settings-field">
          <label className="settings-field-label">Access token — shown once; copy it into the add-on
            <span className="settings-sub">Stored on this machine; sent to your tunnel as a Bearer token. It is never shown again or returned by the app.</span>
          </label>
          <input className="settings-input" readOnly value={token} onFocus={e => e.target.select()} />
        </div>}
      {packaged && on && <div className="settings-field">
        <span className="settings-field-label">Temporary Quick Tunnel</span>
        <span className="settings-sub">Explicitly starts an app-owned Cloudflare tunnel for Google Docs or Word on the web. Quick Tunnels expose every Callosum route; your bearer token is the sole boundary. Stop the tunnel when you finish.</span>
        <div className="settings-keyrow">
          <button className="btn btn-ghost" disabled={tunnelBusy || !tunnel || (!tunnel.available && !tunnel.running)} onClick={() => changeTunnel(!(tunnel && tunnel.running))}>
            {tunnelBusy ? "Working…" : (tunnel && tunnel.running ? "Stop Quick Tunnel" : "Start Quick Tunnel")}
          </button>
          {tunnel && tunnel.running && <button className="btn btn-ghost" disabled={tunnelBusy} onClick={copyTunnelUrl}>Copy URL</button>}
        </div>
        {tunnel && tunnel.url && <input className="settings-input" readOnly value={tunnel.url} onFocus={e => e.target.select()} />}
        {tunnel && !tunnel.available && <span className="settings-sub">Install <code>cloudflared</code> from Cloudflare, restart Callosum, and return here.</span>}
        {tunnelMsg && <div className="settings-note">{tunnelMsg}</div>}
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

// backlog #41: the admin-gated plugins foundation. Off by default; enabling it does nothing
// observable yet -- no loader, no data model, no third-party code ever runs. See
// .claude/docs/specs/2026-08-19-admin-gated-plugins-design.md for the design this is the
// foundation for (a future curated, review-gated plugin store -- not an open marketplace).
function PluginsSettings() {
  const [on, setOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => { api("/settings").then(r => { if (r.ok) setOn(!!r.data.plugins_enabled); }); }, []);

  const toggle = async () => {
    setBusy(true); setMsg("");
    const r = await apiPut("/settings", { plugins_enabled: !on });
    setBusy(false);
    if (r.ok) setOn(!!r.data.plugins_enabled);
    else setMsg("Couldn't toggle: " + (r.error || "error"));
  };

  return (
    <>
      <div className="settings-row settings-ai-control">
        <span className="eyebrow settings-ai-control-title">Plugins</span>
        <button type="button" className={"settings-switch" + (on ? " on" : "")} role="switch" aria-checked={on}
          aria-label="Enable plugins" disabled={busy} onClick={toggle}><span className="settings-knob" /></button>
        <span className="settings-sub">
          <b>Off by default.</b> Foundation for a future curated, review-gated plugin store — user-authored panel modules would need to pass review before being available to install, never an open marketplace. Nothing is installable yet, and enabling this toggle does not change any other behavior — no plugin can run until that store exists.
        </span>
      </div>
      {msg && <div className="settings-note">{msg}</div>}
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
              <button className="btn btn-ghost" disabled={busy} onClick={signOut}>{busy ? "Signing out…" : "Sign Out"}</button>
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

// inc 468: superuser-only diagnostics — the first application of the reusable require_superuser gate (inc 195's
// deferred superuser capabilities). Self-contained (its own /settings check), matching AccountSettings's own
// pattern above, so it renders nothing until is_superuser is confirmed true — never a flash of hidden content.
function DiagnosticsSettings() {
  const [isSuperuser, setIsSuperuser] = useState(false);
  const [stats, setStats] = useState(null);
  useEffect(() => {
    api("/settings").then(r => { if (r.ok) setIsSuperuser(!!(r.data.account && r.data.account.is_superuser)); });
  }, []);
  useEffect(() => {
    if (!isSuperuser) { setStats(null); return; }
    api("/diagnostics").then(r => { if (r.ok) setStats(r.data); });
  }, [isSuperuser]);

  if (!isSuperuser || !stats) return null;
  return (
    <div className="settings-subsection">
      <p className="eyebrow">Diagnostics <span className="settings-sub">(superuser only)</span></p>
      <div className="settings-field">
        <span className="settings-sub">
          Library: {stats.paper_count} papers · {stats.chunk_count} chunks · {stats.embedding_count} embeddings.
          {" "}Remote access {stats.remote_access_enabled ? "on" : "off"} · Sync {stats.sync_enabled ? "on" : "off"}
          {stats.sync_server_configured ? " (server configured)" : ""}.
          {" "}DB {stats.db_reachable ? "reachable" : "unreachable"}{stats.db_migrated ? ", at head" : ", NOT at head"}.
          {stats.app_version ? ` Version ${stats.app_version}.` : ""}
        </span>
      </div>
    </div>
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

// The browser demo cannot execute editor, terminal, agent, or first-run shells. Keep those interfaces
// inspectable without pretending that a static page can install or connect them.
function DemoExternalInterfaces() {
  if (!isDemoMode()) return null;
  return (
    <SettingsCard title="Other interfaces & first run">
      <div className="settings-sections-grid settings-sections-grid-3">
        <div className="settings-section">
          <p className="eyebrow">First-run onboarding</p>
          <span className="settings-sub">The installed app starts with a guided choice: import an existing Zotero library, scan a PDF folder, or begin with an empty local library. This public demo skips setup and opens the curated Library so no visitor is stranded before the evidence workflow.</span>
        </div>
        <div className="settings-section">
          <p className="eyebrow">Terminal client</p>
          <span className="settings-sub"><code>python -m tui</code> provides keyboard-first access to the same local API in the installed app. It cannot run in a browser-only static site.</span>
        </div>
        <div className="settings-section">
          <p className="eyebrow">MCP agent interface</p>
          <span className="settings-sub">The local MCP server exposes five read tools. Four write tools appear only after the explicit agent-write gate is enabled; every agent change is labeled, logged, and reversible. The public demo exposes no agent endpoint.</span>
        </div>
      </div>
    </SettingsCard>
  );
}

// inc 280 (stage 3): the Settings center view (the menu-bar "Settings" utility workspace) — formerly a modal.
// `DesktopUpdateSettings` lives in 04d_update.jsx beside the rest of the updater surface (hoisted
// across the shared IIFE — the inc-208/222/256 precedent); it moved there in inc 574 both to keep
// every "what is the updater doing" string in one file and to keep this one under the 600-line cap.

function SettingsView({ theme, onTheme, hideUncertainDefault, onHideUncertainDefault, axisCutoffDefault, onAxisCutoffDefault, onMyPubsRefreshed, onRetractionRan, desktopUpdate }) {
  const dark = theme === "dark";
  return (
    <div className="workspace-view scroll settings-view">
      <div className="settings-grid">
        <SettingsCard title="Account & sync">
          <div className="settings-sections-grid">
            <div className="settings-section">
              <AccountSettings />
              <DiagnosticsSettings />
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
                  <span className="settings-sub">Dark Mode</span>
                  <button
                    type="button"
                    className={"settings-switch" + (dark ? " on" : "")}
                    role="switch" aria-checked={dark} aria-label="Dark Mode"
                    onClick={() => onTheme(dark ? "light" : "dark")}
                  ><span className="settings-knob" /></button>
                </div>
              </div>
              <DesktopUpdateSettings desktopUpdate={desktopUpdate} />
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
                  <span className="eyebrow settings-axis-title">Hide Uncertain Papers by Default</span>
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
            <div className="settings-section">
              <AcquisitionSettings />
              <div className="settings-subsection"><GrobidSettings /></div>
            </div>
            <div className="settings-section"><LocalMaintenanceSettings onRetractionRan={onRetractionRan} /></div>
            <div className="settings-section settings-section-wide"><PublishersSettings /></div>
          </div>
        </SettingsCard>

        <SettingsCard title="Citation styles" id="citation-styles">
          <CitationStylesSettings />
        </SettingsCard>

        <SettingsCard title="Integrations">
          <ServerAddressSettings />
          <div className="settings-sections-grid settings-sections-grid-3">
            <div className="settings-section"><LibreOfficeSettings /></div>
            <div className="settings-section"><WordSettings /></div>
            <div className="settings-section"><RemoteAccessSettings /></div>
          </div>
        </SettingsCard>

        <SettingsCard title="Plugins">
          <PluginsSettings />
        </SettingsCard>

        <SettingsCard title="Your usage">
          <UsageSettings />
        </SettingsCard>

        <DemoExternalInterfaces />

      </div>
    </div>
  );
}
