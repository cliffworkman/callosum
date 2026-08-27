// Axis merge — a comparison/curation view (inc 43). Per the user: merging is NOT "one whole axis
// wins". You see the content of every selected axis side by side, pick which one's identity the
// merged axis keeps (the survivor row), and curate — piece by piece — what label + description text
// flows into it. Crucially, every folded axis's LABEL is carried over as a default-on "Related:" term
// so the merged axis's embedded text still spans all sources' vocabulary; a re-score then keeps the
// papers each independent axis used to surface discoverable under the merged axis. Backend
// (POST /axes/merge) unions the manual assignments and deletes the folded sources; the parent
// re-scores the survivor automatically afterwards.

// Parse an axis description into its prose base + its "Related:" terms. Robust to a Related: block with
// OR without a leading blank line — an empty prose composes to just "Related: …" (no "\n\n") — and to
// multiple Related: blocks left by old merges: all terms are collected and case-insensitively deduped.
function _axisBase(description) {
  return (description || "").split(/\n*Related:\s*/i)[0].trim();
}

function _axisRelatedTerms(description) {
  const parts = (description || "").split(/\n*Related:\s*/i);
  const seen = new Set();
  const out = [];
  parts.slice(1).join(", ").split(",").forEach(s => {
    const t = s.trim(); const k = t.toLowerCase();
    if (t && !seen.has(k)) { seen.add(k); out.push(t); }
  });
  return out;
}

function MergeAxesModal({ axes, onClose, onMerged }) {
  // `axes` is the set of selected axis objects (>= 2).
  const [keepId, setKeepId] = useState(axes[0].id);
  const [label, setLabel] = useState(axes[0].label || "");
  const [terms, setTerms] = useState([]);          // [{ term, selected }] — carried-over Related: terms
  const [custom, setCustom] = useState("");
  const [descEdited, setDescEdited] = useState(null);  // null → use the composed text; string → manual override
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState(null);

  const survivor = axes.find(a => a.id === keepId) || axes[0];

  // (Re)seed the carried-over terms whenever the survivor changes: the survivor's own Related: terms,
  // then every OTHER axis's label + its Related: terms (deduped, case-insensitive). The folded labels
  // are what keep each source's vocabulary contributing after the merge.
  useEffect(() => {
    const seen = new Set();
    const out = [];
    const push = (t) => {
      const key = (t || "").toLowerCase();
      if (t && !seen.has(key)) { seen.add(key); out.push({ term: t, selected: true }); }
    };
    _axisRelatedTerms(survivor.description).forEach(push);
    axes.filter(a => a.id !== survivor.id).forEach(a => { push(a.label); _axisRelatedTerms(a.description).forEach(push); });
    setTerms(out);
    setLabel(survivor.label || "");
    setDescEdited(null);
  }, [keepId]);

  const toggle = (i) => { setTerms(ts => ts.map((t, j) => j === i ? { ...t, selected: !t.selected } : t)); setDescEdited(null); };
  const addCustom = () => { const v = custom.trim(); if (v) { setTerms(ts => [...ts, { term: v, selected: true }]); setCustom(""); setDescEdited(null); } };

  const base = _axisBase(survivor.description);
  const selectedTerms = terms.filter(t => t.selected).map(t => t.term);
  const composed = selectedTerms.length ? [base, "Related: " + selectedTerms.join(", ")].filter(Boolean).join("\n\n") : base;
  const finalDesc = descEdited != null ? descEdited : composed;

  const apply = async () => {
    if (!label.trim()) return;
    setApplying(true);
    setError(null);
    const r = await apiPost("/axes/merge", {
      keep_axis_id: keepId,
      merge_axis_ids: axes.filter(a => a.id !== keepId).map(a => a.id),
      label: label.trim(),
      description: (finalDesc || "").trim() || null,
    });
    setApplying(false);
    if (r.ok) onMerged(keepId);
    else setError(r.error);
  };

  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Merge {axes.length} axes</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Choose which axis the merged lens keeps as its identity, then curate the text below. Each folded
          axis's label is carried over as a related term so re-scoring still surfaces the papers it found.
        </div>

        {axes.map(a => (
          <label key={a.id} className={"merge-source" + (a.id === keepId ? " keep" : "")}>
            <input className="merge-radio" type="radio" name="merge-keep" checked={a.id === keepId} onChange={() => setKeepId(a.id)} />
            <div className="merge-source-body">
              <div className="merge-source-label">
                {a.label}
                {a.id === keepId && <span className="merge-keep-tag">survivor</span>}
              </div>
              {a.description && <div className="merge-source-desc">{a.description}</div>}
              <div className="merge-source-meta">{a.assignment_count || 0} papers · {a.scored ? (a.stale ? "stale" : "scored") : "not scored"}</div>
            </div>
          </label>
        ))}

        <div className="axis-modal-note">Merged label:</div>
        <input className="axis-input" value={label} onChange={e => setLabel(e.target.value)} />

        <div className="axis-modal-note">Related terms carried into the merged axis (folded labels included so their papers stay discoverable):</div>
        <div className="axis-chips">
          {terms.length === 0 && <span className="axis-hint">No related terms — the labels above are the vocabulary.</span>}
          {terms.map((t, i) => (
            <button key={i} className={"term-chip" + (t.selected ? " on" : "")} onClick={() => toggle(i)}>{t.term}</button>
          ))}
        </div>
        <div className="axis-add-head">
          <input className="axis-add-input" placeholder="add your own term…" value={custom}
            onChange={e => setCustom(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addCustom(); } }} />
          <button className="axis-link" onClick={addCustom}>Add</button>
        </div>

        <div className="axis-modal-note">Resulting description (editable):</div>
        <textarea className="axis-input axis-textarea merge-preview" value={finalDesc} onChange={e => setDescEdited(e.target.value)} />

        <div className="axis-modal-note">Manual paper assignments from all merged axes are combined; the merged axis re-scores automatically.</div>
        {error && <div className="axis-err">{error}</div>}
        <div className="axis-form-actions">
          <button className="axis-btn" disabled={applying || !label.trim()} onClick={apply}>{applying ? "Merging…" : "Merge axes"}</button>
          <button className="axis-link" disabled={applying} onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
