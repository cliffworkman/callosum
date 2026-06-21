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
      {refresh.status === "error" && <div className="settings-note settings-note-err">Refresh failed: {refresh.error}</div>}
      {refresh.status === "done" && <div className="settings-note">{summaryText}</div>}
      <div className="settings-sub">Resolved via OpenAlex (public metadata — not the Gemini gate); never uses an LLM.</div>
    </>
  );
}

function SettingsModal({ theme, onTheme, hideUncertainDefault, onHideUncertainDefault, onMyPubsRefreshed, onClose }) {
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

        <MyPubsSettings onRefreshed={onMyPubsRefreshed} />

        <div className="axis-modal-note">More settings will live here — this is just the start.</div>
      </div>
    </div>
  );
}
