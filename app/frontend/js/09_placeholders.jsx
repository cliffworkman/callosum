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

// ── METHODS: NB — the "Mixed-model reporting" (real: inc 247, 08f) + "Bayesian statistics" (real: inc 241, 08d)
// stubs were removed in inc 248, and the "Meta-analysis" stub in inc 249 (real: 08g_methods_metaanalysis.jsx, the
// consumer-side reporting auditor, order 35 among the real tools) — per the inc-163 convention a stub is dropped in
// the increment its real feature lands. (The producer-side extraction workbench, the full #36 future-track, is next.)
// NB: the METHODS → Citation-equity placeholder was removed in inc 227 — the real structural audit shipped
// (08b_methods_citation_equity.jsx, order 35, among the real tools); per the inc-163 convention a stub is dropped
// in the increment its feature lands. (The SP2 topical "overlooked work" remediation is the remaining backlog #25.)

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
