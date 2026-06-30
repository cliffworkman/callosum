// inc 227 (backlog #25): the "Citation equity" METHODS section — an identity-agnostic, structural audit of a
// library paper's reference list (its OpenAlex referenced_works), shown against a sample of the paper's field.
// Descriptive context, never a score / target / accusation (Principles #2/#7 + the no-accusation A-A boundary).
// NO author-identity inference — the gender module is deliberately deferred (name→gender inference is unreliable
// and not shown). Egress = public OpenAlex metadata (user-initiated "Run audit"), NOT the Gemini library-text gate.

// credit-the-lineage: the methods this audit operationalizes, one-click added to the library (inc-93 import path).
const CITATION_EQUITY_CSL = [
  {
    type: "article-journal",
    title: "Men Set Their Own Cites High: Gender and Self-Citation across Fields and over Time",
    author: [
      { family: "King", given: "Molly M." },
      { family: "Bergstrom", given: "Carl T." },
      { family: "Correll", given: "Shelley J." },
      { family: "Jacquet", given: "Jennifer" },
      { family: "West", given: "Jevin D." },
    ],
    "container-title": "Socius", volume: "3",
    issued: { "date-parts": [[2017]] }, DOI: "10.1177/2378023117738903",
  },
  {
    type: "article-journal",
    title: "The Matthew Effect in Science",
    author: [{ family: "Merton", given: "Robert K." }],
    "container-title": "Science", volume: "159", issue: "3810", page: "56-63",
    issued: { "date-parts": [[1968]] }, DOI: "10.1126/science.159.3810.56",
  },
  {
    type: "article-journal",
    title: "The Matthew effect in empirical data",
    author: [{ family: "Perc", given: "Matjaž" }],
    "container-title": "Journal of the Royal Society Interface", volume: "11", issue: "98", page: "20140378",
    issued: { "date-parts": [[2014]] }, DOI: "10.1098/rsif.2014.0378",
  },
];

function CiteEquityBar({ label, pct, kind }) {
  if (pct == null) return (
    <div className="cite-equity-barrow"><span className="cite-equity-barlabel">{label}</span><span className="cite-equity-barval">—</span></div>
  );
  const w = Math.max(2, Math.round(pct * 100));
  return (
    <div className="cite-equity-barrow">
      <span className="cite-equity-barlabel">{label}</span>
      <span className="cite-equity-bar"><span className={"cite-equity-fill " + kind} style={{ width: w + "%" }} /></span>
      <span className="cite-equity-barval">{Math.round(pct * 100)}%</span>
    </div>
  );
}

function CiteEquitySignal({ s }) {
  return (
    <div className="cite-equity-signal">
      <div className="cite-equity-siglabel">{s.label}</div>
      <div className="cite-equity-summary">{s.summary}</div>
      {(s.list_pct != null || s.field_pct != null) &&
        <div className="cite-equity-bars">
          <CiteEquityBar label="This list" pct={s.list_pct} kind="list" />
          {s.field_pct != null && <CiteEquityBar label="Field" pct={s.field_pct} kind="field" />}
        </div>}
      {s.basis && s.basis.length > 0 &&
        <details className="cite-equity-basis">
          <summary>Show the basis ({s.basis.length})</summary>
          <ul>{s.basis.map((b, i) => <li key={i}>{b}</li>)}</ul>
        </details>}
      <div className="cite-equity-coverage">{s.coverage}</div>
    </div>
  );
}

// credit + the deferred-module honesty note (the gender module is deliberately not built — see the spec).
function CiteEquityFoot() {
  const [added, setAdded] = useState("idle");
  const addCredit = async () => {
    setAdded("adding");
    const r = await apiPost("/library/import", { content: JSON.stringify(CITATION_EQUITY_CSL), format: "csl-json" });
    setAdded(r && r.ok ? "added" : "idle");
  };
  return (
    <React.Fragment>
      <div className="cite-equity-howto">
        Read this as a mirror, not a report card. If a concentration stands out, the move is to read more
        widely — never to drop a relevant citation, or add one to hit a number. A future version will help
        surface relevant work you may have overlooked.
      </div>
      <div className="cite-equity-deferred">
        A gender or identity balance number is deliberately <b>not</b> produced. Name→gender inference is
        unreliable (systematically wrong for non-Western names) and would mean inferring an attribute about people —
        so equity here is measured structurally, not by guessing identities.
      </div>
      <div className="method-credit">
        <b>Methods:</b> self-citation (King et al. 2017, <i>Socius</i>); the Matthew effect (Merton 1968, <i>Science</i>;
        Perc 2014, <i>J. R. Soc. Interface</i>).{" "}
        <button className="btn-link" disabled={added !== "idle"} onClick={addCredit}>
          {added === "added" ? "✓ added to library" : added === "adding" ? "adding…" : "＋ add to library"}
        </button>
        <div className="method-credit-sub">Computed structurally from OpenAlex metadata (public) — credited, not reused.</div>
      </div>
    </React.Fragment>
  );
}

