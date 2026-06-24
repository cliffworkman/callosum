// My Publications — the missing-works modal (inc 117, SP1, #12). Moves the OpenAlex import/reject queue out of
// the dashboard body into a modal opened from the OpenAlex card's "Review N →" button. Same endpoints as before
// (/my-publications/works/{import,dismiss,undismiss}); on any action it calls onChanged so the dashboard re-fetches
// (the cache-only dashboard read), which re-renders this modal's lists.
function MissingWorksModal({ open, onClose, missing, dismissed, onChanged }) {
  const [busy, setBusy] = useState(() => new Set());
  if (!open) return null;
  const missingList = missing || [];
  const dismissedList = dismissed || [];

  const act = async (doi, path) => {
    setBusy(b => new Set(b).add(doi));
    const r = await apiPost(path, { doi });
    if (r.ok && onChanged) await onChanged();
    setBusy(b => { const n = new Set(b); n.delete(doi); return n; });
  };

  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Indexed works not in your library</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          OpenAlex attributes these to you, but they aren't in your library. Import the ones that are yours
          (metadata only — the PDF is a separate "Acquire OA copy" step); dismiss the rest. Dismissals can be restored.
        </div>

        {missingList.length === 0 && dismissedList.length === 0 &&
          <div className="axis-hint">Nothing to review — every indexed work is in your library.</div>}

        {missingList.length > 0 &&
          <div className="missing-list">
            {missingList.map(w => (
              <div key={w.doi} className="missing-row">
                <div className="missing-info">
                  <div className="missing-title" title={w.title || w.doi}>{w.title || w.doi}</div>
                  <div className="missing-meta">{w.year ? w.year + " · " : ""}{w.cited_by_count} cites · {w.doi}</div>
                </div>
                <button className="btn btn-ghost" disabled={busy.has(w.doi)}
                  onClick={() => act(w.doi, "/my-publications/works/import")}>Import</button>
                <button className="axis-link" disabled={busy.has(w.doi)}
                  onClick={() => act(w.doi, "/my-publications/works/dismiss")}>Dismiss</button>
              </div>
            ))}
          </div>}

        {dismissedList.length > 0 &&
          <div className="missing-list">
            <div className="mypubs-source">Previously dismissed ({dismissedList.length}) — restore any to send it back to the list above.</div>
            {dismissedList.map(w => (
              <div key={w.doi} className="missing-row">
                <div className="missing-info">
                  <div className="missing-title" title={w.title || w.doi}>{w.title || w.doi}</div>
                  <div className="missing-meta">{w.year ? w.year + " · " : ""}{w.cited_by_count} cites · {w.doi}</div>
                </div>
                <button className="axis-link" disabled={busy.has(w.doi)}
                  onClick={() => act(w.doi, "/my-publications/works/undismiss")}>Restore</button>
              </div>
            ))}
          </div>}
      </div>
    </div>
  );
}
