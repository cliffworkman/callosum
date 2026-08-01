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
  return <button className="btn btn-ghost" onClick={copy} title="Copy a BibTeX entry (for a reference manager)">{copied ? "Copied ✓" : "BibTeX"}</button>;
}

// A formatted human citation (APA/MLA/IEEE/… in the pane's chosen style) — what a writer hand-citing in a
// document actually pastes. Renders on demand via the inc-106 citeproc engine (local, no egress) + copies the
// reference text. The render is the same engine as Details "Cite as…" + the word-processor adapters.
function FormattedCiteButton({ paperId, style }) {
  const [st, setSt] = useState("idle");  // idle | busy | copied
  const copy = async (e) => {
    e.preventDefault();
    setSt("busy");
    const r = await apiPost("/citations/render", { paper_ids: [paperId], style });
    const item = r.ok && r.data.items && r.data.items[0] ? r.data.items[0] : null;
    if (item && item.reference_text) {
      try {
        await navigator.clipboard.writeText(item.reference_text);
        setSt("copied"); setTimeout(() => setSt("idle"), 1500); return;
      } catch (err) { console.warn("[callosum] copy formatted cite error:", err); }
    }
    setSt("idle");
  };
  return (
    <button className="btn btn-ghost" onClick={copy} disabled={st === "busy"}
      title="Copy the formatted citation in the selected style">
      {st === "copied" ? "Copied ✓" : st === "busy" ? "…" : "Cite"}
    </button>
  );
}

