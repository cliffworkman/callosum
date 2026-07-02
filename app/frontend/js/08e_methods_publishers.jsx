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
function PubSegmented({ options, value, onChange, ariaLabel }) {
  return (
    <div className="tags-srcfilter" role="group" aria-label={ariaLabel}>
      {options.map(o => (
        <button key={o.id} type="button" className={"tags-srcfilter-btn" + (o.id === value ? " on" : "")}
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
      {weightingOn && p.elevated_for && p.elevated_for.length > 0 &&
        <div className="pub-elevated" title="Goods this journal offers that your open-science weighting rewarded — never a mark against the others">
          Elevated for: {p.elevated_for.join(", ")}
        </div>}
      {(doajUrl || oaUrl) &&
        <div className="pub-sources">
          Sources:{" "}
          {oaUrl && <a href={oaUrl} target="_blank" rel="noopener noreferrer">OpenAlex</a>}
          {doajUrl && <>{oaUrl ? " · " : ""}<a href={doajUrl} target="_blank" rel="noopener noreferrer">DOAJ</a></>}
        </div>}
    </div>
  );
}

function PublishersPanel({ ctx }) {
  const [status, setStatus] = useState(null);       // GET /settings (holds the prefs + the gate flag)
  const [meta, setMeta] = useState(null);           // selected paper { title, hasDoi } | null
  const [mode, setMode] = useState(null);           // "paper" | "abstract" (defaulted once status/paper is known)
  const [abstract, setAbstract] = useState("");
  const [subject, setSubject] = useState("");
  const [state, setState] = useState({ status: "idle" });  // idle | running | done | error

  const loadStatus = () => api("/settings").then(r => { if (r.ok) setStatus(r.data); });
  useEffect(() => { loadStatus(); }, []);
  useEffect(() => {  // fetch the selected paper's title for legibility (like CitationEquityPaper)
    setMeta(null);
    if (ctx.selectedPaper == null) return;
    let live = true;
    api(`/papers/${ctx.selectedPaper}`).then(r => { if (live && r.ok) setMeta({ title: r.data.title, hasDoi: !!r.data.doi }); });
    return () => { live = false; };
  }, [ctx.selectedPaper]);
  useEffect(() => {  // default the input mode: a selected paper → "paper", else "abstract"
    if (mode == null && status) setMode(ctx.selectedPaper != null ? "paper" : "abstract");
  }, [status, ctx.selectedPaper]);

  if (!status) return null;
  if (!status.publisher_defaults_set) return <PublishersGate onSaved={loadStatus} />;

  const breadth = PUB_BREADTHS.find(x => x.id === status.publisher_breadth) || PUB_BREADTHS[1];
  const weighting = status.publisher_weighting ?? 0.0;
  const weightingOn = weighting > 0;

  const run = async (overrideWeighting) => {
    const w = overrideWeighting != null ? overrideWeighting : weighting;
    const body = mode === "paper"
      ? { paper_id: ctx.selectedPaper, weighting: w, top_k: breadth.topK }
      : { abstract: abstract, subject: subject, weighting: w, top_k: breadth.topK };
    setState({ status: "running", progress: null });
    const poll = (jobId) => api(`/methods/publishers/run/${jobId}`).then(r => {
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") setState({ status: "done", report: d.report });
      else if (d.status === "error") setState({ status: "error", error: d.detail || "Search failed." });
      else { setState({ status: "running", progress: d.progress }); setTimeout(() => poll(jobId), 1500); }
    });
    const r = await apiPost("/methods/publishers/run", body);
    if (!r.ok) { setState({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };

  // Output legibility: the weighting's state always shows inline, adjustable exactly where it bites (re-runs).
  const adjustWeighting = async (levelId) => {
    const val = PUB_WEIGHTS.find(x => x.id === levelId).value;
    setStatus(s => ({ ...s, publisher_weighting: val }));
    await apiPut("/settings", { set_publisher_weighting: true, publisher_weighting: val });
    if (state.status === "done") run(val);
  };

  const rep = state.report;
  const canRun = mode === "paper" ? (ctx.selectedPaper != null && (!meta || meta.hasDoi)) : (abstract.trim() && subject.trim());
  const elevated = rep ? rep.profiles.filter(p => p.elevated_for && p.elevated_for.length > 0) : [];
  const elevatedGoods = [...new Set(elevated.flatMap(p => p.elevated_for))];
  const absent = rep && rep.profiles[0] ? rep.profiles[0].legitimacy_absent : [];

  return (
    <div className="pub-panel">
      <div className="pub-intro">
        Facts to weigh, never a verdict. Every candidate is shown (including closed journals); elevation underscores
        goods a journal offers, never flags the others. No composite score. Your abstract stays on your machine.
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
            <textarea className="settings-input" rows={4} placeholder="Paste your abstract…" value={abstract} onChange={e => setAbstract(e.target.value)} />
            <input className="settings-input" placeholder="Subject / field (e.g. cognitive neuroscience)" value={subject} onChange={e => setSubject(e.target.value)} />
            <div className="settings-sub">The abstract is embedded locally and never sent; only the subject term (a coarse public keyword) is used to gather candidate journals.</div>
          </div>}

      {state.status !== "running" &&
        <button className="btn btn-primary" disabled={!canRun} onClick={() => run()}>
          {state.status === "done" ? "Search again" : "Find journals"}
        </button>}

      {state.status === "running" && <ProgressBar progress={state.progress} label="Matching journals…" />}
      {state.status === "error" && <div className="axis-err">Couldn't search: {state.error}</div>}

      {state.status === "done" && rep &&
        <div className="pub-results">
          <div className="pub-thumb">
            <span className="pub-thumb-state">
              Open-science weighting: <b>{pubWeightLabel(weighting)}</b>
              {weightingOn ? ` — ${elevated.length} journal${elevated.length === 1 ? "" : "s"} elevated${elevatedGoods.length ? " for " + elevatedGoods.join(", ") : ""}` : " — ranked by topical fit only"} · adjust:
            </span>
            <PubSegmented options={PUB_WEIGHTS} value={pubWeightId(weighting)} onChange={adjustWeighting} ariaLabel="Adjust open-science weighting" />
          </div>
          {rep.shown === 0
            ? <div className="tag-suggest-empty">No candidate journals found for this topic.</div>
            : <React.Fragment>
                {rep.profiles.map(p => <PubProfileCard key={p.source_id} p={p} weightingOn={weightingOn} />)}
                {absent && absent.length > 0 &&
                  <div className="pub-absent">Not checked in this version: {absent.join("; ")}. Absence of a signal is
                    common for new + regional journals and is <b>not</b> a mark against a journal.</div>}
              </React.Fragment>}
        </div>}
    </div>
  );
}

registerPaneSection({
  id: "publishers", label: "Where to submit", paneId: "methods", order: 34, hideInReadOnly: true,
  render: (ctx) => <PublishersPanel ctx={ctx} />,
});
