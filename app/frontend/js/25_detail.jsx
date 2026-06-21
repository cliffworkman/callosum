// ─────────────────────────────────────────────────────────────
// Detail pane — a Mendeley-style inline editor over a paper's bibliographic
// record (inc 49). Every field is always-editable inline (transparent until
// hover/focus; grey "Add …" placeholder when empty) and auto-saves on blur via
// a one-field PATCH. The canonical record is csl_json; the scalar columns are
// projections the backend keeps in sync. The DOI field re-fetches from Crossref
// (🔎). "More" surfaces any extra scalar field a DOI populated beyond the core.
// ─────────────────────────────────────────────────────────────

// Literature Type vocabulary (Mendeley's list → CSL type values). A stored value
// not in this list (e.g. an unusual Crossref type) is preserved as its own option.
const LIT_TYPES = [
  ["bill", "Bill"],
  ["book", "Book"],
  ["chapter", "Book Section"],
  ["legal_case", "Case"],
  ["software", "Computer Program"],
  ["paper-conference", "Conference Proceedings"],
  ["entry-encyclopedia", "Encyclopedia Article"],
  ["motion_picture", "Film"],
  ["hearing", "Hearing"],
  ["article-journal", "Journal Article"],
  ["article-magazine", "Magazine Article"],
  ["article-newspaper", "Newspaper Article"],
  ["patent", "Patent"],
  ["report", "Report"],
  ["legislation", "Statute"],
  ["broadcast", "Television Broadcast"],
  ["thesis", "Thesis"],
  ["document", "Unspecified"],
  ["webpage", "Web Page"],
  ["article", "Working Paper"],
];

// Friendly labels for generic "More" csl keys a DOI may populate (fallback = humanized key).
const CSL_LABELS = {
  publisher: "Publisher",
  "publisher-place": "Place",
  edition: "Edition",
  "collection-title": "Series",
  "number-of-pages": "# Pages",
  "short-title": "Short Title",
  "container-title-short": "Journal Abbr.",
  source: "Source",
  status: "Status",
  subject: "Subject",
  keyword: "Keywords",
};

// csl keys already shown by a curated field — excluded from the "More" passthrough.
const CORE_CSL_KEYS = new Set([
  "title", "abstract", "DOI", "container-title", "language", "type", "volume", "issue",
  "page", "URL", "PMID", "arxiv", "ISSN", "ISBN", "author", "issued", "id",
]);

function cslGet(p, key) {
  const v = p.csl_json && p.csl_json[key];
  return v == null ? "" : String(v);
}
function cslDateParts(p) {
  const issued = p.csl_json && p.csl_json.issued;
  const dp = issued && issued["date-parts"];
  return Array.isArray(dp) && Array.isArray(dp[0]) ? dp[0] : [];
}
function humanizeKey(k) {
  return k.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
function isScalarValue(v) {
  return typeof v === "string" || typeof v === "number";
}

// One inline-editable text row. Holds local state so typing never fights a re-render;
// commits on blur only when the value actually changed (empty → null clears the field).
function EditableRow({ label, value, placeholder, onSave, mono, numeric }) {
  const [v, setV] = useState(value == null ? "" : String(value));
  useEffect(() => { setV(value == null ? "" : String(value)); }, [value]);
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
  const [v, setV] = useState(value == null ? "" : String(value));
  const [expanded, setExpanded] = useState(false);
  useEffect(() => { setV(value == null ? "" : String(value)); }, [value]);
  const commit = () => {
    const current = value == null ? "" : String(value);
    if (v !== current) onSave(v.trim() === "" ? null : v);
  };
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

// DOI row with the 🔎 re-resolve button. Persists a freshly-typed DOI BEFORE re-resolving
// (so Crossref uses the corrected identifier, not the stale stored one).
function DoiRow({ paper, onSave, onResolve, resolving }) {
  const [v, setV] = useState(paper.doi || "");
  useEffect(() => { setV(paper.doi || ""); }, [paper.doi]);
  const commit = async () => {
    const current = paper.doi || "";
    if (v.trim() !== current) await onSave("doi", v.trim() === "" ? null : v.trim());
  };
  const resolve = async () => {
    await commit();
    onResolve();
  };
  return (
    <div className="detail-row">
      <span className="k">DOI</span>
      <span className="v detail-doi-row">
        <input
          className="detail-edit mono"
          value={v}
          placeholder="Add DOI"
          onChange={(e) => setV(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); resolve(); } }}
        />
        <button
          className="detail-reresolve"
          disabled={!v.trim() || resolving}
          title={v.trim() ? "Re-fetch metadata from Crossref using this DOI" : "Enter a DOI first"}
          onClick={resolve}
        >
          {resolving ? "…" : "🔎"}
        </button>
      </span>
    </div>
  );
}

