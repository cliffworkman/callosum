# Increment 610 — Supervised, memory-aware, self-recovering profile index builds

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), on inc 609
`b6b8bfe0`. Not pushed, not merged. Full deliverables: `.claude/docs/research/2026-10-30_arctic-index-recovery/`.

## Implemented

- **Worker process.** `app/backend/embeddings/index_worker.py` (`python -m …index_worker`) loads one profile's
  pinned model and indexes bounded batches. It holds an OS file lock for its whole life (`index_lock.py`), exits if
  its parent dies, and reports a fixed exit-code contract (0 complete, 3 stopped by intent, 65 model, 69 DB busy,
  70 orphaned, 71 not owner, 75 resources).
- **Supervisor.** `index_supervisor.py`, one per app with a monitor thread. It launches with `sys.executable -m`
  from the source root (as the packaged app launches uvicorn), at below-normal priority with no console window. It
  watches exit, heartbeat (600 s stall) and free memory, classifies exits, halves the batch after a resource exit or
  an unexplained kill, and backs off 5 s after progress, otherwise 30/120/600 s. Three exits without new vectors trip
  the circuit breaker (`failed`, `no_progress` or `insufficient_memory`); only Resume clears it. A model failure is
  never retried automatically. Reconciliation (lifespan startup, plus `tick()` for any orphaned row) re-derives
  coverage from vectors and resumes builds whose intent is `run`. Shutdown kills only the owned worker.
- **Durable lifecycle.** Table `embedding_index_runs` (migration 0086, additive): state, intent, counts snapshot,
  batch size, attempts, failures without progress, worker token/pid, heartbeat/checkpoint/next-retry times,
  failure kind, sanitized detail, bounded diagnostic, peak worker RSS, minimum free memory.
- **Bounded memory.** `profile_index.py` plans ids only and reads ≤ batch texts per step. Each batch encodes under
  `torch.inference_mode` and commits its vectors, identity rows **and** checkpoint in one short transaction
  (default batch 8). `repair_partial_vectors` removes this profile's rows that have no stored vector or no chunk.
  `vector_integrity` reports missing/orphan/stale/duplicate.
- **Real resource measurement.** `resources.py`: Windows `GlobalMemoryStatusEx` (commit limit and available
  commit, replacing the old RAM+swap approximation), Linux `/proc/meminfo`, macOS `vm_stat`, worker working set
  via `GetProcessMemoryInfo` or `/proc`. Floors scale with total RAM: reserve `max(512, total/20)`, stop
  `max(256, total/40)`, pause halfway between them. Start requires the worker's measured peak (estimated at
  1,200 MB before the first run) plus the reserve.
- **API/UI.** New sibling router `routers/embedding_index.py`: `POST /embedding-profiles/{key}/index` (start/resume),
  `…/index/{pause,resume,cancel}`, and status by job id (the old job-id cancel now pauses). `ProfileOut.index_run`
  carries state, message, counts from vectors, percent, batch size, attempts, retry flag, actions and diagnostic. The
  durable row is mirrored into the `JobStore` so Status keeps one row. The Settings panel polls `/embedding-profiles`,
  shows the message, attempts, Pause/Resume/Cancel and collapsed technical details. Help corpus updated. QA route 97
  extended (462/462).
- **Developer driver.** `tools/run_profile_index.py` drives the same supervisor from a terminal and samples memory
  to JSONL; `--kill-after-chunks` injects one external kill.
- **psutil removed** from the design: not in `uv.lock`, so absent from the packaged runtime and CI. Test-enforced.

## Key technical detail

- **Truth comes from vectors.** Every state decision re-derives `profile_coverage`. The row's `indexed_chunks` is a
  snapshot; a test gives the row a lying counter (999) and shows reconciliation corrects it.
- **Liveness is an OS lock, not a PID.** The OS releases the lock on any exit, including TerminateProcess/SIGKILL,
  so a stale `running` row is recoverable the moment the worker is gone, and PID reuse cannot fake liveness. It also
  prevents two Callosum processes on one library from running two workers.
- **Batch size does not change the embeddings.** On the real checkpoint, batch sizes 1/8/32 differ from the stored
  vectors by at most 1.06×10⁻⁷ per component (cosine ≥ 0.99999988).
- **Smaller batches were faster here, not slower.** The old per-paper encode padded hundreds of passages to the
  longest in the paper. Measured throughput is in `LOW_MEMORY_RESOURCE_MEASUREMENTS.md`.

## Manual verification script

1. Start the integration worktree's server against a disposable library copy. Settings → Retrieval model →
   **Build index** for Arctic S. Status shows one "Retrieval index build" row; the panel shows N of M passages (P%).
2. **Pause** → "Stopping after the current batch…", then "Paused…". Restart the server: still paused. **Resume**.
3. End the worker process (Task Manager: the `python` child running `index_worker`). Within a few seconds the panel
   says "Indexing was interrupted… will retry automatically". Coverage does not drop, and the build resumes with a
   smaller batch.
4. Quit the server mid-build and start it again: the build resumes on its own.
5. The Arctic radio stays disabled, and the "not yet available for Ask" line stays, until coverage is complete.

**Not performed:** no browser check (Playwright MCP failed to connect). Steps 3–4 were exercised for real through
the developer driver on the disposable copy (same supervisor), not through the UI.

## Pytest

Targeted serial run (no concurrent indexing): **210 passed** (`test_index_recovery` 17, `test_embedding_profiles`,
`test_ask_integration_607_608`, `test_frontend_assembly`, `test_status`, `test_migrations`, `test_startup_migration`,
`test_health`, `test_nli_failure_and_provenance`, `test_help`), peak tree RSS 588 MB. The full suite was not run.
Details: `FINAL_VALIDATION_AND_COMMIT_RECEIPT.md`.

## Known limitations

1. Not run in a packaged desktop build, on macOS or on Linux; the macOS/Linux memory probes and POSIX parent watch
   are untested on those platforms.
2. No Settings toggle for automatic resume on launch (the default resumes a build the user started; Pause is durable).
3. Batch size only shrinks within a build; Resume does not restore it.
4. One active build per library (one non-baseline profile exists).
5. `app/backend/api/app.py` is at exactly 600 lines.
6. The real continuation ran the final code except one later guard (`_stop` no longer relabels a finished build),
   which the run never exercised; that guard is covered by the targeted test run.
7. A worker started with nothing pending still loads the model (about 25 s) before exiting complete.
8. Inc 607 classifications are still absent from the evaluation copy; no 607 backfill, retrieval comparison or
   DeBERTa evaluation was run.
