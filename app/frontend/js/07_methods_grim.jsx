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

// inc 401: paper-aware now (ctx wasn't threaded in before) — a "Save this check" action persists the entered
// inputs + the server-recomputed verdict to a small per-paper log, recalled whenever this section is open for
// that paper. The live "Check" result stays scratch/ephemeral unless explicitly saved, so trying values doesn't
// clutter the saved list.
function GrimSection({ ctx }) {
  const paperId = ctx.selectedPaper;
  const [f, setF] = useState({ mean: "", sd: "", n: "", items: "1" });
  const [state, setState] = useState({ status: "idle" }); // idle | running | done | error
  const [saved, setSaved] = useState({ status: "idle", checks: [] });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  // Reset the scratch form + live result on every paper switch -- otherwise a stale entered value (and its
  // "Save this check" button) keeps showing against whichever paper is now selected, risking a save attributed
  // to the wrong paper.
  useEffect(() => {
    setF({ mean: "", sd: "", n: "", items: "1" });
    setState({ status: "idle" });
  }, [paperId]);

  useEffect(() => {
    setSaved({ status: "idle", checks: [] });
    if (paperId == null) return undefined;
    let live = true;
    api(`/papers/${paperId}/grim-checks`).then(r => {
      if (live && r.ok) setSaved({ status: "done", checks: r.data.checks });
    });
    return () => { live = false; };
  }, [paperId]);

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
  const save = async () => {
    if (paperId == null) return;
    const n = parseInt(f.n, 10);
    const items = parseInt(f.items || "1", 10);
    const body = { mean: f.mean.trim(), n, items: Number.isFinite(items) ? items : 1 };
    if (f.sd.trim()) body.sd = f.sd.trim();
    const r = await apiPost(`/papers/${paperId}/grim-checks`, body);
    if (r.ok) setSaved(s => ({ status: "done", checks: [r.data, ...s.checks] }));
  };
  const removeSaved = async (checkId) => {
    const r = await apiDelete(`/papers/${paperId}/grim-checks/${checkId}`);
    if (r.ok) setSaved(s => ({ ...s, checks: s.checks.filter(c => c.id !== checkId) }));
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
          {paperId != null && <button className="btn-link" onClick={save}>Save this check</button>}
        </div>}
      {paperId != null && saved.checks.length > 0 &&
        <div className="grim-saved-list">
          <p className="eyebrow">Saved checks — this paper</p>
          {saved.checks.map(c =>
            <div className="grim-saved-item" key={c.id}>
              <span className="grim-saved-desc">{c.label || `mean ${c.mean}${c.sd ? ` / SD ${c.sd}` : ""} / N ${c.n}`}</span>
              <span className={"cite-status " + (c.grim.consistent ? "verified" : "flagged")}>{c.grim.consistent ? "consistent" : "impossible"}</span>
              <small className="grim-saved-date">{c.created_at ? c.created_at.slice(0, 10) : ""}</small>
              <button className="btn-icon" title="Remove this saved check" aria-label="Remove this saved check"
                onClick={() => removeSaved(c.id)}>×</button>
            </div>)}
        </div>}
      <div className="method-credit">
        <b>Method:</b> GRIM — Brown &amp; Heathers (2017); GRIMMER — Anaya (2016) / Allard (2018).{" "}
        <MethodCreditButton items={[GRIM_CSL]} />
        <div className="method-credit-sub">Re-implemented in Python; cf. the <i>scrutiny</i> package (Lukas Jung).</div>
      </div>
    </div>
  );
}

// inc 467: DEBIT — the binary-data analog of GRIM/GRIMMER (Heathers & Brown 2019, an unpublished OSF working
// paper — no DOI exists to fabricate). Same "check a value you're reading" shape as GrimSection, including the
// inc-401 paperId-reset fix applied from the start here rather than rediscovering the same bug.
const DEBIT_CSL = {
  type: "report",
  title: "DEBIT: A Simple Consistency Test For Binary Data",
  author: [
    { family: "Heathers", given: "James A. J." },
    { family: "Brown", given: "Nicholas J. L." },
  ],
  URL: "https://osf.io/pm825/",
  issued: { "date-parts": [[2019]] },
};

