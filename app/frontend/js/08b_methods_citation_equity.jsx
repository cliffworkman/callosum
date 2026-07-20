// inc 227 (backlog #25; reworked inc 229): the "Citation concentration" METHODS section — a structural look at a
// library paper's reference list (its OpenAlex referenced_works), shown against a sample of the paper's field.
// Descriptive context, never a score / target / accusation (Principles #2/#7 + the no-accusation A-A boundary).
// It measures WHAT is cited, never WHO wrote it (no author-categorization; a guard test in test_citation_equity.py
// keeps it that way). Egress = public OpenAlex metadata (user-initiated "Run audit"), NOT the Gemini gate.

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
  const lowCov = s.low_coverage && s.coverage_fraction != null;
  return (
    <div className={"cite-equity-signal" + (lowCov ? " low-coverage" : "")}>
      <div className="cite-equity-siglabel">
        {s.label}
        {lowCov && <span className="cite-equity-lowcov"
          title="This number is computed over fewer than half of the references, so it is a thin, possibly-skewed sample — read it as a hint, not a reliable comparison to the field.">
          ⚠ low coverage ({Math.round(s.coverage_fraction * 100)}%)</span>}
      </div>
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

// credit + the how-to note. (The tool measures what is cited, never who wrote it — we don't editorialize that to
// the user; it's just how it works. A regression guard test keeps people-categorization from creeping back in.)
function CiteEquityFoot() {
  return (
    <React.Fragment>
      <div className="cite-equity-howto">
        Read this as a mirror, not a report card. If a concentration stands out, the move is to read more
        widely — never to drop a relevant citation, or add one to hit a number. Use <b>Find overlooked work</b>
        (below) to surface topically-relevant papers your list may have missed.
      </div>
      <div className="method-credit">
        <b>Methods:</b> self-citation (King et al. 2017, <i>Socius</i>); the Matthew effect (Merton 1968, <i>Science</i>;
        Perc 2014, <i>J. R. Soc. Interface</i>).{" "}
        <MethodCreditButton items={CITATION_EQUITY_CSL} />
        <div className="method-credit-sub">Computed structurally from OpenAlex metadata (public) — credited, not reused.</div>
      </div>
    </React.Fragment>
  );
}

function CitationEquityPaper({ paperId, meta }) {
  // meta ({ title, hasDoi } | null) is fetched once by CitationEquitySection and shared with OverlookedWork, so a
  // no-DOI paper gates BOTH controls off one source of truth (no duplicate /papers fetch).
  const [state, setState] = useState({ status: "idle" });  // idle | running | done | error
  useEffect(() => { setState({ status: "idle" }); }, [paperId]);  // reset the audit when the paper changes
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
        How concentrated <b>{meta ? meta.title : "this paper"}</b>'s reference list is — does it lean on your own
        work, famous work, a few venues, a few elite institutions? Descriptive context, never a score or a target.
      </div>
      {meta && !meta.hasDoi &&
        <div className="tag-suggest-empty">This paper has no DOI, so OpenAlex can't resolve its references. Add one under Identifiers in the Detail pane to enable this audit.</div>}
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

// inc 228 (SP2): the topical overlooked-work remediation — surface relevant work the reference list OMITS, ranked
// by callosum's OWN local embedding cosine. Add-only (never "drop this"); the reason is topical match, never an
// author's identity; no quota. A candidate the user judges + adds (metadata-only, no PDF) — nothing auto-inserts.
function OverlookedCard({ c }) {
  const [st, setSt] = useState(c.in_library ? "in" : "idle");  // in | idle | adding | added
  const add = async () => {
    setSt("adding");
    const r = await apiPost("/discovery/save", {
      title: c.title, doi: c.doi || undefined, authors: c.authors || [],
      journal: c.venue || undefined, year: c.year || undefined, abstract: c.abstract || undefined,
    });
    setSt(r && r.ok ? "added" : "idle");
  };
  // a link out so you can READ before deciding (doi.org, else the OpenAlex work page) — an external link, no token.
  const openHref = c.doi ? `https://doi.org/${c.doi}` : (c.openalex_work_id ? `https://openalex.org/${c.openalex_work_id}` : null);
  return (
    <div className="cite-equity-cand">
      <div className="cite-equity-cand-title">{c.title}</div>
      <div className="cite-equity-cand-meta">
        {(c.authors || []).slice(0, 3).join(", ")}{c.year ? ` · ${c.year}` : ""}{c.venue ? ` · ${c.venue}` : ""}
      </div>
      <div className="cite-equity-cand-foot">
        <span className="cite-equity-match" title="callosum's own local embedding cosine to this paper — a topical match, never a 'you must cite this'">topical match: {c.match.toFixed(2)}</span>
        {c.shared_concepts && c.shared_concepts.length > 0 &&
          <span className="cite-equity-cand-why"> · shared: {c.shared_concepts.join(", ")}</span>}
        {openHref && <a className="btn-link cite-equity-cand-open" href={openHref} target="_blank" rel="noopener noreferrer">Open ↗</a>}
        {st === "in"
          ? <span className="cite-equity-cand-inlib">✓ in library</span>
          : <button className="btn-link" disabled={st !== "idle"} onClick={add}>
              {st === "added" ? "✓ in library" : st === "adding" ? "adding…" : "＋ Add to library"}
            </button>}
      </div>
      {c.abstract &&
        <details className="cite-equity-cand-abstract">
          <summary>Abstract</summary>
          <p>{c.abstract}</p>
        </details>}
    </div>
  );
}

function OverlookedWork({ paperId, hasDoi }) {
  const [state, setState] = useState({ status: "idle" });  // idle | running | done | error
  useEffect(() => { setState({ status: "idle" }); }, [paperId]);
  const run = async () => {
    setState({ status: "running", progress: null });
    const poll = (jobId) => api(`/methods/citation-equity/overlooked/${jobId}`).then(r => {
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") setState({ status: "done", report: d.report });
      else if (d.status === "error") setState({ status: "error", error: d.detail || "Search failed." });
      else { setState({ status: "running", progress: d.progress }); setTimeout(() => poll(jobId), 1500); }
    });
    const r = await apiPost("/methods/citation-equity/overlooked", { paper_id: paperId });
    if (!r.ok) { setState({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  if (paperId == null) return null;
  const rep = state.report;
  return (
    <div className="cite-equity-overlooked">
      <p className="eyebrow">Overlooked work</p>
      <div className="cite-equity-overlooked-intro">
        Relevant work you may have missed — candidates to consider, ranked by topical match (callosum's own local
        embedding). Nothing is dropped or auto-added, and an author's identity is never the reason to cite.
      </div>
      {hasDoi === false &&
        <div className="tag-suggest-empty">This paper has no DOI, so OpenAlex can't relate work to it. Add one under Identifiers in the Detail pane to enable the overlooked-work search.</div>}
      {hasDoi && state.status === "idle" &&
        <button className="btn btn-primary" onClick={run}
          title="Find topically-relevant work this paper's reference list omits (OpenAlex related work + a sample of the field, ranked locally)">
          Find overlooked work
        </button>}
      {state.status === "running" && <ProgressBar progress={state.progress} label="Finding related work…" />}
      {state.status === "error" && <div className="axis-err">Couldn't search: {state.error}</div>}
      {state.status === "done" && rep && (rep.shown === 0
        ? <div className="tag-suggest-empty">Nothing clearly relevant that your reference list missed — or OpenAlex relates too few works to this paper. (Considered {rep.considered} candidates you don't already cite.)</div>
        : <div className="cite-equity-cands">
            <div className="cite-equity-cand-cov">
              {rep.shown} candidate{rep.shown === 1 ? "" : "s"} from {rep.considered} works related to your paper that you don't already cite{rep.field_topic ? <> (field: <b>{rep.field_topic.display_name}</b>)</> : null} — ranked by topical match; only clearly-relevant matches (cosine ≥ 0.55) are shown.
            </div>
            {rep.candidates.map((c, i) => <OverlookedCard key={c.openalex_work_id || i} c={c} />)}
          </div>)}
    </div>
  );
}

function CitationEquitySection({ ctx }) {
  const paperId = ctx.selectedPaper;
  const [meta, setMeta] = useState(null);  // { title, hasDoi } | null — fetched once, shared by both children
  useEffect(() => {
    setMeta(null);
    if (paperId == null) return;
    let live = true;
    api(`/papers/${paperId}`).then(r => { if (live && r.ok) setMeta({ title: r.data.title, hasDoi: !!r.data.doi }); });
    return () => { live = false; };
  }, [paperId]);
  return (
    <div className="cite-equity-section">
      <CitationEquityPaper paperId={paperId} meta={meta} />
      <OverlookedWork paperId={paperId} hasDoi={meta ? meta.hasDoi : null} />
    </div>
  );
}

// Rendered directly by MetaReferencePane (37b_meta_reference.jsx) as a Work → Meta-Reference subsection.
