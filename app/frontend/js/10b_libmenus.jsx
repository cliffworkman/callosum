// inc 208: the library-header dropdown menus, extracted from 10_pdf_layer.jsx (which crossed the 600-line cap when
// the saved-search menu landed — rule #1). Both are small, self-contained dropdowns used by PaperList (in
// 10_pdf_layer.jsx) — referenced via the shared-IIFE function hoist, so chunk order is irrelevant.

// inc-93→94: the "bring papers in" actions (Scan folder + Import) folded into one "+ Add ▾" menu to declutter
// the library header. Closes on outside-click. The trigger styles as a .trash-toggle so it blends with the row.
function AddMenu({ onScan, onImport, onImportBundle, onExportBundle }) {
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
          {onImportBundle && <button onClick={() => pick(onImportBundle)} title="Import a callosum library bundle (.json) — metadata + tags + annotations + axes, no PDFs">Import bundle…</button>}
          {onExportBundle && <button onClick={() => pick(onExportBundle)} title="Export your whole library as a portable bundle (.json) — metadata + tags + annotations + axes, no PDFs">Export library bundle…</button>}
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
  const title = date
    ? `Last refreshed ${date}. Fetch each paper's cited-by count from OpenAlex (public metadata; shown verbatim, not a ranking).`
    : "Fetch each paper's cited-by count from OpenAlex (public metadata; shown verbatim, not a ranking).";
  return (
    <button className="trash-toggle" onClick={run} disabled={busy}
      title={title}>
      {busy ? (prog ? `Citations ${prog.current}/${prog.total}${prog.eta ? " ~" + _fmtEta(prog.eta) : ""}` : "Citations…") : "Citations ↻"}
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
  const [lastRun, setLastRun] = useState(null);
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
        if (r.data.status === "done" && r.data.summary) { setDone(r.data.summary); setLastRun(new Date()); }
        onRefreshed && onRefreshed();
        break;
      }
    }
    setBusy(false); setProg(null);
  };
  const label = busy
    ? (prog ? `Enriching ${prog.current}/${prog.total}${prog.eta ? " ~" + _fmtEta(prog.eta) : ""}` : "Enriching…")
    : "Metadata ↻";
  const lastRunText = lastRun ? `Last refreshed ${fmtDateTime(lastRun)}. ` : "";
  const title = done
    ? `${lastRunText}Filled ${done.fields_filled} field(s) across ${done.papers} papers · recovered ${done.dois_recovered} DOI(s) · ${done.still_missing_doi} still missing a DOI. Fills only EMPTY fields — never overwrites what you typed.`
    : "Fill each paper's missing fields (DOI, abstract, venue…) from Crossref/OpenAlex — public metadata, fills only blanks, never overwrites your edits.";
  return <button className="trash-toggle" onClick={run} disabled={busy} title={title}>{label}</button>;
}

function RetractionCheckButton({ onDone }) {
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState(null);
  const [detail, setDetail] = useState("");
  const [lastRun, setLastRun] = useState(null);
  const run = async () => {
    if (busy) return;
    setBusy(true); setSummary(null); setDetail("");
    const start = await apiPost("/methods/retraction/run", {});
    const jid = start.ok && start.data ? start.data.job_id : null;
    if (!jid) { setBusy(false); return; }
    for (let i = 0; i < 1200; i++) {
      await new Promise(r => setTimeout(r, 600));
      const r = await api("/methods/retraction/run/" + jid);
      if (!r.ok) break;
      if (r.data.status === "done" || r.data.status === "error") {
        if (r.data.status === "done") {
          setSummary(r.data.summary || null); setDetail(r.data.detail || ""); setLastRun(new Date());
          onDone && onDone();
        } else {
          setDetail(r.data.detail || "Retraction check failed.");
        }
        break;
      }
    }
    setBusy(false);
  };
  const lastRunText = lastRun ? `Last refreshed ${fmtDateTime(lastRun)}. ` : "";
  const title = summary
    ? `${lastRunText}${summary.checked} checked · ${summary.flagged} retracted. ${detail || "Retraction Watch mirror refreshed first when available."}`
    : "Refresh the Retraction Watch mirror when available, then check every DOI for registry retractions. Signal with evidence, not a verdict.";
  return (
    <button className="trash-toggle" onClick={run} disabled={busy} title={title}>
      {busy ? "Retractions…" : "Retractions ↻"}
    </button>
  );
}

