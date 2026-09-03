// My Publications profile + refresh (inc 78). Set your name/variants/ORCID; "Refresh my papers" resolves
// via OpenAlex and (re)builds the pinned axis. Calls onRefreshed() so the axes panel reloads.
function MyPubsSettings({ onRefreshed }) {
  const [name, setName] = useState("");
  const [variants, setVariants] = useState([]);
  const [variantDraft, setVariantDraft] = useState("");
  const [orcid, setOrcid] = useState("");
  const [saving, setSaving] = useState(false);
  const [refresh, setRefresh] = useState({ status: "idle" });
  // Gates every mutating action until the initial GET resolves — previously a fast click (or an Enter-key
  // submit in the variant-draft field, which calls addVariant directly and bypasses the Add button's own
  // disabled attribute) before the fetch completed would PUT blank values and wipe an existing profile.
  const [loading, setLoading] = useState(true);

  const localDiagnostic = (code, message, suggestedAction, details = {}) =>
    callosumClientDiagnostic(code, "My Publications identity", message, suggestedAction, details);

  useEffect(() => {
    api("/my-publications/profile").then(r => {
      if (r.ok) {
        const p = r.data;
        setName(p.display_name || "");
        setVariants(p.name_variants || []);
        setOrcid(p.orcid || "");
      }
      else setRefresh({ status: "error", error: "Couldn't load the saved identity.", diagnostic:
        localDiagnostic("IDENTITY_METADATA_UNAVAILABLE", "Callosum could not read the saved identity.",
          "Retry after Callosum finishes starting; copy these diagnostics if it persists.", { stage: "profile_load" }) });
      setLoading(false);  // flips even on a failed GET, so the UI never sticks disabled forever
    });
  }, []);

  const persistProfile = async (nextVariants) => {
    if (loading) return false;
    setSaving(true);
    const r = await apiPut("/my-publications/profile", {
      display_name: name.trim() || null,
      name_variants: nextVariants,
      orcid: orcid.trim() || null,
    });
    setSaving(false);
    if (!r.ok) setRefresh({ status: "error", error: r.error || "Couldn't save the identity.", diagnostic:
      localDiagnostic((r.status === 422 ? "IDENTITY_ORCID_INVALID" : "IDENTITY_METADATA_UNAVAILABLE"),
        r.error || "Callosum could not save the identity.", "Correct the ORCID if prompted, then retry.",
        { stage: "profile_save", http_status: r.status || null }) });
    return r.ok;
  };
  const save = async () => {
    if (loading) return;
    const draft = variantDraft.trim();
    const savedVariants = draft && !variants.some(v => v.toLowerCase() === draft.toLowerCase()) ? [...variants, draft] : variants;
    const saved = await persistProfile(savedVariants);
    if (saved && draft) { setVariants(savedVariants); setVariantDraft(""); }
    return saved;
  };
  const addVariant = async (rawValue = variantDraft) => {
    if (loading) return;
    const value = rawValue.trim();
    if (!value) return;
    if (variants.some(v => v.toLowerCase() === value.toLowerCase())) { setVariantDraft(""); return; }
    const nextVariants = [...variants, value];
    setVariants(nextVariants); setVariantDraft("");
    if (!(await persistProfile(nextVariants))) { setVariants(variants); setVariantDraft(value); }
  };
  const removeVariant = async (index) => {
    if (loading) return;
    const nextVariants = variants.filter((_, i) => i !== index);
    setVariants(nextVariants);
    if (!(await persistProfile(nextVariants))) setVariants(variants);
  };

  const runRefresh = async () => {
    if (loading) return;
    if (!(await save())) return;  // never refresh stale/blank identity after a failed save
    setRefresh({ status: "running" });
    const poll = (jobId) => api(`/my-publications/refresh/${jobId}`).then(r => {
      if (!r.ok) { setRefresh({ status: "error", error: r.error, diagnostic:
        localDiagnostic("IDENTITY_ENRICHMENT_OPENALEX_FAILED", "The identity refresh status could not be read.",
          "Retry; copy these diagnostics if it fails again.", { stage: "refresh_poll", http_status: r.status || null }) }); return; }
      const d = r.data;
      if (d.status === "done") { setRefresh({ status: "done", summary: d.summary, diagnostic: d.summary && d.summary.diagnostic }); if (onRefreshed) onRefreshed(); }
      else if (d.status === "error") setRefresh({ status: "error", error: d.detail || "Refresh failed.", diagnostic: d.diagnostic });
      else setTimeout(() => poll(jobId), 1500);
    });
    const r = await apiPost("/my-publications/refresh", {});
    if (!r.ok) { setRefresh({ status: "error", error: r.error, diagnostic:
      localDiagnostic("IDENTITY_ENRICHMENT_OPENALEX_FAILED", "The identity refresh could not start.",
        "Retry; copy these diagnostics if it fails again.", { stage: "refresh_start", http_status: r.status || null }) }); return; }
    poll(r.data.job_id);
  };

  const s = refresh.summary;
  const summaryText = !s ? "" :
    s.status === "ok" ? `Found ${s.confirmed || 0} confirmed + ${s.candidates || 0} candidate${(s.candidates || 0) === 1 ? "" : "s"} (of ${s.indexed_works || 0} indexed works; ${s.in_library || 0} in your library).${s.matched_by === "name" ? " Matched by name, not ORCID (your OpenAlex profile may not be linked to it yet) — lower confidence; double-check this is you." : ""}` :
    s.status === "no-identity" ? "Add your name or ORCID first." :
    s.status === "enrichment-not-found" ? "Your ORCID iD is saved as your Callosum identity. OpenAlex did not return a linked author profile, so publications were not gathered." :
    s.status === "enrichment-failed" ? "Your identity is saved, but OpenAlex enrichment could not complete." :
    s.status === "enrichment-link-mismatch" ? "Your identity is saved, but the OpenAlex candidate did not safely match it." :
    s.status === "invalid-orcid" ? "That ORCID iD is not valid. Check all 16 characters and try again." :
    s.status === "refresh-incomplete" ? "OpenAlex linked your profile, but the publications response was incomplete. No partial result was saved." :
    s.status === "no-match" ? "No unambiguous OpenAlex author matched that name. Try your full published name or ORCID iD." :
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
          <button type="button" className="btn btn-ghost" disabled={loading || saving || !variantDraft.trim()} onClick={() => addVariant()}>Add</button>
        </div>
        {variants.length > 0 && <div className="settings-name-tags" aria-label="Other published names">
          {variants.map((variant, index) => <span className="tag-chip" key={variant + index}>
            <span className="tag-chip-name">{variant}</span>
            <button type="button" className="tag-chip-x" disabled={loading || saving} aria-label={`Remove ${variant}`}
              onClick={() => removeVariant(index)}>×</button>
          </span>)}
        </div>}
      </div>
      <div className="settings-field">
        <label className="settings-field-label">ORCID (Recommended — gives an exact match. Resolved via OpenAlex.)</label>
        <div className="settings-keyrow settings-orcid-row">
          <input className="settings-input" placeholder="0000-0002-1825-0097" value={orcid} onChange={e => setOrcid(e.target.value)} />
          <button className="btn btn-ghost" disabled={loading || saving} onClick={save}>{saving ? "Saving…" : "Save"}</button>
          <button className="btn btn-primary" disabled={loading || refresh.status === "running" || (!name.trim() && !orcid.trim())} onClick={runRefresh}>
            {refresh.status === "running" ? "Gathering…" : loading ? "Loading…" : "Refresh my papers"}
          </button>
        </div>
      </div>
      {refresh.status === "running" && <ProgressBar label="Resolving via OpenAlex…" managedBy="backend-job" />}
      {refresh.status === "error" && <div className="settings-note settings-note-err">Refresh failed: {refresh.error}<div className="settings-actions"><CopyDiagnosticButton diagnostic={refresh.diagnostic} /></div></div>}
      {refresh.status === "done" && <div className="settings-note">{summaryText}{refresh.diagnostic && <div className="settings-actions"><CopyDiagnosticButton diagnostic={refresh.diagnostic} /></div>}</div>}
    </>
  );
}
