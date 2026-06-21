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
          <div className="mypubs-chart-title">Publications by year</div>
          <MyPubsBarChart bars={pubsBars} ariaLabel="Publications by year" />
        </div>
        {citeBars.some(b => b.value > 0) &&
          <div className="mypubs-chart">
            <div className="mypubs-chart-title">Citations by year</div>
            <MyPubsBarChart bars={citeBars} ariaLabel="Citations by year" />
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
