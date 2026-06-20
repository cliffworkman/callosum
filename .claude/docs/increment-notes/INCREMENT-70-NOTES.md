# Increment 70 Notes — Citation export (BibTeX + RIS + CSL-JSON)

callosum is a reference manager you **import into** (Zotero → Crossref-enriched CSL-JSON) but had **no way to
get citations back out** — a core gap. Added export from the canonical `papers.csl_json` in three formats,
two delivery modes (user-chosen): a **bulk file download** (selected papers → one file) from the library
bulk bar, and a **per-paper clipboard copy** from the Details pane.

## Implemented
- **`app/backend/metadata/citation_export.py`** (new, 213) — pure formatters over paper RowMappings:
  `to_bibtex` / `to_ris` / `to_csl_json` + a `render_citations(papers, fmt) -> (text, media_type, ext)`
  dispatch. Reads from `csl_json` (type, author[family/given/literal], issued[date-parts], title,
  container-title, volume, issue, page, DOI, URL, ISSN, ISBN, publisher) with scalar-column fallbacks;
  abstract via **`abstract_plain_text`** (JATS-stripped). BibTeX: CSL type → `@article/@inproceedings/@book/
  @incollection/@phdthesis/@techreport/@misc`; entry key = `citation_key` (Zotero) else `{family}{year}`
  sanitised + **deduped** (`a/b/c`); authors `Family, Given and …`; title `{{…}}` (case-preserve); specials
  `& % $ # _ { }` escaped; pages `-`→`--`. RIS: `TY/AU/TI/PY/T2/VL/IS/DO/UR/SN/AB` + `ER  -`. CSL-JSON:
  the stored records verbatim (lossless).
- **`repository.get_papers_for_export(conn, ids)`** — bound-param `select(papers).where(id.in_(ids),
  deleted_at IS NULL).order_by(id)` — **live papers only** (never export trashed).
- **`POST /papers/export`** (`routers/papers.py`) — body `{paper_ids (min 1), format: Literal[bibtex|ris|
  csl-json]}`; 422 if no live papers resolve; returns a `Response` with the format's `media_type` +
  `Content-Disposition: attachment; filename="callosum-citations.<ext>"` (constant filename). One endpoint
  serves both the download (frontend blobs it) and the copy (frontend reads the text).
- **Frontend:**
  - bulk **export `<select>`** in the library bulk bar (`10_pdf_layer.jsx`) — `BibTeX (.bib)` / `RIS (.ris)`
    / `CSL-JSON`; `bulkExportPapers(fmt)` (`40_app.jsx`) does a **raw `fetch`** (the `apiPost` helper forces
    `.json()`) → `res.blob()` → `URL.createObjectURL` → temp `<a download>`. Selection is **kept** (export
    another format).
  - per-paper **Cite row** in the Details pane (`25_detail.jsx` `CiteRow`) — `BibTeX · RIS · CSL-JSON` links
    (reuse the inc-68 canonical **`.btn-link`**) → raw fetch → `res.text()` → `navigator.clipboard.writeText`
    (secure context on 127.0.0.1) → the link flips to **"Copied ✓"** for ~1.5s.
  - `.bulk-export` + `.detail-cite` CSS (token-based). Rebuilt `callosum-app.html`.

**No migration, no egress, no new dependency.** papers.py 553 / repository.py 585 / citation_export.py 213 —
all < 600.

## Verification
- **pytest 244** (+8): `test_citation_export.py` (7 — BibTeX field mapping/escaping/case/key-dedupe/misc
  fallback, RIS tags + `ER`, CSL-JSON round-trip, dispatch + bad-format, literal author + empty list) +
  `test_export_citations_each_format_and_validation` (endpoint: each format's content-type + `attachment`
  header + body; bad format/empty/nonexistent → 422; trashed excluded). Route-surface invariant
  += `/papers/export`.
- **Live E2E** (`.local/citation_export_e2e/`): select both papers → BibTeX from the picker → a
  `callosum-citations.bib` downloads with both entries (`expect_download`); open a paper's Details → Copy
  BibTeX → read it back from the clipboard (granted perms). **0 console errors.**
- Audit `.claude/security-audits/2026-06-20_citation-export.md` — **PASS** (read-only, local, escaped output,
  validated input, constant filename).

## Manual verification script
1. Select ≥2 papers (checkboxes) → in the bulk bar pick **export… → BibTeX (.bib)** → a `.bib` downloads;
   open it (valid BibTeX, one entry per paper). Repeat for RIS / CSL-JSON.
2. Click a paper → Details pane → **Cite: BibTeX** → paste elsewhere (the entry is on the clipboard;
   the link briefly shows "Copied ✓").

## Deferred (noted)
- A formatted human citation style (APA/MLA via a CSL processor — Track-B backlog).
- One-click "export whole library" without select-all; richer export feedback (a toast on download).
