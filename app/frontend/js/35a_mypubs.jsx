// My Publications profile + refresh (inc 78). Set your name/variants/ORCID; "Refresh my papers" resolves
// via OpenAlex and (re)builds the pinned axis. Calls onRefreshed() so the axes panel reloads.
function MyPubsSettings({ onRefreshed }) {
  const [name, setName] = useState("");
  const [variants, setVariants] = useState([]);
  const [variantDraft, setVariantDraft] = useState("");
  const [orcid, setOrcid] = useState("");
  const [saving, setSaving] = useState(false);
  const [refresh, setRefresh] = useState({ status: "idle" });

  useEffect(() => {
    api("/my-publications/profile").then(r => {
      if (!r.ok) return;
      const p = r.data;
      setName(p.display_name || "");
      setVariants(p.name_variants || []);
      setOrcid(p.orcid || "");
    });
  }, []);

  const persistProfile = async (nextVariants) => {
    setSaving(true);
    const r = await apiPut("/my-publications/profile", {
      display_name: name.trim() || null,
      name_variants: nextVariants,
      orcid: orcid.trim() || null,
    });
    setSaving(false);
    return r.ok;
  };
  const save = async () => {
    const draft = variantDraft.trim();
    const savedVariants = draft && !variants.some(v => v.toLowerCase() === draft.toLowerCase()) ? [...variants, draft] : variants;
    if (await persistProfile(savedVariants) && draft) { setVariants(savedVariants); setVariantDraft(""); }
  };
  const addVariant = async (rawValue = variantDraft) => {
    const value = rawValue.trim();
    if (!value) return;
    if (variants.some(v => v.toLowerCase() === value.toLowerCase())) { setVariantDraft(""); return; }
    const nextVariants = [...variants, value];
    setVariants(nextVariants); setVariantDraft("");
    if (!(await persistProfile(nextVariants))) { setVariants(variants); setVariantDraft(value); }
  };
  const removeVariant = async (index) => {
    const nextVariants = variants.filter((_, i) => i !== index);
    setVariants(nextVariants);
    if (!(await persistProfile(nextVariants))) setVariants(variants);
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
    s.status === "ok" ? `Found ${s.confirmed || 0} confirmed + ${s.candidates || 0} candidate${(s.candidates || 0) === 1 ? "" : "s"} (of ${s.indexed_works || 0} indexed works; ${s.in_library || 0} in your library).${s.matched_by === "name" ? " Matched by name, not ORCID (your OpenAlex profile may not be linked to it yet) — lower confidence; double-check this is you." : ""}` :
    s.status === "no-identity" ? "Add your name or ORCID first." :
    s.status === "no-match" ? `No OpenAlex author found for ${s.name || "that identity"} — check the name / ORCID, or see Help for linking OpenAlex to ORCID.` :
    "Done.";

  return (
    <>
      <div className="settings-field">
        <label className="settings-field-label">Your name</label>
        <input className="settings-input" placeholder="e.g. Karen Spärck Jones" value={name} onChange={e => setName(e.target.value)} />
      </div>
      <div className="settings-field">
        <label className="settings-field-label">Other published names</label>
        <div className="settings-keyrow">
          <input className="settings-input" placeholder="e.g. K. Spärck Jones" value={variantDraft}
            onChange={e => setVariantDraft(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addVariant(e.currentTarget.value); } }} />
          <button type="button" className="btn btn-ghost" disabled={saving || !variantDraft.trim()} onClick={() => addVariant()}>Add</button>
        </div>
        {variants.length > 0 && <div className="settings-name-tags" aria-label="Other published names">
          {variants.map((variant, index) => <span className="tag-chip" key={variant + index}>
            <span className="tag-chip-name">{variant}</span>
            <button type="button" className="tag-chip-x" disabled={saving} aria-label={`Remove ${variant}`}
              onClick={() => removeVariant(index)}>×</button>
          </span>)}
        </div>}
      </div>
      <div className="settings-field">
        <label className="settings-field-label">ORCID (Recommended — gives an exact match. Resolved via OpenAlex.)</label>
        <div className="settings-keyrow settings-orcid-row">
          <input className="settings-input" placeholder="0000-0002-1825-0097" value={orcid} onChange={e => setOrcid(e.target.value)} />
          <button className="btn btn-ghost" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save"}</button>
          <button className="btn btn-primary" disabled={refresh.status === "running" || (!name.trim() && !orcid.trim())} onClick={runRefresh}>
            {refresh.status === "running" ? "Gathering…" : "Refresh my papers"}
          </button>
        </div>
      </div>
      {refresh.status === "running" && <ProgressBar label="Resolving via OpenAlex…" />}
      {refresh.status === "error" && <div className="settings-note settings-note-err">Refresh failed: {refresh.error}</div>}
      {refresh.status === "done" && <div className="settings-note">{summaryText}</div>}
    </>
  );
}