function DetailSection({ title, open, onToggle, children }) {
  return (
    <div className="detail-section">
      <button className="detail-section-head" onClick={onToggle}>
        <span className="detail-section-chevron">{open ? "▾" : "▸"}</span> {title}
      </button>
      {open && <div className="detail-section-body">{children}</div>}
    </div>
  );
}

// inc-70: export this paper's citation (BibTeX/RIS/CSL-JSON). inc-106: render a FORMATTED citation (APA/MLA/
// Chicago/IEEE/Nature/Harvard) via the citeproc engine + show/copy it. `apiPost` is fine for /citations/render
// (JSON); the export links use a raw fetch (apiPost forces .json()). Clipboard works on the 127.0.0.1 secure
// context. reference_html is server-sanitized (allowlisted inline tags) — safe to render.
function CiteRow({ paperId }) {
  const [copied, setCopied] = useState(null);
  const [styles, setStyles] = useState([]);
  const [style, setStyle] = useState("apa");
  const [rendered, setRendered] = useState(null);   // { in_text, reference_text, reference_html }
  const [fmtCopied, setFmtCopied] = useState(false);

  useEffect(() => { api("/citations/styles").then(r => { if (r.ok) setStyles(r.data.styles || []); }); }, []);
  useEffect(() => {
    let alive = true;
    setRendered(null);
    apiPost("/citations/render", { paper_ids: [paperId], style }).then(r => {
      if (alive) setRendered(r.ok && r.data.items && r.data.items[0] ? r.data.items[0] : null);
    });
    return () => { alive = false; };
  }, [paperId, style]);

  const copyExport = async (format) => {
    try {
      const res = await fetch(API_BASE + "/papers/export", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: [paperId], format }),
      });
      if (!res.ok) { console.warn("[callosum] copy citation failed:", res.status); return; }
      await navigator.clipboard.writeText(await res.text());
      setCopied(format);
      setTimeout(() => setCopied(null), 1500);
    } catch (e) { console.warn("[callosum] copy citation error:", e); }
  };
  const copyFormatted = async () => {
    if (!rendered || !rendered.reference_text) return;
    try {
      await navigator.clipboard.writeText(rendered.reference_text);
      setFmtCopied(true);
      setTimeout(() => setFmtCopied(false), 1500);
    } catch (e) { console.warn("[callosum] copy formatted citation error:", e); }
  };

  return (
    <div className="detail-cite">
      <div className="detail-cite-row">
        <span className="detail-cite-label">Cite as</span>
        <select className="detail-cite-style" value={style} onChange={e => setStyle(e.target.value)} title="Citation style">
          {styles.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}
        </select>
        <button className="btn-link" onClick={copyFormatted} disabled={!rendered} title="Copy the formatted citation">
          {fmtCopied ? "Copied ✓" : "Copy"}
        </button>
      </div>
      {rendered && rendered.reference_html &&
        <div className="detail-cite-preview" dangerouslySetInnerHTML={{ __html: rendered.reference_html }} />}
      <div className="detail-cite-row">
        <span className="detail-cite-label">Export</span>
        {[["bibtex", "BibTeX"], ["ris", "RIS"], ["csl-json", "CSL-JSON"]].map(([f, lbl]) => (
          <button key={f} className="btn-link" onClick={() => copyExport(f)} title={`Copy ${lbl} to clipboard`}>
            {copied === f ? "Copied ✓" : lbl}
          </button>
        ))}
      </div>
    </div>
  );
}

