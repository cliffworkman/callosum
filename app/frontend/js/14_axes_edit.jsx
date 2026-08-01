// Axis edit modal (inc 44) — the single home for an axis's title, description, and search-term list.
// The TITLE is a cosmetic display name; the searchable vocabulary is the terms list (stored as the
// description's "Related:" block, primary term first — see `_axisBase`/`_axisRelatedTerms` in
// 16_axes_merge.jsx). Absorbs the inc-41 term suggester: "search related terms" proposes synonyms
// DESELECTED by default (the human curates — keeps the model an aid, not a crutch), and selected terms
// sort to the top so the contributing vocabulary is obvious. Serves both create and edit.
function AxisEditModal({ mode, axisId, initialTitle, initialDescription, initialTerms, onClose, onSaved }) {
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <AxisEditModalBody mode={mode} axisId={axisId} initialTitle={initialTitle}
          initialDescription={initialDescription} initialTerms={initialTerms} onClose={onClose} onSaved={onSaved} />
      </div>
    </div>
  );
}

// inc 416: bare body split out so the onboarding wizard can embed it without a nested overlay —
// AxisEditModal above is now a thin wrapper adding that chrome. Every hook/handler below is unchanged.
function AxisEditModalBody({ mode, axisId, initialTitle, initialDescription, initialTerms, onClose, onSaved }) {
  const [title, setTitle] = useState(initialTitle || "");
  const [prose, setProse] = useState(initialDescription || "");
  const [terms, setTerms] = useState(initialTerms || []);   // [{ term, selected }]
  const [custom, setCustom] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchMsg, setSearchMsg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Selected terms first (stable within group), then deselected — so the contributing vocabulary is
  // visually grouped at the top. `i` preserves the original index for toggling.
  const orderedTerms = terms
    .map((t, i) => ({ ...t, i }))
    .sort((a, b) => (a.selected === b.selected ? a.i - b.i : (a.selected ? -1 : 1)));

  const toggle = (idx) => setTerms(ts => ts.map((t, j) => j === idx ? { ...t, selected: !t.selected } : t));
  const addCustom = () => {
    const v = custom.trim();
    if (v && !terms.some(t => t.term.toLowerCase() === v.toLowerCase())) {
      setTerms(ts => [...ts, { term: v, selected: true }]);
    }
    setCustom("");
  };

  const runSearch = async () => {
    const query = (terms.find(t => t.selected) || terms[0] || {}).term || title.trim();
    if (!query) { setSearchMsg("Add a term or a title first."); return; }
    setSearching(true); setSearchMsg(null);
    const r = await apiPost("/axes/suggest-terms", { label: query, description: prose.trim() || null });
    setSearching(false);
    if (!r.ok) { setSearchMsg(r.error); return; }              // egress-off 503 → guidance, never a crash
    const have = new Set(terms.map(t => t.term.toLowerCase()));
    const fresh = (r.data.terms || [])
      .filter(t => !have.has(t.toLowerCase()))
      .map(t => ({ term: t, selected: false }));               // DESELECTED by default — the user opts in
    if (!fresh.length) { setSearchMsg("No new related terms returned."); return; }
    setTerms(ts => [...ts, ...fresh]);
  };

  const save = async () => {
    const label = title.trim();
    if (!label) { setError("Title must not be empty."); return; }
    const selected = terms.filter(t => t.selected).map(t => t.term);   // preserves original order (primary first)
    const description = [prose.trim(), selected.length ? "Related: " + selected.join(", ") : ""]
      .filter(Boolean).join("\n\n") || null;
    setSaving(true); setError(null);
    const r = mode === "edit"
      ? await apiPatch(`/axes/${axisId}`, { label, description })
      : await apiPost("/axes", { label, description });
    setSaving(false);
    if (!r.ok) { setError(r.error); return; }
    onSaved(r.data ? r.data.id : axisId);
  };

  return (
    <>
      <div className="axis-modal-head">
        <span>{mode === "edit" ? "Edit axis" : "New axis"}</span>
        <button className="axis-link" onClick={onClose}>×</button>
      </div>

      <div className="axis-modal-note">Title — a display name, not a search term:</div>
      <input className="axis-input" value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Resting-state networks" />

      <div className="axis-modal-note">Description — optional context (embedded alongside the terms):</div>
      <textarea className="axis-input axis-textarea" value={prose} onChange={e => setProse(e.target.value)}
        placeholder="Describe the construct this lens captures." />

      <div className="axis-modal-note">Search terms — the vocabulary scored against the library. Select the ones that fit (suggestions start off):</div>
      <div className="axis-chips">
        {orderedTerms.length === 0 && <span className="axis-hint">Add a term below, or search for related ones.</span>}
        {orderedTerms.map(t => (
          <button key={t.i} className={"term-chip" + (t.selected ? " on" : "")} onClick={() => toggle(t.i)}>{t.term}</button>
        ))}
      </div>
      <div className="axis-add-head">
        <input className="axis-add-input" placeholder="add a term…" value={custom}
          onChange={e => setCustom(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addCustom(); } }} />
        <button className="axis-link" onClick={addCustom}>add</button>
        <button className="axis-link" disabled={searching} onClick={runSearch}>{searching ? "searching…" : "search related terms"}</button>
      </div>
      {searching && <ProgressBar label="Suggesting related terms…" managedBy="tracked-request" />}
      {searchMsg && <div className="axis-hint">{searchMsg}</div>}

      {error && <div className="axis-err">{error}</div>}
      <div className="axis-form-actions">
        <button className="axis-btn" disabled={saving || !title.trim()} onClick={save}>
          {saving ? "Saving…" : (mode === "edit" ? "Save changes" : "Create axis")}
        </button>
        <button className="axis-link" disabled={saving} onClick={onClose}>cancel</button>
      </div>
    </>
  );
}
