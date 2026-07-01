// inc 241: Bayesian auditor SP1 — recompute reported default (JZS) Bayes factors for a paper's inline t-test BFs.
// The deterministic sibling of statcheck (Rouder et al. 2009): read the paper's extracted text, recompute the
// default BF10 from each `t(df) = …, BF10 = …`, and flag where it doesn't reproduce under the default prior.
// Local, no AI, no egress. A signal, never a verdict; never an accusation (a mismatch is most often a different
// prior scale, which the text doesn't reveal). See app/backend/methods/bayes.py.

// inc 241 (credit-the-lineage): the source paper, one-click added to the library (matches statcheck/GRIM/p-curve).
const BAYES_CSL = {
  type: "article-journal",
  title: "Bayesian t tests for accepting and rejecting the null hypothesis",
  author: [
    { family: "Rouder", given: "Jeffrey N." },
    { family: "Speckman", given: "Paul L." },
    { family: "Sun", given: "Dongchu" },
    { family: "Morey", given: "Richard D." },
    { family: "Iverson", given: "Geoffrey" },
  ],
  "container-title": "Psychonomic Bulletin & Review",
  volume: "16",
  issue: "2",
  page: "225-237",
  issued: { "date-parts": [[2009]] },
  DOI: "10.3758/PBR.16.2.225",
};

// Per-paper recompute. The section gets only the paper id via ctx, so it self-fetches title + chunk_count (the
// auditor needs extracted text). Each row routes to its page at region precision (page-open, never a fake exact
// highlight — the coordinate-honesty contract). Auto-runs when its section is the open one (like statcheck).
function BayesPaper({ paperId, onOpenPaper, active }) {
  const [meta, setMeta] = useState(null);          // { title, hasText } | null
  const [state, setState] = useState({ status: "idle" });  // idle | running | done | error
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
    const r = await api(`/papers/${paperId}/bayes`);
    setState(r.ok ? { status: "done", data: r.data } : { status: "error", error: r.error });
  };
  useEffect(() => {
    if (active && meta && meta.hasText && state.status === "idle") run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, meta]);
  const open = (page) => { if (onOpenPaper && page != null) onOpenPaper({ id: paperId, title: meta ? meta.title : "" }, { page, precision: "region" }); };
  if (paperId == null) return <div className="tag-suggest-empty">Select a paper to recompute its Bayes factors.</div>;
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
            ? <button className="btn-link" title="Recompute reported default Bayes factors from this paper's text — local, no AI" onClick={run}>Check Bayes factors</button>
            : null}
      {state.status === "running" && <span className="tag-suggest-empty">checking…</span>}
      {state.status === "error" && <div className="axis-err">Couldn't check: {state.error}</div>}
      {state.status === "done" && d && (d.checked === 0
        ? <div className="tag-suggest-empty">No inline t-test Bayes factors (e.g. “t(23) = 2.1, BF₁₀ = 3.4”) found in the extracted text.</div>
        : <div className="statcheck-result">
            <div className="statcheck-summary">{d.checked} checked · {d.not_reproduced} couldn't reproduce under the default prior</div>
            <div className="statcheck-list">
              {d.results.map((r, i) => (
                <button key={i} className={"statcheck-item" + (r.consistency !== "reproduced" ? " flagged-row" : "")} title={r.page != null ? "Open page " + r.page : ""} onClick={() => open(r.page)}>
                  <span className="statcheck-raw">{r.raw}</span>
                  <span className="statcheck-computed">reported BF₁₀ = {r.reported_bf10} · recomputed {reBfLabel(r)}</span>
                  <span className={"cite-status " + (r.consistency === "reproduced" ? "verified" : "flagged")}>{r.consistency === "reproduced" ? "reproduces" : "couldn't reproduce"}</span>
                </button>
              ))}
            </div>
            <div className="statcheck-caveat">
              Recomputed under the <b>default JZS prior</b> (Cauchy scale r ≈ {d.prior_scale}) for a t-test, under both a paired and a two-sample reading — a Bayes factor “reproduces” if it matches either within a factor of ~2. If the paper used a different prior scale or a non-t design, a mismatch is expected — a prompt to look, not a verdict or an accusation. It reads only inline t-test BFs, so a clean result isn't a clean bill.
            </div>
          </div>)}
    </div>
  );
}

// "recomputed" label: show the interpretation that reproduced it, else both candidates.
function reBfLabel(r) {
  if (r.consistency === "reproduced" && r.matched_design) {
    const val = r.matched_design === "paired" ? r.computed_paired : r.computed_two_sample;
    return `${val} (${r.matched_design})`;
  }
  const parts = [];
  if (r.computed_paired != null) parts.push(`${r.computed_paired} (paired)`);
  if (r.computed_two_sample != null) parts.push(`${r.computed_two_sample} (two-sample)`);
  return parts.join(" / ") || "—";
}

function BayesCredit() {
  const [added, setAdded] = useState("idle");
  const addCredit = async () => {
    setAdded("adding");
    const r = await apiPost("/library/import", { content: JSON.stringify([BAYES_CSL]), format: "csl-json" });
    setAdded(r && r.ok ? "added" : "idle");
  };
  return (
    <div className="method-credit">
      <b>Method:</b> the default JZS Bayes factor — Rouder, Speckman, Sun, Morey &amp; Iverson (2009), <i>Psychonomic Bulletin &amp; Review</i> 16(2):225–237.{" "}
      <button className="btn-link" disabled={added !== "idle"} onClick={addCredit}>
        {added === "added" ? "✓ added to library" : added === "adding" ? "adding…" : "＋ add to library"}
      </button>
      <div className="method-credit-sub">Re-implemented in Python (the closed form JASP / the <i>BayesFactor</i> R package [Morey &amp; Rouder] use) — credited, not reused. Surfaced via D. Lakens' automated-review catalog.</div>
    </div>
  );
}

function BayesSection({ ctx }) {
  return (
    <div className="statcheck-section">
      <div className="settings-sub">Recompute a paper's reported <b>default Bayes factors</b> for inline t-test results — the Bayesian analogue of statcheck. Local, no AI. It flags where a reported BF₁₀ doesn't reproduce under the standard JZS prior; usually a different prior, not an error — a prompt to look, never a verdict.</div>
      <p className="eyebrow">This paper</p>
      <BayesPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper} active={ctx.methodsOpen === "bayes"} />
      <BayesCredit />
    </div>
  );
}

registerPaneSection({
  id: "bayes", label: "Bayesian statistics", paneId: "methods", order: 32, hideInReadOnly: true,
  render: (ctx) => <BayesSection ctx={ctx} />,
});
