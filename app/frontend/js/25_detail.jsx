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
  "page", "URL", "PMID", "arxiv", "ISSN", "ISBN", "author", "translator", "issued", "id",
]);

function cslGet(p, key) {
  const v = p.csl_json && p.csl_json[key];
  return v == null ? "" : String(v);
}
// Display names from a CSL contributor array (author/translator/…): literal, else "given family".
function cslContributors(p, key) {
  const arr = p.csl_json && p.csl_json[key];
  if (!Array.isArray(arr)) return [];
  return arr.map((c) => c.literal || [c.given, c.family].filter(Boolean).join(" ")).filter(Boolean);
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
function paperAuthorsText(p) {
  return (p && p.authors || []).join("; ");
}
function paperTagNames(p) {
  return new Set(((p && p.tags) || []).map(t => String(t.name || "").toLowerCase()).filter(Boolean));
}
function describeReresolveChanges(before, after) {
  const fields = [
    ["title", "title"], ["authors", "authors"], ["year", "year"], ["doi", "DOI"], ["venue", "venue"],
    ["publication_date", "publication date"], ["abstract", "abstract"],
  ];
  const changed = fields.filter(([key]) => {
    const a = key === "authors" ? paperAuthorsText(before) : String((before && before[key]) || "");
    const b = key === "authors" ? paperAuthorsText(after) : String((after && after[key]) || "");
    return a !== b;
  }).map(([, label]) => label);
  const beforeTags = paperTagNames(before);
  const addedTags = [...paperTagNames(after)].filter(name => !beforeTags.has(name));
  const parts = [];
  if (changed.length) parts.push(`Updated ${changed.slice(0, 5).join(", ")}${changed.length > 5 ? ` +${changed.length - 5} more` : ""}`);
  if (addedTags.length) parts.push(`added ${addedTags.length} keyword tag${addedTags.length === 1 ? "" : "s"}`);
  return parts.join("; ");
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

// TagsRow (inc-71 + inc-207 color picker) lives in js/25b_tags.jsx; action widgets live in 25a_detail_actions.jsx.

function DetailContent({ paperId, onOpenPaper, onFilterToTag, onTagsChanged, onQueueChanged, readOnly }) {
  const [state, setState] = useState({ status: "idle" });
  const [savingField, setSavingField] = useState(null);
  const [note, setNote] = useState(null);
  const [resolving, setResolving] = useState(null);  // the in-flight re-fetch source (crossref/pmid/arxiv), or null
  const [filling, setFilling] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [queuing, setQueuing] = useState(false);
  const [idOpen, setIdOpen] = useState(true);
  const [moreOpen, setMoreOpen] = useState(true);
  const [mergeOrigin, setMergeOrigin] = useState(null);  // #16: this paper is a merge survivor → offer Un-merge
  const [unmerging, setUnmerging] = useState(false);

  useEffect(() => {
    setNote(null); setMergeOrigin(null);
    if (paperId == null) { setState({ status: "idle" }); return; }
    let live = true;
    setState({ status: "loading" });
    api(`/papers/${paperId}`).then((r) => {
      if (!live) return;
      if (r.ok) setState({ status: "ready", paper: r.data });
      else setState({ status: "error", error: r.error });
    });
    api(`/papers/${paperId}/merge-origin`).then((r) => { if (live && r.ok) setMergeOrigin(r.data); });
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

  const reresolve = useCallback(async (source = "crossref") => {
    if (paperId == null) return;
    setNote(null);
    setResolving(source);
    const before = state.status === "ready" ? state.paper : null;
    const r = await apiPost(`/papers/${paperId}/re-resolve`, { source });
    setResolving(null);
    if (r.ok && r.data) {
      setState({ status: "ready", paper: r.data });
      // A hit lands the source's provenance (crossref → "crossref"; pmid/arxiv → "openalex"); anything else is a miss.
      const expected = source === "crossref" ? "crossref" : "openalex";
      const srcName = source === "crossref" ? "Crossref" : "OpenAlex";
      const idLabel = source === "crossref" ? "DOI" : source === "pmid" ? "PMID" : "arXiv ID";
      const diff = describeReresolveChanges(before, r.data);
      setNote(r.data.imported_source === expected
        ? { kind: "ok", text: diff ? `Resolved from ${srcName}. ${diff}.` : `Resolved from ${srcName}; no displayed fields changed.` }
        : { kind: "warn", text: `Couldn't re-fetch from that ${idLabel}. Check it and try again.` });
    } else {
      setNote({ kind: "err", text: r.error || "Re-fetch failed." });
    }
  }, [paperId, state]);

  // inc 217: multi-pass GAP-FILL of this one paper — recover a missing DOI then fill ONLY empty fields from
  // Crossref/OpenAlex. Never overwrites a typed value (distinct from the force-overwrite 🔎 re-resolve).
  const fillMetadata = useCallback(async () => {
    if (paperId == null) return;
    setNote(null);
    setFilling(true);
    const r = await apiPost(`/papers/${paperId}/fill-metadata`, {});
    setFilling(false);
    if (r.ok && r.data) {
      setState({ status: "ready", paper: r.data.paper });
      const n = (r.data.filled_fields || []).length;
      setNote(n
        ? { kind: "ok", text: `Filled ${n} missing field${n === 1 ? "" : "s"}: ${r.data.filled_fields.join(", ")}.` }
        : { kind: "warn", text: r.data.still_missing_doi
            ? "No DOI found and nothing to fill from public sources."
            : "Nothing missing to fill — this record is already complete." });
    } else {
      setNote({ kind: "err", text: r.error || "Couldn't fill metadata." });
    }
  }, [paperId]);

  const reprocessPdf = useCallback(async () => {
    if (paperId == null) return;
    setNote(null);
    setReprocessing(true);
    const r = await apiPost(`/papers/${paperId}/reprocess-pdf`, {});
    setReprocessing(false);
    if (r.ok && r.data) {
      const refreshed = await api(`/papers/${paperId}`);
      if (refreshed.ok) setState({ status: "ready", paper: refreshed.data });
      setNote({ kind: "ok", text: `Reprocessed PDF text: ${r.data.chunks_created} chunk${r.data.chunks_created === 1 ? "" : "s"} created.` });
    } else {
      setNote({ kind: "err", text: r.error || "Couldn't reprocess PDF text." });
    }
  }, [paperId]);

  // #16: reverse the merge this record is the survivor of — restore the merged-away copies with their moved data.
  const unmergeNow = useCallback(async () => {
    if (!mergeOrigin) return;
    setNote(null); setUnmerging(true);
    const r = await apiPost(`/merge/${mergeOrigin.merge_operation_id}/undo`, {});
    setUnmerging(false);
    if (r.ok && r.data) {
      const n = (r.data.restored_ids || []).length;
      setMergeOrigin(null);
      setNote({ kind: "ok", text: `Un-merged — restored ${n} record${n === 1 ? "" : "s"}.` });
      api(`/papers/${paperId}`).then((rr) => { if (rr.ok) setState({ status: "ready", paper: rr.data }); });
      if (onTagsChanged) onTagsChanged();   // restored copies reappear in the library; the survivor's unioned links are gone
      if (onQueueChanged) onQueueChanged();
    } else {
      setNote({ kind: "err", text: r.error || "Couldn't un-merge." });
    }
  }, [mergeOrigin, paperId, onTagsChanged, onQueueChanged]);

  // inc 219: add this paper to the reading Queue (the left-pane "Queue" tab). Idempotent server-side.
  const addToQueue = useCallback(async () => {
    if (paperId == null) return;
    setNote(null);
    setQueuing(true);
    const r = await apiPost("/reading-queue", { paper_id: paperId });
    setQueuing(false);
    if (r.ok && r.data) {
      setNote({ kind: "ok", text: r.data.added ? "Added to your reading queue." : "Already in your reading queue." });
      if (onQueueChanged) onQueueChanged();
    } else {
      setNote({ kind: "err", text: r.error || "Couldn't add to the queue." });
    }
  }, [paperId, onQueueChanged]);

  const onAcquired = useCallback(() => {
    if (paperId == null) return;
    api(`/papers/${paperId}`).then((r) => { if (r.ok) setState({ status: "ready", paper: r.data }); });
  }, [paperId]);

  const saveAuthors = useCallback((text) => {
    const list = text == null ? [] : text.split("\n").map((s) => s.trim()).filter(Boolean);
    return saveField("authors", list);
  }, [saveField]);

  const saveTranslators = useCallback((text) => {
    const list = text == null ? [] : text.split("\n").map((s) => s.trim()).filter(Boolean);
    return saveField("translators", list);
  }, [saveField]);

  const refreshDetail = useCallback(() => {
    if (paperId == null) return;
    api(`/papers/${paperId}`).then((r) => { if (r.ok) setState({ status: "ready", paper: r.data }); });
  }, [paperId]);

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
    <DetailReadOnly.Provider value={readOnly}>
    <div className="detail-edit-pane" style={{ padding: "10px 0 24px" }}>
      <div className="detail-type-row">
        <TypeSelect value={p.item_type} onSave={saveField} />
        {!readOnly && savingField && <span className="detail-saving">saving…</span>}
        {!readOnly && <button className="btn-link detail-fill" onClick={fillMetadata} disabled={filling}
          title="Fetch any MISSING fields (DOI, abstract, venue…) from Crossref/OpenAlex — fills only blanks, never overwrites what you typed">
          {filling ? "Filling…" : "Fill missing fields"}</button>}
        {!readOnly && <button className="btn-link detail-queue" onClick={addToQueue} disabled={queuing}
          title="Add this paper to your reading Queue (the Queue tab in the left pane)">
          {queuing ? "Adding…" : "+ Reading queue"}</button>}
      </div>

      <EditableText variant="title" value={p.title} placeholder="Add title" onSave={(t) => saveField("title", t)} />

      {mergeOrigin && !readOnly && (
        <div className="detail-merge-origin">
          <span>Merged from {mergeOrigin.merged_from_titles.map((t) => `“${t}”`).join(", ")}.</span>
          <button className="btn-link" onClick={unmergeNow} disabled={unmerging}
            title="Reverse this merge — restore the merged-away record(s) with their PDFs, tags, and highlights">
            {unmerging ? "Un-merging…" : "Un-merge"}
          </button>
        </div>
      )}

      {note && <div className={"detail-note detail-note-" + note.kind}>{note.text}</div>}

      {needsMetadata(p) &&
        <div className="errbox" style={{ margin: "0 0 12px" }}>
          <b>Metadata not yet resolved.</b> This paper came from a raw PDF. Add its DOI under
          Identifiers and click 🔎 to fetch a bibliographic record from Crossref.
        </div>}

      <EditableText label="Authors" value={(p.authors || []).join("\n")}
        placeholder="Add authors (one per line)" onSave={saveAuthors} rows={2} />
      <EditableText label="Translators" value={cslContributors(p, "translator").join("\n")}
        placeholder="Add translators (one per line)" onSave={saveTranslators} rows={2} />
      <EditableRow label="Year" value={dp[0]} numeric onSave={(v) => saveField("year", v)} />
      <EditableRow label="Month" value={dp[1]} numeric onSave={(v) => saveField("month", v)} />
      <EditableRow label="Day" value={dp[2]} numeric onSave={(v) => saveField("day", v)} />
      <EditableRow label="Volume" value={cslGet(p, "volume")} onSave={(v) => saveField("volume", v)} />
      <EditableRow label="Issue" value={cslGet(p, "issue")} onSave={(v) => saveField("issue", v)} />
      <EditableRow label="Pages" value={cslGet(p, "page")} onSave={(v) => saveField("page", v)} />
      <EditableRow label="Journal" value={p.venue} onSave={(v) => saveField("venue", v)} />
      <EditableRow label="Language" value={p.language} onSave={(v) => saveField("language", v)} />
      <EditableRow label="URL" value={cslGet(p, "URL")} mono onSave={(v) => saveField("url", v)} />
      <PaperUrlsEditor paper={p} readOnly={readOnly} onChanged={refreshDetail} />
      <EditableText label="Abstract" value={p.abstract_text != null ? p.abstract_text : p.abstract} placeholder="Add abstract"
        onSave={(t) => saveField("abstract", t)} expandable />

      <TagsRow key={p.id} paperId={p.id} initialTags={p.tags} onFilterToTag={onFilterToTag} onTagsChanged={onTagsChanged} readOnly={readOnly} />

      <DetailSection title="Identifiers" open={idOpen} onToggle={() => setIdOpen((o) => !o)}>
        <IdentifierRow label="DOI" value={p.doi} fieldKey="doi" source="crossref"
          paper={p} onSave={saveField} onResolve={reresolve} resolving={resolving} />
        <IdentifierRow label="PMID" value={cslGet(p, "PMID")} fieldKey="pmid" source="pmid"
          paper={p} onSave={saveField} onResolve={reresolve} resolving={resolving} />
        <IdentifierRow label="ArXiv ID" value={cslGet(p, "arxiv")} fieldKey="arxiv" source="arxiv"
          paper={p} onSave={saveField} onResolve={reresolve} resolving={resolving} />
        <EditableRow label="Cite key" value={p.citation_key} mono onSave={(v) => saveField("citation_key", v)} />
        <EditableRow label="ISBN" value={cslGet(p, "ISBN")} mono onSave={(v) => saveField("isbn", v)} />
        <EditableRow label="ISSN" value={cslGet(p, "ISSN")} mono onSave={(v) => saveField("issn", v)} />
      </DetailSection>

      <DetailSection title="More" open={moreOpen} onToggle={() => setMoreOpen((o) => !o)}>
        {extras.map((k) => (
          <EditableRow key={k} label={CSL_LABELS[k] || humanizeKey(k)}
            value={String(p.csl_json[k])} onSave={(v) => saveField("csl", { [k]: v })} />
        ))}
        {!readOnly && <AddFieldRow onSave={saveField} />}
      </DetailSection>

      {!readOnly && !hasPdf && <AcquireOaRow paperId={p.id} onAcquired={onAcquired} />}
      {!readOnly && hasPdf && p.chunk_count === 0 && <OcrRow paperId={p.id} onOcred={onAcquired} />}
      {!readOnly && hasPdf && p.chunk_count > 0 &&
        <button className="btn-link detail-fill" onClick={reprocessPdf} disabled={reprocessing}
          title="Re-extract searchable PDF text and section labels from the local PDF. Metadata, files, notes, tags, and annotations are preserved.">
          {reprocessing ? "Reprocessing PDF…" : "Reprocess PDF text"}</button>}

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

      <CiteRow paperId={p.id} />

      <div className="prov">
        <b>Metadata source.</b>{" "}
        {p.imported_source
          ? <>Currently <span className="src-tag">{p.imported_source}</span>.</>
          : <>Source not recorded.</>}{" "}
        <span className="detail-tierline">{p.chunk_count} chunks · {tierLabel(p.processing_tier)}</span>
      </div>
    </div>
    </DetailReadOnly.Provider>
  );
}
