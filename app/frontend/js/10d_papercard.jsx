// Paper card + BibTeX quick-copy (inc-103 / inc-117), split out of 10_pdf_layer.jsx (inc 264, rule #1).
// Plain function declarations that hoist across the shared esbuild IIFE, so PaperList (10_pdf_layer.jsx) and
// the My Publications tab call PaperCard/PaperCopyButton unchanged (the inc-208/222 hoist precedent).

// inc-103: per-card quick-copy of the paper's BibTeX. Since .paper cards are user-select:none (inc 98), this
// restores a one-click way to grab a card's citation. Reuses the inc-70 /papers/export endpoint (raw fetch —
// apiPost forces .json(); clipboard works on the 127.0.0.1 secure context). Mirrors 25_detail.jsx CiteRow.
function ClipboardIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}
function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}
function PaperCopyButton({ paperId }) {
  const [copied, setCopied] = useState(false);
  const copy = async (e) => {
    e.stopPropagation();  // don't select/open the card
    try {
      const res = await fetch(API_BASE + "/papers/export", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: [paperId], format: "bibtex" }),
      });
      if (!res.ok) { console.warn("[callosum] copy BibTeX failed:", res.status); return; }
      await navigator.clipboard.writeText(await res.text());
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) { console.warn("[callosum] copy BibTeX error:", err); }
  };
  return (
    <button
      className={"paper-copy" + (copied ? " copied" : "")} onClick={copy}
      title={copied ? "Copied BibTeX ✓" : "Copy BibTeX citation"} aria-label="Copy BibTeX citation"
    >
      {copied ? <CheckIcon /> : <ClipboardIcon />}
    </button>
  );
}

// inc 117 (My-Pubs SP1): the per-paper library card, extracted from PaperList so the My Publications tab can
// render the same aesthetic + parity (#13). `selecting` shows the copy button + checkbox; `footExtra` lets a
// caller append context buttons (the library passes its focus/trash buttons here).
function PaperCard({ paper: p, selecting, isSelected, onSelect, onOpen, checked, onToggleCheck, findings, referenceWarnings, onOpenReferenceWarnings, footExtra, citeInfo, readOnly }) {
  const unresolved = needsMetadata(p);
  return (
    <div
      className={"paper" + (isSelected ? " sel" : "")}
      onClick={() => onSelect && onSelect(p.id)}
      onDoubleClick={() => onOpen && onOpen(p)}  // inc-98: always open; .paper has user-select:none (copy from Details)
      title="Double-click to open the PDF · drag onto an axis to add it"
      draggable  // A6 (inc 206): drag a card onto an axis card (in the AXES pane) to manually add it
      onDragStart={e => { e.dataTransfer.setData("application/x-callosum-paper", String(p.id)); e.dataTransfer.effectAllowed = "copy"; }}
    >
      {selecting && <PaperCopyButton paperId={p.id} />}
      {selecting &&
        <input
          type="checkbox" className="paper-select" checked={!!checked}
          title="Select"
          onClick={e => e.stopPropagation()}
          onChange={() => onToggleCheck && onToggleCheck(p.id)}
        />}
      <p className="paper-title">{p.title || <span className="placeholder">Untitled</span>}</p>
      <div className="paper-meta">
        {unresolved
          ? <span className="placeholder">metadata not yet resolved</span>
          : <>
              {p.authors && p.authors.length > 0 && <span className="paper-authors">{fmtAuthors(p.authors)}</span>}
              {p.year && <span>· {p.year}</span>}
              {p.venue && <span className="paper-venue">· {p.venue}</span>}
            </>}
      </div>
      <div className="paper-foot">
        <span className={"tier " + tierClass(p.processing_tier)}>{tierLabel(p.processing_tier)}</span>
        {p.attachment_count > 0 && <span className="chip">{p.attachment_count} file{p.attachment_count > 1 ? "s" : ""}</span>}
        {unresolved && <span className="needs-doi">needs DOI</span>}
        {/* inc 130: findings — a neutral FactMark + the work-state "N to review" badge (zero shows nothing). */}
        {findings && findings.has_facts && <span className="fact-mark fact-mark-card" title="Has a fact finding (e.g. retracted)">◆ fact</span>}
        {findings && findings.unreviewed_count > 0 && <span className="finding-badge" title="Unreviewed candidate findings to review">{findings.unreviewed_count} to review</span>}
        {referenceWarnings && referenceWarnings.active_count > 0 &&
          <button
            type="button"
            className="refwarn-badge"
            title="Open Meta Reference List for this paper — active signals are unreviewed or confirmed concerns, never a paper-quality verdict"
            aria-label="Open Meta Reference List for this paper"
            onClick={e => { e.stopPropagation(); onOpenReferenceWarnings && onOpenReferenceWarnings(p); }}
          >
            {referenceWarnings.active_count} ref signal{referenceWarnings.active_count === 1 ? "" : "s"}
          </button>}
        {/* inc 119 (SP3 #14): OpenAlex cited-by count; clickable (→ citing list) once the work id is known. */}
        {citeInfo && (citeInfo.workId
          ? <button className="paper-cite" title="Papers that cite this, per OpenAlex — click to view"
              onClick={e => { e.stopPropagation(); citeInfo.onOpenCiting(citeInfo.workId, p); }}>
              {citeInfo.count} cited-by
            </button>
          : <span className="paper-cite paper-cite-static"
              title={citeInfo.asOf ? `Cited by ${citeInfo.count}, per OpenAlex · as of ${String(citeInfo.asOf).slice(0, 10)}` : "Cited-by count, per OpenAlex"}>{citeInfo.count} cited-by</span>)}
        {footExtra}
        {!readOnly && <ReadPriorityControl paper={p} />}  {/* inc 220: read toggle + priority (user markers) */}
      </div>
    </div>
  );
}
