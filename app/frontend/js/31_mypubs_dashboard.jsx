// My Publications impact dashboard (inc 81, Part 2 Layer 1). Opens as the My Publications menu-bar workspace.
// A cache-aware read of the resolved OpenAlex record + the
// local library — headline metrics are OpenAlex's authoritative figures (shown verbatim + attributed), the
// gap is an import nudge, and the research summary is an editable, AI-generated *draft* (egress-gated).

function MyPubsTile({ label, value }) {
  return (
    <div className="metric-tile">
      <div className="metric-value">{(value == null ? 0 : value).toLocaleString()}</div>
      <div className="metric-label">{label}</div>
    </div>
  );
}

// A hand-rolled, dependency-free SVG bar chart (token-themed via CSS). bars = [{label, value}].
function MyPubsBarChart({ bars, ariaLabel }) {
  if (!bars || bars.length === 0) return <div className="axis-hint">No data yet.</div>;
  const max = Math.max(1, ...bars.map(b => b.value));
  const barW = 24, gap = 8, padX = 6, h = 132, padBottom = 18, padTop = 14;
  const w = padX * 2 + bars.length * (barW + gap);
  const plotH = h - padBottom;
  return (
    <svg className="pubs-chart-svg" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMinYMid meet" role="img" aria-label={ariaLabel}>
      {bars.map((b, i) => {
        const barH = Math.max(2, Math.round((b.value / max) * (plotH - padTop)));
        const x = padX + i * (barW + gap);
        const y = plotH - barH;
        return (
          <g key={b.label}>
            <rect className="pubs-bar" x={x} y={y} width={barW} height={barH} rx="2">
              <title>{b.label}: {b.value}</title>
            </rect>
            <text className="pubs-bar-count" x={x + barW / 2} y={y - 3} textAnchor="middle">{b.value}</text>
            <text className="pubs-bar-year" x={x + barW / 2} y={h - 5} textAnchor="middle">{"'" + String(b.label).slice(2)}</text>
          </g>
        );
      })}
    </svg>
  );
}

