// inc 246 (#40 SP1b): the "Where to submit" METHODS section — from an abstract, a uniform, fully-sourced factual
// profile per candidate journal (fit / OA color / APC+waiver / license / DOAJ Seal / open impact / legitimacy),
// ranked by local fit + an open-science weighting the user sets. It surfaces facts and lets the author weigh them;
// it NEVER computes a verdict — no composite score, no "predatory" label, every candidate shown (closed too),
// elevation underscores goods a journal offers (never flags the others). The abstract is embedded locally by the
// backend (topic-seeded pool); the weighting is a LOCAL pref, never transmitted. First-use choice gate: no output
// until the user actively sets BOTH the weighting AND the result breadth (neither pre-selected), so the weighting is
// one forced choice among peers. The results view always shows the weighting's state inline (output legibility).

// Named weighting levels (the gate needs "no pre-selection", so a discrete set with none highlighted until chosen —
// not a slider resting at a value). Each maps to the 0..1 float the /methods/publishers/run endpoint takes.
const PUB_WEIGHTS = [
  { id: "off", label: "Off — best fit only", value: 0.0 },
  { id: "balanced", label: "Balanced", value: 0.5 },
  { id: "strong", label: "Strongly favor open", value: 1.0 },
];
// Result breadth — a genuine second consequential choice (how wide a shortlist), so the weighting isn't the lone
// forced field. Maps to the endpoint's top_k.
const PUB_BREADTHS = [
  { id: "focused", label: "Focused (top 10)", topK: 10 },
  { id: "broad", label: "Broad (top 25)", topK: 25 },
];
const PUB_HISTORY_KEY = "callosum.discover.journalsHistory.v1";
const PUB_HISTORY_LIMIT = 8;

function _pubLoadHistory() {
  try {
    const rows = JSON.parse(localStorage.getItem(PUB_HISTORY_KEY) || "[]");
    return Array.isArray(rows) ? rows.filter(r => r && r.kind).slice(0, PUB_HISTORY_LIMIT) : [];
  } catch (e) {
    return [];
  }
}

function _pubSaveHistory(rows) {
  try { localStorage.setItem(PUB_HISTORY_KEY, JSON.stringify(rows)); } catch (e) { /* ignore */ }
}

function pubWeightId(value) {  // stored float → the nearest named level id (for the segmented control's active state)
  if (value == null) return null;
  let best = PUB_WEIGHTS[0];
  for (const w of PUB_WEIGHTS) if (Math.abs(w.value - value) < Math.abs(best.value - value)) best = w;
  return best.id;
}
function pubWeightLabel(value) {
  const id = pubWeightId(value);
  const w = PUB_WEIGHTS.find(x => x.id === id);
  return w ? w.label : "unset";
}

// A segmented control (reuses the .tags-srcfilter recipe). No option is highlighted until `value` matches one — so
// at first use nothing is pre-selected (the choice-gate veto).
function PubSegmented({ options, value, onChange, ariaLabel, disabled = false }) {
  return (
    <div className="tags-srcfilter" role="group" aria-label={ariaLabel}>
      {options.map(o => (
        <button key={o.id} type="button" disabled={disabled} className={"tags-srcfilter-btn" + (o.id === value ? " on" : "")}
          onClick={() => onChange(o.id)}>{o.label}</button>
      ))}
    </div>
  );
}

// The first-use choice gate: force BOTH consequential publisher defaults, none pre-selected, before any output.
function PublishersGate({ onSaved }) {
  const [w, setW] = useState(null);   // "off" | "balanced" | "strong" | null
  const [b, setB] = useState(null);   // "focused" | "broad" | null
  const [busy, setBusy] = useState(false);
  const ready = w != null && b != null;
  const save = async () => {
    setBusy(true);
    const weight = PUB_WEIGHTS.find(x => x.id === w).value;
    const r = await apiPut("/settings", {
      set_publisher_weighting: true, publisher_weighting: weight,
      set_publisher_breadth: true, publisher_breadth: b,
    });
    setBusy(false);
    if (r.ok) onSaved();
  };
  return (
    <div className="pub-gate">
      <div className="pub-gate-intro">
        Before Where-to-submit runs, set your preferences — each choice is yours to make, none is pre-selected.
        (You can change them anytime here or in Settings.)
      </div>
      <div className="pub-gate-field">
        <div className="pub-gate-label">Open-science weighting
          <span className="settings-sub">How much a journal's openness (diamond/gold OA, a DOAJ Seal) moves the
            ranking. Off ranks by topical fit alone — itself a value choice, so neither is a neutral default.</span>
        </div>
        <PubSegmented options={PUB_WEIGHTS} value={w} onChange={setW} ariaLabel="Open-science weighting" />
      </div>
      <div className="pub-gate-field">
        <div className="pub-gate-label">Result breadth
          <span className="settings-sub">How many candidate journals to shortlist.</span>
        </div>
        <PubSegmented options={PUB_BREADTHS} value={b} onChange={setB} ariaLabel="Result breadth" />
      </div>
      <div className="settings-actions">
        <button className="btn btn-primary" disabled={!ready || busy} onClick={save}>
          {busy ? "Saving…" : "Save preferences"}
        </button>
      </div>
      <div className="pub-gate-privacy">Stored on this machine only — your preferences are never transmitted.</div>
    </div>
  );
}

