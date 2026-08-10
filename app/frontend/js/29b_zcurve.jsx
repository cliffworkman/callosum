// inc 470: z-curve — a COLLECTION-LEVEL expected-replication/discovery-rate estimate over the SELECTED papers.
// Sibling to p-curve (29_pcurve.jsx): same async job / poll / statcheck-extraction pattern, its own modal (not a
// tab inside PcurveModal) since the bootstrap fit is heavier work. EDR/ERR are RATE estimates — more tempting to
// misread as describing the specific selected studies than p-curve's abstract right-skew statistic — so this
// always shows the CI beside the point estimate and never breaks the numbers down by paper or author.

// Bundled CSL-JSON for the source paper, added to the library via the inc-93 import path (credit-the-lineage).
const BS2022_CSL = {
  type: "article-journal",
  title: "Z-curve 2.0: Estimating replication rates and discovery rates",
  author: [
    { family: "Bartoš", given: "František" },
    { family: "Schimmack", given: "Ulrich" },
  ],
  "container-title": "Meta-Psychology",
  volume: "6",
  issued: { "date-parts": [[2022]] },
  DOI: "10.15626/MP.2021.2720",
};

function fmtPct(x) {
  if (x == null) return "—";
  return Math.round(x * 100) + "%";
}

function fmtCI(ci) {
  if (!ci) return null;
  return `95% CI [${Math.round(ci[0] * 100)}–${Math.round(ci[1] * 100)}%]`;
}

function ZcurveStat({ label, value, ci, hint }) {
  return (
    <div className="pcurve-stat">
      <span className="k">{label}</span>
      <span className="v">{fmtPct(value)}{ci && <span className="zcurve-ci"> · {fmtCI(ci)}</span>}</span>
      {hint && <span className="d">{hint}</span>}
    </div>
  );
}

function ZcurveModal({ paperIds, onClose, onOpenPaper, onChanged }) {
  const [state, setState] = useState({ status: "running" }); // running | done | error
  const pollRef = useRef(null);

  useEffect(() => {
    let live = true;
    const poll = (jobId) => api(`/methods/zcurve/run/${jobId}`).then(r => {
      if (!live) return;
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") setState({ status: "done", result: d.result });
      else if (d.status === "error") setState({ status: "error", error: d.detail || "z-curve failed." });
      else pollRef.current = setTimeout(() => poll(jobId), 1200);
    });
    apiPost("/methods/zcurve/run", { paper_ids: paperIds }).then(r => {
      if (!live) return;
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      poll(r.data.job_id);
    });
    return () => { live = false; if (pollRef.current) clearTimeout(pollRef.current); };
  }, [paperIds]);

  const r = state.result;
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal pcurve-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>z-curve · expected replication &amp; discovery rate</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>

        <div className="pcurve-framing">
          A <b>collection-level</b> estimate over your selected papers' significant results: EDR estimates what
          share of <i>all</i> conducted tests would be significant; ERR estimates how often the significant ones
          would replicate. <b>Never a score for these specific papers or their authors — an estimate about the
          assembled set, with real uncertainty.</b>
        </div>

        {state.status === "running" && <ProgressBar label="Extracting results and fitting the z-curve model…" managedBy="backend-job" />}
        {state.status === "error" &&
          <div className="errbox" style={{ margin: "12px 0 0" }}><b>z-curve could not run.</b><br />{state.error}</div>}

        {state.status === "done" && r &&
          <>
            <div className="pcurve-note">{r.note}</div>
            {r.k_significant > 0 &&
              <>
                {r.low_reliability &&
                  <div className="zcurve-reliability-warn">
                    ⚠ Only {r.k_significant} significant result{r.k_significant === 1 ? "" : "s"} — z-curve needs
                    at least 300 for a reliable estimate. Treat EDR/ERR below as exploratory, not stable.
                  </div>}
                <div className="pcurve-stats">
                  <ZcurveStat label="EDR (expected discovery rate)" value={r.edr} ci={r.edr_ci}
                    hint={r.odr != null ? `observed discovery rate: ${fmtPct(r.odr)}` : null} />
                  <ZcurveStat label="ERR (expected replication rate)" value={r.err} ci={r.err_ci} />
                  {r.z0 != null &&
                    <div className="pcurve-stat">
                      <span className="k">Estimated null-component share</span>
                      <span className="v">{fmtPct(r.z0)}</span>
                      <span className="d">share of significant results the model attributes to true-null components</span>
                    </div>}
                </div>
                <details className="pcurve-included">
                  <summary>{r.included_tests.length} included tests · {r.n_papers} papers</summary>
                  {r.included_tests.map((t, i) => (
                    <button key={i} className="pcurve-test" title={t.page != null ? "Open page " + t.page : ""}
                      onClick={() => t.page != null && onOpenPaper && onOpenPaper({ id: t.paper_id, title: "" }, { page: t.page, precision: "region" })}>
                      <span className="pcurve-test-raw">{t.raw}</span>
                      <span className="pcurve-test-p">z = {t.z.toFixed(2)}</span>
                    </button>
                  ))}
                </details>
              </>}
            <div className="pcurve-coverage">
              Coverage: z-curve reads only inline APA-style NHST tests with exact statistics (tables, Bayesian, and
              CI-only reporting are invisible); it includes every extracted significant test rather than each
              study's chosen focal statistic. Run it on a large, curated set for the most meaningful estimate.
            </div>
          </>}

        <div className="method-credit">
          <b>Method:</b> z-curve 2.0 — Bartoš &amp; Schimmack (2022), <i>Meta-Psychology</i> 6, MP.2021.2720.{" "}
          <MethodCreditButton items={[BS2022_CSL]} onChanged={onChanged} />
          <div className="method-credit-sub">
            Re-implemented in Python; reference implementation: <i>zcurve</i> (František Bartoš).
          </div>
          <LakensCredit />
        </div>
      </div>
    </div>
  );
}
