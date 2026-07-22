// inc 241/243: Bayesian auditor — recompute reported default Bayes factors for a paper's inline t-test (JZS, Rouder
// et al. 2009) and Pearson-correlation (Ly et al. 2016) BFs. The deterministic sibling of statcheck: read the paper's
// extracted text, recompute the default BF10 from each `t(df) = …, BF10 = …` / `r(df) = …, BF10 = …`, and flag where
// it doesn't reproduce under the default prior. Local, no AI, no egress. A signal, never a verdict; never an
// accusation (a mismatch is most often a different prior, which the text doesn't reveal). See methods/bayes.py.

// inc 241/243 (credit-the-lineage): the source papers, one-click added to the library (matches statcheck/GRIM/p-curve).
const BAYES_CSL = [
  {
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
    volume: "16", issue: "2", page: "225-237",
    issued: { "date-parts": [[2009]] },
    DOI: "10.3758/PBR.16.2.225",
  },
  {
    type: "article-journal",
    title: "Harold Jeffreys's default Bayes factor hypothesis tests: Explanation, extension, and application in psychology",
    author: [
      { family: "Ly", given: "Alexander" },
      { family: "Verhagen", given: "Josine" },
      { family: "Wagenmakers", given: "Eric-Jan" },
    ],
    "container-title": "Journal of Mathematical Psychology",
    volume: "72", page: "19-32",
    issued: { "date-parts": [[2016]] },
    DOI: "10.1016/j.jmp.2015.06.004",
  },
];

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
  const open = (evidence, key) => {
    if (!onOpenPaper) return;
    const title = meta ? meta.title : "";
    const target = methodEvidenceTarget(paperId, title, evidence, key);
    if (target) onOpenPaper({ id: paperId, title }, target);
  };
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
      {state.status === "done" && d && ((d.checked === 0 && !(d.completeness && d.completeness.is_bayesian))
        ? <div className="tag-suggest-empty">This paper doesn't appear to report a Bayesian analysis — nothing to recompute or check.</div>
        : <div className="statcheck-result">
            {d.checked === 0
              ? <div className="tag-suggest-empty">No inline t-test or correlation Bayes factors to recompute (the paper still reports Bayesian analysis — see the reporting checklist below).</div>
              : <>
                  <div className="statcheck-summary">{d.checked} checked · {d.not_reproduced} couldn't reproduce under the default prior</div>
                  <div className="statcheck-list">
                    {d.results.map((r, i) => (
                      <div key={i} className={"statcheck-item" + (r.consistency !== "reproduced" ? " flagged-row" : "")}>
                        <button type="button" className="statcheck-item-main"
                          title={r.page != null ? (r.coordinate_precision === "exact" ? "Open and highlight this Bayes-factor report" : "Open page " + r.page) : ""}
                          onClick={() => open(r, `bayes:${paperId}:${i}`)}>
                          <EvidenceQuote text={r.raw} match={r.raw} label="Reported result"
                            precision={r.coordinate_precision} hasSourcePage={r.page != null}
                            className="statcheck-context" maxChars={220} />
                          <span className="statcheck-computed">reported BF₁₀ = {r.reported_bf10} · recomputed {reBfLabel(r)}</span>
                          <span className={"cite-status " + (r.consistency === "reproduced" ? "verified" : "flagged")}>{r.consistency === "reproduced" ? "reproduces" : "couldn't reproduce"}</span>
                        </button>
                        <EvidenceTrail detector="Bayesian statistics" matched={r.raw} precision={r.coordinate_precision}
                          hasSourcePage={r.page != null} page={r.page}
                          caveat="Recomputed under default-prior assumptions; mismatch is a prompt to inspect, not an error verdict." />
                      </div>
                    ))}
                  </div>
                  <div className="statcheck-caveat">
                    Recomputed under each test's <b>default prior</b> — the JZS prior (Cauchy scale r ≈ {d.prior_scale}) for a t-test (under both a paired and a two-sample reading), or the default correlation prior (Ly et al. 2016) for an <code>r(df)</code>. A Bayes factor “reproduces” if it matches within a factor of ~2. If the paper used a different prior or a design we can't read (e.g. ANOVA), a mismatch is expected — a prompt to look, not a verdict or an accusation. It reads only inline t-test / correlation BFs, so a clean result isn't a clean bill.
                  </div>
                </>}
            {d.completeness && d.completeness.is_bayesian && <BayesChecklist items={d.completeness.items} onOpen={open} />}
            {d.completeness && d.completeness.advisories && d.completeness.advisories.length > 0 &&
              <BayesAdvisories notes={d.completeness.advisories} onOpen={open} />}
            <BayesCredit />
          </div>)}
    </div>
  );
}

