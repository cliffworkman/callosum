// inc 252 (meta-analysis workbench SP1): the deterministic effect-size converter — an assisted, per-value calculator.
// Hand-enter ONE study's reported stats → a common metric (Hedges' g, Fisher's z, log OR/RR, risk difference) + its
// variance + a 95% CI, via cited formulas, with the conversion path shown and every derivation choice recorded.
// It converts one study at a time; it NEVER pools / models / does bias inference — that's metafor/JASP/RevMan. Local,
// no AI, no egress. (Reading a paper's stats is deliberately the LLM/SP2 job.)

// Bundled CSL-JSON for the primary conversion reference, added via the inc-93 import path (credit-the-lineage).
const EFFECTSIZE_CSL = {
  type: "book",
  title: "Introduction to Meta-Analysis",
  author: [
    { family: "Borenstein", given: "Michael" },
    { family: "Hedges", given: "Larry V." },
    { family: "Higgins", given: "Julian P. T." },
    { family: "Rothstein", given: "Hannah R." },
  ],
  publisher: "Wiley",
  issued: { "date-parts": [[2009]] },
  ISBN: "978-0-470-05724-7",
};

// Per-family field labels (for the compact form).
const ES_FIELD = {
  m1: "Mean 1", s1: "SD 1", n1: "n1", m2: "Mean 2", s2: "SD 2", n2: "n2",
  t: "t", f: "F", r: "r", n: "n", a: "a", b: "b", c: "c", d: "d",
  se: "SE", lo: "CI lower", hi: "CI upper", iqr: "IQR", logor: "log OR", var_logor: "Var(log OR)",
};

// The families + their input shapes. `sub` = a second selector that swaps the fields (alternate-input paths).
const ES_FORMS = [
  { family: "smd", label: "SMD → Hedges' g", sub: { key: "method", label: "from", opts: [
    { val: "means", label: "group means + SDs", fields: ["m1", "s1", "n1", "m2", "s2", "n2"] },
    { val: "t", label: "t + group Ns", fields: ["t", "n1", "n2"] },
    { val: "f", label: "one-way F (2 groups)", fields: ["f", "n1", "n2"] },
  ] } },
  { family: "sd_derivation", label: "SD derivation", sub: { key: "method", label: "from", opts: [
    { val: "se", label: "SE + n", fields: ["se", "n"] },
    { val: "ci", label: "95% CI + n", fields: ["lo", "hi", "n"] },
    { val: "iqr", label: "IQR", fields: ["iqr"] },
  ] } },
  { family: "correlation", label: "Correlation → Fisher's z", fields: ["r", "n"] },
  { family: "binary", label: "Binary 2×2", fields: ["a", "b", "c", "d"], choice: { key: "measure", label: "measure", opts: [
    { val: "or", label: "odds ratio" }, { val: "rr", label: "risk ratio" }, { val: "rd", label: "risk difference" },
  ] } },
  { family: "cross", label: "Cross-metric (approx.)", sub: { key: "kind", label: "convert", opts: [
    { val: "d_to_r", label: "d → r", fields: ["d", "n1", "n2"] },
    { val: "r_to_d", label: "r → d", fields: ["r"] },
    { val: "logor_to_d", label: "log OR → d", fields: ["logor", "var_logor"] },
  ] } },
];

