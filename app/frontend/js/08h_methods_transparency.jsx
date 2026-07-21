// inc 250 (#44 increment 1): transparency-signals auditor — read a paper's extracted text and detect whether it
// *discloses* 7 open-science artifacts (ODDPub/rtransparent-derived): data availability, code availability,
// conflict-of-interest, funding, protocol/trial registration, preregistration, and an "available upon request"
// weak-signal qualifier. FLAG-not-ADJUDICATE: each present / not-found / n/a — never a verdict, never a score, never
// an accusation. "not found" ≠ "absent" (silence≠certificate). Local, rule-based, no AI, no egress. The deterministic
// sibling of statcheck / the LMM / meta-analysis auditors. See methods/transparency.py.

// inc 250 (credit-the-lineage): the detector lineage, one-click added to the library (statcheck/lmm/meta pattern).
// DOIs are included only where confidently known — a missing DOI over a wrong one (import dedups on title+year+author).
const TRANSPARENCY_CSL = [
  {
    type: "article-journal",
    title: "ODDPub — a text-mining algorithm to detect data sharing in biomedical publications",
    author: [
      { family: "Riedel", given: "Nico" },
      { family: "Kip", given: "Miriam" },
      { family: "Bobrov", given: "Evgeny" },
    ],
    "container-title": "Data Science Journal",
    volume: "19", page: "42",
    issued: { "date-parts": [[2020]] },
    DOI: "10.5334/dsj-2020-042",
  },
  {
    type: "article-journal",
    title: "Assessment of transparency indicators across the biomedical literature: How open is open?",
    author: [
      { family: "Serghiou", given: "Stylianos" },
      { family: "Contopoulos-Ioannidis", given: "Despina G." },
      { family: "Boyack", given: "Kevin W." },
      { family: "Riedel", given: "Nico" },
      { family: "Wallach", given: "Joshua D." },
      { family: "Ioannidis", given: "John P. A." },
    ],
    "container-title": "PLOS Biology",
    volume: "19", issue: "3", page: "e3001107",
    issued: { "date-parts": [[2021]] },
    DOI: "10.1371/journal.pbio.3001107",
  },
  {
    type: "article-journal",
    title: "The preregistration revolution",
    author: [
      { family: "Nosek", given: "Brian A." },
      { family: "Ebersole", given: "Charles R." },
      { family: "DeHaven", given: "Alexander C." },
      { family: "Mellor", given: "David T." },
    ],
    "container-title": "Proceedings of the National Academy of Sciences",
    volume: "115", issue: "11", page: "2600-2606",
    issued: { "date-parts": [[2018]] },
    DOI: "10.1073/pnas.1708274114",
  },
];

// Per-paper audit. The section gets only the paper id via ctx, so it self-fetches title + chunk_count. Auto-runs
// when its section is the open one (like statcheck / the LMM / meta auditors).
function TransparencyPaper({ paperId, onOpenPaper, active }) {
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
    const r = await api(`/papers/${paperId}/transparency`);
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
  if (paperId == null) return <div className="tag-suggest-empty">Select a paper to check its transparency disclosures.</div>;
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
            ? <button className="btn-link" title="Detect this paper's open-science disclosures — local, no AI" onClick={run}>Check disclosures</button>
            : null}
      {state.status === "running" && <span className="tag-suggest-empty">checking…</span>}
      {state.status === "error" && <div className="axis-err">Couldn't check: {state.error}</div>}
      {state.status === "done" && d && <TransparencyChecklist checks={d.checks} onOpen={open} />}
    </div>
  );
}

function TransparencyChecklist({ checks, onOpen }) {
  if (!checks || !checks.length) return null;
  const present = checks.filter(c => c.status === "present").length;
  const notFound = checks.filter(c => c.status === "not-found").length;
  const na = checks.filter(c => c.status === "not-applicable").length;
  return (
    <div className="bayes-checklist">
      <p className="eyebrow">Open-science disclosures</p>
      {/* A factual tally of the statuses below — not a score or a grade. */}
      <div className="lmm-summary">{present} disclosed · {notFound} not detected · {na} not applicable · {checks.length} checks</div>
      {checks.map((c) => (
        <div key={c.key} className={"bayes-check-item" + (c.status === "not-applicable" ? " lmm-na" : "")}>
          <div className="bayes-check-head">
            <span className="bayes-check-label">{c.label}</span>
            {c.status === "present"
              ? <span className="cite-status verified">✓ detected</span>
              : <span className="bayes-check-muted">{c.status === "not-applicable" ? "n/a" : "not detected"}</span>}
          </div>
          {c.note && <div className="bayes-check-note">{c.note}</div>}
          {c.explainer && <div className="lmm-explainer">{c.explainer}</div>}
          {c.basis && <div className="lmm-basis">basis: {c.basis}</div>}
          {c.evidence &&
            <EvidenceQuote text={c.evidence} match={c.evidence} label="Evidence" className="bayes-check-ev"
              precision={c.coordinate_precision} hasSourcePage={c.page != null}
              onOpen={c.page != null ? () => onOpen(c, `transparency-check:${c.key}`) : null}
              openLabel={c.coordinate_precision === "exact" ? "Open and highlight this disclosure evidence" : "Open source page for this disclosure evidence"} />}
          {c.evidence && <EvidenceTrail detector="Transparency signals" matched={c.evidence}
            precision={c.coordinate_precision} hasSourcePage={c.page != null} page={c.page}
            caveat="Disclosure signals are text detections only; not detected does not mean absent." />}
        </div>
      ))}
      <div className="statcheck-caveat">
        Detects <b>reported disclosures</b> in the extracted text — it does not judge a paper's openness. <b>“Not detected” means not found in the text, NOT that the artifact is absent</b> — a data-availability statement can live in an appendix, a footnote, or the journal's structured metadata this reader doesn't fully see. It's a prompt to look, never a score, and never an accusation of the authors. “Available upon request” is shown as a weaker signal than an open link, not a concern in itself.
      </div>
    </div>
  );
}