function SuggestionCard({ s, onOpenCitation, style }) {
  const stance = s.stance;
  const canOpen = onOpenCitation && s.paper_id != null;
  const opensMatchedPdf = s.attachment_id != null;
  const open = (event) => {
    event.preventDefault();
    onOpenCitation({
      paper_id: s.paper_id, paper_title: s.title, chunk_id: s.chunk_id,
      page_start: opensMatchedPdf ? s.page_start : null, page_end: opensMatchedPdf ? s.page_end : null,
      coordinate_precision: s.coordinate_precision, bbox_json: s.bbox_json, quote: s.quote,
      attachment_id: s.attachment_id,
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
        {canOpen && <button className="btn btn-ghost" onClick={open}
          title={opensMatchedPdf ? "Open the PDF attachment that supplied this matched passage" : "The matched attachment is not an openable PDF; open this paper's primary PDF without applying its source-page coordinates"}>
          {opensMatchedPdf ? "Open source region" : "Open primary PDF"}
        </button>}
        <FormattedCiteButton paperId={s.paper_id} style={style} />
        <CiteCopyButton paperId={s.paper_id} />
        {stance
          ? <span className="cite-conf">stance confidence {stance.confidence.toFixed(2)}</span>
          : <span className="cite-conf cite-conf-warn">stance unavailable — local model not loaded</span>}
      </div>
    </div>
  );
}

function BeyondSaveButton({ item }) {
  const [state, setState] = useState(item.in_library ? "saved" : "idle");
  const save = async () => {
    setState("saving");
    const r = await apiPost("/discovery/save", {
      title: item.title, doi: item.doi, abstract: item.abstract,
      authors: item.authors || [], journal: item.journal, year: item.year, url: item.url,
    });
    setState(r.ok ? "saved" : "error");
  };
  return (
    <button type="button" className="btn btn-ghost" onClick={save} disabled={state === "saving" || state === "saved"}>
      {state === "saved" ? "In library" : state === "saving" ? "Adding..." : state === "error" ? "Add failed" : "Add to library"}
    </button>
  );
}

function BeyondSuggestionCard({ item }) {
  const stance = item.stance;
  const meta = [(item.authors || [])[0], item.year, item.journal].filter(Boolean).join(" · ");
  return (
    <div className="cite-card cite-card-external">
      <div className="cite-card-head">
        <div>
          <div className="cite-title">{item.title || "Untitled public-metadata result"}</div>
          {meta && <div className="cite-meta">{meta}</div>}
        </div>
        <div className="cite-pills">
          <span className="cite-stance unknown" title="Public metadata source">{(item.sources || []).join(", ") || "public metadata"}</span>
          <span className="cite-match" title="Visible term overlap with your sentence; not a correctness score">
            metadata overlap {Number(item.metadata_overlap || 0).toFixed(2)}
          </span>
        </div>
      </div>
      {item.relationship_label &&
        <div className="cite-relation">
          {item.relationship_label}{item.anchor_title ? `: ${item.anchor_title}` : ""}
        </div>}
      <div className="cite-reason">{item.reason}</div>
      {item.evidence_text && <div className="quote">"{item.evidence_text}"</div>}
      <div className="cite-card-foot">
        <BeyondSaveButton item={item} />
        {item.url && <a className="btn btn-ghost" href={item.url} target="_blank" rel="noopener noreferrer">Source</a>}
        {item.doi && <span className="cite-conf">DOI {item.doi}</span>}
        {stance
          ? <span className="cite-conf">abstract-level stance {stance.label} - {stance.confidence.toFixed(2)}</span>
          : <span className="cite-conf">full text not checked</span>}
      </div>
    </div>
  );
}

function CitationSourceCoverage({ rows }) {
  if (!rows || !rows.length) return null;
  return (
    <div className="cite-coverage">
      {rows.map((r, i) => (
        <span key={i} className={"cite-source " + (r.status || "unknown")}>
          {r.provider_id}: {r.status}{r.result_count != null ? ` - ${r.result_count}` : ""}
          {r.warning ? ` - ${r.warning}` : ""}
        </span>
      ))}
    </div>
  );
}

function CitePane({ ctx }) {
  const [text, setText] = useState("");
  const [includeBeyond, setIncludeBeyond] = useState(false);
  const [state, setState] = useState({ status: "idle" });
  const [styles, setStyles] = useState([]);   // inc 159: formatted-citation styles (inc-106 engine)
  const [style, setStyle] = useState("apa");
  useEffect(() => { api("/citations/styles").then(r => {
    if (r.ok) {
      setStyles(r.data.styles || []);
      setStyle(r.data.default_style || "apa");
    }
  }); }, []);
  const run = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setState({ status: "loading" });
    apiPost("/citations/suggest", {
      text: trimmed, top_k: 5, evaluate: true, include_beyond_library: includeBeyond, beyond_top_k: 5,
    }).then(r => {
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      setState({
        status: "done",
        suggestions: r.data.suggestions || [],
        beyond: r.data.beyond_library_suggestions || [],
        coverage: r.data.source_coverage || [],
      });
    });
  };
  const busy = state.status === "loading";
  const suggestions = state.status === "done" ? state.suggestions : [];
  const beyond = state.status === "done" ? state.beyond : [];
  return (
    <div className="cite-pane ws-pad">
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
          {busy ? "Finding suggestions…" : includeBeyond ? "library + public metadata sources" : "from your library · local, no egress"}
        </span>
      </div>
      <label className="cite-beyond-toggle">
        <input type="checkbox" checked={includeBeyond} onChange={e => setIncludeBeyond(e.target.checked)} />
        <span>Also search beyond my library</span>
        <small>Uses public metadata providers. Abstract-level stance is weaker than full-text library evidence.</small>
      </label>
      {busy && <ProgressBar label="Finding citation evidence locally…" managedBy="tracked-request" />}
      {state.status === "error" &&
        <div className="errbox" style={{ margin: "12px 0 0" }}><b>Couldn't get suggestions.</b><br />{state.error}</div>}
      {state.status === "idle" &&
        <div className="state" style={{ padding: "26px 10px" }}>
          <div className="big">Suggest citations</div>
          Paste a draft sentence. Callosum ranks your library by relevance and checks whether each paper supports, contrasts, or just mentions the claim — you decide the right citation.
        </div>}
      {state.status === "done" && suggestions.length === 0 && beyond.length === 0 &&
        <div className="state" style={{ padding: "22px 10px" }}>
          <div className="big">No citation candidates surfaced.</div>
          Nothing in the sources searched matched this sentence closely enough to suggest. This is not evidence that no relevant papers exist.
        </div>}
      {(suggestions.length > 0 || beyond.length > 0) &&
        <div className="cite-results">
          <div className="cite-results-head">
            <div className="cite-note">Ranked by relevance to your sentence — a ranking aid, not a correctness claim; the author decides the right citation. Evidence is the matched passage block (region-level), not an exact quote highlight.</div>
            {styles.length > 0 &&
              <label className="cite-style" title="Style for the “Cite” (formatted) copy">Cite as
                <select value={style} onChange={e => setStyle(e.target.value)}>
                  {styles.map(o => <option key={o.id} value={o.id}>{o.title}</option>)}
                </select>
              </label>}
          </div>
          <CitationSourceCoverage rows={state.coverage} />
          {suggestions.length > 0 && <div className="cite-subhead">In your library</div>}
          {suggestions.map(s => <SuggestionCard key={s.chunk_id} s={s} onOpenCitation={ctx.onOpenCitation} style={style} />)}
          {beyond.length > 0 && <div className="cite-subhead">Outside your library</div>}
          {beyond.map(s => <BeyondSuggestionCard key={s.dedup_key} item={s} />)}
        </div>}
    </div>
  );
}

// inc 287 (reorg): Work → Cite is now just the Suggest tool directly — the paper-specific citation-integrity
// audits that used to live as nested tabs alongside it moved to Work → Meta-Reference (37b_meta_reference.jsx).
registerWorkspaceTab(
  { id: "work", label: "Work", order: 50 },
  { id: "cite", label: "Cite", order: 10, render: (ctx) => <CitePane ctx={ctx} /> },
);
