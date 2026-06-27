// Merge duplicate papers into one record (inc 161). Launched from the Duplicates modal (a group) or the library
// bulk bar (≥2 selected). Non-destructive: every PDF, link, tag, and highlight is kept on the surviving record;
// the others move to Trash; a "Merged from…" note records their identifiers. The user picks the survivor, resolves
// any conflicting scalar fields, and chooses the primary PDF — additive data merges automatically (backend). The
// metadata picks are sent to POST /papers/merge as `edits` (only values that differ from the survivor's).

const _MERGE_FIELDS = [
  { key: "title", label: "Title", list: false },
  { key: "authors", label: "Authors", list: true },
  { key: "year", label: "Year", list: false },
  { key: "venue", label: "Venue", list: false },
  { key: "doi", label: "DOI", list: false },
  { key: "url", label: "URL / link", list: false },
  { key: "item_type", label: "Type", list: false },
  { key: "abstract", label: "Abstract", list: false },
];

function _mergeFieldVal(p, key) {
  const csl = p.csl_json || {};
  switch (key) {
    case "title": return csl.title || p.title || "";
    case "authors": return p.authors || [];
    case "year": {
      if (p.year != null) return p.year;
      const dp = csl.issued && csl.issued["date-parts"];
      return dp && dp[0] && dp[0][0] != null ? dp[0][0] : null;
    }
    case "venue": return csl["container-title"] || p.venue || "";
    case "doi": return csl.DOI || p.doi || "";
    case "url": return csl.URL || "";
    case "item_type": return csl.type || p.item_type || "";
    case "abstract": return p.abstract_text || p.abstract || "";
    default: return "";
  }
}

function _mergeIsEmpty(v) {
  if (v == null) return true;
  if (Array.isArray(v)) return v.length === 0;
  return String(v).trim() === "";
}

function _mergeCmp(v, list) {
  return list ? JSON.stringify(v || []) : String(v == null ? "" : v).trim();
}

function _mergeDisplay(v, list) {
  if (_mergeIsEmpty(v)) return "—";
  const s = list ? v.join("; ") : String(v);
  return s.length > 160 ? s.slice(0, 160) + "…" : s;
}

function _mergePdfs(papers) {
  return papers.flatMap(p =>
    (p.attachments || [])
      .filter(a => (a.content_type || "").includes("pdf") || a.attachment_type === "pdf")
      .map(a => ({ id: a.id, filename: a.filename || "PDF", role: a.role, paperId: p.id, paperTitle: p.title || "Untitled" }))
  );
}

