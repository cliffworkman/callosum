// My Publications impact dashboard (inc 81, Part 2 Layer 1). Opens as a frame tab (LibraryFrame) from the
// 📊 button on the pinned My Publications axis card. A cache-only read of the resolved OpenAlex record + the
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
            <text className="pubs-bar-year" x={x + barW / 2} y={h - 5} textAnchor="middle">{String(b.label).slice(2)}</text>
          </g>
        );
      })}
    </svg>
  );
}

function MyPubsDashboard({ axisId }) {
  const [data, setData] = useState({ status: "loading" });
  const [summary, setSummary] = useState("");
  const [dirty, setDirty] = useState(false);
  const [gen, setGen] = useState({ status: "idle" });   // idle | running | error
  const [save, setSave] = useState("idle");             // idle | saving | saved
  const [domainJob, setDomainJob] = useState({ status: "idle" });  // idle | running | error | too-few
  const [selectedDomains, setSelectedDomains] = useState(() => new Set());  // indices of domains filtering the chart

  const refetch = () => api("/my-publications/dashboard").then(r => {
    if (r.ok) { setData(r.data); setSummary(r.data.research_summary || ""); }
  });

  useEffect(() => {
    let live = true;
    api("/my-publications/dashboard").then(r => {
      if (!live) return;
      if (r.ok) { setData(r.data); setSummary(r.data.research_summary || ""); }
      else setData({ status: "error", error: r.error });
    });
    return () => { live = false; };
  }, []);

  const generate = async () => {
    setGen({ status: "running" });
    const r = await apiPost("/my-publications/summary/generate", {});
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
  return (
    <div className="mypubs-dashboard">
      <div className="mypubs-head">
        <h2>{data.name || "My Publications"}</h2>
        <span className="mypubs-source">source: OpenAlex{asOf ? " · as of " + asOf : ""} · refresh in ⚙ Settings</span>
      </div>

      <div className="metric-tiles">
        <MyPubsTile label="Citations" value={m.cited_by_count} />
        <MyPubsTile label="h-index" value={m.h_index} />
        <MyPubsTile label="i10-index" value={m.i10_index} />
        <MyPubsTile label="Indexed works" value={m.works_count} />
      </div>

      <div className="mypubs-gap">
        <b>{data.indexed_works}</b> works indexed by OpenAlex · <b>{data.in_library}</b> in your library
        {data.gap > 0 && <span className="mypubs-gap-nudge"> — {data.gap} not yet imported</span>}
      </div>

      <div className="mypubs-charts">
        <div className="mypubs-chart">
          <div className="mypubs-chart-title">Publications by year{activeDomains.length ? " · filtered to selected domain(s)" : ""}</div>
          <MyPubsBarChart bars={chartBars} ariaLabel="Publications by year" />
          {domainSummary &&
            <div className="mypubs-domain-summary">{domainSummary} · <button className="axis-link" onClick={() => setSelectedDomains(new Set())}>clear</button></div>}
        </div>
        {!activeDomains.length && citeBars.some(b => b.value > 0) &&
          <div className="mypubs-chart">
            <div className="mypubs-chart-title">Citations by year</div>
            <MyPubsBarChart bars={citeBars} ariaLabel="Citations by year" />
          </div>}
      </div>

      <div className="mypubs-domains">
        <div className="mypubs-summary-head">
          <span>Research domains{domains.length > 0 && <span className="mypubs-source"> · grouped by similarity — click to filter the chart</span>}</span>
          <span className="mypubs-summary-actions">
            <button className="btn btn-ghost" disabled={domainJob.status === "running"} onClick={decompose}>
              {domainJob.status === "running" ? "Working…" : (domains.length ? "Re-decompose" : "Break down by domain")}
            </button>
          </span>
        </div>
        {domainJob.status === "running" && <ProgressBar label="Clustering your publications…" />}
        {domainJob.status === "error" && <div className="axis-err">{domainJob.error}</div>}
        {domainJob.status === "too-few" && <div className="axis-hint">Need at least a few confirmed publications to break down by domain.</div>}
        {domains.length === 0 && domainJob.status === "idle" &&
          <div className="axis-hint">Group your publications into research domains to see impact by area.</div>}
        {domains.length > 0 &&
          <div className="domain-list">
            {domains.map((d, i) => (
              <button key={i} type="button" className={"domain-row" + (selectedDomains.has(i) ? " on" : "")}
                title={(d.terms || []).join(", ")} onClick={() => toggleDomain(i)}>
                <span className="domain-fill" style={{ width: `${Math.round((d.citation_count / maxDomainCites) * 100)}%` }} />
                <span className="domain-label">{d.label}</span>
                <span className="domain-meta">{d.paper_count}p · {d.citation_count} cites</span>
              </button>
            ))}
          </div>}
      </div>

      <div className="mypubs-summary">
        <div className="mypubs-summary-head">
          <span>Research summary <span className="mypubs-ai-tag">AI-generated draft — edit freely</span></span>
          <span className="mypubs-summary-actions">
            <button className="btn btn-ghost" disabled={gen.status === "running"} onClick={generate}>
              {gen.status === "running" ? "Generating…" : (summary ? "Regenerate" : "Generate")}
            </button>
            <button className="btn btn-primary" disabled={save === "saving" || !dirty} onClick={saveSummary}>
              {save === "saving" ? "Saving…" : (save === "saved" && !dirty ? "Saved" : "Save")}
            </button>
          </span>
        </div>
        {gen.status === "running" && <ProgressBar label="Writing a draft from your publications…" />}
        {gen.status === "error" && <div className="axis-err">{gen.error}</div>}
        <textarea
          className="mypubs-summary-text" rows={5}
          placeholder="Generate a draft from your publications, or write your own."
          value={summary}
          onChange={e => { setSummary(e.target.value); setDirty(true); setSave("idle"); }}
        />
      </div>
    </div>
  );
}
