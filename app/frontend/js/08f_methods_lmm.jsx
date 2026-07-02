// inc 247 (#23): LMM-reporting completeness auditor — read a mixed-model paper's extracted text and flag whether it
// *reports* what a careful reader needs (random-effects structure, df method, convergence, estimation, ICC, R²,
// missing-data sensitivity). FLAG-not-ADJUDICATE: each check present / not-found / n/a — never a verdict, never a
// score, never runs a model. Local, no AI, no egress. Audits reporting completeness, not analysis correctness.
// The deterministic sibling of statcheck / the Bayesian checklist. See methods/lmm.py.

// inc 247 (credit-the-lineage): the methodological sources, one-click added to the library (statcheck/bayes pattern).
// DOIs are included only where confidently known — a missing DOI over a wrong one (import dedups on title+year+author).
const LMM_CSL = [
  {
    type: "article-journal",
    title: "Random effects structure for confirmatory hypothesis testing: Keep it maximal",
    author: [
      { family: "Barr", given: "Dale J." },
      { family: "Levy", given: "Roger" },
      { family: "Scheepers", given: "Christoph" },
      { family: "Tily", given: "Harry J." },
    ],
    "container-title": "Journal of Memory and Language",
    volume: "68", issue: "3", page: "255-278",
    issued: { "date-parts": [[2013]] },
    DOI: "10.1016/j.jml.2012.11.001",
  },
  {
    type: "article-journal",
    title: "Balancing Type I error and power in linear mixed models",
    author: [
      { family: "Matuschek", given: "Hannes" },
      { family: "Kliegl", given: "Reinhold" },
      { family: "Vasishth", given: "Shravan" },
      { family: "Baayen", given: "Harald" },
      { family: "Bates", given: "Douglas" },
    ],
    "container-title": "Journal of Memory and Language",
    volume: "94", page: "305-315",
    issued: { "date-parts": [[2017]] },
    DOI: "10.1016/j.jml.2017.01.001",
  },
  {
    type: "article-journal",
    title: "Evaluating significance in linear mixed-effects models in R",
    author: [{ family: "Luke", given: "Steven G." }],
    "container-title": "Behavior Research Methods",
    volume: "49", issue: "4", page: "1494-1502",
    issued: { "date-parts": [[2017]] },
    DOI: "10.3758/s13428-016-0809-y",
  },
  {
    type: "article-journal",
    title: "Fitting Linear Mixed-Effects Models Using lme4",
    author: [
      { family: "Bates", given: "Douglas" },
      { family: "Mächler", given: "Martin" },
      { family: "Bolker", given: "Ben" },
      { family: "Walker", given: "Steve" },
    ],
    "container-title": "Journal of Statistical Software",
    volume: "67", issue: "1", page: "1-48",
    issued: { "date-parts": [[2015]] },
    DOI: "10.18637/jss.v067.i01",
  },
  {
    type: "article-journal",
    title: "A general and simple method for obtaining R² from generalized linear mixed-effects models",
    author: [
      { family: "Nakagawa", given: "Shinichi" },
      { family: "Schielzeth", given: "Holger" },
    ],
    "container-title": "Methods in Ecology and Evolution",
    volume: "4", issue: "2", page: "133-142",
    issued: { "date-parts": [[2013]] },
    DOI: "10.1111/j.2041-210x.2012.00261.x",
  },
  {
    type: "report",
    title: "ICH E9(R1): Addendum on estimands and sensitivity analysis in clinical trials",
    author: [{ literal: "International Council for Harmonisation (ICH)" }],
    issued: { "date-parts": [[2019]] },
  },
  {
    type: "article-journal",
    title: "Sensitivity analysis for clinical trials with missing continuous outcome data using controlled multiple imputation: A practical guide",
    author: [
      { family: "Cro", given: "Suzie" },
      { family: "Morris", given: "Tim P." },
      { family: "Kenward", given: "Michael G." },
      { family: "Carpenter", given: "James R." },
    ],
    "container-title": "Statistics in Medicine",
    issued: { "date-parts": [[2020]] },
  },
  {
    type: "article-journal",
    title: "Sensitivity analysis of incomplete longitudinal data departing from the missing at random assumption",
    author: [
      { family: "Moreno-Betancur", given: "Margarita" },
      { family: "Chavance", given: "Michel" },
    ],
    "container-title": "Statistical Methods in Medical Research",
    issued: { "date-parts": [[2016]] },
  },
  {
    type: "article-journal",
    title: "Sensitivity analysis for missing data in longitudinal mixed-effects models",
    author: [{ family: "Troendle", given: "James F." }],
    issued: { "date-parts": [[2025]] },
  },
];

