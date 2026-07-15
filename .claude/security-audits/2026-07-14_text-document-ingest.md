# Security Audit - Non-PDF text-document ingestion

**Date:** 2026-07-14
**Feature:** `app/backend/document_text.py` (JATS/XML, DOCX, HTML `DocumentTextProvider` adapters) +
`attach_text_document_to_paper` / `reprocess_pdf_attachment` in `app/backend/pdf_processing/ingest.py`.
Non-PDF scholarly text now feeds the same `chunks` table used by transparency/statcheck/synthesis.
**Triggers:** audit-gate #3 (new file-ingestion path). Filed retroactively during the 2026-07-14
review of Codex's uncommitted work (the reprocess-PDF path already had `2026-07-13_reprocess-pdf-text.md`;
the *non-PDF text* ingest did not).

## Scope

- `extract_text_document(path, content_type)` dispatches to `JatsXmlTextProvider` / `DocxTextProvider`
  / `HtmlTextProvider`, producing `TextSegment`s → `ChunkDraft`s written to `chunks`.
- `attach_text_document_to_paper(...)` attaches a non-PDF document and feeds its extracted text into
  the chunk table.
- **Exposure today:** `attach_text_document_to_paper` is **not wired to any HTTP endpoint** — the only
  callers are its definition and `tests/test_document_text.py`. There is **no remote-reachable surface
  yet**; this audit covers the infrastructure and the controls required *before* it is exposed via an
  upload/ingest endpoint.

## Threat Review

| Vector | Assessment |
|---|---|
| **Data egress** | None. All adapters are deterministic, local, dependency-free (stdlib `xml.etree`, `zipfile`, `html.parser`). No network call, no LLM path. Invariant #3 not touched. |
| **XXE / external entity (file read / SSRF)** | **Not applicable.** Python's stdlib `ElementTree` does not resolve external entities or fetch external DTDs, so a crafted JATS/DOCX cannot read local files or reach internal URLs through entity resolution. |
| **XML entity-expansion DoS ("billion laughs")** | **Residual, low.** `ElementTree` *does* expand internal entities, so a malicious XML/JATS could blow up memory. Within the accepted local-single-user threat model (rule #4 = resource exhaustion on files the user chose to import), acceptable today. **Required before any hosted/multi-user or untrusted-upload exposure:** switch XML parsing to `defusedxml` (or cap entity expansion) + a pre-parse size cap. |
| **DOCX zip decompression bomb** | **Residual, low.** `zipfile.ZipFile(path).read("word/document.xml")` reads one entry with no decompressed-size cap; a crafted `.docx` could inflate to exhaust memory. Same local threat model / same recommendation (add a decompressed-size guard before remote exposure). |
| **File-path safety** | The ingest path is server-side, mirroring the existing PDF ingest/scan model (already localhost-accepted). No filesystem path is built from an unsanitized user-supplied *name*; the caller supplies a resolved path. When this is wired to an endpoint, the path must come from the same validated local-scan/upload flow as PDFs — **never** an arbitrary request-supplied server path (the standing "gate/remove server-file-read before hosted deployment" note applies). |
| **Injection / SQL** | Chunk writes use the existing `create_chunk` SQLAlchemy Core path (bound parameters). No user text interpolated into SQL. |
| **Output encoding** | Extracted text is stored as chunk text and rendered through React text nodes elsewhere; HTML adapter strips tags/scripts (text nodes only, no script execution, no `dangerouslySetInnerHTML`). |
| **Coordinate honesty (#2)** | Text documents have no PDF geometry: `bbox_json=[]`, `bbox_coordinate_system="document-text-offsets"`, char-offset spans only. No exact PDF rectangles are fabricated for non-PDF sources. Consistent with the contract. |
| **Reprocess safety** | `reprocess_pdf_attachment` refuses to replace existing chunks with an empty extraction (`PdfReprocessEmptyExtraction`) — no silent data loss. |
| **Supply chain** | No new dependency (stdlib only). |

## Negative-Path Checks

- Unknown/unsupported suffix + content-type → `extract_text_document` raises `ValueError` (fails closed).
- Empty/whitespace-only segments are dropped by `make_text_chunk_drafts` (no empty chunks).
- Reprocess with an empty extraction over existing chunks raises rather than deleting them.
- No endpoint currently reaches this path, so no remote negative-path surface exists to exercise yet.

## Verification

- `pytest tests/test_document_text.py` — passes (covered by the full-suite run in the same review).
- Confirmed by grep that no router imports/calls `attach_text_document_to_paper` (no live remote surface).

## Result

**Security Audit: PASS (with pre-exposure conditions).** The ingestion infrastructure is local, no-egress,
SQL-safe, honest about coordinates, and not yet remotely reachable. Two residual resource-exhaustion
vectors (XML entity expansion, DOCX decompression) are acceptable under the current local-single-user
model but are **REQUIRED controls before this path is wired to any upload/ingest endpoint or any hosted
deployment:** parse XML via `defusedxml` (or bounded entity expansion) and cap decompressed sizes.
Recorded as a pre-exposure follow-up.
