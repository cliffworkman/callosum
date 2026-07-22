// The inline-editable Details field primitives (EditableRow / EditableText / TypeSelect / IdentifierRow) +
// the B5-SP2 read-only context. Split from 25_detail.jsx (inc 238, rule #1 — it was over the 600-line cap).
// Loads before 25_detail.jsx so DetailReadOnly (a const) is initialized first; the functions hoist in the IIFE.

const DetailReadOnly = React.createContext(false);

// One inline-editable text row. Holds local state so typing never fights a re-render;
// commits on blur only when the value actually changed (empty → null clears the field).
function EditableRow({ label, value, placeholder, onSave, mono, numeric }) {
  const ro = React.useContext(DetailReadOnly);
  const [v, setV] = useState(value == null ? "" : String(value));
  useEffect(() => { setV(value == null ? "" : String(value)); }, [value]);
  if (ro) {
    return <div className="detail-row"><span className="k">{label}</span>
      <span className={"v detail-ro" + (mono ? " mono" : "")}>{value == null || value === "" ? "—" : String(value)}</span></div>;
  }
  const commit = () => {
    const current = value == null ? "" : String(value);
    if (v === current) return;
    if (numeric) {
      const t = v.trim();
      if (t === "") { onSave(null); return; }
      const n = parseInt(t, 10);
      if (Number.isNaN(n)) { setV(current); return; }  // non-numeric → revert, don't save
      onSave(n);
      return;
    }
    onSave(v.trim() === "" ? null : v);
  };
  return (
    <div className="detail-row">
      <span className="k">{label}</span>
      <span className="v">
        <input
          className={"detail-edit" + (mono ? " mono" : "")}
          value={v}
          placeholder={placeholder || "Add " + label.toLowerCase()}
          onChange={(e) => setV(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); e.target.blur(); } }}
        />
      </span>
    </div>
  );
}

// Multi-line editable field (authors, abstract, title). variant="title" renders the
// large serif heading; expandable adds an Expand/Collapse toggle for long abstracts.
function EditableText({ label, value, placeholder, onSave, rows, variant, expandable }) {
  const ro = React.useContext(DetailReadOnly);
  const [v, setV] = useState(value == null ? "" : String(value));
  const [expanded, setExpanded] = useState(false);
  useEffect(() => { setV(value == null ? "" : String(value)); }, [value]);
  const commit = () => {
    const current = value == null ? "" : String(value);
    if (v !== current) onSave(v.trim() === "" ? null : v);
  };
  if (ro) {
    const text = value == null || value === "" ? (variant === "title" ? "Untitled" : "—") : String(value);
    if (variant === "title") return <div className="detail-title-input detail-ro">{text}</div>;
    return <div className="detail-row detail-row-text"><span className="k">{label}</span>
      <span className="v detail-ro">{text}</span></div>;
  }
  if (variant === "title") {
    return (
      <textarea
        className="detail-edit detail-title-input"
        rows={1}
        value={v}
        placeholder={placeholder || "Add title"}
        onChange={(e) => setV(e.target.value)}
        onBlur={commit}
      />
    );
  }
  return (
    <div className="detail-row detail-row-text">
      <span className="k">{label}</span>
      <span className="v">
        <textarea
          className="detail-edit detail-edit-text"
          rows={expandable ? (expanded ? 12 : 3) : rows || 2}
          value={v}
          placeholder={placeholder || "Add " + label.toLowerCase()}
          onChange={(e) => setV(e.target.value)}
          onBlur={commit}
        />
        {expandable && (v.length > 180 || expanded) && (
          <button className="detail-expand" onClick={() => setExpanded((x) => !x)}>
            {expanded ? "Collapse" : "Expand"}
          </button>
        )}
      </span>
    </div>
  );
}

// Literature Type — a select over the Mendeley vocabulary; preserves an unknown stored value.
function TypeSelect({ value, onSave }) {
  const known = LIT_TYPES.some(([v]) => v === value);
  return (
    <select className="detail-type" value={value || "document"} onChange={(e) => onSave("item_type", e.target.value)}>
      {!known && value ? <option value={value}>{value}</option> : null}
      {LIT_TYPES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
    </select>
  );
}

// An identifier row with the 🔎 re-fetch button (inc 226, generalized from the inc-49 DoiRow). Persists a
// freshly-typed identifier BEFORE re-fetching (so the source uses the corrected value, not the stale one).
// `source` picks where the record is re-fetched from: crossref (DOI), pmid (PubMed via OpenAlex), arxiv (the
// arXiv DOI via OpenAlex). `resolving` holds the in-flight source so only the clicked 🔎 spins.
const _RESOLVE_SOURCE_NAME = { crossref: "Crossref", pmid: "PubMed (via OpenAlex)", arxiv: "OpenAlex" };

function IdentifierRow({ label, value, fieldKey, source, paper, onSave, onResolve, resolving }) {
  const ro = React.useContext(DetailReadOnly);
  const [v, setV] = useState(value || "");
  useEffect(() => { setV(value || ""); }, [value]);
  if (ro) {
    return <div className="detail-row"><span className="k">{label}</span>
      <span className="v detail-ro mono">{value == null || value === "" ? "—" : String(value)}</span></div>;
  }
  const commit = async () => {
    if (v.trim() !== (value || "")) await onSave(fieldKey, v.trim() === "" ? null : v.trim());
  };
  const resolve = async () => {
    // inc 174: re-fetch force-overwrites. Guard hand-edited papers so edits aren't lost silently.
    if (paper.imported_source === "user-edited" &&
        !window.confirm("This paper has hand-edited metadata. Re-fetching will overwrite your edits. Continue?")) {
      return;
    }
    await commit();
    onResolve(source);
  };
  return (
    <div className="detail-row">
      <span className="k">{label}</span>
      <span className="v detail-doi-row">
        <input
          className="detail-edit mono"
          value={v}
          placeholder={"Add " + label}
          onChange={(e) => setV(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); resolve(); } }}
        />
        <button
          className="detail-reresolve"
          disabled={!v.trim() || resolving != null}
          title={v.trim() ? `Re-fetch metadata from ${_RESOLVE_SOURCE_NAME[source]} using this ${label}` : `Enter a ${label} first`}
          onClick={resolve}
        >
          {resolving === source ? "…" : "🔎"}
        </button>
      </span>
    </div>
  );
}