function EffectSizeSection() {
  const [family, setFamily] = useState("smd");
  const [subVal, setSubVal] = useState("means"); // the sub-selector value (method/kind), per family
  const [choiceVal, setChoiceVal] = useState("or"); // the fixed choice (measure), for binary
  const [inputs, setInputs] = useState({});
  const [state, setState] = useState({ status: "idle" }); // idle | running | done | error
  const [added, setAdded] = useState("idle");
  const [copied, setCopied] = useState(false);

  const form = ES_FORMS.find((f) => f.family === family);
  const sub = form.sub ? form.sub.opts.find((o) => o.val === subVal) || form.sub.opts[0] : null;
  const fields = sub ? sub.fields : form.fields;

  const pickFamily = (fam) => {
    const f = ES_FORMS.find((x) => x.family === fam);
    setFamily(fam);
    setSubVal(f.sub ? f.sub.opts[0].val : "");
    setChoiceVal(f.choice ? f.choice.opts[0].val : "");
    setInputs({});
    setState({ status: "idle" });
    setCopied(false);
  };
  const setIn = (k) => (e) => setInputs({ ...inputs, [k]: e.target.value });

  const run = async () => {
    // Build the family-specific inputs; blank optional fields (var_logor) are dropped.
    const body = { family, inputs: {} };
    for (const k of fields) {
      const v = inputs[k];
      if (v === undefined || v === "" || v === null) {
        if (k === "var_logor") continue; // optional
        return; // required field missing
      }
      body.inputs[k] = Number(v);
    }
    if (form.sub) body.inputs[form.sub.key] = subVal;
    if (form.choice) body.inputs[form.choice.key] = choiceVal;
    setState({ status: "running" });
    const r = await apiPost("/methods/effect-size", body);
    setState(r.ok ? { status: "done", data: r.data } : { status: "error", error: r.error });
  };

  const addCredit = async () => {
    setAdded("adding");
    const r = await apiPost("/library/import", { content: JSON.stringify([EFFECTSIZE_CSL]), format: "csl-json" });
    setAdded(r && r.ok ? "added" : "idle");
  };

  const d = state.data;
  return (
    <div className="grim-section">
      <div className="settings-sub">Convert <b>one study's</b> reported statistics into a common meta-analytic metric + its variance, by standard cited formulas — the path is shown and every derivation choice is recorded. Local, no AI. It converts one study at a time; it <b>never pools or models</b> — hand the dataset off to metafor / JASP / RevMan for the synthesis.</div>

      <div className="es-form">
        <label>Family
          <select className="es-in es-sel" value={family} onChange={(e) => pickFamily(e.target.value)}>
            {ES_FORMS.map((f) => <option key={f.family} value={f.family}>{f.label}</option>)}
          </select>
        </label>
        {form.sub &&
          <label>{form.sub.label}
            <select className="es-in es-sel" value={subVal} onChange={(e) => { setSubVal(e.target.value); setState({ status: "idle" }); }}>
              {form.sub.opts.map((o) => <option key={o.val} value={o.val}>{o.label}</option>)}
            </select>
          </label>}
        {form.choice &&
          <label>{form.choice.label}
            <select className="es-in es-sel" value={choiceVal} onChange={(e) => setChoiceVal(e.target.value)}>
              {form.choice.opts.map((o) => <option key={o.val} value={o.val}>{o.label}</option>)}
            </select>
          </label>}
      </div>
      <div className="es-form">
        {fields.map((k) => (
          <label key={k}>{ES_FIELD[k]}{k === "var_logor" ? " (opt.)" : ""}
            <input className="es-in" value={inputs[k] || ""} onChange={setIn(k)} spellCheck={false} inputMode="decimal" />
          </label>
        ))}
        <button className="btn btn-primary" disabled={state.status === "running"} onClick={run}>Convert</button>
      </div>

      {state.status === "running" && <ProgressBar />}
      {state.status === "error" && <div className="axis-err">Couldn't convert: {state.error}</div>}
      {state.status === "done" && d &&
        <div className="es-result">
          <div className="es-value">{d.metric} = <b>{d.value}</b> <span className="es-var">(Var {d.variance}, SE {d.se})</span>
            <button className="btn-link es-copy" title="Copy value + variance (tab-separated) for a metafor/JASP row" onClick={() => {
              navigator.clipboard.writeText(`${d.value}\t${d.variance}`).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); });
            }}>{copied ? "✓ copied" : "copy value + variance"}</button>
          </div>
          <div className="es-ci">95% CI [{d.ci_low}, {d.ci_high}]</div>
          {d.path.length > 0 &&
            <ol className="es-path">{d.path.map((p, i) => <li key={i}>{p}</li>)}</ol>}
          {d.choices.map((ch, i) => <div key={i} className="es-choice">↳ {ch}</div>)}
          {d.caveats.map((cv, i) => <div key={i} className="statcheck-caveat">{cv}</div>)}
          <div className="es-src"><b>Formula:</b> {d.formula_source}</div>
        </div>}

      <div className="statcheck-caveat">This converts one study — it is not a meta-analysis. Pooling, heterogeneity (I²/τ²), meta-regression, and publication-bias inference belong to a synthesis tool (metafor / JASP / RevMan); Callosum hands off the dataset + this provenance.</div>
      <div className="method-credit">
        <b>Formulas:</b> Borenstein, Hedges, Higgins &amp; Rothstein (2009), <i>Introduction to Meta-Analysis</i>; Hedges (1981); Fisher (1915); Haldane (1940) / Anscombe (1956); Wan et al. (2014); Hasselblad &amp; Hedges (1995); cf. the <i>metafor</i> package (Viechtbauer 2010).{" "}
        <button className="btn-link" disabled={added !== "idle"} onClick={addCredit}>
          {added === "added" ? "✓ added to library" : added === "adding" ? "adding…" : "＋ add methods source to library"}
        </button>
      </div>
    </div>
  );
}

// inc 280 (stage 2): METHODS → the Extract workspace (a meta-analysis tool, alongside Workbench/Meta-analysis).
registerWorkspaceTab({ id: "extract" }, { id: "effectsize", label: "Effect-Size", order: 20, hideInReadOnly: true, render: () => <EffectSizeSection /> });
