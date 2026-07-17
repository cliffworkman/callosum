// inc 126: p-curve — a COLLECTION-LEVEL evidential-value check over the SELECTED papers. The modal POSTs the
// selection to the async /methods/pcurve/run job (which reuses the statcheck extractor server-side), polls it,
// and renders the curve + the right-skew/binomial statistics. Collection-level only — never per-paper, never
// "p-hacked"; the interpretation is the user's (signal, not verdict). Lineage credited in-context + one-click add.

// Bundled CSL-JSON for the source paper, added to the library via the inc-93 import path (credit-the-lineage).
const SNS2014_CSL = {
  type: "article-journal",
  title: "P-curve: A key to the file-drawer",
  author: [
    { family: "Simonsohn", given: "Uri" },
    { family: "Nelson", given: "Leif D." },
    { family: "Simmons", given: "Joseph P." },
  ],
  "container-title": "Journal of Experimental Psychology: General",
  volume: "143",
  issue: "2",
  page: "534-547",
  issued: { "date-parts": [[2014]] },
  DOI: "10.1037/a0033242",
};

function fmtPval(p) {
  if (p == null) return "—";
  if (p < 0.0001) return "< .0001";
  return p.toFixed(4).replace(/^0/, "");
}

function PcurvePlot({ bins }) {
  const W = 330, H = 150, padL = 30, padB = 28, padT = 12;
  const plotW = W - padL - 10, plotH = H - padB - padT;
  const ymax = Math.max(60, Math.ceil(Math.max(...bins, 20) / 10) * 10);
  const labels = [".01", ".02", ".03", ".04", ".05"];
  const bw = plotW / 5;
  const y = (pct) => padT + plotH * (1 - pct / ymax);
  return (
    <svg className="pcurve-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="p-curve of significant p-values">
      <line x1={padL} y1={y(20)} x2={W - 10} y2={y(20)} className="pcurve-null" strokeDasharray="4 3" />
      <text x={W - 12} y={y(20) - 3} className="pcurve-null-label" textAnchor="end">null (20%)</text>
      {bins.map((pct, i) => {
        const bx = padL + i * bw + bw * 0.18;
        return (
          <g key={i}>
            <rect className="pcurve-bar" x={bx} y={y(pct)} width={bw * 0.64} height={Math.max(0, padT + plotH - y(pct))} />
            <text className="pcurve-axis" x={padL + i * bw + bw / 2} y={H - 14} textAnchor="middle">{labels[i]}</text>
            <text className="pcurve-pct" x={padL + i * bw + bw / 2} y={y(pct) - 3} textAnchor="middle">{Math.round(pct)}%</text>
          </g>
        );
      })}
      <text className="pcurve-axis-title" x={padL} y={H - 2}>reported p-value (significant only)</text>
    </svg>
  );
}

function PcurveModal({ paperIds, onClose, onOpenPaper, onChanged }) {
  const [state, setState] = useState({ status: "running" }); // running | done | error
  const pollRef = useRef(null);

  useEffect(() => {
    let live = true;
    const poll = (jobId) => api(`/methods/pcurve/run/${jobId}`).then(r => {
      if (!live) return;
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") setState({ status: "done", result: d.result });
      else if (d.status === "error") setState({ status: "error", error: d.detail || "p-curve failed." });
      else pollRef.current = setTimeout(() => poll(jobId), 1200);
    });
    apiPost("/methods/pcurve/run", { paper_ids: paperIds }).then(r => {
      if (!live) return;
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      poll(r.data.job_id);
    });
    return () => { live = false; if (pollRef.current) clearTimeout(pollRef.current); };
  }, [paperIds]);

  const r = state.result;
  const sig = !!(r && r.right_skew_p != null && r.right_skew_p < 0.05);
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal pcurve-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>p-curve · evidential value</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>

        <div className="pcurve-framing">
          A <b>collection-level</b> check over your selected papers: is the distribution of significant p-values
          right-skewed (consistent with evidential value) or flat? <b>The curve is yours to interpret — it is not a
          verdict, and it never describes any single paper or author.</b>
        </div>

        {state.status === "running" && <ProgressBar label="Extracting and analysing p-values…" />}
        {state.status === "error" &&
          <div className="errbox" style={{ margin: "12px 0 0" }}><b>p-curve could not run.</b><br />{state.error}</div>}

        {state.status === "done" && r &&
          <>
            <div className="pcurve-note">{r.note}</div>
            {r.k_significant > 0 &&
              <>
                {r.low_power &&
                  <div className="pcurve-warn">⚠ Only {r.k_significant} significant result{r.k_significant === 1 ? "" : "s"} — too few to interpret a p-curve reliably (≥ 5 recommended).</div>}
                <PcurvePlot bins={r.bins} />
                <div className="pcurve-stats">
                  <div className={"pcurve-stat" + (sig ? " pos" : "")}>
                    <span className="k">Right-skew test</span>
                    <span className="v">Z = {r.right_skew_z.toFixed(2)} · p = {fmtPval(r.right_skew_p)}</span>
                    <span className="d">{sig ? "significantly right-skewed — consistent with evidential value" : "not significantly right-skewed"}</span>
                  </div>
                  <div className="pcurve-stat">
                    <span className="k">Binomial (share p &lt; .025)</span>
                    <span className="v">p = {fmtPval(r.binomial_p)}</span>
                  </div>
                </div>
                <details className="pcurve-included">
                  <summary>{r.included_tests.length} included tests · {r.n_papers} papers</summary>
                  {r.included_tests.map((t, i) => (
                    <button key={i} className="pcurve-test" title={t.page != null ? "Open page " + t.page : ""}
                      onClick={() => t.page != null && onOpenPaper && onOpenPaper({ id: t.paper_id, title: "" }, { page: t.page, precision: "region" })}>
                      <span className="pcurve-test-raw">{t.raw}</span>
                      <span className="pcurve-test-p">p = {t.p}</span>
                    </button>
                  ))}
                </details>
              </>}
            <div className="pcurve-coverage">
              Coverage: p-curve reads only inline APA-style NHST tests with exact statistics (tables, Bayesian, and
              CI-only reporting are invisible); it includes every extracted significant test rather than each
              study's chosen focal test, and conservatively drops results so significant their p rounds to ≈0. Run
              it on a small, curated set for the most meaningful curve.
            </div>
          </>}

        <div className="method-credit">
          <b>Method:</b> p-curve — Simonsohn, Nelson &amp; Simmons (2014), <i>J. Exp. Psychol. Gen.</i> 143(2):534–547.{" "}
          <MethodCreditButton items={[SNS2014_CSL]} onChanged={onChanged} />
          <div className="method-credit-sub">
            Re-implemented in Python; reference implementation: <i>scrutiny</i> (Lukas Jung). Surfaced via D. Lakens'
            automated-review catalog.
          </div>
        </div>
      </div>
    </div>
  );
}