// inc 448: credits the TOP Guidelines paper that defines the transparency/openness rubric TOP Factor scores
// journals against (CREDIT-THE-LINEAGE.md names TOP Factor as this tool's lineage alongside DOAJ). No canonical
// paper exists for SciELO itself as an index -- not fabricated here.
const TOP_FACTOR_CSL = {
  type: "article-journal",
  title: "Promoting an open research culture",
  author: [
    { family: "Nosek", given: "Brian A." }, { family: "Alter", given: "George" },
    { family: "Banks", given: "George C." }, { family: "Borsboom", given: "Denny" },
    { family: "Bowman", given: "Sara D." }, { family: "Breckler", given: "Steven J." },
    { family: "Buck", given: "Stuart" }, { family: "Chambers", given: "Christopher D." },
    { family: "Chin", given: "Gilbert" }, { family: "Christensen", given: "Garret" },
  ],
  "container-title": "Science", volume: "348", issue: "6242", page: "1422-1425",
  issued: { "date-parts": [[2015]] }, DOI: "10.1126/science.aab2374",
};

// inc 451: credits the third-party CC-BY-4.0 dataset AJOL facts are drawn from -- a compilation of AJOL's own
// public records, NOT an AJOL-official feed (CREDIT-THE-LINEAGE.md: credit by citation, never by appropriating
// the source's name). Both DOIs readme.csv itself names as the correct citation: the dataset + its companion
// methods report.
const AJOL_CSL = [
  {
    type: "dataset",
    title: "AJOL dataset: structured metadata of articles and journals indexed in African Journals Online",
    author: [{ family: "Alonso-Álvarez", given: "P." }],
    "container-title": "Zenodo",
    issued: { "date-parts": [[2025]] }, DOI: "10.5281/zenodo.14899380",
  },
  {
    type: "article",
    title: "A small step towards the epistemic decentralization of science: a dataset of journals and publications indexed in African Journals Online",
    author: [{ family: "Alonso-Álvarez", given: "P." }],
    "container-title": "Zenodo",
    issued: { "date-parts": [[2025]] }, DOI: "10.5281/zenodo.14900054",
  },
];

// Plain-language glosses for AJOL's own JPPS (Journal Publishing Practices and Standards) jargon -- informative,
// not editorial (mirrors the existing .pub-oa/.pub-fit title= tooltip pattern on this same card).
const AJOL_JPPS_GLOSS = {
  "3 Stars": "AJOL's highest active-journal rating on its own JPPS scale.",
  "2 Stars": "An active-journal rating on AJOL's own JPPS scale.",
  "1 Star": "An active-journal rating on AJOL's own JPPS scale.",
  "New Title": "Less than 2 years on AJOL but meets AJOL's basic inclusion criteria.",
  "No Stars": "Currently not meeting AJOL's basic criteria for inclusion, per AJOL's own assessment.",
  "Pending": "Awaiting AJOL's own JPPS assessment.",
  "Inactive Title": "AJOL reports no new content added to this journal in over a year.",
  "Ceased": "AJOL reports this journal has permanently stopped publishing.",
  "NA": "Not assessed by AJOL's JPPS rubric.",
};

const OA_LABEL = {
  diamond: "Diamond OA — free to publish + free to read",
  gold: "Gold OA — free to read",
  "oa-other": "Open access",
  closed: "Closed access",
};