function CitationEquityPaper({ paperId }) {
  const [meta, setMeta] = useState(null);            // { title, hasDoi } | null
  const [state, setState] = useState({ status: "idle" });  // idle | running | done | error
  useEffect(() => {
    setState({ status: "idle" }); setMeta(null);
    if (paperId == null) return;
    let live = true;
    api(`/papers/${paperId}`).then(r => {
      if (!live || !r.ok) return;
      setMeta({ title: r.data.title, hasDoi: !!r.data.doi });
    });
    return () => { live = false; };
  }, [paperId]);
  const run = async () => {
    setState({ status: "running", progress: null });
    const poll = (jobId) => api(`/methods/citation-equity/run/${jobId}`).then(r => {
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") setState({ status: "done", report: d.report });
      else if (d.status === "error") setState({ status: "error", error: d.detail || "Audit failed." });
      else { setState({ status: "running", progress: d.progress }); setTimeout(() => poll(jobId), 1500); }
    });
    const r = await apiPost("/methods/citation-equity/run", { paper_id: paperId });
    if (!r.ok) { setState({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  if (paperId == null) return <div className="tag-suggest-empty">Select a paper to audit its reference list.</div>;
  const rep = state.report;
  return (
    <div className="cite-equity">
      <div className="cite-equity-intro">
        The structural shape of <b>{meta ? meta.title : "this paper"}</b>'s reference list — descriptive context,
        never a score or a target. Identity-agnostic: no author-identity inference.
      </div>
      {meta && !meta.hasDoi &&
        <div className="tag-suggest-empty">This paper has no DOI, so OpenAlex can't resolve its references.</div>}
      {meta && meta.hasDoi && state.status === "idle" &&
        <React.Fragment>
          <button className="btn btn-primary" onClick={run}
            title="Resolve this paper's references via OpenAlex (public metadata) and compute its structural signals">
            Run audit
          </button>
          <div className="cite-equity-egress-note">Running fetches public OpenAlex metadata about your references (their DOIs) — nothing about your draft or library text leaves your machine.</div>
        </React.Fragment>}
      {state.status === "running" && <ProgressBar progress={state.progress} label="Resolving references…" />}
      {state.status === "error" && <div className="axis-err">Couldn't run the audit: {state.error}</div>}
      {state.status === "done" && rep && (rep.references_total === 0
        ? <div className="tag-suggest-empty">OpenAlex has no reference-list data for this paper, so there's nothing to audit.</div>
        : <div className="cite-equity-report">
            <div className="cite-equity-field">
              {rep.field_topic
                ? <>Compared with a sample of {rep.field_sample_size} recent <b>{rep.field_topic.display_name || "field"}</b> papers (OpenAlex).</>
                : <>No field comparison available (OpenAlex has no topic for this paper) — showing the list's own shape.</>}
            </div>
            <div className="cite-equity-caption">The bars show each value descriptively — context for you to interpret, not a target or a score; neither direction is a verdict.</div>
            {rep.signals.map(s => <CiteEquitySignal key={s.key} s={s} />)}
            <CiteEquityFoot />
          </div>)}
    </div>
  );
}

function CitationEquitySection({ ctx }) {
  return (
    <div className="cite-equity-section">
      <CitationEquityPaper paperId={ctx.selectedPaper} />
    </div>
  );
}

registerPaneSection({
  id: "citation-equity", label: "Citation equity", paneId: "methods", order: 35,
  render: (ctx) => <CitationEquitySection ctx={ctx} />,
});
