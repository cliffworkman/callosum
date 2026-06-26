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

// AI features (inc 146 — BYOK). Set your Gemini API key + turn on data egress here, instead of env vars.
// The key is write-only: GET /settings returns status only (never the value); egress is default-OFF.
function AiSettings() {
  const [status, setStatus] = useState(null);  // {api_key_set, api_key_source, data_egress_enabled, egress_source}
  const [keyInput, setKeyInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [test, setTest] = useState(null);  // {ok, detail} from POST /settings/test-key
  const [testing, setTesting] = useState(false);

  useEffect(() => { api("/settings").then(r => { if (r.ok) setStatus(r.data); }); }, []);

  const testKey = async () => {
    setTesting(true); setTest(null);
    const r = await apiPost("/settings/test-key", {});
    setTesting(false);
    setTest(r.ok ? r.data : { ok: false, detail: r.error || "Test failed." });
  };

  const applyKey = async (value, doneMsg) => {
    setBusy(true); setMsg("");
    const r = await apiPut("/settings", { set_api_key: true, api_key: value });
    setBusy(false);
    if (r.ok) { setStatus(r.data); setKeyInput(""); setMsg(doneMsg); }
    else setMsg("Couldn't save: " + (r.error || "error"));
  };

  const toggleEgress = async () => {
    if (!status) return;
    const r = await apiPut("/settings", { data_egress_enabled: !status.data_egress_enabled });
    if (r.ok) setStatus(r.data);
  };

  const egressOn = !!(status && status.data_egress_enabled);
  const keySet = !!(status && status.api_key_set);
  const fromEnv = status && status.api_key_source === "env";
  return (
    <>
      <p className="eyebrow">AI features</p>
      <div className="settings-field">
        <label className="settings-field-label">Gemini API key
          <span className="settings-sub">
            {keySet
              ? (fromEnv ? "Set via the GOOGLE_API_KEY environment variable." : "A key is saved on this machine.")
              : "Not set. AI summaries need a key — stored locally, never sent anywhere but Google."}
            {" "}<a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer">Get a key →</a>
          </span>
        </label>
        <div className="settings-keyrow">
          <input className="settings-input" type="password" autoComplete="off"
            placeholder={keySet && !fromEnv ? "•••••••• (saved) — type to replace" : "Paste your key"}
            value={keyInput} onChange={e => setKeyInput(e.target.value)} />
          <button className="btn btn-ghost" disabled={busy || !keyInput.trim()} onClick={() => applyKey(keyInput, "Key saved.")}>{busy ? "Saving…" : "Save"}</button>
          {keySet && !fromEnv &&
            <button className="btn btn-ghost" disabled={busy} onClick={() => applyKey("", "Key cleared.")}>Clear</button>}
        </div>
        {keySet &&
          <div className="settings-keytest">
            <button className="btn btn-ghost" disabled={testing} onClick={testKey}>{testing ? "Testing…" : "Test key"}</button>
            {test && <span className={"settings-keytest-result " + (test.ok ? "ok" : "err")}>{test.detail}</span>}
          </div>}
      </div>
      <div className="settings-row">
        <span className="settings-label">Allow AI features (sends text to Google)
          <span className="settings-sub">
            Off by default. When on, generating a summary sends the relevant library text to Google's Gemini API; every sentence is still verified locally against your PDFs.
            {status && status.egress_source === "env" ? " Currently set by the CALLOSUM_ALLOW_DATA_EGRESS environment variable." : ""}
          </span>
        </span>
        <button type="button" className={"settings-switch" + (egressOn ? " on" : "")}
          role="switch" aria-checked={egressOn} aria-label="Allow AI features"
          onClick={toggleEgress}><span className="settings-knob" /></button>
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

        <MyPubsSettings onRefreshed={onMyPubsRefreshed} />

        <div className="axis-modal-note">More settings will live here — this is just the start.</div>
      </div>
    </div>
  );
}
