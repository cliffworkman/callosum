# Security audit — scan / refresh a library folder (inc 87)

**Date:** 2026-06-21
**Feature:** point Callosum at a folder of PDFs → ingest new ones, skip unchanged, flag removed. **Gate trigger:**
a new **file-ingestion path** + 2 new API endpoints + a feature spanning 3+ files.

## Surface added
- `app/backend/pdf_processing/library_scan.py` — `scan_library_folder(conn, folder)` (walk `*.pdf`, ingest new
  via `attach_pdf_to_paper`, skip unchanged by checksum, mark removed `availability="missing"`).
- `routers/library.py` — `POST /library/scan {folder}` (async job) + `GET /library/scan/{job_id}` (poll); the
  job enriches new papers (Crossref) + embeds new chunks/papers.
- Frontend: a "Scan folder" button + `ScanModal`.

## Threat review

**File-path / arbitrary-read.** The folder path is user-supplied and read **server-side**. Callosum is
**local, bound to 127.0.0.1, single-user, no auth** — the server *is* the user's machine, so reading a folder
the user typed is the intended behavior, not a traversal/SSRF vuln (there's no untrusted remote caller). Guards:
the path must be an **existing directory** (`folder.is_dir()` → else 422); only `*.pdf` are globbed
(non-recursive); **nothing is written to the filesystem** (linked/in-place — `storage_mode="linked"` stores the
path, copies nothing), so there is **no write-path traversal**. ⚠️ **Before any hosted/public deployment** this
endpoint MUST be gated or removed — a remote caller could enumerate/read server files; recorded in CLAUDE.md's
"before public deployment" list.

**Untrusted PDF content (rule #4).** Each file is size-capped (`MAX_SCAN_PDF_BYTES` = 80 MiB) before ingest;
`extract_pdf` (PyMuPDF) decodes and **fails closed** on a corrupt/non-PDF file. Per-file failures are isolated
in a SQL **savepoint** (`conn.begin_nested()`) + recorded in `errors[]` — one bad file can't abort the scan or
leave a half-written paper.

**Data egress (invariant #3).** The scan + ingest + embed are **local**. The only network call is the
per-new-paper **Crossref DOI lookup** (`enrich_paper_metadata_from_crossref`, cached, resilient — unresolved →
`crossref-unresolved` → the inc-80 Unsorted view) — public metadata infrastructure, the **same posture as
import/re-resolve/wanted**, explicitly **NOT** the Gemini `CALLOSUM_ALLOW_DATA_EGRESS` gate. No library text
leaves the machine.

**Dedup / idempotence.** New-vs-unchanged is decided by SHA256 checksum against the indexed
`attachments.checksum` — a re-scan is idempotent (all unchanged); a file already in the library (any source) is
skipped. Removed = a previously-scanned (`import_source="library-scan"`) path no longer on disk → marked
`missing` (non-destructive; nothing deleted → no orphaned embeddings).

**SQL / secrets / supply chain.** Bound-param SQL throughout; no new secret; no new dependency (PyMuPDF,
sqlite-vec, sentence-transformers already present).

## Negative-path checks (recorded)
- **Non-existent folder → POST:** 422 (`test_scan_nonexistent_folder_422`). ✓
- **Re-scan:** all unchanged, no duplicates (`test_scan_adds_new_skips_unchanged_flags_removed`). ✓
- **Removed file:** attachment flagged `missing`, paper kept (non-destructive). ✓
- **Corrupt PDF:** isolated to its savepoint + recorded in `errors[]` (the per-file try/except + `begin_nested`);
  the scan continues. ✓
- **Oversize file:** skipped + recorded (size cap). ✓

## Result
**Security Audit: PASS.** On a local single-user app, reading a user-pointed folder is the intent; the scan
writes nothing to disk (linked), size-caps + fail-closed-decodes untrusted PDFs, isolates per-file failures, and
its only egress is the already-audited Crossref lookup (not the Gemini gate). **Flagged:** gate/remove this
endpoint before any hosted deployment (added to the deployment checklist).
