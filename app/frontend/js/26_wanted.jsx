// Wanted-list modal (inc 76). The OA acquisition "track" loop: a persistent list of papers you want an
// open-access copy of (library-linked or external), a manual "Re-check OA" job that runs the resolver
// cascade over the list and auto-acquires hits, plus a coverage readout. Clones DuplicatesModal's poll
// lifecycle; reuses the inc-74 .oa-chip recipe for the acquired summary.

function _wantedTitle(it) {
  return it.paper_title || it.title || it.doi || "Untitled";
}

// inc 588: triage the Wanted list off the STRUCTURED acquisition_state the API now provides (never by parsing
// the human last_result string). `blocked` = an OA copy was found but the automatic download was blocked — the
// user can usually get it themselves via the article page. Sort blocked-first; an item is "openable" iff it has
// a DOI (its actionable URL). The bulk open is bounded so it never spawns ~100 tabs.
const _OPEN_ALL_CAP = 15;
const _WANTED_STATE_RANK = { blocked: 0, unchecked: 1, no_oa: 2, needs_id: 3, error: 4, fulfilled: 5 };

// Plain-language default message per state; the raw last_result stays inspectable in a row tooltip. Deliberately
// NOT "the publisher blocked it" — the evidence doesn't identify a blocker, only that automatic download failed.
function _wantedStateMessage(it) {
  switch (it.acquisition_state) {
    case "blocked": return "Open-access copy found, but the automatic download was blocked";
    case "no_oa": return "No open-access copy found";
    case "needs_id": return "Needs a DOI or PMID to search";
    case "error": return "Couldn’t check (unexpected error)";
    case "fulfilled": return null;  // shown via the status pill + Open
    default: return "Not checked yet";
  }
}

