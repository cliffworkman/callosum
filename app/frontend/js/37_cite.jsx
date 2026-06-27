// inc 156 (Track C SP1a): the in-app "Cite" pane — paste a draft sentence → suggested library papers to cite,
// each carrying its matched quote+page+match-score (the reason) and an NLI stance (supports/contrasts/mentions)
// with confidence. The verification + standalone surface for the local /citations/suggest engine that the
// LibreOffice "Suggest citations" macro (SP1b) will also call. Honesty: evidence is REGION precision (a chunk,
// never a fabricated exact rect); the stance leads with its quote+confidence (no bare verdict); the author picks
// (nothing auto-inserts).

function citePageLabel(s) {
  if (s.page_start == null && s.page_end == null) return "";
  if (s.page_end == null || s.page_start === s.page_end) return "p. " + s.page_start;
  return "pp. " + s.page_start + "–" + s.page_end;
}

// A one-click extract so the pane named "Cite" can actually get a citation OUT (the in-app bridge for a writer
// hand-citing in LibreOffice; the live SP1b macro inserts directly). Reuses the tested inc-70 /papers/export.
function CiteCopyButton({ paperId }) {
  const [copied, setCopied] = useState(false);
  const copy = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(API_BASE + "/papers/export", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: [paperId], format: "bibtex" }),
      });
      if (!res.ok) { console.warn("[callosum] copy BibTeX failed:", res.status); return; }
      await navigator.clipboard.writeText(await res.text());
      setCopied(true); setTimeout(() => setCopied(false), 1500);
    } catch (err) { console.warn("[callosum] copy BibTeX error:", err); }
  };
  return <button className="btn btn-ghost" onClick={copy}>{copied ? "Copied ✓" : "Copy BibTeX"}</button>;
}

function SuggestionCard({ s, onOpenCitation }) {
  const stance = s.stance;
  const canOpen = onOpenCitation && s.paper_id != null && (s.page_start != null || s.page_end != null);
  const open = (event) => {
    event.preventDefault();
    onOpenCitation({
      paper_id: s.paper_id, paper_title: s.title, chunk_id: s.chunk_id,
      page_start: s.page_start, page_end: s.page_end,
      coordinate_precision: s.coordinate_precision, bbox_json: s.bbox_json, quote: s.quote,
    });
  };
  const meta = [s.author, s.year].filter(Boolean).join(" · ");
  return (
    <div className="cite-card">
      <div className="cite-card-head">
        <div>
          <div className="cite-title">{s.title || ("Paper " + s.paper_id)}</div>
          {meta && <div className="cite-meta">{meta}</div>}
        </div>
        <div className="cite-pills">
          {stance
            ? <span className={"cite-stance " + stance.label} title="NLI stance over the matched passage">{stance.label}</span>
            : <span className="cite-stance unknown" title="The local NLI model couldn't be loaded">stance n/a</span>}
          <span className="cite-match" title="Relevance of this passage to your sentence (a ranking aid, not a correctness claim)">match {s.match_score.toFixed(2)}</span>
        </div>
      </div>
      <div className="quote">“{s.quote}”</div>
      <div className="cite-card-foot">
        {canOpen && <button className="btn btn-ghost" onClick={open}>Open source region</button>}
        <CiteCopyButton paperId={s.paper_id} />
        {stance
          ? <span className="cite-conf">stance confidence {stance.confidence.toFixed(2)}</span>
          : <span className="cite-conf cite-conf-warn">stance unavailable — local model not loaded</span>}
      </div>
    </div>
  );
}

function CitePane({ ctx }) {
  const [text, setText] = useState("");
  const [state, setState] = useState({ status: "idle" });
  const run = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setState({ status: "loading" });
    apiPost("/citations/suggest", { text: trimmed, top_k: 5, evaluate: true }).then(r => {
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      setState({ status: "done", suggestions: r.data.suggestions || [] });
    });
  };
  const busy = state.status === "loading";
  const suggestions = state.status === "done" ? state.suggestions : [];
  return (
    <div className="cite-pane">
      <textarea
        className="synth-input"
        placeholder="Paste a sentence from your draft to find papers to cite…"
        value={text}
        onChange={e => setText(e.target.value)}
        disabled={busy}
      />
      <div className="synth-actions">
        <button disabled={busy || !text.trim()} onClick={run}>Suggest</button>
        <span className={"synth-status" + (busy ? " running" : "")}>
          {busy ? "Finding suggestions…" : "from your library · local, no egress"}
        </span>
      </div>
      {busy && <ProgressBar />}
      {state.status === "error" &&
        <div className="errbox" style={{ margin: "12px 0 0" }}><b>Couldn't get suggestions.</b><br />{state.error}</div>}
      {state.status === "idle" &&
        <div className="state" style={{ padding: "26px 10px" }}>
          <div className="big">Suggest citations</div>
          Paste a draft sentence. Callosum ranks your library by relevance and checks whether each paper supports, contrasts, or just mentions the claim — you decide the right citation.
        </div>}
      {state.status === "done" && suggestions.length === 0 &&
        <div className="state" style={{ padding: "22px 10px" }}>
          <div className="big">No related papers in your library.</div>
          Nothing in your library matched this sentence closely enough to suggest.
        </div>}
      {suggestions.length > 0 &&
        <div className="cite-results">
          <div className="cite-note">Ranked by relevance to your sentence — a ranking aid, not a correctness claim; the author decides the right citation. Evidence is the matched passage block (region-level), not an exact quote highlight.</div>
          {suggestions.map(s => <SuggestionCard key={s.chunk_id} s={s} onOpenCitation={ctx.onOpenCitation} />)}
        </div>}
    </div>
  );
}

// inc 156: register CITE as a THEORY-pane accordion section, after SYNTHESIS (order 20).
registerPaneSection({
  id: "cite", label: "Cite", paneId: "theory", order: 25,
  render: (ctx) => <CitePane ctx={ctx} />,
});
