# Security audit — table-aware statcheck

**Date:** 2026-07-25
**Increment:** 387
**Status:** PASS

## Surface

- The existing local statcheck route and library batch may inspect supported attachments belonging to the
  selected paper: PDF, JATS/XML, HTML, DOCX, and ODT.
- Reconstructed table rows remain ephemeral method evidence. They are not added to chunks, embeddings, or a new
  persistence table.
- The API adds explicit scan coverage and table provenance; the frontend presents table rows as region evidence,
  never an exact quotation.

## Threat review

- **Data egress / secrets:** extraction reads only existing local attachment paths resolved from database-owned
  records. It makes no network or LLM request, reads no provider credential, and adds no telemetry.
- **Arbitrary paths:** callers cannot supply a file path. The route looks up attachments already associated with
  the paper and accepts only the supported content types/extensions.
- **Resource exhaustion:** a source file is capped at 256 MiB; archive members at 64 MiB; PDF scanning at 200
  pages; extraction at 100 tables, 1,000 rows, 50 columns, and 2,000 characters per cell; and orchestration at
  eight supported attachments per paper. Coverage marks any cap as truncated. A 64-entry LRU cache is keyed by
  resolved path, content type, size, and modification time.
- **Archive/parser exposure:** DOCX and ODT use bounded ZIP-member reads; JATS/XML uses the standard-library XML
  parser; HTML uses `HTMLParser`; PDF tables use the already-required PyMuPDF parser. No macro, script, external
  entity, embedded object, or executable content is run.
- **Malformed content:** a failed attachment is skipped, counted, and logged without path content entering the
  response. One malformed file cannot erase valid prose results or abort a whole-library batch.
- **False attribution:** the parser fails closed unless one unambiguous p-value column and complete test/type,
  degrees-of-freedom, and statistic fields can be reconstructed, or one cell contains a complete APA tuple.
  Multi-p-value, unlabeled, incomplete, or conflicting rows are skipped.
- **Coordinate honesty:** source header and row text, attachment/page, table/row index, caption/section, and the
  PDF table-row bbox are retained. Table evidence is `region`; quote-location is deliberately bypassed so a
  reconstructed row can never be presented as an exact prose match.
- **Transactions / persistence:** table parsing happens outside write transactions. The existing batch summary
  and finding rows are then written per paper through the established short transaction. No migration or new
  persisted document representation is introduced.
- **Compatibility / scope:** prose statcheck and p-curve behavior remain unchanged. WIP statcheck continues to
  use only its supplied snapshot chunks; attachment table scanning is limited to library-paper statcheck.
- **Supply chain:** no dependency, subprocess, downloaded asset, or new executable surface was added.

## Negative-path evidence

- Unit tests cover PDF/JATS/HTML/DOCX/ODT extraction, conservative structured-row parsing, ambiguous and
  incomplete rows, file/attachment caps, and malformed documents.
- API tests use a real ruled PDF table, assert exact coverage/provenance, preserve prose through an attachment
  failure, and persist a table-only inconsistency in the library batch.
- Chromium smoke renders a table badge, reconstructed row, coverage, region caveat, and mobile layout with a
  zero console/page-error budget.

## Result

**Security Audit: PASS.** No unresolved finding or accepted risk.