function DebitSection({ ctx }) {
  const paperId = ctx.selectedPaper;
  const [f, setF] = useState({ mean: "", sd: "", n: "" });
  const [state, setState] = useState({ status: "idle" }); // idle | running | done | error
  const [saved, setSaved] = useState({ status: "idle", checks: [] });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    setF({ mean: "", sd: "", n: "" });
    setState({ status: "idle" });
  }, [paperId]);

  useEffect(() => {
    setSaved({ status: "idle", checks: [] });
    if (paperId == null) return undefined;
    let live = true;
    api(`/papers/${paperId}/debit-checks`).then(r => {
      if (live && r.ok) setSaved({ status: "done", checks: r.data.checks });
    });
    return () => { live = false; };
  }, [paperId]);

  const run = async () => {
    const n = parseInt(f.n, 10);
    if (!f.mean.trim() || !f.sd.trim() || !Number.isFinite(n)) return;
    setState({ status: "running" });
    const r = await apiPost("/methods/debit", { mean: f.mean.trim(), sd: f.sd.trim(), n });
    setState(r.ok ? { status: "done", data: r.data } : { status: "error", error: r.error });
  };
  const save = async () => {
    if (paperId == null) return;
    const n = parseInt(f.n, 10);
    const r = await apiPost(`/papers/${paperId}/debit-checks`, { mean: f.mean.trim(), sd: f.sd.trim(), n });
    if (r.ok) setSaved(s => ({ status: "done", checks: [r.data, ...s.checks] }));
  };
  const removeSaved = async (checkId) => {
    const r = await apiDelete(`/papers/${paperId}/debit-checks/${checkId}`);
    if (r.ok) setSaved(s => ({ ...s, checks: s.checks.filter(c => c.id !== checkId) }));
  };
  const d = state.data;
  return (
    <div className="grim-section">
      <div className="settings-sub">Check whether a reported mean and SD of <b>binary (0/1)</b> data — a proportion or response rate — is mathematically possible for the sample size. For binary data the SD is fully determined by the mean and N. Enter a value you're reading; local, no AI.</div>
      <div className="grim-form">
        <label>Mean <input className="grim-in" value={f.mean} onChange={set("mean")} placeholder="0.500" spellCheck={false} /></label>
        <label>SD <input className="grim-in" value={f.sd} onChange={set("sd")} placeholder="0.527" spellCheck={false} /></label>
        <label>N <input className="grim-in" value={f.n} onChange={set("n")} placeholder="50" spellCheck={false} /></label>
        <button className="btn btn-primary" disabled={state.status === "running" || !f.mean.trim() || !f.sd.trim() || !f.n.trim()} onClick={run}>Check</button>
      </div>
      {state.status === "running" && <ProgressBar />}
      {state.status === "error" && <div className="axis-err">Couldn't check: {state.error}</div>}
      {state.status === "done" && d &&
        <div className="grim-result">
          <div className="grim-line">
            <span className="grim-k">DEBIT</span>
            <span className={"cite-status " + (d.debit.consistent ? "verified" : "flagged")}>{d.debit.consistent ? "consistent" : "impossible"}</span>
          </div>
          <div className="grim-caveat">{d.debit.note}</div>
          {paperId != null && <button className="btn-link" onClick={save}>Save this check</button>}
        </div>}
      {paperId != null && saved.checks.length > 0 &&
        <div className="grim-saved-list">
          <p className="eyebrow">Saved checks — this paper</p>
          {saved.checks.map(c =>
            <div className="grim-saved-item" key={c.id}>
              <span className="grim-saved-desc">{c.label || `mean ${c.mean} / SD ${c.sd} / N ${c.n}`}</span>
              <span className={"cite-status " + (c.debit.consistent ? "verified" : "flagged")}>{c.debit.consistent ? "consistent" : "impossible"}</span>
              <small className="grim-saved-date">{c.created_at ? c.created_at.slice(0, 10) : ""}</small>
              <button className="btn-icon" title="Remove this saved check" aria-label="Remove this saved check"
                onClick={() => removeSaved(c.id)}>×</button>
            </div>)}
        </div>}
      <div className="method-credit">
        <b>Method:</b> DEBIT — Heathers &amp; Brown (2019).{" "}
        <MethodCreditButton items={[DEBIT_CSL]} />
        <div className="method-credit-sub">Re-implemented in Python; cf. the <i>scrutiny</i> package (Lukas Jung). An unpublished OSF working paper — no DOI exists.</div>
      </div>
    </div>
  );
}