function PubProfileCard({ p, weightingOn }) {
  const issn = p.issn_l || (p.issns && p.issns[0]) || null;
  const doajUrl = p.is_in_doaj && issn ? `https://doaj.org/toc/${issn}` : null;
  const oaUrl = p.source_id ? `https://openalex.org/${p.source_id}` : null;
  const ajolUrl = p.ajol_status && p.ajol_status.source_url ? p.ajol_status.source_url : null;
  const apcText = p.oa_color === "diamond" || p.apc_amount === 0
    ? "No APC — free to publish"
    : (p.apc_amount != null ? `APC: ${p.apc_amount}${p.apc_currency ? " " + p.apc_currency : ""}` : "APC: not listed");
  return (
    <div className="pub-card">
      <div className="pub-card-title">
        {p.homepage_url
          ? <a href={p.homepage_url} target="_blank" rel="noopener noreferrer">{p.display_name || "Untitled journal"}</a>
          : (p.display_name || "Untitled journal")}
      </div>
      <div className="pub-card-facts">
        <span className="pub-oa" title="Open-access category, from OpenAlex/DOAJ (a labeled fact, not a verdict)">{OA_LABEL[p.oa_color] || p.oa_color}</span>
        <span className="pub-fit" title="callosum's own local embedding cosine between your abstract and this journal's scope — a topical match, not a recommendation">topical fit {Number(p.fit).toFixed(2)}</span>
      </div>
      {weightingOn && p.fit_rank !== p.weighted_rank &&
        <div className="pub-caveat" title="A neutral, fit-only ordering — how this journal would rank with the weighting off">
          Ranked #{p.weighted_rank} here with weighting on · #{p.fit_rank} by topical fit alone
        </div>}
      <div className="pub-card-row"><b>Cost:</b> {apcText}{p.apc_waiver ? " · waiver policy available" : ""}</div>
      {p.license && p.license.length > 0 && <div className="pub-card-row"><b>License:</b> {p.license.join(", ")}</div>}
      {(p.two_year_mean_citedness != null || p.h_index != null) &&
        <div className="pub-card-row">
          <b>Open impact:</b>{" "}
          {p.two_year_mean_citedness != null ? `2-yr mean citedness ${Number(p.two_year_mean_citedness).toFixed(1)}` : ""}
          {p.h_index != null ? `${p.two_year_mean_citedness != null ? " · " : ""}h-index ${p.h_index}` : ""}
          {" "}<span className="pub-caveat">(one fact among many; impact metrics carry a Matthew-effect bias)</span>
        </div>}
      {p.legitimacy_signals && p.legitimacy_signals.length > 0 &&
        <div className="pub-chips">{p.legitimacy_signals.map((s, i) => <span key={i} className="pub-chip">{s}</span>)}</div>}
      {p.top_factor &&
        <details className="cite-equity-basis">
          <summary>TOP Factor — show the basis ({p.top_factor.categories.length} categor{p.top_factor.categories.length === 1 ? "y" : "ies"})</summary>
          <ul>{p.top_factor.categories.map((c, i) =>
            <li key={i}>{c.name}: {c.score}/{c.max}{c.justification ? ` — ${c.justification}` : ""}</li>
          )}</ul>
          <div className="pub-caveat">Total (sum of the categories above): {p.top_factor.total}</div>
        </details>}
      {p.ajol_status &&
        <div className="pub-card-row" title={AJOL_JPPS_GLOSS[p.ajol_status.jpps_status] || "AJOL's own journal status, shown as reported -- not a Callosum judgment."}>
          <b>AJOL status:</b> {p.ajol_status.jpps_status || "unknown"}
          {p.ajol_status.country ? ` · ${p.ajol_status.country}` : ""}
          {p.ajol_status.is_diamond === true ? " · diamond OA (AJOL-confirmed)" : ""}
        </div>}
      {weightingOn && p.elevated_for && p.elevated_for.length > 0 &&
        <div className="pub-elevated" title="Goods this journal offers that your open-science weighting rewarded — never a mark against the others">
          Elevated for: {p.elevated_for.join(", ")}
        </div>}
      {(doajUrl || oaUrl || ajolUrl) &&
        <div className="pub-sources">
          Sources:{" "}
          {oaUrl && <a href={oaUrl} target="_blank" rel="noopener noreferrer">OpenAlex</a>}
          {doajUrl && <>{oaUrl ? " · " : ""}<a href={doajUrl} target="_blank" rel="noopener noreferrer">DOAJ</a></>}
          {ajolUrl && <>{(oaUrl || doajUrl) ? " · " : ""}<a href={ajolUrl} target="_blank" rel="noopener noreferrer">AJOL</a></>}
        </div>}
    </div>
  );
}

