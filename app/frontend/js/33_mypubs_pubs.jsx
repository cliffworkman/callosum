// My Publications — the publications list (inc 117, SP1). Renders the user's confirmed own-papers (the
// My Publications axis members) as library-style PaperCards with full parity: search + sort, checkbox
// multi-select + a bulk bar (summarize / export / bibliography / delete), copy-BibTeX, open-on-double-click.
// Reuses GET /papers?axis_id=<my-pubs> + the shared PaperCard, so it inherits the library aesthetic and the
// tested list/bulk endpoints. The Decompose button is passed in (decomposeSlot) so it hangs with the controls (#10).
function MyPubsPublications({ axisId, onSummarize, onSelect, onOpenPdf, decomposeSlot, domains, starredIds, paperCitations, onOpenCiting }) {
  const demoMode = isDemoMode();
  const [state, setState] = useState({ status: "loading", papers: [] });
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [sort, setSort] = useState("year_desc");
  const [sel, setSel] = useState(() => new Set());
  const [refresh, setRefresh] = useState(0);
  const [citeStyles, setCiteStyles] = useState([]);
  // inc 118 (SP2 #9): group the cards by research domain (persisted). Only offered once domains are decomposed.
  const [groupByDomain, setGroupByDomain] = useState(() => localStorage.getItem("callosum.mypubsGroupByDomain") === "1");
  useEffect(() => { localStorage.setItem("callosum.mypubsGroupByDomain", groupByDomain ? "1" : "0"); }, [groupByDomain]);

  useEffect(() => { const t = setTimeout(() => setDebounced(q), 250); return () => clearTimeout(t); }, [q]);
  useEffect(() => { api("/citations/styles").then(r => { if (r.ok) setCiteStyles(r.data.styles || []); }); }, []);

  useEffect(() => {
    if (axisId == null) { setState({ status: "ready", papers: [] }); return; }
    let live = true;
    setState(s => ({ ...s, status: "loading" }));
    const qs = new URLSearchParams({ axis_id: axisId, limit: 200 });  // /papers caps limit at 200
    if (debounced.trim()) qs.set("q", debounced.trim());
    if (sort !== "added" && sort !== "most_cited") qs.set("sort", sort);  // "most_cited" is a client-side sort (OpenAlex counts)
    api(`/papers?${qs.toString()}`).then(r => {
      if (!live) return;
      if (r.ok) setState({ status: "ready", papers: r.data });
      else setState({ status: "error", error: r.error, papers: [] });
    });
    return () => { live = false; };
  }, [axisId, debounced, sort, refresh]);

  const toggleSel = (id) => setSel(s => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const clearSel = () => setSel(new Set());

  const doExport = (format) => {
    const list = [...sel]; if (!list.length) return;
    const ext = format === "ris" ? "ris" : format === "csl-json" ? "json" : "bib";
    (async () => {
      try {
        const res = await callosumFetch(API_BASE + "/papers/export", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ paper_ids: list, format }),
        });
        if (!res.ok) { console.warn("[callosum] export failed:", res.status); return; }
        const url = URL.createObjectURL(await res.blob());
        const a = document.createElement("a");
        a.href = url; a.download = `callosum-my-publications.${ext}`;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (e) { console.warn("[callosum] export error:", e); }
    })();
  };

  const doBibliography = (style) => {
    const list = [...sel]; if (!list.length) return;
    (async () => {
      const r = await apiPost("/citations/render", { paper_ids: list, style });
      if (!r.ok) { console.warn("[callosum] bibliography failed:", r.error); return; }
      const entries = (r.data && r.data.bibliography_html) || [];
      if (!entries.length) return;
      const body = entries.map(e => `<p style="text-indent:-2em;padding-left:2em;margin:0 0 .6em">${e}</p>`).join("");
      const html = `<!doctype html><meta charset="utf-8"><title>Bibliography (${style})</title>` +
        `<body style="font-family:Georgia,'Times New Roman',serif;font-size:12pt;line-height:1.5;max-width:46em;margin:2em auto">${body}</body>`;
      const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
      const a = document.createElement("a");
      a.href = url; a.download = `callosum-bibliography-${style}.html`;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(url);
    })();
  };

  const doDelete = () => {
    const list = [...sel]; if (!list.length) return;
    if (!window.confirm(`Move ${list.length} ${list.length === 1 ? "paper" : "papers"} to Trash? You can restore from Trash.`)) return;
    Promise.all(list.map(id => apiDelete(`/papers/${id}`))).then(() => { clearSel(); setRefresh(n => n + 1); });
  };

  const doSummarize = () => { const list = [...sel]; if (!list.length) return; if (onSummarize) onSummarize(list); clearSel(); };

  const rawPapers = state.papers || [];
  // inc 119 (SP3 #14): per-card OpenAlex cited-by info; "Most cited" is a client-side sort (counts aren't a /papers column).
  const citeCount = (p) => ((paperCitations && paperCitations[String(p.id)]) || {}).cited_by_count || 0;
  const citeInfoFor = (p) => {
    const c = paperCitations && paperCitations[String(p.id)];
    return c ? { count: c.cited_by_count, workId: c.openalex_work_id, onOpenCiting } : undefined;
  };
  const papers = sort === "most_cited" ? [...rawPapers].sort((a, b) => citeCount(b) - citeCount(a)) : rawPapers;
  // inc 118 (SP2 #17): starred-first — stable-partition so each sub-list keeps the chosen sort order.
  const starredSet = new Set(starredIds || []);
  const starFirst = (list) => [...list.filter(p => starredSet.has(p.id)), ...list.filter(p => !starredSet.has(p.id))];
  const renderCard = (p) => (
    <PaperCard
      key={p.id} paper={p} selecting={true} isSelected={false}
      onSelect={onSelect} onOpen={onOpenPdf}
      checked={sel.has(p.id)} onToggleCheck={toggleSel} citeInfo={citeInfoFor(p)}
    />
  );
  // inc 118 (SP2 #9): group-by-domain — buckets in citation-impact order (the domains order), "Other" last.
  const hasDomains = Array.isArray(domains) && domains.length > 0;
  let groups = null;
  if (groupByDomain && hasDomains) {
    groups = [];
    const taken = new Set();
    for (const d of domains) {
      const ids = new Set(d.paper_ids || []);
      const inDom = papers.filter(p => ids.has(p.id) && !taken.has(p.id));
      inDom.forEach(p => taken.add(p.id));
      if (inDom.length) groups.push({ label: d.label, papers: starFirst(inDom) });
    }
    const other = papers.filter(p => !taken.has(p.id));
    if (other.length) groups.push({ label: "Other", papers: starFirst(other) });
  }
  return (
    <div className="mypubs-pubs">
      <div className="mypubs-pubs-head">
        <span className="mypubs-pubs-title">Publications{state.status === "ready" ? ` (${papers.length})` : ""}</span>
        <span className="mypubs-pubs-controls">
          <input
            className="mypubs-pubs-search" placeholder="Search your publications…" value={q}
            onChange={e => setQ(e.target.value)} spellCheck={false}
          />
          <select className="lib-sort" value={sort} onChange={e => setSort(e.target.value)} title="Sort your publications">
            <option value="year_desc">Year (newest)</option>
            <option value="year_asc">Year (oldest)</option>
            <option value="title">Title (A–Z)</option>
            <option value="title_desc">Title (Z–A)</option>
            <option value="added">Date Added</option>
            {paperCitations && <option value="most_cited">Most Cited</option>}
          </select>
          {hasDomains &&
            <label className="mypubs-group-toggle" title="Group your publications by research domain">
              <input type="checkbox" checked={groupByDomain} onChange={e => setGroupByDomain(e.target.checked)} /> Group by Domain
            </label>}
          {decomposeSlot}
        </span>
      </div>

      {sel.size > 0 &&
        <div className="axis-bulk-bar">
          <span className="axis-bulk-count">{sel.size} selected</span>
          <button className="axis-link" disabled={demoMode} onClick={doSummarize}
            title={demoMode ? "Generating a new synthesis requires local Callosum." : "Generate a verified synthesis of the selected papers"}>Summarize</button>
          <select className="bulk-export" value="" title="Export citations for the selected papers"
            disabled={demoMode}
            onChange={e => { if (e.target.value) { doExport(e.target.value); e.target.value = ""; } }}>
            <option value="" disabled>Export…</option>
            <option value="bibtex">BibTeX (.bib)</option>
            <option value="ris">RIS (.ris)</option>
            <option value="csl-json">CSL-JSON</option>
          </select>
          {citeStyles.length > 0 &&
            <select className="bulk-export" value="" disabled={demoMode} title={demoMode ? "Formatting and downloading a new bibliography requires local Callosum." : "Download a formatted bibliography for the selected papers"}
              onChange={e => { if (e.target.value) { doBibliography(e.target.value); e.target.value = ""; } }}>
              <option value="" disabled>Bibliography…</option>
              {citeStyles.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}
            </select>}
          <button className="axis-link axis-danger" disabled={demoMode} title={demoMode ? "Deleting publications requires the local Callosum database." : undefined} onClick={doDelete}>Delete</button>
          <button className="axis-link" onClick={clearSel}>Clear</button>
          {demoMode && <span className="axis-hint">Selection is local to this page; synthesis, export, bibliography, and deletion require the installed app.</span>}
        </div>}

      {state.status === "loading" && <div className="axis-hint">Loading your publications…</div>}
      {state.status === "error" && <div className="axis-err">Couldn't load your publications: {state.error}</div>}
      {state.status === "ready" && papers.length === 0 &&
        <div className="axis-hint">{debounced.trim() ? "No publications match that search." : "No publications in your library yet."}</div>}
      {state.status === "ready" && papers.length === 200 &&
        <div className="axis-hint">Showing the first 200 — narrow with search to see the rest.</div>}

      {state.status === "ready" && (groups
        ? groups.map(g => (
            <div key={g.label} className="mypubs-domain-group">
              <div className="mypubs-domain-group-head">{g.label} <span className="mypubs-group-count">{g.papers.length}</span></div>
              <div className="mypubs-domain-group-body">{g.papers.map(renderCard)}</div>
            </div>
          ))
        : starFirst(papers).map(renderCard))}
    </div>
  );
}
