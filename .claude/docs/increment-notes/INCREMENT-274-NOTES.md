# Increment 274 — Long-job incremental commits: A2 (scan per-file extraction commits)

Finishes the scan half of the `database is locked` work (spec:
`.claude/docs/specs/2026-07-15-long-job-incremental-commits-design.md`). Increment A (inc 273) made the scan's
enrich+embed phase commit per paper but left the **extraction phase** (`scan_library_folder`) holding the write
lock for the whole file loop — it isolated each new file with a `conn.begin_nested()` **savepoint**, which does
not release the lock. A2 makes each new file commit in its own transaction, so the lock is released between files
during extraction too.

## Implemented
- **`scan_library_folder` now takes `engine` (was `conn`) and owns its transactions** (`pdf_processing/library_scan.py`):
  - upfront dedup/removed-detection reads run once on a read connection (`engine.connect()`);
  - **each new file is ingested (`create_paper` + `attach_pdf_to_paper` — the slow extract+chunk) in its own
    `run_write` transaction** (replacing the per-file savepoint) → the write lock is released between files, and a
    corrupt-PDF failure rolls back just that file's transaction and the scan continues (per-file isolation preserved);
  - removed-file detection (`availability="missing"`) runs in one final short `run_write`.
- **Callers updated** (`routers/library.py`): `_run_scan_job` + `_run_watched_rescan_job` now call
  `scan_library_folder(engine, folder, …)` directly (dropping the inc-A `run_write(engine, lambda conn: …)`
  wrapper, since the function self-commits). library.py 528→**522**.
- **Tests** (`tests/test_library_scan.py`): the 5 existing call sites updated to the `engine` signature (the
  scan-then-assert blocks split so reads use `engine.connect()`), plus a new `test_scan_commits_each_file_itself`
  — calls `scan_library_folder(engine, folder)` with **no caller transaction** and asserts a fresh connection sees
  the added papers, proving each file committed itself (was: one caller-committed transaction over all files).

## Key technical detail
The savepoint (`begin_nested`) gave per-file *rollback isolation* but shared the caller's single transaction, so
the lock was held across the whole extraction loop. Swapping it for a per-file `run_write` keeps the isolation
(each file's transaction rolls back independently on a corrupt PDF) **and** commits per file (lock released
between files). Signature `conn → engine` is the honest way to own those boundaries — a `conn` in a caller's
`engine.begin()` block can't commit mid-loop without breaking the block. In-scan content dedup still works: the
in-memory `existing_by_checksum` map is updated after each committed file, so two identical files in one scan
still dedup. Atomicity is per-file (intended, consistent with inc 273): a scan is idempotent (content-hash dedup).

## Not in scope (still open)
- **A3:** the axis-score job (`score_axis` embed-phase hoist).
- Increments **B–D** (ingest family; method batches + citation-counts; dedup/gap-finder/my-pubs) per the spec.

## Manual verification script
`uvicorn app.backend.api.app:app --port 8888`; trigger a scan of a folder with several **new** PDFs (so the
extraction phase runs), and while it's reading files, toggle a read marker / add a tag in another tab → succeeds
(the lock is released between files) rather than 500ing. A corrupt PDF in the folder is still isolated + surfaced
in the done-summary; the scan completes.

## Pytest
`tests/test_library_scan.py` (14, incl. the new per-file self-commit test) + `tests/test_watched_folders.py`
green. Full suite: **1219 passed, 1 skipped**.