// inc-71: lightweight free-form tags. Local state seeded from the paper detail (the parent keys this by
// paper id so it remounts on paper switch); add via POST, remove via DELETE, datalist suggests existing
// tags. Clicking a chip's name filters the library to that tag.
function TagsRow({ paperId, initialTags, onFilterToTag, onTagsChanged }) {
  const [tags, setTags] = useState(initialTags || []);
  const [all, setAll] = useState([]);
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState([]);   // inc-72: c-TF-IDF candidates
  const [suggested, setSuggested] = useState(false);    // have we fetched candidates at least once?
  const sortByName = (ts) => [...ts].sort((x, y) => x.name.toLowerCase().localeCompare(y.name.toLowerCase()));
  const refreshSuggestions = () => api("/tags").then(r => { if (r.ok) setAll(r.data); });
  useEffect(() => { refreshSuggestions(); }, []);
  // Re-sync to server truth when the parent refetches the detail (e.g. 🔎 re-resolve adds keyword tags for
  // the SAME paper id, so the key={p.id} remount doesn't fire). initialTags identity only changes on a real
  // detail refetch, so optimistic add/remove between refetches is preserved.
  useEffect(() => { setTags(initialTags || []); }, [initialTags]);
  const add = async (nameArg) => {
    const name = (nameArg != null ? nameArg : input).trim();
    if (!name) return;
    if (nameArg == null) setInput("");
    const r = await apiPost(`/papers/${paperId}/tags`, { name });
    if (r.ok) {
      setTags(ts => ts.some(t => t.id === r.data.id) ? ts : sortByName([...ts, r.data]));
      setSuggestions(s => s.filter(x => x.toLowerCase() !== name.toLowerCase()));  // drop the accepted candidate
      refreshSuggestions();
      if (onTagsChanged) onTagsChanged();  // refresh the sidebar Tags browser (inc 96)
    }
  };
  const remove = async (tagId) => {
    const r = await apiDelete(`/papers/${paperId}/tags/${tagId}`);
    if (r.ok) { setTags(ts => ts.filter(t => t.id !== tagId)); refreshSuggestions(); if (onTagsChanged) onTagsChanged(); }
  };
  const suggest = async () => {   // inc-72: local c-TF-IDF — propose distinctive terms, the user opts in
    const r = await api(`/papers/${paperId}/suggested-tags`);
    setSuggested(true);
    if (r.ok) setSuggestions(r.data.suggestions || []);
  };
  return (
    <div className="detail-tags">
      <span className="detail-cite-label">Tags</span>
      <div className="detail-tags-chips">
        {tags.map(t => (
          <span key={t.id} className={"tag-chip" + (tagIsImported(t.source) ? " tag-chip-imported" : "")}>
            <button className="tag-chip-name" title={tagSourceLabel(t.source) + " · click to filter the library"}
              onClick={() => onFilterToTag && onFilterToTag({ id: t.id, name: t.name })}>{t.name}</button>
            <button className="tag-chip-x" title="Remove this tag" onClick={() => remove(t.id)}>×</button>
          </span>
        ))}
        <input className="tag-add" list="tag-suggestions" placeholder="add tag…" value={input} spellCheck={false}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
          onBlur={() => add()} />
        <datalist id="tag-suggestions">{all.map(t => <option key={t.id} value={t.name} />)}</datalist>
        <button className="btn-link" title="Suggest tags from this paper's text (local, no AI sent off-device)"
          onClick={suggest}>✨ Suggest</button>
        {suggestions.map(name => (
          <button key={"sug-" + name} className="term-chip tag-suggest-chip" title="Add this suggested tag"
            onClick={() => add(name)}>+ {name}</button>
        ))}
        {suggested && suggestions.length === 0 && <span className="tag-suggest-empty">no new suggestions</span>}
      </div>
    </div>
  );
}

// Acquisition clean lane (Increment A): fetch a free, rights-holder-authorized open-access copy via OpenAlex
// and import it into the local library. Shown only when a paper has no available PDF. Async job → poll →
// refresh the detail on success (or an honest "no authorized open-access copy found").
function AcquireOaRow({ paperId, onAcquired }) {
  const [status, setStatus] = useState("idle"); // idle | running | done | error
  const [msg, setMsg] = useState(null);
  const poll = async (jobId) => {
    const r = await api(`/papers/acquire-oa/${jobId}`);
    if (!r.ok) { setStatus("error"); setMsg(r.error || "Acquisition status check failed."); return; }
    const j = r.data;
    if (j.status === "done") {
      setStatus("done");
      if (j.found) {
        setMsg("Imported a " + j.oa_color + (j.bronze_unstable ? " (unstable)" : "") + " open-access copy.");
        onAcquired && onAcquired();
      } else {
        setMsg(j.detail || "No authorized open-access copy found.");
      }
      return;
    }
    if (j.status === "error") { setStatus("error"); setMsg(j.detail || "Acquisition failed."); return; }
    setTimeout(() => poll(jobId), 1200); // pending / running → keep polling
  };
  const start = async () => {
    setStatus("running"); setMsg(null);
    const r = await apiPost(`/papers/${paperId}/acquire-oa`, {});
    if (!r.ok) { setStatus("error"); setMsg(r.error || "Couldn't start acquisition."); return; }
    poll(r.data.job_id);
  };
  return (
    <div className="detail-acquire">
      <button className="btn btn-primary" disabled={status === "running"} onClick={start}
        title="Fetch a free, rights-holder-authorized open-access copy via OpenAlex and import it locally">
        {status === "running" ? "Acquiring…" : "Acquire OA copy"}
      </button>
      {status === "running" && <ProgressBar label="Searching open-access sources…" />}
      {msg && <span className={"detail-acquire-msg" + (status === "error" ? " detail-acquire-err" : "")}>{msg}</span>}
    </div>
  );
}

