// Annotations (Notes) panel for the PDF viewer — extracted from 30_viewer.jsx (inc 176) to keep the viewer under
// the 600-line cap and give the reading-pane features a home. Purely presentational: the list + Copy/Export +
// per-row jump/edit/delete; all state + handlers live in PdfViewer and arrive as props. Loaded as a chunk after
// 30_viewer; the function declaration hoists within the shared IIFE, so PdfViewer can reference it.
function AnnotationsPanel({ annotations, onCopy, onExport, onJump, onEdit, onDelete }) {
  const [notedOnly, setNotedOnly] = useState(false);  // inc 176: show only highlights that carry a note
  const [query, setQuery] = useState("");              // inc 176: search note + highlighted text
  const q = query.trim().toLowerCase();
  const shown = annotations.filter(a => {
    if (notedOnly && !(a.note && a.note.trim())) return false;
    if (q && !((a.note || "").toLowerCase().includes(q) || (a.anchor_text || "").toLowerCase().includes(q))) return false;
    return true;
  });
  return (
    <div className="pdf-annot-panel">
      <div className="pdf-annot-head">Annotations <span>· {shown.length === annotations.length ? annotations.length : `${shown.length} / ${annotations.length}`}</span>
        {annotations.length > 0 &&
          <span className="pdf-annot-export">
            <button className="btn-link" onClick={onCopy} title="Copy all highlights + notes as text">Copy</button>
            <button className="btn-link" onClick={onExport} title="Download highlights + notes as a Markdown file">Export .md</button>
          </span>}
      </div>
      {annotations.length > 0 &&
        <div className="pdf-annot-filter">
          <input className="pdf-annot-search" value={query} placeholder="Search notes & text…"
                 onChange={e => setQuery(e.target.value)} />
          <label className="pdf-annot-notedonly" title="Show only highlights that have a note">
            <input type="checkbox" checked={notedOnly} onChange={e => setNotedOnly(e.target.checked)} /> Noted
          </label>
        </div>}
      {annotations.length === 0 &&
        <div className="pdf-annot-empty">No highlights yet. Select text in the PDF to add one, then click it to add a note.</div>}
      {annotations.length > 0 && shown.length === 0 &&
        <div className="pdf-annot-empty">No highlights match this filter.</div>}
      {shown.map(a =>
        <div key={a.id} className="pdf-annot-item">
          <div className="pdf-annot-row" onClick={() => onJump(a)} title="Jump to this highlight">
            <span className="pdf-annot-chip" style={{ background: a.color }}></span>
            <span className="pdf-annot-page">p.{a.page}</span>
            <span className="pdf-annot-snip">{(a.anchor_text || "").slice(0, 90) || "(no text)"}</span>
          </div>
          {a.note && <div className="pdf-annot-note">{a.note}</div>}
          <div className="pdf-annot-actions">
            <button onClick={(e) => onEdit(a, e.clientX - 250, e.clientY + 6)}>{a.note ? "Edit note" : "Add note"}</button>
            <button className="danger" onClick={() => onDelete(a.id)}>Delete</button>
          </div>
        </div>)}
    </div>
  );
}
