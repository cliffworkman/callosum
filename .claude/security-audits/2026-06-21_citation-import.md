# Security audit — Citation-file import (inc 93)

**Date:** 2026-06-21
**Feature:** Import a BibTeX / RIS / CSL-JSON file → parse → dedup → create metadata-only library papers → embed.
**Trigger(s):** new API endpoint (`POST /library/import` + `GET /library/import/{job_id}`); new ingestion path;
parses untrusted file content; net-new feature spanning 3+ files. (No new third-party dependency.)

## Surface
- `app/backend/metadata/citation_import.py` — hand-rolled parsers (`parse_bibtex`/`parse_ris`/`parse_csl_json`),
  `detect_format`, `csl_record_to_paper_fields`, `import_citations` (dedup + create).
- `app/backend/api/routers/library.py` — `POST /library/import` (async job) + `GET /library/import/{job_id}`.
- `app/backend/api/app.py` — `library_import_jobs` JobStore.
- Frontend `28_import.jsx` — browser reads the chosen file and POSTs its text as JSON.

## Threat review
- **Input validation / untrusted content (rule #4).** The file content is fully untrusted. Parsers are
  **defensive**: a malformed entry is skipped and counted (`failed`), never fatal — each record is created in a
  per-record `conn.begin_nested()` savepoint, so one bad record can't abort the batch or corrupt the txn. A
  whole-parse exception is caught → empty result (reported, not 500). Format is sniffed/validated against an
  allowlist (`IMPORT_FORMATS`); an unrecognised file → `format: null`, 0 imported (honest, not an error).
- **Resource exhaustion.** `MAX_IMPORT_BYTES` (5 MB) rejects oversized content; `MAX_IMPORT_RECORDS` (5000)
  caps how many papers one import creates; the request body has a Pydantic `max_length`. The BibTeX brace-matcher
  is linear (single forward scan); RIS/CSL parsers are linear. No catastrophic-backtrack regexes (the few
  regexes are anchored/simple). Embedding the new papers is bounded by the record cap. Runs as an async job so a
  large file doesn't block the event loop.
- **SSRF / external calls / EGRESS.** **None.** Import is **entirely local** — it parses the supplied text and
  writes the DB. It fetches **no URL** and calls **no external service** (no Crossref, no Gemini). A `URL`/`DOI`
  field in the file is stored as data, never dereferenced. The data-egress gate is therefore not even in play —
  nothing leaves the machine. (Crossref-enrich / My-Pubs auto-join were deliberately deferred to keep this so.)
- **File-path safety.** Unlike the inc-87 scan (which reads a server-side folder path), import takes the file
  **content in the JSON body** — there is **no filesystem path** from the client and **no file is read
  server-side**, so there is no path-traversal / server-file-enumeration surface here at all.
- **SQL injection.** All writes go through `create_paper` + `find_existing_paper_by_identity` (SQLAlchemy Core
  bound parameters, rule #3). No identifier or value is interpolated into SQL text. `imported_source` is a
  server-side constant (`<fmt>-import`), not client input.
- **Output encoding / stored-XSS.** Imported strings land in `papers.csl_json` + scalar columns and render
  through the existing escaped/allowlisted paths (the Detail pane is plain-text fields; titles render as text).
  No new render path. (`csl_json` is stored as data, surfaced via the same projections as every other paper.)
- **Provenance / clobber protection.** `<fmt>-import` is deliberately **outside** enrichment's
  `_can_update_from_crossref` allowlist, so a later batch-enrich won't silently overwrite the file's metadata
  (same protection as user-edited papers, inc 49).
- **Supply chain.** **No new dependency** — the parsers are hand-rolled stdlib (`json` + `re`), matching the
  inc-75 decision to hand-roll rather than add a parser. Nothing new to pin/audit.

## Negative-path checks (run)
- Unrecognised content (`"not a citation file at all"`) → job `done`, `imported: 0, format: null` (test
  `test_import_endpoint_unrecognized_content`). ✓ no 500.
- `@comment{…}` + a title-less `@article{junk}` → ignored / dropped at parse (test `test_parse_bibtex`). ✓
- Re-import of the same file → all deduped, **zero** copies created (tests
  `test_import_citations_creates_dedups_and_isolates`, `test_import_roundtrips_exported_csl_json`). ✓
- Empty body → 422 at the endpoint (`min_length=1` + the strip check). ✓
- Oversized content → `parse_records` raises `ValueError` → the job records `error` (not a crash). ✓ (cap path)
- Egress while the library egress gate is OFF → unaffected: import performs no egress regardless. ✓

## Result
**Security Audit: PASS.** Import is local-only (zero egress, no server-side file read), bounded
(size + record caps + per-record savepoint isolation), defensive (malformed input reported, never fatal), uses
bound-param SQL, and adds no dependency. v1 parser limitations (no BibTeX `@string`-macro/`#`-concat expansion;
`{`-delimited entries only) are correctness/coverage trade-offs, not security risks — unparsed entries are
simply skipped and counted.
