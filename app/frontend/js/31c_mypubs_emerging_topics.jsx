// My Publications Layer 4 (inc 390): primary topics that occur more often among bounded OpenAlex citing works
// in the last three complete years than in the preceding three. Reads are local; explicit refresh is the only
// egress. Every count expands to the citing works and exact own publications behind it.

function MyPubsEmergingTopics({ domains, onSelectPaper }) {
  const [state, setState] = useState({ status: "loading", topics: [], coverage: null, computedAt: null });
  const [refresh, setRefresh] = useState({ status: "idle" });
  const [selectedDomainKeys, setSelectedDomainKeys] = useState(() => new Set());
  const availableDomains = (domains || []).filter(domain => domain.key);
  const availableKeyToken = availableDomains.map(domain => domain.key).sort().join("|");
  const selectedKeys = Array.from(selectedDomainKeys).sort();
  const scopeQuery = selectedKeys.map(key => `domain_key=${encodeURIComponent(key)}`).join("&");
  const listPath = `/my-publications/emerging-citing-topics${scopeQuery ? `?${scopeQuery}` : ""}`;
  const selectedLabels = availableDomains
    .filter(domain => selectedDomainKeys.has(domain.key))
    .map(domain => domain.label);
  const scopeLabel = selectedLabels.length ? selectedLabels.join(" + ") : "all confirmed publications";

  const load = React.useCallback(() => {
    setState({ status: "loading", topics: [], coverage: null, computedAt: null });
    api(listPath).then(r => {
      if (r.ok) {
        setState({
          status: "ready",
          topics: r.data.topics || [],
          coverage: r.data.coverage || null,
          computedAt: r.data.computed_at || null,
        });
      } else setState({ status: "error", error: r.error, topics: [], coverage: null, computedAt: null });
    });
  }, [listPath]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const available = new Set(availableDomains.map(domain => domain.key));
    setSelectedDomainKeys(previous => {
      const next = new Set(Array.from(previous).filter(key => available.has(key)));
      return next.size === previous.size ? previous : next;
    });
  }, [availableKeyToken]);

  const runRefresh = async () => {
    setRefresh({ status: "running" });
    const started = await apiPost("/my-publications/emerging-citing-topics/refresh", {
      domain_keys: selectedKeys,
    });
    if (!started.ok) { setRefresh({ status: "error", error: started.error }); return; }
    const poll = (jobId) => api(`/my-publications/emerging-citing-topics/refresh/${jobId}`).then(r => {
      if (!r.ok) { setRefresh({ status: "error", error: r.error }); return; }
      if (r.data.status === "done") {
        setRefresh({ status: "idle" });
        load();
      } else if (r.data.status === "error") {
        setRefresh({ status: "error", error: r.data.detail || "Emerging-topic refresh failed." });
      } else setTimeout(() => poll(jobId), 1800);
    });
    poll(started.data.job_id);
  };

  const toggleDomain = (key) => {
    setRefresh({ status: "idle" });
    setSelectedDomainKeys(previous => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const clearDomains = () => {
    setRefresh({ status: "idle" });
    setSelectedDomainKeys(new Set());
  };

  const coverage = state.coverage;
  const topics = coverage ? (state.topics || []) : [];
  const running = refresh.status === "running";
  const refreshLabel = selectedKeys.length
    ? (state.computedAt ? "↻ Refresh scoped topics" : "Find scoped topics")
    : (state.computedAt ? "↻ Refresh topics" : "Find emerging topics");
  const yearRange = (start, end) => `${start}–${end}`;
  return (
    <section className="mypubs-prospection" aria-labelledby="mypubs-emerging-topics-title">
      <div className="mypubs-summary-head">
        <span id="mypubs-emerging-topics-title">
          Emerging citing topics <span className="mypubs-grounded-tag">Grounded prospection</span>
        </span>
        <button className="btn btn-ghost" disabled={isDemoMode() || running} onClick={runRefresh}
          title={isDemoMode() ? "Refreshing emerging topics queries OpenAlex and requires local Callosum." : undefined}>
          {running ? "Scanning…" : refreshLabel}
        </button>
      </div>
      <p className="mypubs-prospection-intro">
        OpenAlex primary topics appearing more often among recent works that cite you than in the preceding
        equal-length window. The visible paper-count increase is descriptive evidence, not a forecast.
      </p>
      {isDemoMode() && <div className="settings-note">Saved bounded comparison of recent and earlier citing-work windows. Refreshing the OpenAlex snapshot requires local Callosum.</div>}
      {availableDomains.length > 0 &&
        <div className="mypubs-gap-scope">
          <span className="mypubs-gap-scope-label">Scan scope</span>
          <div className="mypubs-gap-scope-options" aria-label="Emerging-topic research-domain scope">
            <button type="button" className={"mypubs-gap-scope-chip" + (selectedKeys.length === 0 ? " on" : "")}
              aria-pressed={selectedKeys.length === 0} disabled={running} onClick={clearDomains}>
              All publications
            </button>
            {availableDomains.map(domain => (
              <button type="button" key={domain.key}
                className={"mypubs-gap-scope-chip" + (selectedDomainKeys.has(domain.key) ? " on" : "")}
                aria-pressed={selectedDomainKeys.has(domain.key)} disabled={running}
                onClick={() => toggleDomain(domain.key)}>
                {domain.label} <span>{domain.paper_count}p</span>
              </button>
            ))}
          </div>
          <span className="mypubs-gap-scope-hint">
            {selectedKeys.length
              ? `Scanning the union of ${selectedKeys.length} selected domain${selectedKeys.length === 1 ? "" : "s"}.`
              : "Select one or more domains to narrow the scan; each scope keeps its own local snapshot."}
          </span>
        </div>}

      {running && <ProgressBar label={`Comparing citing-topic windows for ${scopeLabel} through OpenAlex…`} managedBy="backend-job" />}
      {refresh.status === "error" && <div className="axis-err">{refresh.error}</div>}
      {state.status === "error" && <div className="axis-err">{state.error}</div>}
      {state.status === "loading" && <div className="axis-hint">Loading the local emerging-topic snapshot…</div>}

      {state.computedAt && coverage &&
        <div className="mypubs-gap-coverage">
          Last refreshed {new Date(state.computedAt).toLocaleString()} · resolved {coverage.checked} of{" "}
          {coverage.total} confirmed publications in {scopeLabel}
          {coverage.total > coverage.with_doi ? ` (${coverage.total - coverage.with_doi} had no DOI)` : ""}.
          {coverage.unresolved_openalex_count > 0 &&
            ` ${coverage.unresolved_openalex_count} DOI-backed publications did not resolve in OpenAlex.`}
          Compared {coverage.recent_work_count} citing works from{" "}
          {yearRange(coverage.recent_start_year, coverage.recent_end_year)} with{" "}
          {coverage.previous_work_count} from{" "}
          {yearRange(coverage.previous_start_year, coverage.previous_end_year)}.
          {coverage.missing_primary_topic_count > 0 &&
            ` ${coverage.missing_primary_topic_count} retrieved works had no usable primary topic.`}
          {coverage.publication_cap_reached && " The publication scan cap was reached."}
          {(coverage.recent_window_cap_reached || coverage.previous_window_cap_reached) &&
            " At least one citing-work window reached its result cap."}
          <span>{coverage.note}</span>
        </div>}

      {!state.computedAt && state.status === "ready" &&
        <div className="axis-hint">
          No local snapshot for {scopeLabel}. Run an explicit scan when you want to query OpenAlex.
        </div>}
      {state.computedAt && !running && topics.length === 0 &&
        <div className="axis-hint">
          No primary topic had at least two recent citing works and a positive increase in this bounded scan.
          This does not mean the citing landscape is static or complete.
        </div>}

      <div className="mypubs-topic-list">
        {topics.map(topic => {
          const hierarchy = [topic.subfield, topic.field, topic.domain].filter(Boolean).join(" · ");
          const renderWorks = (works, label, years) => (
            <div className="mypubs-topic-period">
              <div className="mypubs-topic-period-title">{label} · {years}</div>
              {(works || []).map(work => (
                <div className="mypubs-topic-work" key={work.openalex_work_id}>
                  <a href={`https://openalex.org/${work.openalex_work_id}`} target="_blank"
                    rel="noopener noreferrer">
                    {work.title || work.doi || work.openalex_work_id} ↗
                  </a>
                  <span>{work.year ? ` · ${work.year}` : ""}</span>
                  {(work.authors || []).length > 0 &&
                    <span> · {work.authors.slice(0, 3).join(", ")}{work.authors.length > 3 ? " et al." : ""}</span>}
                  <div className="mypubs-topic-cites">
                    cites{" "}
                    {(work.cited_publications || []).map((paper, index) => (
                      <React.Fragment key={paper.paper_id}>
                        {index > 0 && <span>, </span>}
                        <button className="axis-link" onClick={() =>
                          onSelectPaper && onSelectPaper(paper.paper_id)}>
                          {paper.title}
                        </button>
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          );
          return (
            <article className="mypubs-topic-card" key={topic.topic_id}>
              <div className="mypubs-topic-card-main">
                <div>
                  <a className="mypubs-gap-title" href={`https://openalex.org/${topic.topic_id}`}
                    target="_blank" rel="noopener noreferrer">{topic.name} ↗</a>
                  {hierarchy && <div className="mypubs-topic-hierarchy">{hierarchy}</div>}
                </div>
                <div className="mypubs-topic-change">
                  <b>+{topic.increase}</b>
                  <span>
                    {topic.recent_count} vs {topic.previous_count} citing work
                    {topic.previous_count === 1 ? "" : "s"}
                  </span>
                </div>
              </div>
              <details className="mypubs-gap-evidence">
                <summary>Inspect the citing works behind both counts</summary>
                {renderWorks(
                  topic.recent_works,
                  "Recent",
                  yearRange(coverage.recent_start_year, coverage.recent_end_year),
                )}
                {renderWorks(
                  topic.previous_works,
                  "Earlier",
                  yearRange(coverage.previous_start_year, coverage.previous_end_year),
                )}
                <div className="mypubs-gap-caveat">
                  The increase describes retrieved OpenAlex records assigned to this primary topic; it does not
                  establish that the research area itself is growing.
                </div>
              </details>
            </article>
          );
        })}
      </div>
    </section>
  );
}
