// inc 209 (A3): full-text PDF search results — the verbatim/lexical complement to the semantic axes. Rendered by
// PaperList (10_pdf_layer.jsx, via the shared-IIFE function hoist) when the "Full text" search scope is active + a
// query is present. Self-contained: it does its OWN debounced fetch to GET /papers/fulltext, so 40_app is untouched.
// Per-occurrence hits (one card per matching chunk), each opening the PDF at its page (region precision — page
// scroll, no fabricated exact rect; reuses citationTarget → openPdf, the inc-156 Cite-pane pattern).

// Render a snippet, bolding the matched terms (the backend wraps them in the SNIPPET_OPEN/CLOSE private-use markers
// U+E000/U+E001). Split-and-rebuild as React nodes (text segments are escaped — no dangerouslySetInnerHTML).
function renderFtSnippet(snippet) {
  const OPEN = "";   // U+E000 (private-use) — matches fulltext_repo SNIPPET_OPEN
  const CLOSE = "";  // U+E001 (private-use) — matches fulltext_repo SNIPPET_CLOSE
  const segments = String(snippet || "").split(OPEN);
  const out = [segments[0]];
  for (let i = 1; i < segments.length; i++) {
    const [matched, ...rest] = segments[i].split(CLOSE);
    out.push(<b className="ft-mark" key={i}>{matched}</b>);
    out.push(rest.join(CLOSE));
  }
  return out;
}

function FulltextResults({ query, onOpenPdf }) {
  const [state, setState] = useState({ status: "idle", hits: [] });
  useEffect(() => {
    const q = (query || "").trim();
    if (!q) {
      setState({ status: "idle", hits: [] });
      return;
    }
    let live = true;
    setState((s) => ({ ...s, status: "loading" }));
    const t = setTimeout(() => {
      api("/papers/fulltext?q=" + encodeURIComponent(q)).then((r) => {
        if (!live) return;
        if (r.ok) setState({ status: "ready", hits: r.data || [] });
        else setState({ status: "error", hits: [], error: r.error });
      });
    }, 280);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [query]);

  const hits = state.hits;
  const paperCount = new Set(hits.map((h) => h.paper_id)).size;
  const openHit = (h) =>
    onOpenPdf(
      { id: h.paper_id, title: h.title },
      citationTarget({
        paper_id: h.paper_id,
        paper_title: h.title,
        page_start: h.page_start,
        page_end: h.page_end,
        coordinate_precision: h.coordinate_precision,
      }),
    );

  return (
    <div className="fulltext-results">
      <div className="fulltext-hint">Searching <b>inside your PDFs</b> — exact wording, not meaning. (For meaning-based search, use an Axis or a Synthesis.)</div>
      {state.status === "loading" && <div className="axis-hint">Searching…</div>}
      {state.status === "error" && <div className="errbox">Couldn't search: {state.error}</div>}
      {state.status === "ready" && hits.length === 0 &&
        <div className="state">
          <div className="big">No matches in your PDFs.</div>
          Try different wording. Only papers with extracted text are searched.
        </div>}
      {state.status === "ready" && hits.length > 0 &&
        <div className="fulltext-meta">{hits.length} match{hits.length === 1 ? "" : "es"} in {paperCount} paper{paperCount === 1 ? "" : "s"}</div>}
      {hits.map((h, i) => (
        <div className="cite-card fulltext-hit" key={h.chunk_id || i}>
          <div className="cite-card-head">
            <div>
              <div className="cite-title">{h.title || "Paper " + h.paper_id}</div>
              {(h.author || h.year) && <div className="cite-meta">{[h.author, h.year].filter(Boolean).join(" · ")}</div>}
            </div>
          </div>
          <div className="quote">…{renderFtSnippet(h.snippet)}…</div>
          <div className="cite-card-foot">
            <span className="ft-page">{pageLabel(h)}</span>
            <button className="btn btn-ghost" onClick={() => openHit(h)}>Open at page</button>
          </div>
        </div>
      ))}
    </div>
  );
}
