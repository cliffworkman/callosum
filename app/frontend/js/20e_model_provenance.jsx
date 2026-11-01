// Inc 609: which models produced a synthesis, read only from what that run recorded (model_provenance in the
// summary response) -- never from the current Settings, so switching profiles never relabels an older result.
// A row saved before provenance was recorded says so plainly instead of guessing MiniLM. A failed verification
// never reaches this line: the job fails and nothing is saved.
function ModelProvenanceLine({ provenance }) {
  if (!provenance) return null; // an imported synthesis: the sender's run is not described here
  if (!provenance.recorded) {
    return (
      <div className="synth-coverage" title="Saved before Callosum recorded which models produced each synthesis.">
        Models: not recorded for this synthesis
      </div>
    );
  }
  const r = provenance.retrieval;
  const v = provenance.verification;
  const name = (p) => (p ? p.label || p.model_name || "unknown" : "not recorded");
  const detail = [
    r && `Retrieval: ${r.model_name || "unknown"}${r.model_version ? ` (${r.model_version})` : ""}`,
    r && r.note,
    v && `Verification: ${v.model_name || "unknown"}${v.revision ? `@${v.revision}` : ""}`,
    v && v.thresholds_calibrated_on && `Verification thresholds calibrated on ${v.thresholds_calibrated_on}`,
  ].filter(Boolean).join("\n");
  return (
    <div className="synth-coverage" title={detail}>
      Retrieval: <b>{name(r)}</b>{r && r.experimental ? " (experimental)" : ""}
      {" · "}Verification: <b>{name(v)}</b>
      {v && v.experimental ? " (experimental; thresholds calibrated on MiniLM2)" : ""}
      {r && r.fallback_reason && r.note ? <>{" · "}{r.note}</> : null}
    </div>
  );
}