// statcheck (inc 95): recompute reported NHST p-values from this paper's extracted text — a local, deterministic
// signal (no AI). Consistent = green; inconsistent / decision-error = amber (a status to LOOK at, never a verdict
// or accusation). Each row routes to its page. Gated on the paper having extracted text (chunks).
function StatcheckRow({ paperId, paperTitle, hasText, onOpenPaper }) {
  const [state, setState] = useState({ status: "idle" }); // idle | running | done | error
  const run = async () => {
    setState({ status: "running" });
    const r = await api(`/papers/${paperId}/statcheck`);
    setState(r.ok ? { status: "done", data: r.data } : { status: "error", error: r.error });
  };
  const open = (page) => { if (onOpenPaper && page != null) onOpenPaper({ id: paperId, title: paperTitle }, { page, precision: "region" }); };
  const label = (c) => c === "consistent" ? "consistent" : c === "decision-error" ? "decision error" : "inconsistent";
  const d = state.data;
  return (
    <div className="detail-statcheck">
      <span className="detail-cite-label">Statistical reporting</span>
      {!hasText
        ? <span className="tag-suggest-empty">Process a PDF first — statcheck reads the paper's extracted text.</span>
        : state.status === "idle"
          ? <button className="btn-link" title="Recompute reported p-values from this paper's text — local, no AI" onClick={run}>Check statistics</button>
          : null}
      {state.status === "running" && <span className="tag-suggest-empty">checking…</span>}
      {state.status === "error" && <div className="axis-err">Couldn't check: {state.error}</div>}
      {state.status === "done" && d && (d.checked === 0
        ? <div className="tag-suggest-empty">No APA-format statistics found in the extracted text.</div>
        : <div className="statcheck-result">
            <div className="statcheck-summary">{d.checked} checked · {d.inconsistent} inconsistent · {d.decision_errors} decision error{d.decision_errors === 1 ? "" : "s"}</div>
            <div className="statcheck-list">
              {d.results.map((r, i) => (
                <button key={i} className="statcheck-item" title={r.page != null ? "Open page " + r.page : ""} onClick={() => open(r.page)}>
                  <span className="statcheck-raw">{r.raw}</span>
                  <span className="statcheck-computed">computed p = {r.computed_p}</span>
                  <span className={"cite-status " + (r.consistency === "consistent" ? "verified" : "flagged")}>{label(r.consistency)}</span>
                </button>
              ))}
            </div>
            <div className="statcheck-caveat">
              statcheck reads only inline APA-style tests and recomputes each p — it can't see tables, Bayesian stats, or CIs, so a clean result isn't a clean bill. Inconsistencies are common and usually innocent (typos, rounding, one-tailed tests) — a prompt to look, not a verdict.
            </div>
          </div>)}
    </div>
  );
}

// inc-97: add an arbitrary CSL bibliographic field by hand (completes the inc-49 "More" deferral). Reuses the
// validated generic `csl` patch — the backend allows letter-led [A-Za-z0-9_-] keys, rejecting reserved/core
// ones (those have their own fields) with a 422 that surfaces as the pane's save note.
function AddFieldRow({ onSave }) {
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const add = async () => {
    const key = name.trim();
    if (!key || !value.trim() || busy) return;
    setBusy(true);
    const r = await onSave("csl", { [key]: value.trim() });
    setBusy(false);
    if (r && r.ok) { setName(""); setValue(""); }
  };
  return (
    <div className="detail-addfield">
      <input className="detail-addfield-key" placeholder="field name" value={name} spellCheck={false}
        onChange={(e) => setName(e.target.value)} />
      <input className="detail-addfield-val" placeholder="value" value={value} spellCheck={false}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") add(); }} />
      <button className="btn-link" disabled={busy || !name.trim() || !value.trim()} onClick={add}>+ add</button>
    </div>
  );
}

function DetailContent({ paperId, onOpenPaper, onFilterToTag, onTagsChanged }) {
  const [state, setState] = useState({ status: "idle" });
  const [savingField, setSavingField] = useState(null);
  const [note, setNote] = useState(null);
  const [resolving, setResolving] = useState(false);
  const [idOpen, setIdOpen] = useState(true);
  const [moreOpen, setMoreOpen] = useState(true);

  useEffect(() => {
    setNote(null);
    if (paperId == null) { setState({ status: "idle" }); return; }
    let live = true;
    setState({ status: "loading" });
    api(`/papers/${paperId}`).then((r) => {
      if (!live) return;
      if (r.ok) setState({ status: "ready", paper: r.data });
      else setState({ status: "error", error: r.error });
    });
    return () => { live = false; };
  }, [paperId]);

  const saveField = useCallback(async (name, value) => {
    if (paperId == null) return { ok: false };
    setNote(null);
    setSavingField(name);
    const r = await apiPatch(`/papers/${paperId}`, { [name]: value });
    setSavingField(null);
    if (r.ok && r.data) setState({ status: "ready", paper: r.data });
    else setNote({ kind: "err", text: "Couldn't save " + name + " — " + (r.error || "error") });
    return r;
  }, [paperId]);

  const reresolve = useCallback(async () => {
    if (paperId == null) return;
    setNote(null);
    setResolving(true);
    const r = await apiPost(`/papers/${paperId}/re-resolve`, {});
    setResolving(false);
    if (r.ok && r.data) {
      setState({ status: "ready", paper: r.data });
      setNote(r.data.imported_source === "crossref"
        ? { kind: "ok", text: "Resolved from Crossref." }
        : { kind: "warn", text: "Crossref couldn't resolve that DOI. Check it and try again." });
    } else {
      setNote({ kind: "err", text: r.error || "Re-resolve failed." });
    }
  }, [paperId]);

  const onAcquired = useCallback(() => {
    if (paperId == null) return;
    api(`/papers/${paperId}`).then((r) => { if (r.ok) setState({ status: "ready", paper: r.data }); });
  }, [paperId]);

  const saveAuthors = useCallback((text) => {
    const list = text == null ? [] : text.split("\n").map((s) => s.trim()).filter(Boolean);
    return saveField("authors", list);
  }, [saveField]);

  if (state.status === "idle")
    return <div className="state"><div className="big">Select a paper</div>Its metadata and provenance appear here — and are editable.</div>;
  if (state.status === "loading")
    return <div style={{ padding: 18 }}><div className="skel" style={{ border: "none", padding: 0 }}>
      <div className="bar" style={{ width: "85%", height: 16, marginBottom: 12 }}></div>
      <div className="bar" style={{ width: "60%", marginBottom: 8 }}></div>
      <div className="bar" style={{ width: "70%" }}></div></div></div>;
  if (state.status === "error")
    return <div className="errbox">Couldn't load this paper.<br />{state.error}</div>;

  const p = state.paper;
  const dp = cslDateParts(p);
  const extras = Object.keys(p.csl_json || {}).filter(
    (k) => !CORE_CSL_KEYS.has(k) && isScalarValue(p.csl_json[k])
  );
  const hasPdf = (p.attachments || []).some((a) => a.attachment_type === "pdf" && a.availability === "available");

  return (
    <div className="detail-edit-pane" style={{ padding: "12px 18px 32px" }}>
      <div className="detail-type-row">
        <TypeSelect value={p.item_type} onSave={saveField} />
        {savingField && <span className="detail-saving">saving…</span>}
      </div>

      <EditableText variant="title" value={p.title} placeholder="Add title" onSave={(t) => saveField("title", t)} />

      {note && <div className={"detail-note detail-note-" + note.kind}>{note.text}</div>}

      {needsMetadata(p) &&
        <div className="errbox" style={{ margin: "0 0 12px" }}>
          <b>Metadata not yet resolved.</b> This paper came from a raw PDF. Add its DOI under
          Identifiers and click 🔎 to fetch a bibliographic record from Crossref.
        </div>}

      <EditableText label="Authors" value={(p.authors || []).join("\n")}
        placeholder="Add authors (one per line)" onSave={saveAuthors} rows={2} />
      <EditableRow label="Year" value={dp[0]} numeric onSave={(v) => saveField("year", v)} />
      <EditableRow label="Month" value={dp[1]} numeric onSave={(v) => saveField("month", v)} />
      <EditableRow label="Day" value={dp[2]} numeric onSave={(v) => saveField("day", v)} />
      <EditableRow label="Volume" value={cslGet(p, "volume")} onSave={(v) => saveField("volume", v)} />
      <EditableRow label="Issue" value={cslGet(p, "issue")} onSave={(v) => saveField("issue", v)} />
      <EditableRow label="Pages" value={cslGet(p, "page")} onSave={(v) => saveField("page", v)} />
      <EditableRow label="Journal" value={p.venue} onSave={(v) => saveField("venue", v)} />
      <EditableRow label="Language" value={p.language} onSave={(v) => saveField("language", v)} />
      <EditableRow label="URL" value={cslGet(p, "URL")} mono onSave={(v) => saveField("url", v)} />
      <EditableText label="Abstract" value={p.abstract_text != null ? p.abstract_text : p.abstract} placeholder="Add abstract"
        onSave={(t) => saveField("abstract", t)} expandable />

      <TagsRow key={p.id} paperId={p.id} initialTags={p.tags} onFilterToTag={onFilterToTag} onTagsChanged={onTagsChanged} />

      <DetailSection title="Identifiers" open={idOpen} onToggle={() => setIdOpen((o) => !o)}>
        <DoiRow paper={p} onSave={saveField} onResolve={reresolve} resolving={resolving} />
        <EditableRow label="ArXiv ID" value={cslGet(p, "arxiv")} mono onSave={(v) => saveField("arxiv", v)} />
        <EditableRow label="PMID" value={cslGet(p, "PMID")} mono onSave={(v) => saveField("pmid", v)} />
        <EditableRow label="Cite key" value={p.citation_key} mono onSave={(v) => saveField("citation_key", v)} />
        <EditableRow label="ISBN" value={cslGet(p, "ISBN")} mono onSave={(v) => saveField("isbn", v)} />
        <EditableRow label="ISSN" value={cslGet(p, "ISSN")} mono onSave={(v) => saveField("issn", v)} />
      </DetailSection>

      <DetailSection title="More" open={moreOpen} onToggle={() => setMoreOpen((o) => !o)}>
        {extras.map((k) => (
          <EditableRow key={k} label={CSL_LABELS[k] || humanizeKey(k)}
            value={String(p.csl_json[k])} onSave={(v) => saveField("csl", { [k]: v })} />
        ))}
        <AddFieldRow onSave={saveField} />
      </DetailSection>

      {!hasPdf && <AcquireOaRow paperId={p.id} onAcquired={onAcquired} />}

      {p.attachments && p.attachments.length > 0 &&
        <div className="detail-files">
          <span className="detail-files-label">Files</span>
          <div className="detail-files-list">
            {p.attachments.map((a) => (
              <button key={a.id} className="detail-file" title="Open this PDF"
                onClick={() => onOpenPaper && onOpenPaper({ id: p.id, title: p.title })}>
                <span className="src-tag">{a.filename || "file"}</span>
                {a.role ? <span className="detail-file-role">{a.role}</span> : null}
                {a.oa_color ? <span className={"oa-chip " + (a.oa_bronze_unstable ? "oa-bronze" : "oa-durable")}
                  title={a.oa_bronze_unstable ? "Bronze OA: free-to-read without an open license — may revert to paywalled" : a.oa_color + " open access"}>{a.oa_color}</span> : null}
                {a.oa_version ? <span className="oa-meta">{a.oa_version}{a.oa_source ? " · " + a.oa_source : ""}</span> : null}
              </button>
            ))}
          </div>
        </div>}

      <StatcheckRow paperId={p.id} paperTitle={p.title} hasText={(p.chunk_count || 0) > 0} onOpenPaper={onOpenPaper} />

      <CiteRow paperId={p.id} />

      <div className="prov">
        <b>Metadata source.</b>{" "}
        {p.imported_source
          ? <>Currently <span className="src-tag">{p.imported_source}</span>.</>
          : <>Source not recorded.</>}{" "}
        <span className="detail-tierline">{p.chunk_count} chunks · {tierLabel(p.processing_tier)}</span>
      </div>
    </div>
  );
}
