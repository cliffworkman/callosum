// inc 163: honest "Coming soon" scaffolds for the THEORY/METHODS accordion — a visible roadmap of genuinely
// planned (backlog-tracked) sections + subsection tabs. Each names a real future capability, is placed by
// COGNITIVE TASK (DESIGN.md §5), and bakes in the principle framing it will ship with (signal-not-verdict,
// never accusation) so the roadmap itself coheres to the charter. The stubs are INERT (no controls, no data) —
// "silence is not a certificate": a placeholder honestly signals incomplete work, it never fakes a result.
//
// Loads at 09 (after the registry at 05 and the METHODS sections at 06–08), so it can append a tab to the
// existing Statistics-check section; THEORY sections it just find-or-creates (registerPaneTab, inc 121/139).

function ComingSoon({ title, body, builds }) {
  return (
    <div className="coming-soon">
      <span className="coming-soon-badge">Coming soon</span>
      <p className="coming-soon-title">{title}</p>
      <p className="coming-soon-body">{body}</p>
      {builds && <p className="coming-soon-builds">{builds}</p>}
    </div>
  );
}

// NB: the THEORY → Discover placeholder (Beyond library / Feed / Search tabs) was removed in inc 205 — the real
// Discover/Search (inc 184) + Feed (inc 188) shipped as center-pane tabs in the library frame (30c_frame.jsx), which
// is their home; per the inc-163 convention, a stub is dropped in the increment its real feature lands.

// ── METHODS: future evaluation modules (after Review @40), ordered by cognitive task (DESIGN.md §5).
registerPaneSection({
  id: "lmm", label: "Mixed-model reporting", paneId: "methods", order: 50,
  render: () => <ComingSoon
    title="A reader's checklist for mixed-model (LMM) papers"
    body="Flags what to look for in a mixed-model paper — random-effects structure, df method, convergence, REML vs ML, ICC/R², missing-data sensitivity — read from the reported text. It tells you what to check; it never runs a model."
    builds="A consumer-side reporting auditor. (Backlog #23)" />,
});
registerPaneSection({
  id: "bayesian", label: "Bayesian statistics", paneId: "methods", order: 60,
  render: () => <ComingSoon
    title="Recompute Bayes factors + audit completeness"
    body="Recompute default Bayes factors for canonical designs (t / F / r + N) and audit reporting completeness. A signal to inspect — never a 'BF > 3 = significant' verdict."
    builds="A deterministic recompute + completeness pass. (Backlog #24)" />,
});
registerPaneSection({
  id: "meta-analysis", label: "Meta-analysis", paneId: "methods", order: 70,
  render: () => <ComingSoon
    title="Surface a meta-analysis's choices"
    body="Extract and structure a meta-analysis's effect sizes, model, heterogeneity, and sensitivity choices so you can inspect them. It extracts and structures — it never pools, models, or adjudicates."
    builds="An extraction/structuring aid, never a re-analysis. (Backlog #37)" />,
});
registerPaneSection({
  id: "citation-equity", label: "Citation equity", paneId: "methods", order: 80,
  render: () => <ComingSoon
    title="A structural look at the reference list"
    body="An identity-agnostic, structural audit of a paper's references — self-citation, source concentration, topical gaps, overlooked work — to inform, with add-only 'overlooked work' remediation. Descriptive, never an accusation about anyone."
    builds="Structural + topical, identity-agnostic. (Backlog #25)" />,
});

// ── METHODS: a subsection TAB on the shipped Statistics-check section (DESIGN.md §5: more stat checks become
// tabs, not new sections). registerPaneTab find-or-creates by id, so this appends to the inc-122 statcheck
// section without touching 06_methods_statcheck.jsx; the section then shows a [Statistics check | More checks] strip.
registerPaneTab(
  { id: "statcheck", label: "Statistics check", paneId: "methods", order: 30 },
  {
    id: "statcheck-more", label: "More checks", order: 20,
    render: () => <ComingSoon
      title="More test forms + p-curve, here"
      body="Additional NHST forms (test-statistic comparisons, results reported in tables) and the collection-level p-curve will live alongside statcheck."
      builds="Extends the inc-95 statcheck engine. (Backlog #27)" />,
  },
);
