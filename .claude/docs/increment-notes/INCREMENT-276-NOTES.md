# Increment 276 — Long-job incremental commits: B (ingest family)

Increment B of the long-job half (spec: `.claude/docs/specs/2026-07-15-long-job-incremental-commits-design.md`):
per-item commits for the three **ingest** jobs — citation import, bundle import, and the metadata enrich-batch —
so they release the SQLite write lock between papers instead of holding it for the whole run. These are
user-initiated (not auto-running), so lower urgency than the A/A2/A3 offenders, but the same pattern.

## Implemented
- **Citation import** (`_run_import_job`, `routers/library.py`): `import_citations` (parse → dedup → create)
  commits as its own unit (`run_write`); then each new paper is **embedded + retraction-checked in its own
  committed transaction** (`commit_each`, per-paper, skip-on-error). Mirrors the scan pipeline.
- **Bundle import** (`_run_bundle_import_job`): `import_bundle` commits as its own unit; then each new paper is
  embedded per committed transaction.
- **Metadata enrich-batch** (`_run_metadata_enrich_job`, `routers/library_enrich.py`): was a per-paper loop inside
  **one** transaction; now each paper's external-metadata fetch + write runs in its **own `run_write`
  transaction** (lock released between papers, and the per-paper HTTP is no longer inside a batch-wide lock). One
  paper's hard failure is skipped + logged, never aborting the batch. The `list_live_paper_ids` + titles read moves
  to a plain read connection.

## Key technical detail
Import + bundle follow the scan shape (monolithic create phase committed as one unit, then a per-paper embed
loop) — `import_citations`/`import_bundle` stay single-`conn` calls, committed via `run_write`. The enrich-batch
is the cleanest conversion: an existing per-paper loop, so each iteration becomes a `run_write`. Atomicity is
per-paper (intended, consistent with A): a mid-run failure leaves earlier papers imported/embedded/enriched; the
imports are additive + idempotent-ish (dedup on re-import), so partial progress is safe.

## Not in scope (still open)
Increments **C** (method batches: statcheck / retraction / transparency + citation-counts) and **D** (read-heavy:
dedup, gap-finder, my-publications refresh/decompose) per the spec.

## Manual verification script
`uvicorn app.backend.api.app:app --port 8888`; import a large citation file (`POST /library/import`) or run a
library-wide **enrich refresh** (`POST /library/enrich/refresh`), and while it runs toggle a read marker / add a
tag in another tab → succeeds (the lock is released between papers) instead of 500ing. A mid-run failure leaves
the earlier papers imported/enriched (partial progress), and the job completes rather than erroring the whole run.

## Pytest
`tests/test_citation_import.py` (+ new `test_import_commits_embeddings_per_paper_partial_progress`),
`tests/test_library_bundle.py`, `tests/test_metadata_multi_enrich.py` (+ new
`test_enrich_commits_per_paper_partial_progress`) green (41). Full suite: **1223 passed, 1 skipped**.