// Per-paper audit. The section gets only the paper id via ctx, so it self-fetches title + chunk_count (the auditor
// needs extracted text). Auto-runs when its section is the open one (like statcheck / the Bayesian auditor).
function LmmPaper({ paperId, onOpenPaper, active }) {
  const [meta, setMeta] = useState(null); // { title, hasText } | null
  const [state, setState] = useState({ status: "idle" }); // idle | running | done | error
  useEffect(() => {
    setState({ status: "idle" }); setMeta(null);
    if (paperId == null) return;
    let live = true;
    api(`/papers/${paperId}`).then(r => {
      if (!live || !r.ok) return;
      setMeta({ title: r.data.title, hasText: (r.data.chunk_count || 0) > 0 });
    });
    return () => { live = false; };
  }, [paperId]);
  const run = async () => {
    setState({ status: "running" });
    const r = await api(`/papers/${paperId}/lmm`);
    setState(r.ok ? { status: "done", data: r.data } : { status: "error", error: r.error });
  };
  useEffect(() => {
    if (active && meta && meta.hasText && state.status === "idle") run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, meta]);
  const open = (page) => { if (onOpenPaper && page != null) onOpenPaper({ id: paperId, title: meta ? meta.title : "" }, { page, precision: "region" }); };
  if (paperId == null) return <div className="tag-suggest-empty">Select a paper to audit its mixed-model reporting.</div>;
  const hasText = meta ? meta.hasText : false;
  const d = state.data;
  return (
    <div className="detail-statcheck">
      <span className="detail-cite-label">{meta ? meta.title : "This paper"}</span>
      {!meta
        ? <span className="tag-suggest-empty">loading…</span>
        : !hasText
          ? <span className="tag-suggest-empty">Process a PDF first — the auditor reads the paper's extracted text.</span>
          : state.status === "idle"
            ? <button className="btn-link" title="Audit this paper's mixed-model reporting — local, no AI" onClick={run}>Audit reporting</button>
            : null}
      {state.status === "running" && <span className="tag-suggest-empty">auditing…</span>}
      {state.status === "error" && <div className="axis-err">Couldn't audit: {state.error}</div>}
      {state.status === "done" && d && (!d.is_lmm
        ? <div className="tag-suggest-empty">This paper doesn't appear to use a linear mixed model — nothing to audit.</div>
        : <LmmChecklist checks={d.checks} onOpen={open} />)}
    </div>
  );
}

function LmmChecklist({ checks, onOpen }) {
  if (!checks || !checks.length) return null;
  return (
    <div className="bayes-checklist">
      <p className="eyebrow">Reporting checklist</p>
      {checks.map((c) => (
        <div key={c.key} className="bayes-check-item">
          <div className="bayes-check-head">
            <span className="bayes-check-label">{c.label}</span>
            {c.status === "present"
              ? <span className="cite-status verified">✓ present</span>
              : <span className="bayes-check-muted">{c.status === "not-applicable" ? "n/a" : "not found"}</span>}
          </div>
          {c.note && <div className="bayes-check-note">{c.note}</div>}
          {c.explainer && <div className="lmm-explainer">{c.explainer}</div>}
          {c.basis && <div className="lmm-basis">basis: {c.basis}</div>}
          {c.evidence &&
            <button className="bayes-check-ev" title={c.page != null ? "Open page " + c.page : ""} onClick={() => c.page != null && onOpen(c.page)}>
              “{c.evidence}”
            </button>}
        </div>
      ))}
      <div className="statcheck-caveat">
        Audits reporting <b>completeness</b>, not analysis <b>correctness</b> — a paper can report everything and still model badly, or omit an item and be fine. This flags what a careful reader should check, not what's wrong. It reads the extracted text, so <b>“not found” means not detected there</b> — check the paper (tables aren't fully read). ICC + missing-data show only when their precondition holds. Never a verdict, never a score, never an accusation.
      </div>
    </div>
  );
}

function LmmCredit() {
  const [added, setAdded] = useState("idle");
  const addCredit = async () => {
    setAdded("adding");
    const r = await apiPost("/library/import", { content: JSON.stringify(LMM_CSL), format: "csl-json" });
    setAdded(r && r.ok ? "added" : "idle");
  };
  return (
    <div className="method-credit">
      <b>Methods:</b> random-effects structure — Barr et al. (2013), Matuschek et al. (2017); df/inference — Luke (2017); convergence &amp; estimation — Bates et al. (2015, <i>lme4</i>); R² — Nakagawa &amp; Schielzeth (2013); missing-data sensitivity — FDA ICH E9(R1), Troendle et al. (2025), Cro et al. (2020), Moreno-Betancur &amp; Chavance (2016).{" "}
      <button className="btn-link" disabled={added !== "idle"} onClick={addCredit}>
        {added === "added" ? "✓ added to library" : added === "adding" ? "adding…" : "＋ add methods sources to library"}
      </button>
      <div className="method-credit-sub">A reading aid — it never runs a model, imputation, or sensitivity analysis. Surfaced via D. Lakens' automated-review catalog.</div>
    </div>
  );
}

function LmmSection({ ctx }) {
  return (
    <div className="statcheck-section">
      <div className="settings-sub">Audit a paper's <b>mixed-model reporting</b> — does it report the random-effects structure, df/inference method, convergence, estimation (REML/ML), ICC, R², and (for longitudinal designs with dropout) a missing-data sensitivity analysis? Local, no AI. It flags what's not reported, with a grounded recommendation — never a verdict.</div>
      <p className="eyebrow">This paper</p>
      <LmmPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper} active={ctx.methodsOpen === "lmm"} />
      <LmmCredit />
    </div>
  );
}

registerPaneSection({
  id: "lmm", label: "Mixed-model reporting", paneId: "methods", order: 33, hideInReadOnly: true,
  render: (ctx) => <LmmSection ctx={ctx} />,
});
