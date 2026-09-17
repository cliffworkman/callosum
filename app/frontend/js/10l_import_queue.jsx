// #61 provisional ingestion — Import Queue human review/resolution loop. Closes the loop from
// "artifact silently sits in a table" to "user can see it, understand why it's there, and resolve
// it": confirm the system's own best candidate, supply a DOI manually, retry a known-paper attach,
// open the conflicting existing Paper, or delete the capture outright. Never turns candidate metadata
// into canonical metadata merely by displaying it — a candidate is a proposal until the backend's
// `confirm`/`retry` endpoints run it through the SAME canonical admission/attachment-safety substrate
// every other capture path uses (see `app/backend/capture/provisional.py`).
//
// The pure state->copy/actions/request-shape logic lives in the sibling `10l_import_queue_logic.jsx`
// (no JSX, Node-testable via `vm` — see that file's header comment); this file is the thin React glue
// that calls it, then performs the real network call. Styling reuses `.add-menu`/`.add-menu-pop`
// (10b_libmenus.jsx), `.axis-modal-overlay`/`.axis-modal` and `.gap-row*` (30h_reference_finder.jsx),
// and `.tags-srcfilter`/`.tags-srcfilter-btn` (08z_critical_triage.jsx) rather than inventing new
// modal/card/filter chrome.

function ImportQueueThumbnail({ artifactId }) {
  const [state, setState] = useState({ status: "loading" });
  const canvasRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let pdfjsLib;
      try {
        pdfjsLib = await loadPdfJs();
      } catch (e) {
        if (!cancelled) setState({ status: "error" });
        return;
      }
      const { path } = buildPdfPreviewRequest(artifactId);
      let res;
      try {
        res = await callosumFetch(API_BASE + path, { headers: { Accept: "application/pdf" } });
      } catch (e) {
        if (!cancelled) setState({ status: "error" });
        return;
      }
      if (!res.ok) { if (!cancelled) setState({ status: "error" }); return; }
      try {
        const buf = await res.arrayBuffer();
        const doc = await pdfjsLib.getDocument({ data: buf }).promise;
        const page = await doc.getPage(1);
        const targetWidth = 96;
        const base = page.getViewport({ scale: 1 });
        const viewport = page.getViewport({ scale: targetWidth / base.width });
        if (cancelled) return;
        setState({ status: "ready", width: viewport.width, height: viewport.height });
        // Render on the next tick, once the canvas ref is attached from the "ready" render.
        requestAnimationFrame(async () => {
          if (cancelled || !canvasRef.current) return;
          const canvas = canvasRef.current;
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          try {
            await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
          } catch (e) { /* a cancelled/late render is harmless — the card may have unmounted */ }
        });
      } catch (e) {
        if (!cancelled) setState({ status: "error" });
      }
    })();
    return () => { cancelled = true; };
  }, [artifactId]);

  if (state.status === "error") return <div className="iq-thumb iq-thumb-fallback">PDF</div>;
  if (state.status !== "ready") return <div className="iq-thumb iq-thumb-fallback">…</div>;
  return <canvas ref={canvasRef} className="iq-thumb" width={state.width} height={state.height} />;
}

function ImportQueueDoiEntry({ artifactId, onConfirmed, busy, setBusy }) {
  const [doi, setDoi] = useState("");
  const [preview, setPreview] = useState(null); // { status, title, authors, year, paper_id, error }

  const lookup = useCallback(async () => {
    const value = doi.trim();
    if (!value) return;
    setBusy(true); setPreview(null);
    const req = buildPreviewDoiRequest(artifactId, value);
    const r = await apiPost(req.path, req.body);
    setBusy(false);
    setPreview(r.ok ? r.data : { status: "invalid", error: r.error || "The lookup failed." });
  }, [artifactId, doi, setBusy]);

  const confirm = useCallback(async () => {
    const value = doi.trim();
    if (!value) return;
    setBusy(true);
    const req = buildConfirmRequest(artifactId, value, "manual");
    const r = await apiPost(req.path, req.body);
    setBusy(false);
    if (r.ok) onConfirmed(r.data);
  }, [artifactId, doi, onConfirmed, setBusy]);

  return (
    <div className="gap-row" style={{ flexDirection: "column", alignItems: "stretch" }}>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          className="reffind-text"
          style={{ minHeight: "auto", flex: 1 }}
          placeholder="Enter a different DOI…"
          value={doi}
          onChange={e => { setDoi(e.target.value); setPreview(null); }}
        />
        <button className="btn btn-ghost" disabled={busy || !doi.trim()} onClick={lookup}>Look up</button>
      </div>
      {preview && preview.status === "resolved" &&
        <div className="gap-row-info">
          <div className="gap-row-title">{preview.title || preview.doi}</div>
          <div className="gap-row-meta">{[(preview.authors || []).slice(0, 3).join(", "), preview.year].filter(Boolean).join(" · ")}</div>
          <button className="btn btn-primary" disabled={busy} onClick={confirm} style={{ marginTop: 6 }}>Confirm this identity</button>
        </div>}
      {preview && preview.status === "existing" &&
        <div className="gap-row-info">
          <div className="gap-row-title">{preview.title}</div>
          <div className="gap-row-meta">Already in your Library.</div>
          <button className="btn btn-primary" disabled={busy} onClick={confirm} style={{ marginTop: 6 }}>Attach to this paper</button>
        </div>}
      {preview && (preview.status === "invalid" || preview.status === "unresolved") &&
        <div className="reffind-outcome err">{preview.error || "That doesn't look like a resolvable DOI."}</div>}
    </div>
  );
}

