# Increment 273 — Long-job incremental commits: Increment A (commit_each + scan/rescan)

The second half of the `database is locked` concurrency item (the first half — foreground `run_write` +
`SqliteWriteRetryMiddleware` — shipped inc 272). This increment adds the reusable per-item-commit primitive and
converts the auto-running scan / watched-rescan jobs so they release the SQLite write lock **between papers**
instead of holding it for the whole multi-minute run. Design: `.claude/docs/specs/2026-07-15-long-job-incremental-commits-design.md`;
plan: `.claude/docs/plans/2026-07-15-long-job-incremental-commits-A-plan.md`.

## Implemented

- **`commit_each(engine, items, process, *, on_item_error="skip", logger=None)`** (`persistence/sqlite_retry.py`)
  — runs each item in its OWN short transaction via `run_write` (inc 272), releasing the write lock between items.
  The long-job counterpart to `run_write`; both concurrency layers now share one primitive. `on_item_error="skip"`
  logs a non-lock failure and continues (resilient batch — one bad item never aborts the run); `"raise"` propagates.
  A transient per-item writer lock is retried by `run_write`, not skipped.
- **`_process_scan_result` → per-paper commits** (`routers/library.py`). Was: enrich-loop + one `embed_chunks(all)`
  + one `embed_papers(all)` inside the caller's single transaction. Now: iterate the scanned papers and run each
  paper's enrich + embed-its-chunks + embed-itself + retraction-check as one `commit_each` item (its own committed
  transaction). Signature changed `conn` → `engine`.
- **`_run_scan_job` + `_run_watched_rescan_job` rewired**. The `scan_library_folder` **insert phase** commits as its
  own unit (`run_write`), then `_process_scan_result` commits per paper, then the watched-folder bookkeeping is a
  final short `run_write`. The rescan reads its target folder list on a plain `engine.connect()` (a read needs no
  write txn), then processes each folder's insert-phase + per-paper enrich/embed with the lock released between.

## Key technical detail — atomicity moves from per-job to per-item (intended)
Previously a mid-job failure rolled back the whole run (all-or-nothing). With per-item commits, papers processed
before a failure stay committed. This is **intended and better**: (a) partial progress is usable and the scan is
idempotent (content-hash dedup, inc 45), so a re-run continues; (b) it fixes a latent bug where a caught per-item
exception inside the old shared transaction could poison *subsequent* items' writes — a fresh per-item transaction
isolates each paper. The done-summary already reports per-file error counts, so partial completion stays observable.

Vector writes are safe per item: `vector_store.add(conn, …)` writes the sqlite-vec index through the **same**
connection as the `embeddings` row, so a paper's chunk-embeddings + paper-embedding + vector index all commit (or
roll back) together.

## Deferred (noted, not dropped)
- **A2:** `scan_library_folder`'s extraction phase still commits as one unit — it isolates each new file with a
  *savepoint* (which doesn't release the lock). Converting it to per-file *commits* is a distinct ingest refactor.
- **A3:** the axis-score job (`score_axis` in `clustering/`) — its slow part (embedding all candidate papers) is
  buried in a monolithic call; needs an embed-phase hoist, a different-subsystem change.
- Increments **B–D** (ingest family, method batches, read-heavy + my-pubs) per the spec's sequencing.

## Manual verification script
1. `uvicorn app.backend.api.app:app --port 8888`. 2. Trigger a scan of a folder with several new PDFs
   (`POST /library/scan`). 3. While it runs, in another tab rapidly toggle a paper's read marker / add a tag / add
   to the reading queue → they succeed (the lock is released between papers, and inc-272's retry slips them in)
   instead of 500ing. 4. Interrupt a scan partway → the already-processed papers are present + embedded (partial
   progress), and a re-scan continues rather than redoing everything.

## Pytest
`tests/test_sqlite_retry.py` (12: retry_sqlite_locked + run_write + commit_each) + `tests/test_library_scan.py`
(incl. the new `test_scan_commits_per_paper_partial_progress`) + `tests/test_watched_folders.py` green. Full
suite: **1218 passed, 1 skipped**.
