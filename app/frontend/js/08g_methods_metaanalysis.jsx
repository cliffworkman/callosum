// inc 249 (#36): meta-analysis reporting auditor — read a published meta-analysis's extracted text and flag whether
// it *reports* what a careful reader needs (effect-size metric, model, heterogeneity, publication bias, sensitivity,
// study count, search & selection). FLAG-not-ADJUDICATE: each check present / not-found / n/a — never a verdict,
// never a score, never pools/models/re-computes. Local, no AI, no egress. Audits reporting completeness, not
// analysis correctness. The deterministic sibling of statcheck / the LMM auditor. See methods/metaanalysis.py.

// inc 249 (credit-the-lineage): the methodological sources, one-click added to the library (statcheck/lmm pattern).
// DOIs are included only where confidently known — a missing DOI over a wrong one (import dedups on title+year+author).
const META_CSL = [
  {
    type: "article-journal",
    title: "Measuring inconsistency in meta-analyses",
    author: [
      { family: "Higgins", given: "Julian P. T." },
      { family: "Thompson", given: "Simon G." },
      { family: "Deeks", given: "Jonathan J." },
      { family: "Altman", given: "Douglas G." },
    ],
    "container-title": "BMJ",
    volume: "327", issue: "7414", page: "557-560",
    issued: { "date-parts": [[2003]] },
    DOI: "10.1136/bmj.327.7414.557",
  },
  {
    type: "article-journal",
    title: "Bias in meta-analysis detected by a simple, graphical test",
    author: [
      { family: "Egger", given: "Matthias" },
      { family: "Davey Smith", given: "George" },
      { family: "Schneider", given: "Martin" },
      { family: "Minder", given: "Christoph" },
    ],
    "container-title": "BMJ",
    volume: "315", issue: "7109", page: "629-634",
    issued: { "date-parts": [[1997]] },
    DOI: "10.1136/bmj.315.7109.629",
  },
  {
    type: "article-journal",
    title: "Trim and fill: A simple funnel-plot-based method of testing and adjusting for publication bias in meta-analysis",
    author: [
      { family: "Duval", given: "Sue" },
      { family: "Tweedie", given: "Richard" },
    ],
    "container-title": "Biometrics",
    volume: "56", issue: "2", page: "455-463",
    issued: { "date-parts": [[2000]] },
    DOI: "10.1111/j.0006-341X.2000.00455.x",
  },
  {
    type: "article-journal",
    title: "Recommendations for examining and interpreting funnel plot asymmetry in meta-analyses of randomised controlled trials",
    author: [
      { family: "Sterne", given: "Jonathan A. C." },
      { family: "Sutton", given: "Alex J." },
      { family: "Ioannidis", given: "John P. A." },
    ],
    "container-title": "BMJ",
    volume: "343", page: "d4002",
    issued: { "date-parts": [[2011]] },
    DOI: "10.1136/bmj.d4002",
  },
  {
    type: "article-journal",
    title: "Meta-analysis in clinical trials",
    author: [
      { family: "DerSimonian", given: "Rebecca" },
      { family: "Laird", given: "Nan" },
    ],
    "container-title": "Controlled Clinical Trials",
    volume: "7", issue: "3", page: "177-188",
    issued: { "date-parts": [[1986]] },
    DOI: "10.1016/0197-2456(86)90046-2",
  },
  {
    type: "article-journal",
    title: "The Hartung-Knapp-Sidik-Jonkman method for random effects meta-analysis is straightforward and considerably outperforms the standard DerSimonian-Laird method",
    author: [
      { family: "IntHout", given: "Joanna" },
      { family: "Ioannidis", given: "John P. A." },
      { family: "Borm", given: "George F." },
    ],
    "container-title": "BMC Medical Research Methodology",
    volume: "14", page: "25",
    issued: { "date-parts": [[2014]] },
    DOI: "10.1186/1471-2288-14-25",
  },
  {
    type: "article-journal",
    title: "Conducting meta-analyses in R with the metafor package",
    author: [{ family: "Viechtbauer", given: "Wolfgang" }],
    "container-title": "Journal of Statistical Software",
    volume: "36", issue: "3", page: "1-48",
    issued: { "date-parts": [[2010]] },
    DOI: "10.18637/jss.v036.i03",
  },
  {
    type: "article-journal",
    title: "Outlier and influence diagnostics for meta-analysis",
    author: [
      { family: "Viechtbauer", given: "Wolfgang" },
      { family: "Cheung", given: "Mike W.-L." },
    ],
    "container-title": "Research Synthesis Methods",
    volume: "1", issue: "2", page: "112-125",
    issued: { "date-parts": [[2010]] },
    DOI: "10.1002/jrsm.11",
  },
  {
    type: "article-journal",
    title: "The PRISMA 2020 statement: an updated guideline for reporting systematic reviews",
    author: [
      { family: "Page", given: "Matthew J." },
      { family: "McKenzie", given: "Joanne E." },
      { family: "Bossuyt", given: "Patrick M." },
    ],
    "container-title": "BMJ",
    volume: "372", page: "n71",
    issued: { "date-parts": [[2021]] },
    DOI: "10.1136/bmj.n71",
  },
  {
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
  },
];