function MergePapersModal({ ids, onClose, onMerged }) {
  const [papers, setPapers] = useState(null);  // null = loading; [] = error/too-few
  const [survivorId, setSurvivorId] = useState(null);
  const [picks, setPicks] = useState({});       // field key → chosen raw value
  const [primaryId, setPrimaryId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let live = true;
    Promise.all(ids.map(id => api(`/papers/${id}`))).then(rs => {
      if (!live) return;
      const ok = rs.filter(r => r.ok).map(r => r.data);
      if (ok.length < 2) { setPapers([]); return; }
      setPapers(ok);
      const surv = ok.find(p => p.doi) || ok[0];  // default: the published/citeable copy
      setSurvivorId(surv.id);
      const fp = {};
      _MERGE_FIELDS.forEach(f => {
        const sv = _mergeFieldVal(surv, f.key);
        const chosen = _mergeIsEmpty(sv)
          ? ok.map(p => _mergeFieldVal(p, f.key)).find(v => !_mergeIsEmpty(v))  // fill a survivor gap
          : sv;
        if (!_mergeIsEmpty(chosen)) fp[f.key] = chosen;
      });
      setPicks(fp);
      const pdfs = _mergePdfs(ok);
      const def = pdfs.find(a => a.paperId === surv.id && a.role === "primary")
        || pdfs.find(a => a.paperId === surv.id) || pdfs[0];
      setPrimaryId(def ? def.id : null);
    });
    return () => { live = false; };
  }, [ids]);

  const survivor = papers && papers.find(p => p.id === survivorId);

  // Per field, the distinct non-empty values across the papers — a choice is only needed when there are ≥2.
  const conflicts = (papers || []).length
    ? _MERGE_FIELDS.map(f => {
        const seen = new Map();
        papers.forEach(p => {
          const v = _mergeFieldVal(p, f.key);
          if (_mergeIsEmpty(v)) return;
          const k = _mergeCmp(v, f.list);
          if (!seen.has(k)) seen.set(k, v);
        });
        return { f, options: [...seen.values()] };
      }).filter(c => c.options.length >= 2)
    : [];

  const pdfs = _mergePdfs(papers || []);

  const submit = async () => {
    if (!survivor) return;
    setBusy(true); setErr(null);
    const metadata = {};
    _MERGE_FIELDS.forEach(f => {
      const chosen = picks[f.key];
      if (_mergeIsEmpty(chosen)) return;
      if (_mergeCmp(chosen, f.list) !== _mergeCmp(_mergeFieldVal(survivor, f.key), f.list)) {
        metadata[f.key] = chosen;  // differs from the survivor → adopt / gap-fill
      }
    });
    const merged_ids = papers.map(p => p.id).filter(id => id !== survivorId);
    const r = await apiPost("/papers/merge", {
      survivor_id: survivorId, merged_ids, metadata, primary_attachment_id: primaryId,
    });
    setBusy(false);
    if (!r.ok) { setErr(r.error || "Merge failed."); return; }
    onMerged(survivorId);
  };

  const count = papers ? papers.length : ids.length;
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Merge {count} papers</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Combine these into one record. Every PDF, link, tag, and highlight is kept on the surviving record; the
          others move to Trash, and a “Merged from…” note records their identifiers so nothing is lost.
        </div>

        {papers === null && <ProgressBar label="Loading papers…" />}
        {papers !== null && papers.length < 2 && <div className="axis-err">Couldn’t load at least two papers to merge.</div>}

        {survivor && <React.Fragment>
          <div className="merge-section">
            <div className="merge-eyebrow">Keep as the main record</div>
            {papers.map(p => (
              <label key={p.id} className="merge-opt">
                <input type="radio" name="merge-survivor" checked={p.id === survivorId}
                  onChange={() => setSurvivorId(p.id)} />
                {p.title || "Untitled"}
                <span className="merge-opt-from"> {p.year ? "· " + p.year : ""}{p.doi ? " · " + p.doi : ""}</span>
              </label>
            ))}
          </div>

          {conflicts.length > 0 &&
            <div className="merge-section">
              <div className="merge-eyebrow">Resolve differing fields</div>
              {conflicts.map(({ f, options }) => (
                <div key={f.key} className="merge-field">
                  <div className="merge-field-label">{f.label}</div>
                  {options.map((v, i) => (
                    <label key={i} className="merge-opt">
                      <input type="radio" name={"merge-f-" + f.key}
                        checked={_mergeCmp(picks[f.key], f.list) === _mergeCmp(v, f.list)}
                        onChange={() => setPicks(prev => ({ ...prev, [f.key]: v }))} />
                      {_mergeDisplay(v, f.list)}
                    </label>
                  ))}
                </div>
              ))}
            </div>}

          {pdfs.length > 0 &&
            <div className="merge-section">
              <div className="merge-eyebrow">Primary PDF</div>
              {pdfs.map(a => (
                <label key={a.id} className="merge-opt">
                  <input type="radio" name="merge-primary" checked={a.id === primaryId}
                    onChange={() => setPrimaryId(a.id)} />
                  {a.filename}<span className="merge-opt-from"> · from “{a.paperTitle}”</span>
                </label>
              ))}
              <div className="merge-keep-note">All {pdfs.length} PDFs are kept; this one leads.</div>
            </div>}

          {err && <div className="axis-err">{err}</div>}

          <div className="axis-form-actions">
            <button className="axis-link" onClick={onClose} disabled={busy}>Cancel</button>
            <button className="btn btn-primary" onClick={submit} disabled={busy}>
              {busy ? "Merging…" : "Merge"}
            </button>
          </div>
        </React.Fragment>}
      </div>
    </div>
  );
}
