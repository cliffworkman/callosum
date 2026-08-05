// Settings → Local maintenance (split from 35_settings.jsx, backlog #40 -- adding the TOP Factor mirror row
// pushed that file over the 600-line cap; extracted whole, matching the inc-256 35b_providers.jsx precedent).
// Hoists across the shared IIFE, so SettingsModal (35_settings.jsx) calls it directly, unchanged.

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

  // TOP Factor mirror (backlog #40) — a periodically-updated public snapshot (no live query API exists) that
  // feeds Where-to-submit's TOP Factor fact once downloaded. Mirrors the Retraction Watch block above exactly,
  // minus the contact-email requirement (no auth needed).
  const [tf, setTf] = useState(null);  // { count, retrieved_at } | null
  const [tfRun, setTfRun] = useState({ status: "idle" });
  const loadTf = () => api("/methods/top-factor/database").then(r => { if (r.ok) setTf(r.data); });
  useEffect(() => { loadTf(); }, []);
  const refreshTf = async () => {
    setTfRun({ status: "running" });
    const poll = (jobId) => api(`/methods/top-factor/database/refresh/${jobId}`).then(r => {
      if (!r.ok) { setTfRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setTfRun({ status: "done" }); loadTf(); }
      else if (d.status === "error") setTfRun({ status: "error", error: d.detail || "Download failed." });
      else setTimeout(() => poll(jobId), 2000);
    });
    const r = await apiPost("/methods/top-factor/database/refresh", {});
    if (!r.ok) { setTfRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };

  // AJOL mirror (backlog #40, inc 451) — a THIRD-PARTY compiled snapshot (not an AJOL-official feed), dated
  // to a fixed vintage (snapshot_date) that a re-download can never change -- "Download database" (never
  // "Refresh") is the honest verb here; TOP Factor/Retraction Watch are periodically republished by their own
  // source org, this is a one-time academic dataset with no such guarantee.
  const [ajol, setAjol] = useState(null);  // { count, retrieved_at, snapshot_date } | null
  const [ajolRun, setAjolRun] = useState({ status: "idle" });
  const loadAjol = () => api("/methods/ajol/database").then(r => { if (r.ok) setAjol(r.data); });
  useEffect(() => { loadAjol(); }, []);
  const downloadAjol = async () => {
    setAjolRun({ status: "running" });
    const poll = (jobId) => api(`/methods/ajol/database/refresh/${jobId}`).then(r => {
      if (!r.ok) { setAjolRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setAjolRun({ status: "done" }); loadAjol(); }
      else if (d.status === "error") setAjolRun({ status: "error", error: d.detail || "Download failed." });
      else setTimeout(() => poll(jobId), 2000);
    });
    const r = await apiPost("/methods/ajol/database/refresh", {});
    if (!r.ok) { setAjolRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
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
          <span className="settings-field-label">TOP Factor database</span>
          <button className="btn btn-ghost" disabled={tfRun.status === "running"} onClick={refreshTf}>
            {tfRun.status === "running" ? "Downloading…" : "Refresh database"}
          </button>
        </div>
        <span className="settings-sub">
          The Center for Open Science's per-journal transparency/openness rubric — a periodically-updated public
          snapshot (no live query API exists) that feeds Discover → Journals' TOP Factor fact once downloaded.
        </span>
        <div className="settings-note">
          {tf && tf.count > 0
            ? `${tf.count.toLocaleString()} journals${tf.retrieved_at ? " · as of " + tf.retrieved_at.slice(0, 10) : ""}`
            : "Not downloaded — refresh to include TOP Factor in Where-to-submit results"}
        </div>
      </div>
      {tfRun.status === "error" && <div className="settings-note settings-note-err">{tfRun.error}</div>}
      <div className="settings-field">
        <div className="settings-row settings-maintenance-action">
          <span className="settings-field-label">AJOL database</span>
          <button className="btn btn-ghost" disabled={ajolRun.status === "running"} onClick={downloadAjol}>
            {ajolRun.status === "running" ? "Downloading…" : "Download database"}
          </button>
        </div>
        <span className="settings-sub">
          A third-party, CC-BY-4.0 compiled snapshot of African Journals Online (AJOL) journal metadata — not an
          AJOL-official feed. A one-time academic dataset, not a periodically-updated source: downloading again
          will not fetch newer data than the {ajol ? ajol.snapshot_date : "dataset's"} snapshot, and it may not
          reflect journals AJOL has added, removed, or reclassified since.
        </span>
        <div className="settings-note">
          {ajol && ajol.count > 0
            ? `${ajol.count.toLocaleString()} journals · ${ajol.snapshot_date} snapshot, downloaded ${ajol.retrieved_at ? ajol.retrieved_at.slice(0, 10) : "?"}`
            : "Not downloaded — download to include AJOL in Where-to-submit results"}
        </div>
      </div>
      {ajolRun.status === "error" && <div className="settings-note settings-note-err">{ajolRun.error}</div>}
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
