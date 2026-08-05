// Local usage instrumentation + personal dashboard (backlog #38A, inc 450). Split from 35_settings.jsx per the
// inc-256/448 file-per-concern precedent (35b_providers.jsx / 35e_maintenance.jsx) -- hoists across the shared
// IIFE, so SettingsView calls <UsageSettings /> directly, unchanged.
//
// Design doc: .claude/docs/future-tracks/opus4.8_future-tracks_researchimpactanalytics.md (Stage 1+2 only --
// zero egress, nothing ever leaves this machine). Recording defaults ON (unlike every other toggle in Settings)
// because nothing here egresses; read/export/clear always work regardless of the toggle's state.

function UsageSettings() {
  const [summary, setSummary] = useState(null);  // { enabled, types: [{event_type,label,all_time,last_30_days}] }
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const refresh = () => { api("/usage/summary").then(r => { if (r.ok) setSummary(r.data); }); };
  useEffect(() => { refresh(); }, []);

  const toggle = async () => {
    setBusy(true); setMsg("");
    const r = await apiPut("/settings", { usage_events_enabled: !summary.enabled });
    setBusy(false);
    if (r.ok) refresh();
    else setMsg("Couldn't toggle: " + (r.error || "error"));
  };

  const exportLog = () => downloadAsset("/usage/export", "callosum-usage-log.json");

  const clearLog = async () => {
    if (!window.confirm("Clear your local usage log? This only removes the counts below -- nothing in your library, PDFs, or citations is touched.")) return;
    setBusy(true); setMsg("");
    const r = await apiPost("/usage/clear", {});
    setBusy(false);
    if (r.ok) { setMsg(`Cleared ${r.data.deleted} local event${r.data.deleted === 1 ? "" : "s"}.`); refresh(); }
    else setMsg("Couldn't clear: " + (r.error || "error"));
  };

  if (!summary) return null;
  const on = summary.enabled;

  return (
    <>
      <div className="settings-row settings-ai-control">
        <span className="eyebrow settings-ai-control-title">Track local usage</span>
        <button type="button" className={"settings-switch" + (on ? " on" : "")} role="switch" aria-checked={on}
          aria-label="Track local usage" disabled={busy} onClick={toggle}><span className="settings-knob" /></button>
        <span className="settings-sub">
          <b>On by default</b> -- nothing here ever leaves this machine, so this behaves like any other local
          feature rather than the egress-consent toggles elsewhere on this page. Callosum counts a handful of
          specific actions (exporting a citation, resolving a duplicate, re-resolving metadata, locating a quote,
          reviewing a flagged reference) -- never PDF text, searches, library contents, or anything else you type
          or read. This is a count of actions, not a score: for tedious operations, doing them <i>less</i> is the
          win, so a rising number here is not itself a goal. Turn it off anytime -- the counts below stay readable
          and exportable regardless.
        </span>
      </div>
      {msg && <div className="settings-note settings-ai-agent-details">{msg}</div>}
      <div className="settings-field settings-ai-agent-details">
        <label className="settings-field-label">Your counts</label>
        <div className="agent-activity">
          {summary.types.map(t => (
            <div key={t.event_type} className="agent-activity-row">
              <span className="agent-activity-what">{t.label}</span>
              <span className="settings-sub">{t.all_time} all time · {t.last_30_days} in the last 30 days</span>
            </div>
          ))}
        </div>
      </div>
      <div className="settings-actions">
        <button type="button" className="btn btn-ghost" onClick={exportLog}>Export usage log</button>
        <button type="button" className="btn btn-ghost" disabled={busy} onClick={clearLog}>Clear usage log</button>
      </div>
    </>
  );
}