// inc 469: a blunt data-fabrication smell (scrutiny's duplicate_count/duplicate_tally, Lukas Jung) — how often
// does each exact reported value repeat within one paper's own table? Unlike GRIM/GRIMMER/DEBIT, no
// peer-reviewed method backs this, so it deliberately renders NO consistent/flagged pill or verdict — just a
// plain, neutral frequency list. Same paperId-reset + save/list/delete shape as GrimSection/DebitSection.
function DuplicateValuesSection({ ctx }) {
  const paperId = ctx.selectedPaper;
  const [text, setText] = useState("");
  const [state, setState] = useState({ status: "idle" }); // idle | running | done | error
  const [saved, setSaved] = useState({ status: "idle", checks: [] });

  useEffect(() => {
    setText("");
    setState({ status: "idle" });
  }, [paperId]);

  useEffect(() => {
    setSaved({ status: "idle", checks: [] });
    if (paperId == null) return undefined;
    let live = true;
    api(`/papers/${paperId}/duplicate-value-checks`).then(r => {
      if (live && r.ok) setSaved({ status: "done", checks: r.data.checks });
    });
    return () => { live = false; };
  }, [paperId]);

  const valuesFromText = () => text.split(/[\n,]/).map(v => v.trim()).filter(Boolean);

  const run = async () => {
    const values = valuesFromText();
    if (values.length === 0) return;
    setState({ status: "running" });
    const r = await apiPost("/methods/duplicate-values", { values });
    setState(r.ok ? { status: "done", data: r.data } : { status: "error", error: r.error });
  };
  const save = async () => {
    if (paperId == null) return;
    const values = valuesFromText();
    const r = await apiPost(`/papers/${paperId}/duplicate-value-checks`, { values });
    if (r.ok) setSaved(s => ({ status: "done", checks: [r.data, ...s.checks] }));
  };
  const removeSaved = async (checkId) => {
    const r = await apiDelete(`/papers/${paperId}/duplicate-value-checks/${checkId}`);
    if (r.ok) setSaved(s => ({ ...s, checks: s.checks.filter(c => c.id !== checkId) }));
  };
  const d = state.data;
  return (
    <div className="grim-section">
      <div className="settings-sub">How often does each exact value repeat in a table of numbers you're reading — a possible data-fabrication smell, but a <b>blunt heuristic with no peer-reviewed method</b> behind it (unlike GRIM/GRIMMER/DEBIT above). Paste values, one per line or comma-separated; local, no AI.</div>
      <div className="grim-form">
        <textarea className="grim-in duplicate-values-in" rows={3} value={text} onChange={e => setText(e.target.value)}
          placeholder={"3.45\n3.45\n2.10"} spellCheck={false} />
        <button className="btn btn-primary" disabled={state.status === "running" || valuesFromText().length === 0} onClick={run}>Check</button>
      </div>
      {state.status === "running" && <ProgressBar />}
      {state.status === "error" && <div className="axis-err">Couldn't check: {state.error}</div>}
      {state.status === "done" && d &&
        <div className="grim-result">
          {d.duplicate_values.repeats.length > 0
            ? <ul className="duplicate-values-list">
                {d.duplicate_values.repeats.map(r => <li key={r.value}>{r.value} × {r.count}</li>)}
              </ul>
            : <div className="grim-caveat">No exact value repeats more than once.</div>}
          <div className="grim-caveat">{d.duplicate_values.note}</div>
          {paperId != null && <button className="btn-link" onClick={save}>Save this check</button>}
        </div>}
      {paperId != null && saved.checks.length > 0 &&
        <div className="grim-saved-list">
          <p className="eyebrow">Saved checks — this paper</p>
          {saved.checks.map(c =>
            <div className="grim-saved-item" key={c.id}>
              <span className="grim-saved-desc">{c.label || `${c.values.length} values, ${c.duplicate_values.repeats.length} repeat${c.duplicate_values.repeats.length === 1 ? "" : "s"}`}</span>
              <small className="grim-saved-date">{c.created_at ? c.created_at.slice(0, 10) : ""}</small>
              <button className="btn-icon" title="Remove this saved check" aria-label="Remove this saved check"
                onClick={() => removeSaved(c.id)}>×</button>
            </div>)}
        </div>}
      <div className="method-credit">
        <b>Method:</b> a repeated-value counter — cf. <i>scrutiny</i>'s <code>duplicate_count</code>/<code>duplicate_tally</code> (Lukas Jung).
        <div className="method-credit-sub">No canonical paper exists — a software-only reference implementation, not a citable method like GRIM/GRIMMER/DEBIT above.</div>
        <LakensCredit />
      </div>
    </div>
  );
}

registerPaneSection({ id: "grim", label: "Data", paneId: "methods", order: 20, hideInReadOnly: true, render: (ctx) => <><GrimSection ctx={ctx} /><DebitSection ctx={ctx} /><DuplicateValuesSection ctx={ctx} /></> });