function PublishersPanel({ ctx }) {
  // inc 404: a WIP manuscript has no papers.id, so ctx.selectedPaper stays null while one is active -- mode
  // already falls through to "abstract" for free; this seeds the manual fields and tags the run.
  const manuscript = ctx.researchContext && ctx.researchContext.kind === "manuscript" ? ctx.researchContext.entity : null;
  const [status, setStatus] = useState(null);       // GET /settings (holds the prefs + the gate flag)
  const [meta, setMeta] = useState(null);           // selected paper { title, hasDoi } | null
  const [mode, setMode] = useState(null);           // "paper" | "abstract" (defaulted once status/paper is known)
  const [abstract, setAbstract] = useState("");
  const [subject, setSubject] = useState("");
  const [state, setState] = useState({ status: "idle" });  // idle | running | done | error
  const [history, setHistory] = useState(_pubLoadHistory);
  const [lastRunInput, setLastRunInput] = useState(null);

  const loadStatus = () => api("/settings").then(r => { if (r.ok) setStatus(r.data); });
  useEffect(() => { loadStatus(); }, []);
  useEffect(() => {
    if (!isDemoMode()) return;
    api("/demo/saved-artifacts/journals").then(r => {
      if (!r.ok) return;
      setLastRunInput({ kind: "paper", paperId: 67, label: "Why we dehumanize people with facial anomalies" });
      setState({ status: "done", report: r.data });
    });
  }, []);
  useEffect(() => {  // fetch the selected paper's title for legibility (like CitationEquityPaper)
    setMeta(null);
    if (ctx.selectedPaper == null) return;
    let live = true;
    api(`/papers/${ctx.selectedPaper}`).then(r => { if (live && r.ok) setMeta({ title: r.data.title, hasDoi: !!r.data.doi }); });
    return () => { live = false; };
  }, [ctx.selectedPaper]);
  useEffect(() => {  // default/redirect the input mode: a selected paper → "paper", else "abstract" -- also
    // corrects a stale "paper" mode left from an earlier paper selection once no paper is selected anymore (e.g.
    // a WIP manuscript became active instead), so mode never dead-ends on an unusable "Select a paper" empty state.
    if (status && (mode == null || (mode === "paper" && ctx.selectedPaper == null))) {
      setMode(ctx.selectedPaper != null ? "paper" : "abstract");
    }
  }, [status, ctx.selectedPaper]);
  // Seed (never clobber) the manual fields from the active manuscript -- a convenience starter, freely editable.
  useEffect(() => {
    if (!manuscript) return;
    setAbstract(prev => prev.trim() ? prev : [manuscript.display_title, manuscript.notes].filter(Boolean).join("\n\n"));
  }, [manuscript && manuscript.id]);

  if (!status) return null;
  if (!status.publisher_defaults_set) return <PublishersGate onSaved={loadStatus} />;

  const breadth = PUB_BREADTHS.find(x => x.id === status.publisher_breadth) || PUB_BREADTHS[1];
  const weighting = status.publisher_weighting ?? 0.0;
  const weightingOn = weighting > 0;

  const rememberRun = (entry) => {
    setHistory(prev => {
      const key = entry.kind === "paper"
        ? `paper:${entry.paperId}`
        : `abstract:${(entry.subject || "").trim().toLowerCase()}\n${(entry.abstract || "").trim().toLowerCase()}`;
      const next = [entry, ...prev.filter(p => {
        const pkey = p.kind === "paper"
          ? `paper:${p.paperId}`
          : `abstract:${(p.subject || "").trim().toLowerCase()}\n${(p.abstract || "").trim().toLowerCase()}`;
        return pkey !== key;
      })].slice(0, PUB_HISTORY_LIMIT);
      _pubSaveHistory(next);
      return next;
    });
  };

  const clearRunHistory = () => {
    setHistory([]); _pubSaveHistory([]);
  };

  const run = async (overrideWeighting, overrideInput) => {
    const w = overrideWeighting != null ? overrideWeighting : weighting;
    const input = overrideInput || (mode === "paper"
      ? { kind: "paper", paperId: ctx.selectedPaper, label: meta ? meta.title : null }
      : { kind: "abstract", abstract: abstract.trim(), subject: subject.trim() });
    if (overrideInput) {
      setMode(input.kind === "paper" ? "paper" : "abstract");
      if (input.kind === "abstract") { setAbstract(input.abstract || ""); setSubject(input.subject || ""); }
    }
    const body = input.kind === "paper"
      ? { paper_id: input.paperId, weighting: w, top_k: breadth.topK }
      : manuscript
      ? { abstract: input.abstract, subject: input.subject, weighting: w, top_k: breadth.topK, manuscript_id: manuscript.id }
      : { abstract: input.abstract, subject: input.subject, weighting: w, top_k: breadth.topK };
    setLastRunInput(input);
    setState({ status: "running", progress: null });
    const poll = (jobId) => api(`/methods/publishers/run/${jobId}`).then(r => {
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") {
        setState({ status: "done", report: d.report });
        // Let the manuscript's own WIP tab (Checks) pick up this run's receipt without a manual reload.
        if (manuscript && ctx.onReloadWip) ctx.onReloadWip();
      }
      else if (d.status === "error") setState({ status: "error", error: d.detail || "Search failed." });
      else { setState({ status: "running", progress: d.progress }); setTimeout(() => poll(jobId), 1500); }
    });
    const r = await apiPost("/methods/publishers/run", body);
    if (!r.ok) { setState({ status: "error", error: r.error }); return; }
    rememberRun(input.kind === "paper"
      ? { kind: "paper", paperId: input.paperId, label: input.label || `Paper ${input.paperId}` }
      : { kind: "abstract", abstract: input.abstract, subject: input.subject });
    poll(r.data.job_id);
  };

  // Output legibility: the weighting's state always shows inline, adjustable exactly where it bites (re-runs).
  const adjustWeighting = async (levelId) => {
    const val = PUB_WEIGHTS.find(x => x.id === levelId).value;
    setStatus(s => ({ ...s, publisher_weighting: val }));
    await apiPut("/settings", { set_publisher_weighting: true, publisher_weighting: val });
    if (state.status === "done") run(val, lastRunInput || undefined);
  };

  const rep = state.report;
  const canRun = mode === "paper" ? (ctx.selectedPaper != null && (!meta || meta.hasDoi)) : (abstract.trim() && subject.trim());
  const elevated = rep ? rep.profiles.filter(p => p.elevated_for && p.elevated_for.length > 0) : [];
  const elevatedGoods = [...new Set(elevated.flatMap(p => p.elevated_for))];
  const absent = rep && rep.profiles[0] ? rep.profiles[0].legitimacy_absent : [];
  const historyLabel = (h) => h.kind === "paper"
    ? `Selected paper · ${h.label || "paper " + h.paperId}`
    : `Abstract · ${h.subject || "untitled subject"}`;

  return (
    <div className="pub-panel ws-pad">
      <div className="pub-intro">
        Facts to weigh, never a verdict. Every candidate is shown (including closed journals); elevation underscores
        goods a journal offers, never flags the others. No composite score. Your abstract stays on your machine.
      </div>
      {ctx.onOpenCreditBuilder &&
        <button type="button" className="btn-link pub-credit-jump" onClick={ctx.onOpenCreditBuilder}
          title="Build the contribution statement most journals now require, in Work → CRediT">
          Once you've picked a journal, build your CRediT statement →
        </button>}

      <div className="method-credit">
        <b>Methods:</b> TOP Factor's transparency/openness rubric (Nosek et al. 2015, <i>Science</i>).{" "}
        <MethodCreditButton items={[TOP_FACTOR_CSL]} />
        <div className="method-credit-sub">Scored from the Center for Open Science's public per-journal database — credited, not reused.</div>
      </div>

      <div className="method-credit">
        <b>Methods:</b> AJOL journal facts, from a third-party compiled dataset (Alonso-Álvarez 2025).{" "}
        <MethodCreditButton items={AJOL_CSL} />
        <div className="method-credit-sub">A CC-BY-4.0 compilation of AJOL's own public records — not an AJOL-official feed; a static February 2024 snapshot, credited, not reused.</div>
      </div>

      <div className="tags-srcfilter pub-mode" role="group" aria-label="Input">
        <button type="button" className={"tags-srcfilter-btn" + (mode === "paper" ? " on" : "")} onClick={() => setMode("paper")}>Selected paper</button>
        <button type="button" className={"tags-srcfilter-btn" + (mode === "abstract" ? " on" : "")} onClick={() => setMode("abstract")}>Paste an abstract</button>
      </div>

      {mode === "paper"
        ? (ctx.selectedPaper == null
            ? <div className="tag-suggest-empty">Select a paper in the library, or paste an abstract instead.</div>
            : meta && !meta.hasDoi
              ? <div className="tag-suggest-empty">This paper has no DOI, so its research topic can't be resolved — paste its abstract + a subject instead.</div>
              : <div className="pub-input-note">Matching <b>{meta ? meta.title : "the selected paper"}</b> against candidate journals in its field.</div>)
        : <div className="pub-input">
            {manuscript && <div className="pub-input-note">Pre-filled from <b>{manuscript.display_title}</b> — edit freely; add a subject to search.</div>}
            <textarea className="settings-input" rows={4} placeholder="Paste your abstract…" value={abstract} onChange={e => setAbstract(e.target.value)} />
            <input className="settings-input" placeholder="Subject / field (e.g. cognitive neuroscience)" value={subject} onChange={e => setSubject(e.target.value)} />
            <div className="settings-sub">The abstract is embedded locally and never sent; only the subject term (a coarse public keyword) is used to gather candidate journals.</div>
          </div>}

      {state.status !== "running" &&
        <div className="settings-actions">
          <button className="btn btn-primary" disabled={!canRun || isDemoMode()} onClick={() => run()}>
            {state.status === "done" ? "Search again" : "Find journals"}
          </button>
          <select className="lib-sort" value="" onChange={e => {
            const h = history[Number(e.target.value)];
            if (h) run(null, h);
          }} title="Recall and re-run a recent Journals search">
            <option value="">Recent Journal Searches</option>
            {history.map((h, i) => <option key={`${h.kind}-${h.paperId || h.subject}-${i}`} value={i}>
              {historyLabel(h)}
            </option>)}
          </select>
          <button className="btn btn-primary" disabled={!history.length} onClick={clearRunHistory}
            title="Clear recent Journals search history stored in this browser">Clear History</button>
        </div>}

      {state.status === "running" && <ProgressBar progress={state.progress} label="Matching journals…" managedBy="backend-job" />}
      {isDemoMode() && <div className="settings-note">Saved journal search from the curated five-paper sandbox. New searches and preference changes require local Callosum.</div>}
      {state.status === "error" && <div className="axis-err">Couldn't search: {state.error}</div>}

      {state.status === "done" && rep &&
        <div className="pub-results">
          <div className="pub-thumb">
            <span className="pub-thumb-state">
              Open-science weighting: <b>{pubWeightLabel(weighting)}</b>
              {weightingOn ? ` — ${elevated.length} journal${elevated.length === 1 ? "" : "s"} elevated${elevatedGoods.length ? " for " + elevatedGoods.join(", ") : ""}` : " — ranked by topical fit only"} · adjust:
            </span>
            <PubSegmented options={PUB_WEIGHTS} value={pubWeightId(weighting)} onChange={adjustWeighting} disabled={isDemoMode()} ariaLabel="Adjust open-science weighting" />
          </div>
          {rep.shown === 0
            ? <div className="tag-suggest-empty">No candidate journals found for this topic.</div>
            : <React.Fragment>
                {rep.profiles.map(p => <PubProfileCard key={p.source_id} p={p} weightingOn={weightingOn} />)}
                {absent && absent.length > 0 &&
                  <div className="pub-absent">Not checked in this version: {absent.join("; ")}. Absence of a signal is
                    common for new + regional journals and is <b>not</b> a mark against a journal.</div>}
                {rep.top_factor_coverage && rep.top_factor_coverage.count === 0 &&
                  <div className="pub-absent">
                    TOP Factor data hasn't been downloaded to this machine yet (Settings → Local maintenance) — this
                    is different from "no journal has one": the local copy simply hasn't been fetched, so no TOP
                    Factor fact could be checked for any journal above.
                  </div>}
                {rep.ajol_coverage && rep.ajol_coverage.count === 0 &&
                  <div className="pub-absent">
                    AJOL data hasn't been downloaded to this machine yet (Settings → Local maintenance) — this is
                    different from "no journal is AJOL-indexed": the local copy simply hasn't been fetched, so no
                    AJOL fact could be checked for any journal above.
                  </div>}
              </React.Fragment>}
        </div>}
    </div>
  );
}

// inc 261: METHODS → THEORY; inc 280 (stage 2): THEORY → the Discover workspace as the "Journals" tab (outward
// discovery — finding a venue to submit to, alongside Search/Feed/Funding). Render unchanged (reads ctx.selectedPaper).
registerWorkspaceTab(
  { id: "discover" },
  { id: "journals", label: "Journals", order: 30, hideInReadOnly: true, render: (ctx) => <PublishersPanel ctx={ctx} /> },
);
