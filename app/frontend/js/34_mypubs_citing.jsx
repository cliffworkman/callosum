// My Publications — the citing-articles modal (inc 119, SP3 #14). Lists the papers OpenAlex records as CITING one
// of the user's works (discovery candidates — coverage stated, not exhaustive) and imports selected ones
// (metadata-only) into the GENERAL library (not My Publications — they aren't the user's works). Per-row Import +
// a confirm-gated "Import all". The PDF stays the separate "Acquire OA copy" step (no paywall circumvention).
function CitingModal({ workId, paperTitle, onClose }) {
  const [state, setState] = useState({ status: "loading" });
  const [busy, setBusy] = useState(() => new Set());

  const load = () => {
    setState({ status: "loading" });
    api(`/my-publications/citing/${workId}`).then(r => {
      if (r.ok) setState({ status: "ready", works: r.data.works || [], capped: !!r.data.capped });
      else setState({ status: "error", error: r.error });
    });
  };
  useEffect(load, [workId]);

  const importOne = async (w) => {
    setBusy(b => new Set(b).add(w.doi));
    const r = await apiPost("/my-publications/citing/import", { doi: w.doi, title: w.title });
    if (r.ok) load();  // refresh the in-library markers
    setBusy(b => { const n = new Set(b); n.delete(w.doi); return n; });
  };

  const importAll = async () => {
    const todo = (state.works || []).filter(w => w.doi && !w.in_library);
    if (!todo.length) return;
    if (!window.confirm(`Import ${todo.length} citing paper${todo.length === 1 ? "" : "s"} (metadata only) into your library?`)) return;
    for (const w of todo) {
      await apiPost("/my-publications/citing/import", { doi: w.doi, title: w.title });
    }
    load();
  };

  const works = state.works || [];
  const importable = works.filter(w => w.doi && !w.in_library).length;
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Cited by{paperTitle ? ` — ${paperTitle}` : ""}</span>
          <button className="axis-link citing-close" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Papers OpenAlex records as citing this work (as of your last refresh — OpenAlex's coverage, not exhaustive).
          {isDemoMode()
            ? " This saved cited-by result is fully inspectable; importing a record or acquiring its document requires local Callosum."
            : " Import the ones you want (metadata only; use a paper's “Acquire OA copy” afterward for the PDF)."}
          {state.capped ? " Showing the first 100." : ""}
        </div>
        {state.status === "loading" && <div className="axis-hint">Loading citing papers…</div>}
        {state.status === "error" && <div className="axis-err">Couldn't load citing papers: {state.error}</div>}
        {state.status === "ready" && works.length === 0 &&
          <div className="axis-hint">OpenAlex records no citing papers for this work (yet).</div>}
        {state.status === "ready" && importable > 0 &&
          <div className="citing-allbar">
            <button className="btn btn-ghost" disabled={isDemoMode()} onClick={importAll}
              title={isDemoMode() ? "Importing citing works requires the local Callosum database." : undefined}>Import all ({importable})</button>
          </div>}
        {works.map((w, i) => (
          <div key={(w.doi || "") + i} className="citing-row missing-row">
            <div className="missing-info">
              <div className="missing-title" title={w.title || w.doi}>{w.title || w.doi || "(untitled)"}</div>
              <div className="missing-meta">
                {(w.authors || []).slice(0, 3).join(", ")}{w.year ? ` · ${w.year}` : ""} · {w.cited_by_count} cited-by{w.doi ? ` · ${w.doi}` : ""}
              </div>
            </div>
            {w.in_library
              ? <span className="citing-inlib">✓ in library</span>
              : (w.doi
                  ? <button className="btn btn-ghost citing-import" disabled={isDemoMode() || busy.has(w.doi)}
                      title={isDemoMode() ? "Importing this citing work requires the local Callosum database." : undefined}
                      onClick={() => importOne(w)}>Import</button>
                  : <span className="axis-hint">no DOI</span>)}
          </div>
        ))}
      </div>
    </div>
  );
}