function MyPubsDashboard({ axisId, axisRefresh, onSummarize, onSelectPaper, onOpenPdf, onLibraryChanged }) {
  const [data, setData] = useState({ status: "loading" });
  const [resolvedAxisId, setResolvedAxisId] = useState(axisId || null);
  const [summary, setSummary] = useState("");
  const [dirty, setDirty] = useState(false);
  const [gen, setGen] = useState({ status: "idle" });   // idle | running | error
  const [save, setSave] = useState("idle");             // idle | saving | saved
  const [domainJob, setDomainJob] = useState({ status: "idle" });  // idle | running | error | too-few
  const [selectedDomains, setSelectedDomains] = useState(() => new Set());  // indices of domains filtering the chart
  const [starredOnly, setStarredOnly] = useState(false);  // inc 84: scope the summary draft to starred pubs
  const [missingOpen, setMissingOpen] = useState(false);  // inc 117 (#12): the missing-works review modal
  const [refreshing, setRefreshing] = useState(false);    // inc 117 (#11): the OpenAlex-card Refresh button
  // inc 117 (SP1): Overview is collapsible (persisted) and shows ONE chart with a Publications⇄Citations flip.
  const [overviewOpen, setOverviewOpen] = useState(() => localStorage.getItem("callosum.mypubsOverviewCollapsed") !== "1");
  useEffect(() => { localStorage.setItem("callosum.mypubsOverviewCollapsed", overviewOpen ? "0" : "1"); }, [overviewOpen]);
  const [chartMode, setChartMode] = useState("pubs");  // "pubs" | "cites"
  // inc 118 (SP2 #15): rename a domain — pre-suggest the closest existing axis name.
  const [editingDomain, setEditingDomain] = useState(null);  // index being renamed, or null
  const [editLabel, setEditLabel] = useState("");
  const [axisNames, setAxisNames] = useState([]);
  useEffect(() => { api("/axes").then(r => { if (r.ok) setAxisNames((r.data || []).map(a => a.label)); }); }, []);
  const [citing, setCiting] = useState(null);  // inc 119 (SP3 #14): {workId, title} → the citing-articles modal

  const refetch = () => api("/my-publications/dashboard").then(r => {
    if (r.ok) { setData(r.data); setSummary(r.data.research_summary || ""); }
  });
  const resolveAxis = useCallback(() => {
    if (axisId != null) { setResolvedAxisId(axisId); return; }
    api("/axes").then(r => {
      if (!r.ok) return;
      const ax = (r.data || []).find(a => a.kind === "my_publications");
      setResolvedAxisId(ax ? ax.id : null);
    });
  }, [axisId]);

  useEffect(() => {
    let live = true;
    api("/my-publications/dashboard").then(r => {
      if (!live) return;
      if (r.ok) { setData(r.data); setSummary(r.data.research_summary || ""); }
      else setData({ status: "error", error: r.error });
    });
    return () => { live = false; };
  }, [axisRefresh]);
  useEffect(() => { resolveAxis(); }, [resolveAxis, axisRefresh]);

  const generate = async () => {
    setGen({ status: "running" });
    const r = await apiPost("/my-publications/summary/generate", { starred_only: starredOnly });
    if (r.ok) { setSummary(r.data.summary || ""); setDirty(true); setSave("idle"); setGen({ status: "idle" }); }
    else setGen({ status: "error", error: r.error });
  };

  const saveSummary = async () => {
    setSave("saving");
    const r = await apiPut("/my-publications/summary", { summary });
    if (r.ok) { setSave("saved"); setDirty(false); } else setSave("idle");
  };

  const decompose = () => {
    setDomainJob({ status: "running" });
    setSelectedDomains(new Set());
    const poll = (jobId) => api(`/my-publications/domains/${jobId}`).then(r => {
      if (!r.ok) { setDomainJob({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") {
        if (d.result_status === "too-few") setDomainJob({ status: "too-few" });
        else { setDomainJob({ status: "idle" }); refetch(); }
      } else if (d.status === "error") {
        setDomainJob({ status: "error", error: d.detail || "Decompose failed." });
      } else setTimeout(() => poll(jobId), 1500);
    });
    apiPost("/my-publications/domains", {}).then(r => {
      if (!r.ok) { setDomainJob({ status: "error", error: r.error }); return; }
      poll(r.data.job_id);
    });
  };

  const toggleDomain = (i) => setSelectedDomains(prev => {
    const next = new Set(prev);
    if (next.has(i)) next.delete(i); else next.add(i);
    return next;
  });

  // inc 117 (#11): the OpenAlex-card refresh — re-resolve via OpenAlex (same job as Settings), then re-read the dashboard.
  const refreshMyPubs = () => {
    setRefreshing(true);
    const poll = (jobId) => api(`/my-publications/refresh/${jobId}`).then(r => {
      if (!r.ok) { setRefreshing(false); return; }
      const d = r.data;
      if (d.status === "done") { setRefreshing(false); refetch(); resolveAxis(); }
      else if (d.status === "error") { setRefreshing(false); }
      else setTimeout(() => poll(jobId), 1500);
    });
    apiPost("/my-publications/refresh", {}).then(r => {
      if (!r.ok) { setRefreshing(false); return; }
      poll(r.data.job_id);
    });
  };

  if (data.status === "loading") return <div className="mypubs-dashboard"><div className="axis-hint">Loading…</div></div>;
  if (data.status === "error") return <div className="mypubs-dashboard"><div className="axis-err">Couldn't load the dashboard: {data.error}</div></div>;
  if (data.status === "no-identity" || data.status === "not-resolved")
    return (
      <div className="mypubs-dashboard">
        <div className="mypubs-empty">
          <h2>My Publications</h2>
          <p>{data.status === "no-identity"
            ? "Set your name and ORCID in ⚙ Settings → My Publications, then click Refresh to gather your publications."
            : "Resolve your publications first — open ⚙ Settings → My Publications and click Refresh. The dashboard reads only cached data, so it never fetches on its own."}</p>
        </div>
      </div>
    );

  const m = data.metrics || {};
  const pubsBars = (data.pubs_by_year || []).map(p => ({ label: p.year, value: p.count }));
  const citeBars = (data.counts_by_year || []).map(c => ({ label: c.year, value: c.cited_by_count }));
  const asOf = data.as_of ? String(data.as_of).slice(0, 10) : null;

  // Domain re-filter: when domain(s) are selected, the pubs-by-year chart shows the union of their papers.
  const domains = data.domains || [];
  const activeDomains = domains.filter((_, i) => selectedDomains.has(i));
  const maxDomainCites = Math.max(1, ...domains.map(d => d.citation_count));
  let chartBars = pubsBars;
  let domainSummary = null;
  if (activeDomains.length) {
    const yearCounts = {};
    let papers = 0;
    let citations = 0;
    activeDomains.forEach(d => {
      papers += d.paper_count;
      citations += d.citation_count;
      (d.paper_years || []).forEach(y => { yearCounts[y] = (yearCounts[y] || 0) + 1; });
    });
    chartBars = Object.keys(yearCounts).map(Number).sort((a, b) => a - b).map(y => ({ label: y, value: yearCounts[y] }));
    domainSummary = `${papers} paper${papers === 1 ? "" : "s"} · ${citations} citation${citations === 1 ? "" : "s"} in ${activeDomains.length} selected domain${activeDomains.length === 1 ? "" : "s"}`;
  }

  // inc 117 (#10): the Decompose button is rendered inside the Publications controls row (passed as decomposeSlot),
  // not in the domains section header.
  const decomposeButton = (
    <button className="btn btn-ghost" disabled={domainJob.status === "running"} onClick={decompose}>
      {domainJob.status === "running" ? "Working…" : (domains.length ? "Re-decompose domains" : "Break down by domain")}
    </button>
  );

  // inc 118 (SP2 #18): when domain(s) are selected, lock the chart to Publications (domain-filtered) + disable Citations.
  const chartLocked = activeDomains.length > 0;
  const effectiveMode = chartLocked ? "pubs" : chartMode;

  // inc 118 (SP2 #15): rename helpers — suggest the closest axis name by domain-term overlap.
  const suggestAxis = (d) => {
    const terms = new Set((d.terms || []).map(t => String(t).toLowerCase()));
    let best = null;
    let bestScore = 0;
    for (const name of axisNames) {
      const score = String(name).toLowerCase().split(/\W+/).filter(Boolean).filter(w => terms.has(w)).length;
      if (score > bestScore) { bestScore = score; best = name; }
    }
    return bestScore > 0 ? best : null;
  };
  const startRename = (i, d) => { setEditLabel(suggestAxis(d) || d.label || ""); setEditingDomain(i); };
  const saveRename = (d) => {
    const label = editLabel.trim();
    if (!label) return;
    apiPost("/my-publications/domains/rename", { paper_ids: d.paper_ids || [], label }).then(r => {
      if (r.ok) { setEditingDomain(null); refetch(); }
    });
  };
  return (
    <div className="mypubs-dashboard">
      <div className="mypubs-head">
        <h2>{data.name || "My Publications"}</h2>
      </div>

      {/* Overview (#3/#4/#5) — collapsible: metrics 2×2 (left) + one flip-chart (right), last 10 years, 'NN labels */}
      <section className="mypubs-overview">
        <button className="mypubs-collapse" onClick={() => setOverviewOpen(o => !o)} title="Show/hide your metrics and chart">
          {overviewOpen ? "▾" : "▸"} Overview
        </button>
        {overviewOpen &&
          <div className="mypubs-overview-cols">
            <div className="metric-tiles metric-grid-2x2">
              <MyPubsTile label="Citations" value={m.cited_by_count} />
              <MyPubsTile label="h-index" value={m.h_index} />
              <MyPubsTile label="i10-index" value={m.i10_index} />
              <MyPubsTile label="Indexed works" value={m.works_count} />
            </div>
            <div className="mypubs-chart">
              <div className="mypubs-chart-flip">
                <button className={"chart-pill" + (effectiveMode === "pubs" ? " on" : "")} onClick={() => setChartMode("pubs")}>Publications</button>
                <button className={"chart-pill" + (effectiveMode === "cites" ? " on" : "")} disabled={chartLocked}
                  title={chartLocked ? "Clear the domain filter to see citations" : ""}
                  onClick={() => setChartMode("cites")}>Citations</button>
              </div>
              <MyPubsBarChart
                bars={(effectiveMode === "cites" ? citeBars : chartBars).slice(-10)}
                ariaLabel={effectiveMode === "cites" ? "Citations by year" : "Publications by year"}
              />
              {effectiveMode === "pubs" && domainSummary &&
                <div className="mypubs-domain-summary">{domainSummary} · <button className="axis-link" onClick={() => setSelectedDomains(new Set())}>clear</button></div>}
            </div>
          </div>}
      </section>

      {/* Research summary (r2) — #8: hide the "⭐ only" toggle when there are no starred pubs */}
      <div className="mypubs-summary">
        <div className="mypubs-summary-head">
          <span>Research summary <span className="mypubs-ai-tag">AI-generated draft — edit freely</span></span>
          <span className="mypubs-summary-actions">
            {(data.starred_count || 0) > 0 &&
              <label className="mypubs-starred-toggle" title="Generate from only your ⭐ starred publications (star them in the My Publications sidebar card)">
                <input type="checkbox" checked={starredOnly} onChange={e => setStarredOnly(e.target.checked)} /> ⭐ only
              </label>}
            <button className="btn btn-ghost" disabled={gen.status === "running"} onClick={generate}>
              {gen.status === "running" ? "Generating…" : (summary ? "Regenerate" : "Generate")}
            </button>
            <button className="btn btn-primary" disabled={save === "saving" || !dirty} onClick={saveSummary}>
              {save === "saving" ? "Saving…" : (save === "saved" && !dirty ? "Saved" : "Save")}
            </button>
          </span>
        </div>
        {gen.status === "running" && <ProgressBar label="Writing a draft from your publications…" managedBy="tracked-request" />}
        {gen.status === "error" && <div className="axis-err">{gen.error}</div>}
        <textarea
          className="mypubs-summary-text" rows={5}
          placeholder="Generate a draft from your publications, or write your own."
          value={summary}
          onChange={e => { setSummary(e.target.value); setDirty(true); setSave("idle"); }}
        />
      </div>

      {/* Publications (r3) — axis-scoped library cards with full parity (#7/#10/#13); Decompose hangs in its controls row */}
      <MyPubsPublications
        axisId={resolvedAxisId} onSummarize={onSummarize} onSelect={onSelectPaper} onOpenPdf={onOpenPdf}
        decomposeSlot={decomposeButton} domains={domains} starredIds={data.starred_ids}
        paperCitations={data.paper_citations} onOpenCiting={(workId, paper) => setCiting({ workId, title: paper.title })}
      />

      <div className="mypubs-domains">
        <div className="mypubs-summary-head">
          <span>Research domains{domains.length > 0 && <span className="mypubs-source"> · grouped by similarity — click to filter the chart</span>}</span>
        </div>
        {domainJob.status === "running" && <ProgressBar label="Clustering your publications…" managedBy="backend-job" />}
        {domainJob.status === "error" && <div className="axis-err">{domainJob.error}</div>}
        {domainJob.status === "too-few" && <div className="axis-hint">Need at least a few confirmed publications to break down by domain.</div>}
        {domains.length === 0 && domainJob.status === "idle" &&
          <div className="axis-hint">Group your publications into research domains to see impact by area.</div>}
        {domains.length > 0 &&
          <div className="domain-list">
            {domains.map((d, i) => (
              <div key={i} className="domain-row-wrap">
                {editingDomain === i
                  ? <div className="domain-rename">
                      <input className="domain-rename-input" list="mypubs-axis-names" autoFocus value={editLabel}
                        onChange={e => setEditLabel(e.target.value)}
                        onKeyDown={e => { if (e.key === "Enter") saveRename(d); if (e.key === "Escape") setEditingDomain(null); }} />
                      <button className="axis-link" onClick={() => saveRename(d)}>save</button>
                      <button className="axis-link" onClick={() => setEditingDomain(null)}>cancel</button>
                    </div>
                  : <>
                      <button type="button" className={"domain-row" + (selectedDomains.has(i) ? " on" : "")}
                        title={(d.terms || []).join(", ")} onClick={() => toggleDomain(i)}>
                        <span className="domain-fill" style={{ width: `${Math.round((d.citation_count / maxDomainCites) * 100)}%` }} />
                        <span className="domain-label">{d.label}</span>
                        <span className="domain-meta">{d.paper_count}p · {d.citation_count} cites</span>
                      </button>
                      <button className="axis-icon-btn domain-edit" title="Rename this domain" onClick={() => startRename(i, d)}>✎</button>
                    </>}
              </div>
            ))}
            <datalist id="mypubs-axis-names">{axisNames.map(n => <option key={n} value={n} />)}</datalist>
          </div>}
      </div>

      <MyPubsCitationGaps domains={domains} onSelectPaper={onSelectPaper} onLibraryChanged={onLibraryChanged} />
      <MyPubsEmergingTopics domains={domains} onSelectPaper={onSelectPaper} />
      <MyPubsCitingAuthors domains={domains} onSelectPaper={onSelectPaper} />

      {/* OpenAlex card (r4, footer) — provenance + gap + richer stats + refresh + the missing-works modal trigger (#1/#6/#11/#12) */}
      <section className="openalex-card">
        <div className="mypubs-summary-head">
          <span>OpenAlex</span>
          <span className="mypubs-source">{asOf ? "as of " + asOf : "not yet refreshed"}</span>
        </div>
        <div className="openalex-gap">
          <b>{data.indexed_works}</b> indexed · <b>{data.in_library}</b> in library
          {data.gap > 0 && <> · <span className="mypubs-gap-nudge">{data.gap} not imported</span></>}
          {((data.missing_works || []).length > 0 || (data.dismissed_works || []).length > 0) &&
            <button className="btn btn-ghost openalex-review" onClick={() => setMissingOpen(true)}>
              {(data.missing_works || []).length > 0
                ? `Review ${data.missing_works.length} →`
                : `Dismissed (${data.dismissed_works.length}) →`}
            </button>}
        </div>
        {data.openalex_extra &&
          <div className="mypubs-source openalex-stats">
            2-yr mean citedness {data.openalex_extra.two_year_mean_citedness}
            {data.openalex_extra.affiliation ? ` · ${data.openalex_extra.affiliation}` : ""}
            {data.openalex_extra.openalex_author_id &&
              <> · <a className="btn-link" href={`https://openalex.org/${data.openalex_extra.openalex_author_id}`}
                target="_blank" rel="noopener noreferrer">OpenAlex profile ↗</a></>}
          </div>}
        <div className="openalex-actions">
          <button className="btn btn-ghost" disabled={refreshing} onClick={refreshMyPubs}>
            {refreshing ? "Refreshing…" : "↻ Refresh from OpenAlex"}
          </button>
        </div>
        {refreshing && <ProgressBar label="Resolving via OpenAlex…" managedBy="backend-job" />}
      </section>

      <MissingWorksModal
        open={missingOpen} onClose={() => setMissingOpen(false)}
        missing={data.missing_works} dismissed={data.dismissed_works} onChanged={refetch}
      />

      {citing && <CitingModal workId={citing.workId} paperTitle={citing.title} onClose={() => setCiting(null)} />}
    </div>
  );
}
