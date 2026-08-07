// My Publications Layer 4 (inc 391): stable OpenAlex authors who appear on at least two bounded citing works
// that together cite at least two confirmed own publications. Reads are local; explicit refresh is the only
// egress. This is an evidence index for inspecting work, never a collaboration-fit recommendation.

function MyPubsCitingAuthors({ domains, onSelectPaper }) {
  const [state, setState] = useState({ status: "loading", authors: [], coverage: null, computedAt: null });
  const [refresh, setRefresh] = useState({ status: "idle" });
  const [selectedDomainKeys, setSelectedDomainKeys] = useState(() => new Set());
  // backlog #29 (inc 454): a quick "Follow" action reusing this card's already-resolved author_id — zero
  // extra OpenAlex resolution, feeds the Discover → Followed Authors gap source.
  const [followedIds, setFollowedIds] = useState(() => new Set());
  useEffect(() => {
    api("/followed-authors").then(r => { if (r.ok) setFollowedIds(new Set((r.data || []).map(a => a.author_id))); });
  }, []);
  const followAuthor = useCallback(async (authorId, displayName) => {
    const r = await apiPost("/followed-authors", { author_id: authorId, display_name: displayName });
    if (r.ok) setFollowedIds(prev => new Set(prev).add(authorId));
  }, []);
  const availableDomains = (domains || []).filter(domain => domain.key);
  const availableKeyToken = availableDomains.map(domain => domain.key).sort().join("|");
  const selectedKeys = Array.from(selectedDomainKeys).sort();
  const scopeQuery = selectedKeys.map(key => `domain_key=${encodeURIComponent(key)}`).join("&");
  const listPath = `/my-publications/citing-authors${scopeQuery ? `?${scopeQuery}` : ""}`;
  const selectedLabels = availableDomains
    .filter(domain => selectedDomainKeys.has(domain.key))
    .map(domain => domain.label);
  const scopeLabel = selectedLabels.length ? selectedLabels.join(" + ") : "all confirmed publications";

  const load = React.useCallback(() => {
    setState({ status: "loading", authors: [], coverage: null, computedAt: null });
    api(listPath).then(r => {
      if (r.ok) {
        setState({
          status: "ready",
          authors: r.data.authors || [],
          coverage: r.data.coverage || null,
          computedAt: r.data.computed_at || null,
        });
      } else setState({ status: "error", error: r.error, authors: [], coverage: null, computedAt: null });
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
    const started = await apiPost("/my-publications/citing-authors/refresh", {
      domain_keys: selectedKeys,
    });
    if (!started.ok) { setRefresh({ status: "error", error: started.error }); return; }
    const poll = (jobId) => api(`/my-publications/citing-authors/refresh/${jobId}`).then(r => {
      if (!r.ok) { setRefresh({ status: "error", error: r.error }); return; }
      if (r.data.status === "done") {
        setRefresh({ status: "idle" });
        load();
      } else if (r.data.status === "error") {
        setRefresh({ status: "error", error: r.data.detail || "Citing-author refresh failed." });
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
  const authors = coverage ? (state.authors || []) : [];
  const running = refresh.status === "running";
  const refreshLabel = selectedKeys.length
    ? (state.computedAt ? "↻ Refresh scoped authors" : "Find scoped authors")
    : (state.computedAt ? "↻ Refresh authors" : "Find citing authors");
  return (
    <section className="mypubs-prospection" aria-labelledby="mypubs-citing-authors-title">
      <div className="mypubs-summary-head">
        <span id="mypubs-citing-authors-title">
          Authors citing your work <span className="mypubs-grounded-tag">Grounded prospection</span>
        </span>
        <button className="btn btn-ghost" disabled={running} onClick={runRefresh}>
          {running ? "Scanning…" : refreshLabel}
        </button>
      </div>
      <p className="mypubs-prospection-intro">
        Authors on at least two retrieved works that together cite at least two of your confirmed publications.
        Use this private index to inspect their work; it does not infer collaboration fit or recommend a person.
      </p>
      {availableDomains.length > 0 &&
        <div className="mypubs-gap-scope">
          <span className="mypubs-gap-scope-label">Scan scope</span>
          <div className="mypubs-gap-scope-options" aria-label="Citing-author research-domain scope">
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

      {running && <ProgressBar label={`Checking repeated citing authors for ${scopeLabel} through OpenAlex…`} managedBy="backend-job" />}
      {refresh.status === "error" && <div className="axis-err">{refresh.error}</div>}
      {state.status === "error" && <div className="axis-err">{state.error}</div>}
      {state.status === "loading" && <div className="axis-hint">Loading the local citing-author snapshot…</div>}

      {state.computedAt && coverage &&
        <div className="mypubs-gap-coverage">
          Last refreshed {new Date(state.computedAt).toLocaleString()} · resolved {coverage.checked} of{" "}
          {coverage.total} confirmed publications in {scopeLabel}
          {coverage.total > coverage.with_doi ? ` (${coverage.total - coverage.with_doi} had no DOI)` : ""}.{" "}
          {coverage.unresolved_openalex_count > 0 &&
            ` ${coverage.unresolved_openalex_count} DOI-backed publications did not resolve in OpenAlex.`}
          Checked {coverage.citing_work_count} citing works from {coverage.start_year}–{coverage.end_year} and
          coauthorship metadata for {coverage.coauthor_checked_publication_count} of {coverage.checked} resolved
          publications.{" "}
          {coverage.coauthor_unresolved_publication_count > 0 &&
            ` ${coverage.coauthor_unresolved_publication_count} resolved publications had no returned authorship metadata.`}
          {coverage.excluded_coauthor_count > 0 &&
            ` Excluded ${coverage.excluded_coauthor_count} author identities found as coauthors.`}
          {coverage.missing_author_id_count > 0 &&
            ` ${coverage.missing_author_id_count} citing-work authorship positions lacked a retained OpenAlex author id.`}
          {coverage.publication_cap_reached && " The publication scan cap was reached."}
          {coverage.citing_window_cap_reached && " At least one citing-work window reached its result cap."}
          {(coverage.source_authorship_cap_count > 0 || coverage.citing_authorship_cap_count > 0) &&
            " At least one work's authorship list reached the per-work analysis cap."}
          <span>{coverage.note}</span>
        </div>}

      {!state.computedAt && state.status === "ready" &&
        <div className="axis-hint">
          No local snapshot for {scopeLabel}. Run an explicit scan when you want to query OpenAlex.
        </div>}
      {state.computedAt && !running && authors.length === 0 &&
        <div className="axis-hint">
          No retained author appeared on at least two citing works covering at least two of your publications in
          this bounded scan. This does not mean no relevant connection exists.
        </div>}

      <div className="mypubs-topic-list">
        {authors.map(author => (
          <article className="mypubs-topic-card" key={author.author_id}>
            <div className="mypubs-topic-card-main">
              <div>
                <a className="mypubs-gap-title" href={`https://openalex.org/${author.author_id}`}
                  target="_blank" rel="noopener noreferrer">{author.name} ↗</a>
                {followedIds.has(author.author_id)
                  ? <span className="discover-inlib" title="Already following">✓ Following</span>
                  : <button className="btn btn-link" onClick={() => followAuthor(author.author_id, author.name)}>
                      Follow
                    </button>}
                <div className="mypubs-topic-hierarchy">
                  OpenAlex author · latest retrieved citing work {author.latest_year}
                </div>
              </div>
              <div className="mypubs-topic-change">
                <b>{author.cited_publication_count}</b>
                <span>
                  of your publications · {author.citing_work_count} citing work
                  {author.citing_work_count === 1 ? "" : "s"}
                </span>
              </div>
            </div>
            <details className="mypubs-gap-evidence">
              <summary>Inspect every citing work and publication connection</summary>
              <div className="mypubs-topic-period">
                {(author.citing_works || []).map(work => (
                  <div className="mypubs-topic-work" key={work.openalex_work_id}>
                    <a href={`https://openalex.org/${work.openalex_work_id}`} target="_blank"
                      rel="noopener noreferrer">
                      {work.title || work.doi || work.openalex_work_id} ↗
                    </a>
                    <span>{work.year ? ` · ${work.year}` : ""}</span>
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
              <div className="mypubs-gap-caveat">
                No coauthorship was found in the checked OpenAlex own-work authorships. This bounded metadata
                check is not proof that you have never collaborated.
              </div>
            </details>
          </article>
        ))}
      </div>
    </section>
  );
}
