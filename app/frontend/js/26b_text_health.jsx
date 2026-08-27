// PDF text-health queue. Shows deterministic extraction-health signals for local PDFs and exposes bounded local
// reprocess actions. No OCR, no metadata fetch, no network beyond the local API.

const TEXT_HEALTH_GROUPS = [
  ["missing_section_labels", "Missing section labels", "Can be reprocessed to pick up newer section metadata."],
  ["stale_chunk_version", "Stale extraction version", "Older extraction or chunking provenance; reprocess separately after inspection."],
  ["no_chunks", "No extracted text", "Likely needs OCR or a better PDF; this queue does not OCR automatically."],
  ["tiny_text", "Very little text", "Needs human inspection; extraction may be poor or the paper may be short."],
  ["no_local_pdf", "No local PDF", "Metadata-only or unavailable attachment."],
];

function _textHealthTitle(paperId, titles) {
  return titles[paperId] || `Paper ${paperId}`;
}

function _textHealthMeta(item) {
  return `${item.chunk_count} chunks · ${item.text_chars} chars · ${item.section_labeled_chunks} section-labeled`;
}

function TextHealthModal({ onClose, onOpenPaper, onOpenDetails, onShowLibrary, onChanged, context }) {
  const [state, setState] = useState({ status: "loading", items: [], counts: null });
  const [titles, setTitles] = useState({});
  const [run, setRun] = useState({ status: "idle" });
  const scopedIds = new Set(((context && context.paperIds) || []).map(Number).filter(Boolean));
  const [scopedOnly, setScopedOnly] = useState(scopedIds.size > 0);

  const refresh = useCallback(async () => {
    setState(s => ({ ...s, status: "loading" }));
    const r = await api("/papers/text-health/overview");
    if (!r.ok) { setState({ status: "error", error: r.error, items: [], counts: null }); return; }
    const items = r.data.items || [];
    setState({ status: "ready", items, counts: r.data.counts });
    const missing = items.filter(i => titles[i.paper_id] == null).slice(0, 80);
    const pairs = await Promise.all(missing.map(i => api(`/papers/${i.paper_id}`)));
    const next = {};
    pairs.forEach((res, i) => { if (res.ok) next[missing[i].paper_id] = res.data.title || `Paper ${missing[i].paper_id}`; });
    if (Object.keys(next).length) setTitles(prev => ({ ...prev, ...next }));
  }, [titles]);

  useEffect(() => { refresh(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const poll = async (jobId) => {
    const done = await pollTextReprocess(jobId, () => {});
    setRun(done && done.status === "done" ? { status: "done", summary: done.summary } : { status: "error" });
    await refresh();
    if (done && done.status === "done" && onChanged) onChanged();
  };

  const runMissingSections = async () => {
    setRun({ status: "running" });
    const start = await apiPost("/papers/text-health/reprocess", { mode: "missing_section_labels", paper_ids: [] });
    if (!start.ok) { setRun({ status: "error", error: start.error }); return; }
    poll(start.data.job_id);
  };

  const reprocessOne = async (paperId) => {
    setRun({ status: "running" });
    const start = await apiPost("/papers/text-health/reprocess", { mode: "selected", paper_ids: [paperId] });
    if (!start.ok) { setRun({ status: "error", error: start.error }); return; }
    poll(start.data.job_id);
  };
  const openDetailsForOcr = (item) => {
    if (onOpenDetails) onOpenDetails({ id: item.paper_id, title: _textHealthTitle(item.paper_id, titles) });
    onClose && onClose();
  };

  const allItems = state.items || [];
  const items = scopedOnly && scopedIds.size ? allItems.filter(item => scopedIds.has(Number(item.paper_id))) : allItems;
  const scopedActionableIds = [...new Set(allItems
    .filter(item => scopedIds.has(Number(item.paper_id))
      && (item.flags.includes("missing_section_labels") || item.flags.includes("stale_chunk_version")))
    .map(item => Number(item.paper_id)))];
  const runScopedReprocess = async () => {
    if (!scopedActionableIds.length) return;
    setRun({ status: "running" });
    const start = await apiPost("/papers/text-health/reprocess", { mode: "selected", paper_ids: scopedActionableIds });
    if (!start.ok) { setRun({ status: "error", error: start.error }); return; }
    poll(start.data.job_id);
  };
  const counts = state.counts;
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal text-health-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>PDF Text Health</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Deterministic checks over local PDF attachments and extracted chunks. Reprocessing re-reads local PDFs and
          replaces extracted chunks only; it does not OCR, fetch metadata, or send text anywhere. OCR remains a
          separate explicit action because it creates a searchable copy.
        </div>
        {context && scopedIds.size > 0 &&
          <div className="wanted-summary">
            Opened from Synthesis · showing text-health signals for {scopedIds.size} source paper{scopedIds.size === 1 ? "" : "s"}.
            {" "}<button className="btn-link" onClick={() => setScopedOnly(v => !v)}>
              {scopedOnly ? "Show all text-health items" : "Return to synthesis scope"}
            </button>
          </div>}

        {counts && <div className="wanted-coverage">
          {counts.local_pdfs} local PDFs · {counts.missing_section_labels} missing section labels ·{" "}
          {counts.stale_chunk_version} stale extraction · {counts.no_chunks} no text ·{" "}
          {counts.tiny_text} tiny text · {counts.no_local_pdf} no local PDF
        </div>}

        <div className="wanted-actions">
          <button className="btn btn-primary" disabled={run.status === "running" || !counts || !counts.missing_section_labels}
            onClick={runMissingSections}>Reprocess missing section labels</button>
          {context && scopedIds.size > 0 &&
            <button className="btn btn-ghost" disabled={run.status === "running" || !scopedActionableIds.length}
              title={scopedActionableIds.length
                ? "Reprocess only scoped papers with missing section labels or stale extraction."
                : "No scoped paper has a reprocessable text-health signal."}
              onClick={runScopedReprocess}>Reprocess scoped papers</button>}
          <button className="axis-link" onClick={refresh}>Refresh</button>
        </div>
        {run.status === "running" && <ProgressBar label="Reprocessing PDF text…" managedBy="backend-job" />}
        {run.status === "error" && <div className="axis-err">{run.error || "Reprocess failed."}</div>}
        {run.status === "done" && run.summary &&
          <div className="wanted-summary">
            Reprocessed {run.summary.reprocessed} · created {run.summary.chunks_created} chunks
            {run.summary.skipped_no_chunks ? ` · ${run.summary.skipped_no_chunks} skipped without text` : ""}
            {run.summary.skipped_no_local_pdf ? ` · ${run.summary.skipped_no_local_pdf} skipped without local PDF` : ""}
            {context && context.onRetry &&
              <button className="btn-link" onClick={() => { onClose && onClose(); context.onRetry(); }}>Retry synthesis</button>}
          </div>}

        {state.status === "loading" && <div className="axis-hint">Loading…</div>}
        {state.status === "error" && <div className="axis-err">Couldn't load text health: {state.error}</div>}
        {state.status === "ready" && items.length === 0 && <div className="axis-hint">No papers to inspect.</div>}

        {TEXT_HEALTH_GROUPS.map(([flag, label, note]) => {
          const group = items.filter(item => item.flags.includes(flag));
          if (!group.length) return null;
          const showGroupInLibrary = () => {
            if (onShowLibrary) onShowLibrary({ key: flag, label, paperIds: group.map(item => item.paper_id) });
            onClose && onClose();
          };
          return (
            <div className="text-health-group" key={flag}>
              <div className="text-health-group-head">
                <div className="dup-dismissed-toggle">{label} ({group.length})</div>
                <button className="axis-link" onClick={showGroupInLibrary}>Show in Library</button>
              </div>
              <div className="axis-modal-note">{note}</div>
              {group.slice(0, 80).map(item => (
                <div className="wanted-row" key={`${flag}:${item.paper_id}`}>
                  <div className="wanted-row-info">
                    <div className="wanted-row-title">{_textHealthTitle(item.paper_id, titles)}</div>
                    <div className="wanted-row-meta">{_textHealthMeta(item)}</div>
                  </div>
                  <button className="axis-link"
                    onClick={() => onOpenPaper && onOpenPaper({ id: item.paper_id, title: _textHealthTitle(item.paper_id, titles) })}>Open</button>
                  {(flag === "missing_section_labels" || flag === "stale_chunk_version") &&
                    <button className="axis-link" disabled={run.status === "running"}
                      onClick={() => reprocessOne(item.paper_id)}>Reprocess</button>}
                  {flag === "no_chunks" &&
                    <button className="axis-link" onClick={() => openDetailsForOcr(item)}>Details for OCR</button>}
                </div>
              ))}
              {group.length > 80 && <div className="axis-hint">Showing first 80 of {group.length}.</div>}
            </div>
          );
        })}

        <div className="axis-form-actions">
          <button className="axis-link" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