// SP4: Tier-3 advisory prompts — clearly demarcated from the Tier-1/Tier-2 flags; exploratory, requires expert judgment.
function BayesAdvisories({ notes, onOpen }) {
  return (
    <div className="bayes-advisory">
      <p className="eyebrow">Advisory — requires expert judgment</p>
      {notes.map((a, i) => (
        <div key={i} className="bayes-advisory-item">
          <div><span className="bayes-advisory-label">{a.label}:</span> {a.note}.</div>
          {a.evidence &&
            <EvidenceQuote text={a.evidence} match={a.evidence} label="Evidence" className="bayes-check-ev"
              precision={a.coordinate_precision} hasSourcePage={a.page != null}
              onOpen={a.page != null ? () => onOpen(a, `bayes-advisory:${a.key}:${i}`) : null}
              openLabel={a.coordinate_precision === "exact" ? "Open and highlight this advisory evidence" : "Open source page for this advisory evidence"} />}
          {a.evidence && <EvidenceTrail detector="Bayesian advisory" matched={a.evidence}
            precision={a.coordinate_precision} hasSourcePage={a.page != null} page={a.page}
            caveat="Advisory prompts require expert judgment and do not change review state." />}
        </div>
      ))}
      <div className="statcheck-caveat">
        Exploratory prompts, not verdicts or flags — the text merely *suggests* a possible mislabel; a human should confirm. Deliberately conservative (many are false alarms).
      </div>
    </div>
  );
}

// SP2: the Tier-2 reporting checklist (BARG / WAMBS / JASP) — presence/absence + a coherence flag, never a verdict.
function BayesChecklist({ items, onOpen }) {
  if (!items || !items.length) return null;
  return (
    <div className="bayes-checklist">
      <p className="eyebrow">Reporting checklist</p>
      {items.map((it) => (
        <div key={it.key} className={"bayes-check-item" + (it.status === "coherence-flag" ? " flagged-row" : "")}>
          <div className="bayes-check-head">
            <span className="bayes-check-label">{it.label}</span>
            {it.status === "present"
              ? <span className="cite-status verified">✓ present</span>
              : it.status === "coherence-flag"
                ? <span className="cite-status flagged">⚠ check</span>
                : <span className="bayes-check-muted">{it.status === "not-applicable" ? "n/a" : "not found"}</span>}
          </div>
          {it.note && <div className="bayes-check-note">{it.note}</div>}
          {it.evidence &&
            <EvidenceQuote text={it.evidence} match={it.evidence} label="Evidence" className="bayes-check-ev"
              precision={it.coordinate_precision} hasSourcePage={it.page != null}
              onOpen={it.page != null ? () => onOpen(it, `bayes-check:${it.key}`) : null}
              openLabel={it.coordinate_precision === "exact" ? "Open and highlight this checklist evidence" : "Open source page for this checklist evidence"} />}
          {it.evidence && <EvidenceTrail detector="Bayesian reporting checklist" matched={it.evidence}
            precision={it.coordinate_precision} hasSourcePage={it.page != null} page={it.page}
            caveat="Checklist presence/absence is text detection only; not found means not detected in extracted text." />}
        </div>
      ))}
      <div className="statcheck-caveat">
        A completeness prompt from the Bayesian reporting guidelines (BARG — Kruschke 2021; WAMBS — Depaoli &amp; van de Schoot 2017; the JASP guidelines — van Doorn et al. 2021): presence/absence in the text, never a verdict. It runs only on a Bayesian paper; <b>“not found” means not detected in the extracted text</b> — tables aren't read, so check the paper. Thresholds (R-hat &lt; 1.1, ESS &gt; 400) are cited conventions, not laws.
      </div>
    </div>
  );
}

// "recomputed" label: show the interpretation that reproduced it, else the candidate value(s).
function reBfLabel(r) {
  const byDesign = { paired: r.computed_paired, "two-sample": r.computed_two_sample, correlation: r.computed_correlation };
  if (r.consistency === "reproduced" && r.matched_design && byDesign[r.matched_design] != null) {
    return `${byDesign[r.matched_design]} (${r.matched_design})`;
  }
  const parts = [];
  if (r.computed_paired != null) parts.push(`${r.computed_paired} (paired)`);
  if (r.computed_two_sample != null) parts.push(`${r.computed_two_sample} (two-sample)`);
  if (r.computed_correlation != null) parts.push(`${r.computed_correlation} (correlation)`);
  return parts.join(" / ") || "—";
}