async function pollTextReprocess(jobId, setProg) {
  for (let i = 0; i < 1200; i++) {
    await new Promise(r => setTimeout(r, 600));
    const r = await api("/papers/text-health/reprocess/" + jobId);
    if (!r.ok) break;
    if (r.data.progress) setProg({
      current: r.data.progress.current, total: r.data.progress.total, eta: r.data.progress.eta_seconds
    });
    if (r.data.status === "done" || r.data.status === "error") return r.data;
  }
  return null;
}

function TextHealthButton({ onOpen }) {
  const [counts, setCounts] = useState(null);
  const [lastLoaded, setLastLoaded] = useState(null);
  const load = useCallback(() => {
    api("/papers/text-health/overview").then(r => { if (r.ok) { setCounts(r.data.counts); setLastLoaded(new Date()); } });
  }, []);
  useEffect(() => { load(); }, [load]);
  const missing = counts ? counts.missing_section_labels : 0;
  const label = "Text Health";
  const lastLoadedText = lastLoaded ? `Last refreshed ${fmtDateTime(lastLoaded)}. ` : "";
  const title = counts
    ? `${lastLoadedText}${missing} local PDF(s) have chunks without section labels · ${counts.no_chunks} may need OCR · ${counts.tiny_text} have very little extracted text. Open the text-health queue.`
    : "Open extracted PDF text-health details.";
  return <button className="trash-toggle" onClick={onOpen} title={title}>{label}</button>;
}

function ReprocessSelectedTextButton({ paperIds, onDone }) {
  const [busy, setBusy] = useState(false);
  const [prog, setProg] = useState(null);
  const ids = paperIds || [];
  const run = async () => {
    if (busy || ids.length === 0) return;
    setBusy(true); setProg(null);
    const start = await apiPost("/papers/text-health/reprocess", { mode: "selected", paper_ids: ids });
    const jid = start.ok && start.data ? start.data.job_id : null;
    const done = jid ? await pollTextReprocess(jid, setProg) : null;
    setBusy(false); setProg(null);
    if (done && done.status === "done") onDone && onDone();
  };
  const label = busy
    ? (prog ? `text ${prog.current}/${prog.total}${prog.eta ? " ~" + _fmtEta(prog.eta) : ""}` : "text…")
    : "reprocess text";
  return (
    <button className="axis-link" onClick={run} disabled={busy || ids.length === 0}
      title="Re-extract text and section labels for the selected local PDFs. No OCR, no metadata changes, no network.">
      {label}
    </button>
  );
}

function BulkReferenceCheckButton({ paperIds, onDone }) {
  const [busy, setBusy] = useState(false);
  const [prog, setProg] = useState(null);
  const [summary, setSummary] = useState(null);
  const ids = paperIds || [];
  const poll = (jobId) => api(`/reference-integrity/run/${jobId}`).then(r => {
    if (!r.ok) { setBusy(false); setProg(null); return; }
    if (r.data.status === "done") {
      setBusy(false); setProg(null); setSummary(r.data.bulk_report || null);
      onDone && onDone(r.data.bulk_report || null);
    } else if (r.data.status === "error") {
      setBusy(false); setProg(null); setSummary({ failed_count: ids.length });
    } else {
      setProg(r.data.progress || null);
      setTimeout(() => poll(jobId), 1400);
    }
  });
  const run = async () => {
    if (busy || ids.length === 0) return;
    setBusy(true); setProg(null); setSummary(null);
    const start = await apiPost("/reference-integrity/run-selected", { paper_ids: ids });
    if (!start.ok) { setBusy(false); return; }
    poll(start.data.job_id);
  };
  const label = busy
    ? (prog ? `refs ${prog.current}/${prog.total}` : "refs…")
    : summary ? `refs checked ${summary.checked_count}/${summary.requested_count}` : "check refs";
  const title = summary
    ? `Checked ${summary.checked_count}; skipped ${summary.skipped_no_doi_count || 0} without DOI; failed ${summary.failed_count || 0}.`
    : "Run Meta Reference List checks for selected papers with DOIs; then show papers with active reference signals.";
  const note = summary && (summary.skipped_no_doi_count || summary.failed_count)
    ? `refs: ${summary.skipped_no_doi_count || 0} no DOI · ${summary.failed_count || 0} failed`
    : "";
  return (
    <>
      <button className="axis-link" onClick={run} disabled={busy || ids.length === 0} title={title}>{label}</button>
      {note ? <span className="axis-bulk-count">{note}</span> : null}
    </>
  );
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