// Per-paper audit. The section gets only the paper id via ctx, so it self-fetches title + chunk_count. Auto-runs
// when its section is the open one (like statcheck / the LMM auditor).
function MetaPaper({ paperId, onOpenPaper, active }) {
  const [meta, setMeta] = useState(null); // { title, hasText } | null
  const [state, setState] = useState({ status: "idle" });
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
    const r = await api(`/papers/${paperId}/meta-analysis`);
    setState(r.ok ? { status: "done", data: r.data } : { status: "error", error: r.error });
  };
  useEffect(() => {
    if (active && meta && meta.hasText && state.status === "idle") run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, meta]);
  const open = (evidence, key) => {
    if (!onOpenPaper) return;
    const title = meta ? meta.title : "";
    const target = methodEvidenceTarget(paperId, title, evidence, key);
    if (target) onOpenPaper({ id: paperId, title }, target);
  };
  if (paperId == null) return <div className="tag-suggest-empty">Select a paper to audit its meta-analysis reporting.</div>;
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
            ? <button className="btn-link" title="Audit this paper's meta-analysis reporting — local, no AI" onClick={run}>Audit reporting</button>
            : null}
      {state.status === "running" && <span className="tag-suggest-empty">auditing…</span>}
      {state.status === "error" && <div className="axis-err">Couldn't audit: {state.error}</div>}
      {state.status === "done" && d && (!d.is_meta_analysis
        ? <div className="tag-suggest-empty">This paper doesn't appear to report a meta-analysis — nothing to audit.</div>
        : <MetaChecklist checks={d.checks} onOpen={open} />)}
    </div>
  );
}

function MetaChecklist({ checks, onOpen }) {
  if (!checks || !checks.length) return null;
  const present = checks.filter(c => c.status === "present").length;
  const notFound = checks.filter(c => c.status === "not-found").length;
  const na = checks.filter(c => c.status === "not-applicable").length;
  return (
    <div className="bayes-checklist">
      <p className="eyebrow">Reporting checklist</p>
      {/* A factual tally of the statuses below — not a score or a grade. */}
      <div className="lmm-summary">{present} reported · {notFound} not detected · {na} not applicable · {checks.length} checks</div>
      {checks.map((c) => (
        <div key={c.key} className={"bayes-check-item" + (c.status === "not-applicable" ? " lmm-na" : "")}>
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
            <EvidenceQuote text={c.evidence} match={c.evidence} label="Evidence" className="bayes-check-ev"
              precision={c.coordinate_precision} hasSourcePage={c.page != null}
              onOpen={c.page != null ? () => onOpen(c, `meta-check:${c.key}`) : null}
              openLabel={c.coordinate_precision === "exact" ? "Open and highlight this checklist evidence" : "Open source page for this checklist evidence"} />}
          {c.evidence && <EvidenceTrail detector="Meta-analysis reporting" matched={c.evidence}
            precision={c.coordinate_precision} hasSourcePage={c.page != null} page={c.page}
            caveat="Reporting checklist signals are text detections only; they do not pool, recompute, or judge the analysis." />}
        </div>
      ))}
      <div className="statcheck-caveat">
        Audits reporting <b>completeness</b>, not analysis <b>correctness</b> — a meta-analysis can report everything and still pool badly, or omit an item and be fine. This flags what a careful reader should check, not what's wrong. It reads the extracted text, so <b>“not found” means not detected there</b> — check the paper (tables/figures aren't fully read). It never pools, models, re-computes, scores, or accuses.
      </div>
    </div>
  );
}

function MetaCredit() {
  const [added, setAdded] = useState("idle");
  const addCredit = async () => {
    setAdded("adding");
    const r = await apiPost("/library/import", { content: JSON.stringify(META_CSL), format: "csl-json" });
    setAdded(r && r.ok ? "added" : "idle");
  };
  return (
    <div className="method-credit">
      <b>Methods:</b> effect sizes &amp; general — Borenstein et al. (2009), Viechtbauer (2010, <i>metafor</i>); model — DerSimonian &amp; Laird (1986), IntHout et al. (2014); heterogeneity — Higgins et al. (2003); publication bias — Egger et al. (1997), Duval &amp; Tweedie (2000), Sterne et al. (2011); influence — Viechtbauer &amp; Cheung (2010); reporting — PRISMA 2020 (Page et al. 2021).{" "}
      <button className="btn-link" disabled={added !== "idle"} onClick={addCredit}>
        {added === "added" ? "✓ added to library" : added === "adding" ? "adding…" : "＋ add methods sources to library"}
      </button>
      <div className="method-credit-sub">A reading aid — it never pools, models, or re-computes a meta-analysis. Surfaced via D. Lakens' automated-review catalog.</div>
    </div>
  );
}

function MetaSection({ ctx }) {
  return (
    <div className="statcheck-section">
      <div className="settings-sub">Audit a published <b>meta-analysis's reporting</b> — does it state the effect-size metric, the model (fixed vs random-effects), heterogeneity, a publication-bias assessment, a sensitivity/influence analysis, the number of studies pooled, and (for a systematic review) the search &amp; selection? Local, no AI. It flags what's not reported, with a grounded recommendation — never a verdict, and it never pools or re-computes.</div>
      <p className="eyebrow">This paper</p>
      <MetaPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper} active={ctx.methodsOpen === "meta"} />
      <MetaCredit />
    </div>
  );
}

// inc 280 (stage 2): METHODS → the Extract workspace as "Meta-Analysis". The {methodsOpen: active ? "meta" : null}
// adapter makes MetaSection's existing `ctx.methodsOpen === "meta"` active-check resolve to WorkspacePane's `active`
// 2nd render arg — so MetaSection is unchanged. Reads ctx.selectedPaper + ctx.onOpenPaper (both in workspaceCtx).
registerWorkspaceTab(
  { id: "extract" },
  {
    id: "meta", label: "Meta-Analysis", order: 30, hideInReadOnly: true,
    render: (ctx, active) => <MetaSection ctx={{ ...ctx, methodsOpen: active ? "meta" : null }} />,
  },
);