function BayesCredit() {
  return (
    <div className="method-credit">
      <b>Methods:</b> the default JZS t-test Bayes factor — Rouder, Speckman, Sun, Morey &amp; Iverson (2009), <i>Psychonomic Bulletin &amp; Review</i> 16(2):225–237; and the default correlation Bayes factor — Ly, Verhagen &amp; Wagenmakers (2016), <i>Journal of Mathematical Psychology</i> 72:19–32.{" "}
      <MethodCreditButton items={BAYES_CSL} />
      <div className="method-credit-sub">Re-implemented in Python (the closed forms JASP / the <i>BayesFactor</i> R package [Morey &amp; Rouder] use) — credited, not reused. Surfaced via D. Lakens' automated-review catalog.</div>
    </div>
  );
}

// backlog #23 (F1): whole-library batch — mirrors LmmLibrary/MetaLibrary/TransparencyLibrary. Persists a
// per-paper #23 signal via the shared apply_bayes (methods/bayes.py), so the header chip + GET /papers?signal=
// bayes-flagged stay current even for papers nobody has opened this panel for yet.
function BayesLibrary({ onShowFlagged, onRan }) {
  const [run, setRun] = useState({ status: "idle" });
  const start = async () => {
    setRun({ status: "running" });
    const poll = (jobId) => api(`/methods/bayes/run/${jobId}`).then(r => {
      if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setRun({ status: "done", summary: d.summary }); if (onRan) onRan(); }
      else if (d.status === "error") setRun({ status: "error", error: d.detail || "Audit failed." });
      else setTimeout(() => poll(jobId), 1500);
    });
    const r = await apiPost("/methods/bayes/run", {});
    if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  const s = run.summary;
  return (
    <div className="statcheck-lib">
      <div className="settings-sub">Audit Bayesian statistics across your whole library — local, no AI. Papers where a Bayes factor didn't reproduce, or the reporting checklist found a gap, appear below, filterable from the library header.</div>
      <div className="settings-actions">
        <button className="btn btn-primary" disabled={run.status === "running"} onClick={start}>
          {run.status === "running" ? "Auditing…" : "Audit all papers"}
        </button>
      </div>
      {run.status === "running" && <ProgressBar label="Auditing Bayesian statistics…" />}
      {run.status === "error" && <div className="settings-note settings-note-err">Audit failed: {run.error}</div>}
      {run.status === "done" && s &&
        <div className="settings-note">
          {s.total} paper{s.total === 1 ? "" : "s"} checked · <b>{s.detected}</b> detectably Bayesian
          {s.flagged > 0 && onShowFlagged && <React.Fragment>{" "}· <button className="btn-link" onClick={onShowFlagged}>{s.flagged} flagged</button></React.Fragment>}
          {s.flagged === 0 && s.detected > 0 && <React.Fragment> · 0 flagged</React.Fragment>}
        </div>}
    </div>
  );
}

function BayesSection({ ctx, active }) {
  return (
    <div className="statcheck-section">
      <div className="settings-sub">Recompute a paper's reported <b>default Bayes factors</b> for inline t-test and correlation results — the Bayesian analogue of statcheck. Local, no AI. It flags where a reported BF₁₀ doesn't reproduce under the standard default prior; usually a different prior, not an error — a prompt to look, never a verdict.</div>
      <p className="eyebrow">Whole library</p>
      <BayesLibrary onShowFlagged={ctx.onShowBayesFlagged} onRan={ctx.onBayesRan} />
      <p className="eyebrow">This paper</p>
      <BayesPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper} active={active} />
    </div>
  );
}

// Part of the Checklists 2x2-grid tab group (order 30 -> bottom-left) — see 08h_methods_transparency.jsx for the
// registerPaneTab/active-prop rationale shared by all four checklist tools.
registerPaneTab(
  { id: "checklists", label: "Checklists", paneId: "methods", order: 40 },
  {
    id: "bayes", label: "Bayesian statistics", order: 30, hideInReadOnly: true,
    render: (ctx, active) => <BayesSection ctx={ctx} active={active} />,
  },
);
