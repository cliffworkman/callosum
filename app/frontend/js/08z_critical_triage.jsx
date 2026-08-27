// 08z_critical_triage.jsx — shared critique-triage UI (a reversible display layer, mirrors inc-435's
// registration-comparison AI triage exactly: "All rows"/"AI-focused" toggle + a per-item label/rationale
// badge). Reused by 08x_methods_critical.jsx (single-paper) and 08y_critical_set.jsx (set) -- never WIP,
// which has no Tier-2 and sends nothing to any provider by design.

function CritiqueRunToggles({ wantLlm, setWantLlm, wantTriage, setWantTriage, aiReady, suggestLabel }) {
  if (!aiReady) return null;
  return (
    <React.Fragment>
      <label className="settings-check">
        <input type="checkbox" checked={wantLlm} onChange={e => setWantLlm(e.target.checked)} /> {suggestLabel}
      </label>
      <label className="settings-check">
        <input type="checkbox" checked={wantTriage} onChange={e => setWantTriage(e.target.checked)} /> AI triage (flag likely-noise items)
      </label>
    </React.Fragment>
  );
}

const CRITIQUE_TRIAGE_LABELS = { prioritize: "Prioritize", uncertain: "Uncertain", likely_noise: "Likely noise" };

function TriageBadge({ triage }) {
  if (!triage) return null;
  return (
    <div className={"cr-triage triage-" + triage.label + (triage.status === "stale" ? " stale" : "")}>
      <b>AI triage · {CRITIQUE_TRIAGE_LABELS[triage.label] || triage.label}</b>
      {triage.rationale && <div>{triage.rationale}</div>}
      {!!(triage.concerns || []).length &&
        <div className="settings-sub">Review caveat: {triage.concerns.join(" · ")}</div>}
      <small>Display aid only — not a revised fact or a judgment about the paper or authors.</small>
    </div>
  );
}

function TriageFilterControls({ hasTriage, triageOnly, onView, hiddenCount }) {
  if (!hasTriage) return null;
  return (
    <div className="cr-triage-view">
      <div className="tags-srcfilter" role="group" aria-label="Critique row view">
        <button className={"tags-srcfilter-btn" + (!triageOnly ? " on" : "")} onClick={() => onView(false)}>All rows</button>
        <button className={"tags-srcfilter-btn" + (triageOnly ? " on" : "")} onClick={() => onView(true)}>AI-focused</button>
      </div>
      <span className="settings-sub">
        {triageOnly
          ? `${hiddenCount} lower-yield row${hiddenCount === 1 ? "" : "s"} hidden from this display.`
          : "Everything these checks surfaced is visible."}
      </span>
    </div>
  );
}

function critiqueTriageVisible(item, triageOnly) {
  return !triageOnly || !item.llm_triage || item.llm_triage.show_in_triage;
}
