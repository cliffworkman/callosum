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