function WantedModal({ onClose, onOpenPaper, onChanged }) {
  const [items, setItems] = useState([]);
  const [coverage, setCoverage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [addDoi, setAddDoi] = useState("");
  const [busy, setBusy] = useState(false);
  const [recheck, setRecheck] = useState({ status: "idle" });  // idle | running | done | error
  const [showOnlyBlocked, setShowOnlyBlocked] = useState(false);
  const [openAllOffset, setOpenAllOffset] = useState(0);  // where the next "Open all" batch resumes
  const [openAllMsg, setOpenAllMsg] = useState(null);

  const refresh = useCallback(() => {
    return Promise.all([api("/wanted"), api("/wanted/coverage")]).then(([li, cov]) => {
      if (li.ok) setItems(li.data.items || []);
      if (cov.ok) setCoverage(cov.data);
      setLoading(false);
    });
  }, []);

  useEffect(() => { refresh(); }, [refresh]);
  // A fresh list resets the bulk-open cursor + its feedback (the batches no longer line up).
  useEffect(() => { setOpenAllOffset(0); setOpenAllMsg(null); }, [items]);

  // Triage off the structured acquisition_state (inc 588): sort blocked-first, count what's actually actionable.
  const sortedItems = React.useMemo(
    () => [...items].sort((a, b) => (_WANTED_STATE_RANK[a.acquisition_state] ?? 9) - (_WANTED_STATE_RANK[b.acquisition_state] ?? 9)),
    [items],
  );
  const blockedItems = React.useMemo(() => sortedItems.filter(it => it.acquisition_state === "blocked"), [sortedItems]);
  const openableBlocked = React.useMemo(() => blockedItems.filter(it => it.doi), [blockedItems]);  // openable = has a DOI
  const visibleItems = showOnlyBlocked ? blockedItems : sortedItems;
  const blockedCount = blockedItems.length;
  const openableCount = openableBlocked.length;
  const nextBatchCount = Math.min(_OPEN_ALL_CAP, Math.max(0, openableCount - openAllOffset));

  // Bounded bulk open (inc 588): only openable (DOI-bearing) blocked items, ≈15 per click, explicit confirm,
  // honest remaining-count feedback. Never silently opens ~100 tabs. Opens the article PAGE via its DOI (not
  // necessarily the same OA copy that failed) in the user's browser — the free-and-legal hand-off, no scraping.
  const openAllBlocked = () => {
    const batch = openableBlocked.slice(openAllOffset, openAllOffset + _OPEN_ALL_CAP);
    if (!batch.length) { setOpenAllOffset(0); setOpenAllMsg("Reached the end — click once more to start over."); return; }
    if (!window.confirm(`Open ${batch.length} article page${batch.length === 1 ? "" : "s"} in your browser?`)) return;
    batch.forEach(it => openExternalUrl("https://doi.org/" + it.doi));
    const next = openAllOffset + batch.length;
    setOpenAllOffset(next);
    setOpenAllMsg(next < openableCount
      ? `Opened ${batch.length} — ${openableCount - next} of ${openableCount} left. Click again for the next batch.`
      : `Opened the last ${batch.length} of ${openableCount}.`);
  };

  const syncLibrary = async () => {
    setBusy(true);
    await apiPost("/wanted/sync-library", {});
    setBusy(false);
    refresh();
  };

  const addExternal = async () => {
    const doi = addDoi.trim();
    if (!doi) return;
    setBusy(true);
    const r = await apiPost("/wanted", { doi });
    setBusy(false);
    if (r.ok) { setAddDoi(""); refresh(); }
  };

  const removeItem = async (id) => {
    const r = await apiDelete(`/wanted/${id}`);
    if (r.ok) refresh();
  };

  const runRecheck = () => {
    setRecheck({ status: "running" });
    const poll = (jobId) => {
      api(`/wanted/recheck/${jobId}`).then(r => {
        if (!r.ok) { setRecheck({ status: "error", error: r.error }); return; }
        const d = r.data;
        if (d.status === "done") {
          setRecheck({ status: "done", summary: d.summary });
          refresh();
          if (onChanged) onChanged();  // acquired PDFs → refresh the main library
        } else if (d.status === "error") {
          setRecheck({ status: "error", error: d.detail || "Re-check failed." });
        } else {
          setTimeout(() => poll(jobId), 1500);
        }
      });
    };
    apiPost("/wanted/recheck", {}).then(r => {
      if (!r.ok) { setRecheck({ status: "error", error: r.error }); return; }
      poll(r.data.job_id);
    });
  };

  const cov = coverage;
  const summary = recheck.summary;
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Wanted list</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Papers you want an open-access copy of. <b>Sync from Library</b> adds your PDF-less papers;{" "}
          <b>Re-check OA</b> searches the open-access sources and imports any authorized copy it finds
          (bronze = unstable). Add an external paper by DOI.
        </div>

        {cov &&
          <div className="wanted-coverage">
            {cov.with_pdf} of {cov.library_total} papers have PDFs · acquired{" "}
            {cov.acquired_oa.gold} gold / {cov.acquired_oa.green} green / {cov.acquired_oa.bronze} bronze ·{" "}
            {cov.wanted_open} wanted
          </div>}

        <div className="wanted-actions">
          <button className="axis-link" disabled={busy} onClick={syncLibrary}>Sync from Library</button>
          <button className="btn btn-primary" disabled={recheck.status === "running"} onClick={runRecheck}>
            {recheck.status === "running" ? "Re-checking…" : "Re-check OA"}
          </button>
          <input className="wanted-add" placeholder="Add by DOI…" value={addDoi}
            onChange={e => setAddDoi(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") addExternal(); }} />
          <button className="axis-link" disabled={busy || !addDoi.trim()} onClick={addExternal}>Add</button>
        </div>

        {/* inc 588: blocked-OA triage banner — an OA copy exists but couldn't be downloaded automatically. Counts
            are honest: openable (can be opened directly) is stated separately from the blocked total, never conflated. */}
        {blockedCount > 0 &&
          <div className="wanted-blocked-summary">
            <span>
              <b>{blockedCount}</b> paper{blockedCount === 1 ? " has" : "s have"} an open-access copy that couldn’t be
              downloaded automatically{openableCount < blockedCount ? ` · ${openableCount} can be opened directly` : ""}.
            </span>
            <span className="wanted-blocked-actions">
              <label className="wanted-filter-toggle" title="Show only papers whose OA copy was blocked">
                <input type="checkbox" checked={showOnlyBlocked} onChange={e => setShowOnlyBlocked(e.target.checked)} />
                Show only these
              </label>
              {openableCount > 0 &&
                <button className="axis-link" onClick={openAllBlocked}
                  title="Open the article pages (via DOI) for blocked open-access papers in your browser, in bounded batches — so you can download them yourself. Callosum never fetches them for you.">
                  Open {nextBatchCount || openableCount} in browser ↗
                </button>}
            </span>
            {openAllMsg && <span className="wanted-openall-msg">{openAllMsg}</span>}
          </div>}
        {recheck.status === "running" && <ProgressBar label="Searching open-access sources…" managedBy="backend-job" />}

        {recheck.status === "error" && <div className="axis-err">Re-check failed: {recheck.error}</div>}
        {recheck.status === "done" && summary &&
          <div className="wanted-summary">
            Acquired {summary.acquired.length} · {summary.still_wanted} still wanted
            {summary.skipped ? ` · ${summary.skipped} need an identifier` : ""}
            {summary.errors ? ` · ${summary.errors} error${summary.errors === 1 ? "" : "s"}` : ""}
            {summary.acquired.length > 0 &&
              <div className="oa-meta wanted-acquired">
                {summary.acquired.map((a, i) =>
                  <span key={i} className={"oa-chip " + (a.oa_color === "bronze" ? "oa-bronze" : "oa-durable")}>
                    {a.oa_color}/{a.oa_version}
                  </span>)}
              </div>}
          </div>}

        {loading && <div className="axis-hint">Loading…</div>}
        {!loading && items.length === 0 &&
          <div className="axis-hint">Your wanted list is empty. Sync from library or add a DOI.</div>}
        {!loading && items.length > 0 && visibleItems.length === 0 &&
          <div className="axis-hint">No blocked open-access papers. <button className="axis-link" onClick={() => setShowOnlyBlocked(false)}>Show all</button></div>}
        {visibleItems.map(it => (
          <div key={it.id} className="wanted-row">
            <div className="wanted-row-info">
              <div className="wanted-row-title">{_wantedTitle(it)}</div>
              <div className="wanted-row-meta">
                {it.paper_id ? "library" : "external"}
                {it.paper_year ? " · " + it.paper_year : ""}
                {/* Plain-language state by default; the raw last_result stays inspectable on hover (inc 588). */}
                {_wantedStateMessage(it) &&
                  <span className={"wanted-row-state" + (it.acquisition_state === "blocked" ? " is-blocked" : "")}
                    title={it.last_result || undefined}> · {_wantedStateMessage(it)}</span>}
              </div>
            </div>
            <span className={"wanted-status" + (it.status === "fulfilled" ? " fulfilled" : "")}>{it.status}</span>
            {it.paper_id && it.status === "fulfilled" &&
              <button className="axis-link"
                onClick={() => onOpenPaper && onOpenPaper({ id: it.paper_id, title: _wantedTitle(it) })}>Open</button>}
            {/* inc 587/588: fetch it yourself when Callosum couldn't download it (an OA copy exists but the
                automatic download was blocked). Opens the article's own PAGE via its DOI (not necessarily the same
                OA copy that failed) in the user's browser — the free-and-legal hand-off, never scraping. */}
            {it.doi && it.status !== "fulfilled" &&
              <button className="axis-link"
                title="Open this article's page (via its DOI) in your browser — if it's freely readable, download the PDF yourself and add it to your library."
                onClick={() => openExternalUrl("https://doi.org/" + it.doi)}>
                Open article ↗
              </button>}
            <button className="axis-link" title="Remove from the wanted list" onClick={() => removeItem(it.id)}>×</button>
          </div>
        ))}

        <div className="axis-form-actions">
          <button className="axis-link" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
