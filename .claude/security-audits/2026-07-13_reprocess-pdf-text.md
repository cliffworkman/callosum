# Security audit: Reprocess PDF text

Date: 2026-07-13

## Scope

New local API endpoint:

- `POST /papers/{paper_id}/reprocess-pdf`

User-visible control:

- Details pane: `Reprocess PDF text`

## Data flow

1. Client sends only a numeric `paper_id`.
2. Backend loads the paper from the local database.
3. Backend selects the existing primary local PDF attachment using the same trusted helper as PDF serving/OCR.
4. Backend resolves the attachment path from stored server-side attachment metadata.
5. Backend runs the existing local PyMuPDF extraction/chunking path.
6. Backend deletes chunks, embedding rows, and vector-store rows for that attachment only.
7. Backend writes replacement chunks and refreshes the paper processing tier.

## Threat review

- **Client path injection:** Not applicable. The endpoint accepts no path or filename from the client.
- **Remote fetch / SSRF:** Not applicable. The endpoint performs no network request.
- **Arbitrary file read:** Bounded to the PDF path already stored in Callosum attachment metadata and accepted by the existing `_local_attachment_path` helper. URL-mode and unavailable attachments are rejected.
- **Over-broad deletion:** The delete predicate is scoped by both `paper_id` and `attachment_id`; paper metadata, attachments, tags, notes, annotations, and other papers are not deleted.
- **Stale vector/search data:** Existing chunk embedding rows and vector-store rows are removed before the replacement chunks are created.
- **SQL injection:** SQLAlchemy Core expressions with bound values; no user-controlled SQL fragments.
- **PII / egress:** No upload, model call, DOI lookup, or third-party provider call. PDF text stays local.
- **Resource exhaustion:** Reuses the existing PDF extraction path and its operational envelope. No background daemon or polling loop is introduced.
- **Auth/access control:** Covered by the existing app access-control middleware for local/remote access modes.

## Result

PASS for the implemented scope.

Residual risk: a very large or malformed local PDF can still take time or fail inside the existing extraction backend. The endpoint returns normal API errors and does not introduce a new remote attack surface.

## Addendum: text-health overview and batch reprocess

Additional endpoints:

- `GET /papers/text-health/overview`
- `POST /papers/text-health/reprocess`
- `GET /papers/text-health/reprocess/{job_id}`

Additional review:

- **Read surface:** The overview returns paper IDs plus aggregate extraction-health counters only. It does not return PDF text, filenames, paths, annotations, notes, or private manuscript content.
- **Batch scope:** `selected` mode accepts at most 500 paper IDs and intersects them with live local papers. `missing_section_labels` mode derives candidates locally from existing chunk metadata.
- **No silent OCR:** Papers with no chunks are counted/skipped; the batch job does not invoke OCR or create searchable PDF copies.
- **No empty replacement:** If re-extraction would replace existing chunks with zero chunks, the existing chunks are preserved.
- **No egress:** Overview and batch reprocess perform no network, model, metadata-provider, or LLM calls.
- **Job lifetime:** Uses the existing process-local `JobStore`; restart clears status only. Work is re-runnable.
- **Deletion boundary:** Same scoped chunk/embedding/vector deletion as the single-paper endpoint: `paper_id` plus `attachment_id`.

Addendum result: PASS.

## Correction (2026-07-14 review): reprocess did not re-embed the replacement chunks

A trust-but-verify review found a **functional-integrity defect** the original audit missed: step 6 deletes the
old chunks' embedding + vector-store rows, and step 7 writes replacement chunks — but nothing **re-embedded** the
new chunks. So after any reprocess (single-paper or batch), the paper's fresh chunks had no embeddings.

- **Impact:** synthesis self-heals (it lazily embeds in-scope chunks before ranking), but vector-search retrieval
  (find-related, gap-finder, axis scoring, library-wide citation-suggest) searches existing embeddings — so a
  reprocessed paper silently dropped out of those flows until re-embedded. A maintenance action degrading
  retrievability, undisclosed. Not a security issue; a correctness one.
- **Fix:** `reprocess_pdf_attachment` now takes an `embedding_model` and calls `embed_chunks(conn, model=…,
  vector_store=…, chunk_ids=new_chunk_ids)` after creating the replacement chunks (idempotent per chunk_version —
  the same primitive verification/synthesis use). Both callers (`routers/papers.py`, `routers/text_health.py`)
  pass the model via an `_embedding_model(app)` accessor mirroring `_vector_store(app)`.
- **Test:** `tests/test_text_health.py::test_text_health_overview_and_missing_section_batch` now asserts every
  reprocessed chunk has an embedding row.

Correction result: PASS after fix. Security posture unchanged (still local, no egress, scoped deletion).