function ImportQueueCard({ item, onOpenPaper, onChanged, onRemove }) {
  const [busy, setBusy] = useState(false);
  const [showDoiEntry, setShowDoiEntry] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const headline = importQueueStateHeadline(item.identity_state, item.promotion_state);
  const actions = importQueueStateActions(item.identity_state, item.promotion_state, !!item.best_candidate);

  // Called after confirm/retry/manual-DOI-confirm succeed -- every one of those is a mutating action
  // (importQueueActionRequiresOnChanged is true for all three), so the header count always refreshes.
  const afterMutation = useCallback((data) => {
    setBusy(false);
    onChanged();
    if (data && data.promotion_state === "promoted") {
      onRemove(item.artifact_id); // no longer actionable -- it left the queue
    } else {
      onRemove(item.artifact_id, data); // refresh this one card's state in place
    }
  }, [item.artifact_id, onChanged, onRemove]);

  const confirmCandidate = useCallback(async () => {
    if (!item.best_candidate) return;
    setBusy(true);
    const req = buildConfirmRequest(item.artifact_id, item.best_candidate.doi, "candidate");
    const r = await apiPost(req.path, req.body);
    if (r.ok) afterMutation(r.data); else setBusy(false);
  }, [item, afterMutation]);

  const retry = useCallback(async () => {
    setBusy(true);
    const req = buildRetryRequest(item.artifact_id);
    const r = await apiPost(req.path, req.body);
    if (r.ok) afterMutation(r.data); else setBusy(false);
  }, [item.artifact_id, afterMutation]);

  const doDelete = useCallback(async () => {
    setBusy(true);
    const req = buildDeleteRequest(item.artifact_id);
    const r = await apiDelete(req.path);
    setBusy(false);
    if (r.ok) { onChanged(); onRemove(item.artifact_id); }
  }, [item.artifact_id, onChanged, onRemove]);

  const openExisting = useCallback(() => {
    if (onOpenPaper) onOpenPaper(openExistingPaperArgs(item));
  }, [item, onOpenPaper]);

  const sourceHost = (() => {
    if (!item.last_source_url) return null;
    try { return new URL(item.last_source_url).hostname; } catch (e) { return item.last_source_url; }
  })();

  return (
    <div className="iq-card">
      <ImportQueueThumbnail artifactId={item.artifact_id} />
      <div className="iq-card-body">
        <div className="iq-card-headline">{headline}</div>
        <div className="gap-row-meta">
          {item.last_original_filename || "PDF"}
          {sourceHost && ` · ${sourceHost}`}
          {item.last_captured_at && ` · ${item.last_captured_at}`}
          {item.encounter_count > 1 && ` · captured ${item.encounter_count} times`}
        </div>
        <div className="axis-hint">{item.explanation}</div>

        {item.best_candidate &&
          <div className="gap-row-info" style={{ marginTop: 4 }}>
            <div className="gap-row-title">{item.best_candidate.title || item.best_candidate.doi}</div>
            {item.best_candidate.doi && <div className="reffind-doi">{item.best_candidate.doi}</div>}
          </div>}

        {item.promotion_state === "attachment_conflict" &&
          <div className="axis-hint" style={{ marginTop: 4 }}>{importQueueAttachmentConflictExplanation()}</div>}
        {(item.promotion_state === "processing_failed" || item.promotion_state === "indexing_unavailable") &&
          <div className="axis-hint" style={{ marginTop: 4 }}>{importQueueProcessingFailedExplanation()}</div>}

        <div className="gap-row-actions" style={{ marginTop: 8, flexWrap: "wrap" }}>
          {actions.includes("confirm_candidate") &&
            <button className="btn btn-primary" disabled={busy} onClick={confirmCandidate}>Confirm this identity</button>}
          {actions.includes("open_existing_paper") &&
            <button className="btn btn-ghost" disabled={busy} onClick={openExisting}>Open existing Paper</button>}
          {actions.includes("retry") &&
            <button className="btn btn-ghost" disabled={busy} onClick={retry}>Retry</button>}
          {actions.includes("enter_doi") && !showDoiEntry &&
            <button className="btn btn-link" disabled={busy} onClick={() => setShowDoiEntry(true)}>Enter a different DOI…</button>}
          {!confirmingDelete &&
            <button className="btn btn-link" disabled={busy} onClick={() => setConfirmingDelete(true)}>Delete</button>}
          {confirmingDelete &&
            <span className="reffind-outcome err" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {importQueueDeleteConfirmMessage()}
              <button className="btn btn-primary" disabled={busy} onClick={doDelete}>Delete</button>
              <button className="btn btn-ghost" disabled={busy} onClick={() => setConfirmingDelete(false)}>Cancel</button>
            </span>}
        </div>

        {showDoiEntry &&
          <ImportQueueDoiEntry
            artifactId={item.artifact_id}
            busy={busy}
            setBusy={setBusy}
            onConfirmed={(data) => { setShowDoiEntry(false); afterMutation(data); }}
          />}
      </div>
    </div>
  );
}

