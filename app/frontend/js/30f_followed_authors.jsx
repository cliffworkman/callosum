// Followed-authors gap-finder source (backlog #29, inc 454): follow an OpenAlex author (reuses the same
// resolve-author flow My-Publications' profile/citing-authors already use) — Refresh fetches their works
// (cached/TTL) and surfaces those absent from the library, "by <author> (followed)". Flat, deduped-against-
// library, NOT ranked by axis relevance (a disclosed v1 limitation — that machinery doesn't exist for this
// source yet). Clones FeedPane's subs-chips + add-row shell and GapsModal's gap-row candidate-list idiom.

function FollowedAuthorsPane({ active, onSaved }) {
  const [authors, setAuthors] = useState([]);
  const [nameInput, setNameInput] = useState("");
  const [orcidInput, setOrcidInput] = useState("");
  const [followErr, setFollowErr] = useState("");
  const [rows, setRows] = useState([]);
  const [refresh, setRefresh] = useState({ status: "idle" });
  const [lastScan, setLastScan] = useState(null);

  const loadAuthors = useCallback(() => {
    api("/followed-authors").then(r => { if (r.ok) setAuthors(r.data || []); });
  }, []);
  const loadCandidates = useCallback(() => {
    api("/followed-authors/candidates").then(r => { if (r.ok) setRows(r.data.candidates || []); });
  }, []);
  useEffect(() => { loadAuthors(); loadCandidates(); }, [loadAuthors, loadCandidates]);

  const follow = async () => {
    const name = nameInput.trim(), orcid = orcidInput.trim();
    if (!name && !orcid) return;
    setFollowErr("");
    const r = await apiPost("/followed-authors", { name: name || null, orcid: orcid || null });
    if (!r.ok) { setFollowErr(r.error); return; }
    if (r.data.status === "no-match") { setFollowErr("No OpenAlex author matched that name/ORCID."); return; }
    setNameInput(""); setOrcidInput(""); loadAuthors();
  };

  const unfollow = async (authorId) => {
    await apiDelete(`/followed-authors/${authorId}`);
    loadAuthors(); loadCandidates();
  };

  const runRefresh = async (authorId) => {
    setRefresh({ status: "running" }); setLastScan(null);
    const poll = (jobId) => api(`/followed-authors/refresh/${jobId}`).then(r => {
      if (!r.ok) { setRefresh({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") {
        setRefresh({ status: "idle" });
        setLastScan({ authorsRefreshed: d.result.authors_refreshed, worksChecked: d.result.works_checked, note: d.result.note });
        loadAuthors(); loadCandidates();
      } else if (d.status === "error") setRefresh({ status: "error", error: d.detail || "Followed-authors refresh failed." });
      else setTimeout(() => poll(jobId), 2000);
    });
    const r = await apiPost("/followed-authors/refresh", { author_id: authorId || null });
    if (!r.ok) { setRefresh({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };

  const add = async (row) => {
    const r = await apiPost("/followed-authors/add", { doi: row.doi, openalex_work_id: row.openalex_work_id, title: row.title });
    if (r.ok) { loadCandidates(); if (onSaved) onSaved(); }
  };
  const dismiss = async (row) => {
    const r = await apiPost("/followed-authors/dismiss", { openalex_work_id: row.openalex_work_id, doi: row.doi });
    if (r.ok) loadCandidates();
  };

  const running = refresh.status === "running";
  return (
    <div className="discover followed-authors">
      <div className="pane-head">
        <div className="feed-subs">
          {authors.map(a => (
            <span key={a.author_id} className="feed-sub"
              title={`OpenAlex ${a.author_id}${a.matched_by === "name" ? " · matched by name, not ORCID — lower confidence" : ""}${a.last_refreshed_at ? ` · last refreshed ${new Date(a.last_refreshed_at).toLocaleString()}` : " · never refreshed"}`}>
              <span className="feed-sub-kind">Author</span>{a.display_name}
              <button className="feed-sub-x"
                title={isDemoMode() ? "Unfollowing needs the persistent local library" : "Unfollow"}
                onClick={() => unfollow(a.author_id)}>×</button>
            </span>
          ))}
          {!authors.length ? <span className="discover-hint">Follow an author to start surfacing their absent works.</span> : null}
        </div>
        <div className="searchbar">
          <input value={nameInput} disabled={isDemoMode()} onChange={e => setNameInput(e.target.value)} placeholder="Author name…" />
          <input value={orcidInput} disabled={isDemoMode()} onChange={e => setOrcidInput(e.target.value)} placeholder="or ORCID (0000-0002-1825-0097)" />
          <button className="btn btn-ghost" onClick={follow} disabled={isDemoMode() || (!nameInput.trim() && !orcidInput.trim())}>Follow</button>
          <button className="btn btn-primary" disabled={running || !authors.length} onClick={() => runRefresh(null)}
            title={isDemoMode() ? "Refresh needs the local backend and OpenAlex" : undefined}>
            {running ? "Scanning…" : "Refresh all"}
          </button>
        </div>
        {followErr && <div className="axis-err">{followErr}</div>}
      </div>
      <div className="axis-modal-note">
        Works by a followed author that aren't in your library yet. <b>Add</b> imports the metadata; <b>Dismiss</b> hides
        it for good. Not filtered or ranked by relevance to your research axes — only deduplicated against your library.
      </div>
      {running && <ProgressBar label="Checking followed authors' works through OpenAlex…" managedBy="backend-job" />}
      {refresh.status === "error" && <div className="axis-err">{refresh.error}</div>}
      {lastScan &&
        <div className="gaps-coverage">
          Refreshed {lastScan.authorsRefreshed} author{lastScan.authorsRefreshed === 1 ? "" : "s"}, checked {lastScan.worksChecked} works. {lastScan.note}
        </div>}
      {!running && authors.length > 0 && rows.length === 0 &&
        <div className="axis-hint">No absent works for your followed authors — everything found is already in your library, or nothing has been refreshed yet.</div>}
      <div className="pane-list-body">
        {rows.map(row => (
          <div key={`${row.author_id}-${row.openalex_work_id || row.doi}`} className="gap-row">
            <div className="gap-row-info">
              <div className="gap-row-title">{row.title || row.doi}</div>
              <div className="gap-row-meta">
                <span className="gap-count">by {row.author_display_name} (followed)</span>
                {row.year ? ` · ${row.year}` : ""}
              </div>
            </div>
            <div className="gap-row-actions">
              <button className="axis-link" onClick={() => add(row)}
                title={isDemoMode() ? "Adding changes the persistent local library" : undefined}>Add</button>
              <button className="axis-link" onClick={() => dismiss(row)}
                title={isDemoMode() ? "Dismissing changes persistent local state" : undefined}>Dismiss</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
