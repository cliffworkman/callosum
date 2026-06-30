// inc 208: the library-header dropdown menus, extracted from 10_pdf_layer.jsx (which crossed the 600-line cap when
// the saved-search menu landed — rule #1). Both are small, self-contained dropdowns used by PaperList (in
// 10_pdf_layer.jsx) — referenced via the shared-IIFE function hoist, so chunk order is irrelevant.

// inc-93→94: the "bring papers in" actions (Scan folder + Import) folded into one "+ Add ▾" menu to declutter
// the library header. Closes on outside-click. The trigger styles as a .trash-toggle so it blends with the row.
function AddMenu({ onScan, onImport }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);
  const pick = (fn) => { setOpen(false); fn(); };
  return (
    <span className="add-menu" ref={ref}>
      <button className="trash-toggle add" onClick={() => setOpen(o => !o)} title="Add papers to the library">+ Add ▾</button>
      {open &&
        <div className="add-menu-pop">
          <button onClick={() => pick(onScan)} title="Add &amp; watch folders of PDFs — new files are picked up automatically">Watched folders…</button>
          <button onClick={() => pick(onImport)} title="Import a BibTeX, RIS, or CSL-JSON citation file">Import file…</button>
        </div>}
    </span>
  );
}

// inc-210 (A2): a header control to refresh per-paper OpenAlex cited-by counts. Self-contained: POSTs the async
// batch, polls the job, then calls onRefreshed() (the library reloads → the cards show counts). `asOf` (the
// freshest retrieved_at across the loaded list) makes the source + date VISIBLE — verbatim + attributed, never a
// silent rank (Principles #2/#7/#8). Public-metadata egress, NOT the Gemini gate.
function CitationCountsButton({ asOf, onRefreshed }) {
  const [busy, setBusy] = useState(false);
  const [prog, setProg] = useState(null);  // {current,total}
  const run = async () => {
    if (busy) return;
    setBusy(true); setProg(null);
    const start = await apiPost("/papers/citation-counts/refresh", {});
    const jid = start.ok && start.data ? start.data.job_id : null;
    if (!jid) { setBusy(false); return; }
    for (let i = 0; i < 600; i++) {
      await new Promise(r => setTimeout(r, 600));
      const r = await api("/papers/citation-counts/refresh/" + jid);
      if (!r.ok) break;
      if (r.data.progress) setProg({ current: r.data.progress.current, total: r.data.progress.total, eta: r.data.progress.eta_seconds });
      if (r.data.status === "done" || r.data.status === "error") { onRefreshed && onRefreshed(); break; }
    }
    setBusy(false); setProg(null);
  };
  const date = asOf ? String(asOf).slice(0, 10) : null;
  return (
    <button className="trash-toggle" onClick={run} disabled={busy}
      title="Fetch each paper's cited-by count from OpenAlex (public metadata; shown verbatim, not a ranking)">
      {busy ? (prog ? `Citations ${prog.current}/${prog.total}${prog.eta ? " ~" + _fmtEta(prog.eta) : ""}` : "Citations…") : (date ? `Citations · ${date}` : "Citations ↻")}
    </button>
  );
}

// inc-217: a header control to gap-fill missing bibliographic metadata across the whole library. Self-contained:
// POSTs the async batch, polls the job, then calls onRefreshed() (the library reloads). Each paper's EMPTY fields
// are filled from Crossref/OpenAlex (SP2 adds Europe PMC + PubMed) — never overwriting a value you typed. Public
// bibliographic-metadata egress (the inc-87/183/210 posture), NOT the Gemini library-text gate.
function EnrichMetadataButton({ onRefreshed }) {
  const [busy, setBusy] = useState(false);
  const [prog, setProg] = useState(null);  // {current,total}
  const [done, setDone] = useState(null);  // {papers,dois_recovered,fields_filled,still_missing_doi}
  const run = async () => {
    if (busy) return;
    setBusy(true); setProg(null); setDone(null);
    const start = await apiPost("/library/enrich/refresh", {});
    const jid = start.ok && start.data ? start.data.job_id : null;
    if (!jid) { setBusy(false); return; }
    for (let i = 0; i < 1200; i++) {  // ~12 min cap; the job keeps running server-side if the poll gives up
      await new Promise(r => setTimeout(r, 600));
      const r = await api("/library/enrich/refresh/" + jid);
      if (!r.ok) break;
      if (r.data.progress) setProg({ current: r.data.progress.current, total: r.data.progress.total, eta: r.data.progress.eta_seconds });
      if (r.data.status === "done" || r.data.status === "error") {
        if (r.data.status === "done" && r.data.summary) setDone(r.data.summary);
        onRefreshed && onRefreshed();
        break;
      }
    }
    setBusy(false); setProg(null);
  };
  const label = busy
    ? (prog ? `Enriching ${prog.current}/${prog.total}${prog.eta ? " ~" + _fmtEta(prog.eta) : ""}` : "Enriching…")
    : (done ? `Filled ${done.fields_filled}` : "Enrich metadata ↻");
  const title = done
    ? `Filled ${done.fields_filled} field(s) across ${done.papers} papers · recovered ${done.dois_recovered} DOI(s) · ${done.still_missing_doi} still missing a DOI. Fills only EMPTY fields — never overwrites what you typed.`
    : "Fill each paper's missing fields (DOI, abstract, venue…) from Crossref/OpenAlex — public metadata, fills only blanks, never overwrites your edits.";
  return <button className="trash-toggle" onClick={run} disabled={busy} title={title}>{label}</button>;
}

// inc-208 (A1): saved searches — a "Saved ▾" menu mirroring AddMenu. Recall a named bundle of the current library
// facets (filters + sort + search box), save the current set, or delete one. Closes on outside-click.
function SavedSearchMenu({ searches, onApply, onSave, onDelete }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);
  const saveNew = () => {
    const name = window.prompt("Name this search (saves the current filters, sort, and search box):");
    setOpen(false);
    if (name && name.trim()) onSave(name.trim());
  };
  return (
    <span className="add-menu" ref={ref}>
      <button className="trash-toggle" onClick={() => setOpen(o => !o)} title="Saved searches — recall a named set of filters + sort">Saved ▾</button>
      {open &&
        <div className="add-menu-pop saved-search-pop">
          <button className="saved-search-save" onClick={saveNew} title="Save the current filters, sort, and search box as a named search">+ Save current search…</button>
          {(searches || []).length === 0
            ? <span className="saved-search-empty">No saved searches yet.</span>
            : (searches || []).map(s => (
                <div key={s.id} className="saved-search-row">
                  <button className="saved-search-name" title="Apply this saved search"
                    onClick={() => { setOpen(false); onApply(s.params); }}>{s.name}</button>
                  <button className="saved-search-del" title="Delete this saved search" onClick={() => onDelete(s.id)}>×</button>
                </div>))}
        </div>}
    </span>
  );
}