function TransparencyCredit() {
  return (
    <div className="method-credit">
      <b>Detectors:</b> data &amp; code availability — ODDPub (Riedel et al. 2020); conflict-of-interest, funding &amp; registration indicators — rtransparent (Serghiou et al. 2021); preregistration — Nosek et al. (2018).{" "}
      <MethodCreditButton items={TRANSPARENCY_CSL} />
      <div className="method-credit-sub">A reading aid — a rule-based text detector, never a transparency score or a judgment of the authors. Surfaced via D. Lakens' automated-review catalog.</div>
    </div>
  );
}

// inc 251: batch-detect transparency signals across the whole library, then jump to a review queue. The queues are
// "not detected — go look", never "papers that hide their data" (the A-A no-accusation boundary).
function TransparencyLibrary({ onReview, onRan }) {
  const [run, setRun] = useState({ status: "idle" });  // idle | running | done | error
  const start = async () => {
    setRun({ status: "running" });
    const poll = (jobId) => api(`/methods/transparency/run/${jobId}`).then(r => {
      if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setRun({ status: "done", summary: d.summary }); if (onRan) onRan(); }
      else if (d.status === "error") setRun({ status: "error", error: d.detail || "Detection failed." });
      else setTimeout(() => poll(jobId), 1500);
    });
    const r = await apiPost("/methods/transparency/run", {});
    if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  const s = run.summary;
  return (
    <div className="statcheck-lib">
      <div className="settings-sub">Detect open-science disclosures across your whole library — local, no AI. Present disclosures become evidence-carrying marks in each paper's Review section; the review queues below list papers where the auditor <i>didn't</i> detect a disclosure in the text (it may still share elsewhere — a prompt to look, never a claim it hides anything).</div>
      <div className="settings-actions">
        <button className="btn btn-primary" disabled={run.status === "running"} onClick={start}>
          {run.status === "running" ? "Detecting…" : "Check all papers"}
        </button>
      </div>
      {run.status === "running" && <ProgressBar label="Detecting transparency signals…" />}
      {run.status === "error" && <div className="settings-note settings-note-err">Detection failed: {run.error}</div>}
      {run.status === "done" && s &&
        <div className="settings-note">
          {s.total} paper{s.total === 1 ? "" : "s"} checked · <b>{s.with_disclosures}</b> with ≥1 disclosure detected.
          {onReview && <div className="transparency-queues">
            Review queues (not detected in the text — go look):{" "}
            {TRANSPARENCY_QUEUES.map((q, i) => (
              <React.Fragment key={q.key}>
                {i > 0 && " · "}
                <button className="btn-link" onClick={() => onReview(q.key)}>{q.label}</button>
              </React.Fragment>
            ))}
          </div>}
        </div>}
    </div>
  );
}

// The 7 review-queue signal keys (repository.SIGNAL_FILTERS). Registration is a `not-detected` queue (n/a papers are
// excluded upstream — precondition scoping); upon-request is the PRESENT case (a weaker-openness prompt, not an absence).
const TRANSPARENCY_QUEUES = [
  { key: "transparency-data-not-detected", label: "data" },
  { key: "transparency-code-not-detected", label: "code" },
  { key: "transparency-coi-not-detected", label: "COI" },
  { key: "transparency-funding-not-detected", label: "funding" },
  { key: "transparency-registration-not-detected", label: "registration" },
  { key: "transparency-preregistration-not-detected", label: "preregistration" },
  { key: "transparency-upon-request", label: "available upon request" },
];

function TransparencySection({ ctx, active }) {
  return (
    <div className="statcheck-section">
      <div className="settings-sub">Detect a paper's <b>open-science disclosures</b> — does it state where the data &amp; code live, declare conflicts of interest &amp; funding, and (for a trial/review) report a registration or preregistration? Local, no AI, rule-based. It surfaces what's <i>reported</i>, with the matched sentence — never a transparency score, and “not detected” never means the artifact is absent.</div>
      <p className="eyebrow">Whole library</p>
      <TransparencyLibrary onReview={ctx.onShowTransparencyReview} onRan={ctx.onTransparencyRan} />
      <p className="eyebrow">This paper</p>
      <TransparencyPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper} active={active} />
      <TransparencyCredit />
    </div>
  );
}

// Part of the Checklists 2x2-grid tab group (order 10 -> top-left) — 05_panes.jsx's registerPaneTab find-or-creates
// the "checklists" host regardless of which of its 4 sibling files loads first, as long as they agree on its
// metadata (label/paneId/order). `active` now arrives as a real prop (section open AND this tab selected) rather
// than derived from ctx.methodsOpen, which only ever reflected the open SECTION id, not the active tab within it.
registerPaneTab(
  { id: "checklists", label: "Checklists", paneId: "methods", order: 40 },
  {
    id: "transparency", label: "Transparency signals", order: 10, hideInReadOnly: true,
    render: (ctx, active) => <TransparencySection ctx={ctx} active={active} />,
  },
);