const IMPORT_QUEUE_FILTERS = [
  { key: "all", label: "All" },
  { key: "needs_identity", label: "Needs identity" },
  { key: "attachment_conflict", label: "Attachment conflict" },
  { key: "processing_failed", label: "Processing failed" },
];

function importQueueMatchesFilter(item, filter) {
  if (filter === "all") return true;
  if (filter === "needs_identity") return item.identity_state === "unresolved";
  if (filter === "attachment_conflict") return item.promotion_state === "attachment_conflict";
  if (filter === "processing_failed") return item.promotion_state === "processing_failed" || item.promotion_state === "indexing_unavailable";
  return true;
}

function ImportQueueReviewModal({ onClose, onOpenPaper, onChanged }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const load = useCallback(() => {
    setLoading(true);
    const req = buildListRequest();
    api(req.path).then(r => {
      setLoading(false);
      if (r.ok) setItems(r.data.items || []);
    });
  }, []);

  useEffect(() => { load(); }, [load]);

  const removeOrUpdate = useCallback((artifactId, updatedFields) => {
    setItems(prev => {
      if (!updatedFields) return prev.filter(it => it.artifact_id !== artifactId);
      return prev.map(it => (it.artifact_id === artifactId ? { ...it, ...updatedFields } : it));
    });
  }, []);

  const visible = items.filter(it => importQueueMatchesFilter(it, filter));

  return (
    <div className="axis-modal-overlay" onMouseDown={onClose}>
      <div className="axis-modal" onMouseDown={e => e.stopPropagation()} style={{ maxWidth: 640 }}>
        <div className="axis-modal-head">
          <span>Import Queue</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Direct-PDF captures Callosum preserved but has not yet identified confidently, or matched to a
          paper it could not safely attach to automatically. Nothing here has been lost.
        </div>

        <div className="tags-srcfilter" role="group" aria-label="Import Queue filter">
          {IMPORT_QUEUE_FILTERS.map(f => (
            <button key={f.key} className={"tags-srcfilter-btn" + (filter === f.key ? " on" : "")} onClick={() => setFilter(f.key)}>
              {f.label}
            </button>
          ))}
        </div>

        {loading && <div className="axis-hint">Loading…</div>}
        {!loading && visible.length === 0 && <div className="axis-hint">Nothing here.</div>}
        {!loading && visible.map(item => (
          <ImportQueueCard
            key={item.artifact_id}
            item={item}
            onOpenPaper={onOpenPaper}
            onChanged={onChanged}
            onRemove={removeOrUpdate}
          />
        ))}
      </div>
    </div>
  );
}

function ImportQueuePanel({ count, onChanged, onOpenPaper }) {
  const [open, setOpen] = useState(false);

  return (
    <span className="lib-chip-group lib-chip-queue">
      <button className="trash-toggle findings-chip" onClick={() => setOpen(true)}>🗂 Import Queue ({count})</button>
      {open &&
        <ImportQueueReviewModal
          onClose={() => setOpen(false)}
          onOpenPaper={onOpenPaper}
          onChanged={onChanged}
        />}
    </span>
  );
}
