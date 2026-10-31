# Increment 616 — Disk-space safety and automatic recovery for index builds

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), on `68b690fa`.
Implementation commit `0686a5f6`. Local only: not pushed, not merged.

Authorized by the 2026-10-31 "Increment 616: Disk-Space Safety and Automatic Recovery" instruction. It implements
release blocker **B7** (no disk-space guard). Status: **implemented, focused-tested, process-tested with simulated
resources; not release-validated.**

## Implemented
- **`app/backend/embeddings/disk_guard.py`** (new): the free-space floor, the library-volume probe, the
  remaining-growth estimate, the running hard stop, and `is_disk_full` (SQLite `SQLITE_FULL` / "database or disk
  is full", or OS `ENOSPC`, however wrapped). `free_bytes(path)` is the one shared free-space probe; the inc-615
  provisioner now calls it instead of its own copy.
- **`embeddings/index_worker.py`:** checks the disk before every batch (`EXIT_DISK = 74`, kind `disk_low`) and maps a
  full-disk exception to the same exit code (kind `disk_full`). The failing batch's transaction rolls back; every
  earlier batch is committed. The worker records the disk check (numbers only) when it can; a full disk may refuse
  that write too, so it is wrapped and the exit code still says why.
- **`embeddings/index_supervisor.py`:**
  - preflight before a launch: no worker and no model load while the next batches would not fit;
  - the remaining-growth estimate is recorded at launch, before the first batch;
  - the monitor stops a running worker if something else drives free space below 256 MB;
  - exit 74 (or the supervisor's own `disk_stop`) → `waiting_disk`, outside the circuit breaker, same batch size,
    recheck after `disk_recheck_seconds` (60 s);
  - a disk exit while the user's intent is pause or cancel ends `paused`/`cancelled` (Pause stays authoritative);
  - restart reconciliation keeps a `waiting_disk` row waiting and rechecks immediately, instead of relabelling it
    an interruption of unknown cause;
  - the thread launcher's status write after a worker outcome is now wrapped like the process worker's, so a full
    disk can never leave a thread handle with no exit code.
- **`persistence/schema_index_runs.py` + migration `0087_index_run_waiting_disk`:** the `waiting_disk` state and three
  integer columns (`disk_required_bytes`, `disk_free_bytes`, `disk_estimated_bytes`). The migration rebuilds the
  inc-610 table once (SQLite cannot alter a CHECK constraint), copies every row unchanged, and is a no-op on a fresh
  or already-upgraded database. The table holds build lifecycle rows only: no vectors, no user data, no inbound FKs.
- **`api/routers/embedding_index.py`:** `waiting_disk` offers Pause and Cancel and counts as an automatic retry. The
  message reads "Waiting for disk space: needs about X GB free, Y GB free now. Completed work is saved. Callosum checks
  again every minute and resumes automatically." (or "the disk holding your library filled up" for `disk_full`).
  A structured `disk` field carries `required_free_bytes`, `free_bytes` and `estimated_remaining_bytes`, byte counts
  only. The Status mirror already treats every `ACTIVE_STATES` row as running work, so `waiting_disk` stays visible
  in the Status popover with that label. No percentage or ETA is invented.

**Unchanged:** model revisions and embeddings, source-role classification, retrieval ranking, NLI thresholds,
scientific verification, Qwen2.5 synthesis, historical provenance, the DeBERTa release gates (still unarmed).
No frontend file changed.

## Disk-resource state and recovery contract
1. **Which disk:** the filesystem holding the SQLite library file (`library_dir(db_url)`). The Hugging Face cache is
   checked separately by the inc-615 provisioner on its own volume; neither check can block the other.
2. **The floor** = `RESERVE_BYTES` (1 GB) + `WAL_ALLOWANCE_BYTES` (64 MB) + `2 × LOOKAHEAD_BATCHES (4) × batch ×
   BYTES_PER_CHUNK (2,048)`.
   - `BYTES_PER_CHUNK`: 1,662 bytes measured on a disposable synthetic library with the real sqlite-vec store and
     384-dimension vectors (vector + `embeddings` row + index entries), rounded up about 23%.
   - The ×2 counts pages written once into the WAL and again into the main file at checkpoint.
   - WAL allowance: the autocheckpoint held the WAL at about 4 MB in the measurement; 64 MB covers a reader that
     pins a snapshot and delays the checkpoint.
   - **Audit floor corrected.** The audit proposed `max(1 GB, 2 × next N batches)`. With `max`, the reserve and the
     in-flight need overlap: once the batch term passes the reserve, a batch eats into the reserve, and WAL growth
     is not covered. The implemented floor adds them, so the reserve is untouched after the next batches land.
   - At the default batch of 8 the floor is about 1.07 GB. It covers only the next bounded step, never the whole
     build: a 4,000-paper library (about 2.5 GB estimated) starts with 2 GB free and progresses in increments.
   - The full remaining estimate is recorded and reported, never required.
3. **Where it is checked:** before launch (supervisor preflight), before every batch (worker), and continuously
   while running (monitor, 256 MB hard stop). Runtime `SQLITE_FULL`/`ENOSPC` is handled independently of every
   estimate, so a quota, a sparse file or a racing application cannot defeat the guard.
4. **`waiting_disk`** is retryable at a fixed interval, never terminal, never counts toward
   `failures_without_progress`, never halves the batch, and never deletes original data or MiniLM vectors.
5. **Unmeasurable disk** (no file, probe error) does not block; `SQLITE_FULL` still stops the batch.
6. **Pause/Cancel** are authoritative in every disk path, including across a restart.
7. **Status/API** fields are byte counts; no path, drive name or filename. User-facing UI work (the settings panel
   still lists `waiting_disk` as inactive, so it does not poll or show a progress bar) stays with the modernization
   interface increment. **Automatic model downloads and indexing must not ship without visible, truthful progress
   reporting** (invariant #5; recorded in the blocker matrix under B2/B7).

## Interruption / restart validation receipt (automated)
`tests/test_index_disk_guard.py`, 14 tests, all simulated on disposable database copies. Low disk is a fake
`disk_usage`; a genuine SQLite `database or disk is full` is produced with `PRAGMA max_page_count` on the worker's
own connections after a `VACUUM` (no free pages). No real disk was filled.

| # | Requirement | Test |
|---|---|---|
| 1 | Low disk before the first batch | `test_low_disk_before_the_first_batch_waits_without_a_worker_then_resumes` (no worker, 0 attempts, estimate recorded) |
| 2 | Disk insufficient after earlier batches | `test_disk_running_low_after_committed_batches_keeps_them_and_resumes` (4 committed rows kept) |
| 3 | Injected SQLite full | `test_genuine_sqlite_full_rolls_back_the_batch_never_trips_the_breaker_and_recovers`; process: `test_process_worker_hitting_a_real_sqlite_full_recovers_after_restart` |
| 4 | Recovery after space returns | every waiting test ends `completed` with full coverage |
| 5 | Process interruption while waiting | `test_app_killed_while_waiting_for_disk_recovers_on_restart`; process restart test |
| 6 | Recovery after restart | same two, plus `test_pause_stays_authoritative_over_a_disk_wait_across_restart` |
| 7 | In-flight transaction | committed counts are whole batches only; `vector_integrity` clean; no duplicates |
| 8 | No breaker escalation | six consecutive full-disk retries with `max_failures_without_progress=3`: always `waiting_disk`, failures 0 |
| 9 | Legacy MiniLM untouched | MiniLM rows byte-identical before/after in the thread and process full-disk tests |
| 10 | SQLite integrity | `PRAGMA integrity_check` = `ok` after each failed and retried write |
| 11 | Cache and library on different filesystems | `test_model_cache_and_library_on_different_volumes_are_checked_independently` |
| 12 | Ordinary use unaffected | `test_disk_wait_is_structured_in_status_and_browsing_keeps_working` (`/papers`, `/status/jobs`, no path in status) |
| — | Real worker exit code | `test_process_worker_declines_a_batch_on_low_disk_with_its_exit_code` (exit 74 from a separate process) |
| — | Pause during a disk exit | `test_disk_shortage_with_a_pause_requested_ends_paused` |
| — | Migration | `test_migration_0087_upgrades_an_inc_610_table_keeping_rows_and_is_idempotent` |
| — | Floor/classifier units | three unit tests |

## Manual verification script
1. Disposable DB copy; `$env:CALLOSUM_DB_URL` pointed at it; start uvicorn.
2. Start an Arctic S index build. With ample space, `GET /embedding-profiles` shows `index_run.disk` with an
   `estimated_remaining_bytes` before the first batch.
3. To see `waiting_disk` without filling a disk, use the test seam: run
   `pytest tests/test_index_disk_guard.py -k status -q`, which drives the real API with a fake low disk.

## Not done / release-validation gaps
- **Not release-validated.** Still owed: a real low-disk run on a small dedicated volume (not the primary disk),
  packaged-runtime checks (B10), and the UI state above.
- If the disk is truly full, the supervisor's own status writes can fail too; the monitor swallows the error and
  retries on its next tick, and the worker's exit code still drives the state. Not separately tested.
- The 2 KB-per-passage estimate is from synthetic text; real libraries may differ, which only affects the
  reported estimate and a small part of the floor (the reserve dominates).
- The demo/website coverage gates fingerprint `app/backend/api/routers/*.py`; 616 changed `embedding_index.py`
  (the index-run response gained `waiting_disk` and `disk`). The surface changed, so the deferral was **not**
  extended administratively (see the final report).

## Pytest
- `tests/test_index_disk_guard.py`: 14 passed.
- Regression: `test_index_recovery.py`, `test_model_provisioning.py`, `test_embedding_profiles.py`,
  `test_migrations.py`: 70 passed.
- Gates: line budget OK, tach OK, QA surface map OK, ruff format/check clean, bandit clean (pre-commit).
