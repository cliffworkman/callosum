// inc 127: GRIM + GRIMMER — an assisted, per-value data-consistency calculator (Brown & Heathers 2017; Anaya
// 2016 / Allard 2018). The user enters a reported mean (+ SD), N, and items; it reports whether they're possible
// for integer data. User-driven → inherently non-accusatory: a prompt to look, never a verdict. No paper scan.

// Bundled CSL-JSON for the source paper, added to the library via the inc-93 import path (credit-the-lineage).
const GRIM_CSL = {
  type: "article-journal",
  title: "The GRIM test: A simple technique detects numerous anomalies in the reporting of results in psychology",
  author: [
    { family: "Brown", given: "Nicholas J. L." },
    { family: "Heathers", given: "James A. J." },
  ],
  "container-title": "Social Psychological and Personality Science",
  volume: "8",
  issue: "4",
  page: "363-369",
  issued: { "date-parts": [[2017]] },
  DOI: "10.1177/1948550616673876",
};

function GrimSection() {
  const [f, setF] = useState({ mean: "", sd: "", n: "", items: "1" });
  const [state, setState] = useState({ status: "idle" }); // idle | running | done | error
  const [added, setAdded] = useState("idle");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const run = async () => {
    const n = parseInt(f.n, 10);
    const items = parseInt(f.items || "1", 10);
    if (!f.mean.trim() || !Number.isFinite(n)) return;
    setState({ status: "running" });
    const body = { mean: f.mean.trim(), n, items: Number.isFinite(items) ? items : 1 };
    if (f.sd.trim()) body.sd = f.sd.trim();
    const r = await apiPost("/methods/grim", body);
    setState(r.ok ? { status: "done", data: r.data } : { status: "error", error: r.error });
  };
  const addCredit = async () => {
    setAdded("adding");
    const r = await apiPost("/library/import", { content: JSON.stringify([GRIM_CSL]), format: "csl-json" });
    setAdded(r && r.ok ? "added" : "idle");
  };
  const d = state.data;
  return (
    <div className="grim-section">
      <div className="settings-sub">Check whether a reported mean (and SD) of <b>integer-scale</b> data — counts or Likert-type items — is mathematically possible for the sample size. Enter a value you're reading; local, no AI.</div>
      <div className="grim-form">
        <label>Mean <input className="grim-in" value={f.mean} onChange={set("mean")} placeholder="3.45" spellCheck={false} /></label>
        <label>SD <input className="grim-in" value={f.sd} onChange={set("sd")} placeholder="(optional)" spellCheck={false} /></label>
        <label>N <input className="grim-in" value={f.n} onChange={set("n")} placeholder="50" spellCheck={false} /></label>
        <label>items <input className="grim-in" value={f.items} onChange={set("items")} title="scale items averaged per score; 1 for a single integer measure" /></label>
        <button className="btn btn-primary" disabled={state.status === "running" || !f.mean.trim() || !f.n.trim()} onClick={run}>Check</button>
      </div>
      {state.status === "running" && <ProgressBar />}
      {state.status === "error" && <div className="axis-err">Couldn't check: {state.error}</div>}
      {state.status === "done" && d &&
        <div className="grim-result">
          <div className="grim-line">
            <span className="grim-k">GRIM</span>
            <span className={"cite-status " + (d.grim.consistent ? "verified" : "flagged")}>{d.grim.consistent ? "consistent" : "impossible"}</span>
            {!d.grim.consistent && <span className="grim-near">nearest possible: {d.grim.nearest.join(" / ")}</span>}
          </div>
          {d.grim.no_power && <div className="grim-caveat">N is large for this precision — GRIM has little power here (most means are achievable).</div>}
          {d.grimmer &&
            <div className="grim-line">
              <span className="grim-k">GRIMMER</span>
              <span className={"cite-status " + (d.grimmer.consistent ? "verified" : "flagged")}>{d.grimmer.consistent ? "consistent" : "impossible"}</span>
            </div>}
          <div className="grim-caveat">GRIM/GRIMMER assume integer-scale data — they don't apply to continuous measures. An inconsistency is a prompt to look, not a verdict or an accusation.</div>
        </div>}
      <div className="grim-credit">
        <b>Method:</b> GRIM — Brown &amp; Heathers (2017); GRIMMER — Anaya (2016) / Allard (2018).{" "}
        <button className="btn-link" disabled={added !== "idle"} onClick={addCredit}>
          {added === "added" ? "✓ added to library" : added === "adding" ? "adding…" : "＋ add to library"}
        </button>
        <div className="grim-credit-sub">Re-implemented in Python; cf. the <i>scrutiny</i> package (Lukas Jung). Surfaced via D. Lakens' automated-review catalog.</div>
      </div>
    </div>
  );
}

registerPaneSection({ id: "grim", label: "Data consistency (GRIM)", paneId: "methods", order: 20, render: () => <GrimSection /> });
