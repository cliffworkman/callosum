# Increment 19 Notes

## Implemented

- Added `--reuse-db` and `run_validation(..., reuse_db=True)` for opt-in reuse of an existing scratch database.
- Preserved the default behavior: without reuse, the existing scratch DB is deleted and recreated.
- Reuse semantics:
  - If the scratch DB exists and has an Alembic version, it is opened as-is.
  - If `--reuse-db` is set but the DB is missing or not migrated, the harness creates/runs migrations instead of failing.
  - With `--pdf-dir --reuse-db`, standalone PDFs are treated as already ingested when an existing PDF attachment has the same checksum and content type. The harness reports the existing chunk count and skips `ingest_pdf_scaffold`, so repeated runs do not duplicate papers, attachments, or chunks.
- Added explicit SQLAlchemy engine disposal at the end of `run_validation` so repeated fresh runs can unlink the SQLite DB on Windows.
- Added a loud zero-chunk summarization guard. The report now says:
  - `No source chunks were available for this summarization scope. Likely causes: no PDFs were ingested into this scratch DB, or the selected scope has no chunks. Run with --pdf-dir first, or pass --reuse-db with a populated --output-dir.`

## Deferred / Unchanged

- No extraction, embedding, retrieval, summarization, verification, or schema behavior changed.
- No data-copying mode was added.
- No real-library run was performed for this increment; tests used hermetic synthetic PDFs.

## Raw Pytest Output

```text
.....................................................................    [100%]
69 passed in 46.26s
```
