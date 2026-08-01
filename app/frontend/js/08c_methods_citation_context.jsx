// inc 232 (B4 SP1): "How this paper is cited" — the scite analogue. Fetch the citing sentences from Semantic
// Scholar, classify each stance LOCALLY (support/contrast/mention), and show the real sentence + confidence + counts.
// Honesty: counts are NEVER folded into a composite score; the citing sentence is always the evidence; the stance is
// a labeled signal, not a verdict; a "contrast" describes the shown sentence's rhetorical relationship, never an
// accusation of an author. Only the paper's DOI leaves the machine (public metadata); classification is local.

// credit-the-lineage: this echoes scite; credited + one-click added to the library (inc-93 import path).
const CITATION_CONTEXT_CSL = [
  {
    type: "article-journal",
    title: "scite: A smart citations index that displays the context of citations and classifies their intent using deep learning",
    author: [
      { family: "Nicholson", given: "Josh M." },
      { family: "Mordaunt", given: "Milo" },
      { family: "Lopez", given: "Patrice" },
      { family: "Uppala", given: "Ashish" },
      { family: "Rosati", given: "Domenic" },
      { family: "Rife", given: "Sean C." },
    ],
    "container-title": "Quantitative Science Studies", volume: "2", issue: "3", page: "882-898",
    issued: { "date-parts": [[2021]] }, DOI: "10.1162/qss_a_00146",
  },
];

function CitationContextCredit() {
  return (
    <div className="method-credit">
      <b>Method:</b> smart citations (Nicholson et al. 2021, <i>Quantitative Science Studies</i> — the <b>scite</b> index this echoes).{" "}
      <MethodCreditButton items={CITATION_CONTEXT_CSL} />
      <div className="method-credit-sub">Citing sentences from <b>Semantic Scholar</b> (Allen Institute for AI); stance classified locally by callosum's own NLI — a signal to read, never a verdict.</div>
    </div>
  );
}

function CitationContextItem({ it }) {
  const stance = it.stance || "unknown";
  const who = [(it.citing_authors || []).slice(0, 3).join(", "), it.citing_year].filter(Boolean).join(" · ");
  const href = it.citing_doi ? `https://doi.org/${it.citing_doi}` : null;
  return (
    <div className="citec-item">
      <div className="citec-item-head">
        <span className={"cite-stance " + stance} title="callosum's local NLI stance over this citing sentence — a signal, not a verdict">{it.stance || "unclassified"}</span>
        {it.confidence != null && <span className="citec-conf">conf {it.confidence.toFixed(2)}</span>}
        {it.is_influential && <span className="citec-infl" title="Semantic Scholar flags this as a highly-influential citation">influential</span>}
      </div>
      <div className="citec-citer">
        {href
          ? <a className="btn-link" href={href} target="_blank" rel="noopener noreferrer">{it.citing_title || "Untitled"} ↗</a>
          : (it.citing_title || "Untitled")}
        {who && <span className="citec-who"> — {who}</span>}
      </div>
      {it.sentence && <div className="citec-sentence">“{it.sentence}”</div>}
    </div>
  );
}

function CitationContextPaper({ paperId, direction }) {
  const [meta, setMeta] = useState(null);
  const [state, setState] = useState({ status: "idle" });
  useEffect(() => {
    setState({ status: "idle" }); setMeta(null);
    if (paperId == null) return;
    let live = true;
    api(`/papers/${paperId}`).then(r => { if (live && r.ok) setMeta({ title: r.data.title, hasDoi: !!r.data.doi }); });
    return () => { live = false; };
  }, [paperId]);
  const D = direction === "references"
    ? { noun: "references", verb: "Fetch references",
        intro: <>How <b>{meta ? meta.title : "this paper"}</b> cites its own sources — does it <b>support</b>, <b>contrast</b>, or just <b>mention</b> each? A labeled signal to read, never a verdict.</>,
        empty: "Semantic Scholar has no reference data for this paper." }
    : { noun: "citations", verb: "Fetch citations",
        intro: <>How the later literature has responded to <b>{meta ? meta.title : "this paper"}</b> — do later papers <b>support</b>, <b>contrast</b>, or just <b>mention</b> it? A labeled signal to read, never a verdict.</>,
        empty: "Semantic Scholar has no recorded citations for this paper yet." };
  const run = async () => {
    setState({ status: "running", progress: null });
    const poll = (jid) => api(`/papers/citation-context/run/${jid}`).then(r => {
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") setState({ status: "done", report: d.report });
      else if (d.status === "error") setState({ status: "error", error: d.detail || "Failed." });
      else { setState({ status: "running", progress: d.progress }); setTimeout(() => poll(jid), 1500); }
    });
    const r = await apiPost("/papers/citation-context/run", { paper_id: paperId, direction });
    if (!r.ok) { setState({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  if (paperId == null) return <div className="tag-suggest-empty">Select a paper to see how it's been cited.</div>;
  const rep = state.report;
  return (
    <div className="cite-equity">
      <div className="meta-ref-action-row">
        <div className="meta-ref-action-copy">
          <div className="cite-equity-intro">{D.intro}</div>
          {meta && meta.hasDoi && state.status === "idle" &&
            <div className="cite-equity-egress-note">Running sends this paper's DOI to Semantic Scholar (public metadata) and classifies the returned sentences on your machine — your library text never leaves.</div>}
        </div>
        <div className="meta-ref-action-slot">
          {meta && meta.hasDoi && state.status === "idle" &&
            <button className="btn btn-primary" onClick={run}
              title="Fetch the citing sentences from Semantic Scholar (public metadata) and classify each stance locally">
              {D.verb}
            </button>}
        </div>
      </div>
      {meta && !meta.hasDoi &&
        <div className="tag-suggest-empty">This paper has no DOI, so Semantic Scholar can't look up its citation graph. Add one under Identifiers in the Detail pane to enable it.</div>}
      {state.status === "running" && <ProgressBar progress={state.progress} label="Fetching + classifying…" managedBy="backend-job" />}
      {state.status === "error" && <div className="axis-err">Couldn't fetch {D.noun}: {state.error}</div>}
      {state.status === "done" && rep && (rep.total_citations === 0
        ? <div className="tag-suggest-empty">{D.empty}</div>
        : <div className="cite-equity-report">
            <div className="citec-breakdown">
              <span className="citec-count support">{rep.counts.support || 0} supporting</span>
              <span className="citec-count contrast">{rep.counts.contrast || 0} contrasting</span>
              <span className="citec-count mention">{rep.counts.mention || 0} mentioning</span>
            </div>
            <div className="cite-equity-caption">Counts of individual citing sentences — read the sentences below and decide; there's no single "score", and neither direction is a verdict.</div>
            <div className="citec-coverage">
              Classified {rep.classified} of {rep.total_citations} {D.noun}
              {rep.total_citations > rep.with_context ? ` (${rep.total_citations - rep.with_context} had no citing sentence to read)` : ""}.
              {rep.total_citations >= 500 ? " Showing the first 500." : ""}
            </div>
            {rep.items.filter(i => i.sentence).map((it, ix) => <CitationContextItem key={ix} it={it} />)}
            <CitationContextCredit />
          </div>)}
    </div>
  );
}

function CitationContextSection({ ctx, direction }) {
  return <div className="cite-equity-section"><CitationContextPaper paperId={ctx.selectedPaper} direction={direction} /></div>;
}

// Rendered directly by MetaReferencePane (37b_meta_reference.jsx) as a Work → Meta-Reference subsection.
