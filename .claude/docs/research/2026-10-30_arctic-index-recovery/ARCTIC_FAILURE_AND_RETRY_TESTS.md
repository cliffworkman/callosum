# Failure-injection and retry tests (inc 610)

All automated tests use fake encoders and disposable temp databases; none loads a real model. "Real subprocess" means
a separate OS process (`python -m tests.index_worker_fake`, which runs the production `index_worker.main` with a
fake encoder), so kills, exit codes and app deaths happen as they would in production. An exception raised in-process
would not reproduce a worker that vanishes without running any cleanup code.

## `tests/test_index_recovery.py` — 17 tests, all passing

| # | Test | Mechanism | What it proves |
|---|---|---|---|
| 1 | `test_policy_floors_scale_with_the_machine_not_a_fixed_16gb` | pure | 8 GB and 64 GB machines get different floors; available commit binds even when physical memory looks fine |
| 2 | `test_windows_measurement_reports_real_commit_limit` | real OS call | `GlobalMemoryStatusEx` commit limit ≥ physical, available commit ≤ limit |
| 3 | `test_fresh_build_completes_and_a_rerun_adds_nothing` | thread | fresh build → `completed`; a rerun adds 0 rows; no duplicate current vectors |
| 4 | `test_low_memory_at_start_waits_without_launching_then_starts` | thread | low memory → `waiting_resources`, 0 attempts, no worker; starts when headroom returns |
| 5 | `test_pressure_mid_build_halves_batch_waits_and_resumes` | thread | pressure after several batches → worker leaves, batch 2→1, committed work kept, no relaunch while still low, resumes to 12/12 without duplicates |
| 6 | `test_persistent_allocation_failure_ends_in_an_honest_blocked_state_then_manual_resume` | thread | repeated `MemoryError` → 2→1 → `failed`/`insufficient_memory` after 3 attempts; no further automatic attempt; explicit Resume completes |
| 7 | `test_model_unavailable_is_never_retried_automatically` | thread | missing checkpoint → `failed`/`model_unavailable`, 1 attempt; raw error only in `diagnostic` |
| 8 | `test_pause_and_cancel_are_durable_across_restart` | thread + new supervisor | paused stays paused after restart and reconciliation; cancelled stays cancelled |
| 9 | `test_partial_vectors_are_repaired_and_minilm_rows_are_untouched` | thread | an Arctic identity row with no vector (otherwise counted as indexed) is removed and re-embedded; MiniLM rows byte-identical |
| 10 | `test_changed_chunk_reopens_the_index_and_ask_fails_closed_until_rebuilt` | thread | edited chunk → incomplete → `require_complete_index` raises → rebuild re-embeds only it; stale row kept, not counted |
| 11 | `test_restart_reconciles_a_dead_worker_from_stored_vectors` | dead real PID + new supervisor | `running` row with a dead worker and a lying counter (999) → `retrying`, count re-derived (0), then completes |
| 12 | `test_subprocess_worker_killed_externally_is_detected_and_resumed` | **real subprocess, hard kill** | TerminateProcess/SIGKILL mid-build → `retrying`, `interrupted_unknown_cause`, batch 2→1, failures 0 (progress made), committed rows kept, bystander alive; resumes to 10/10, no missing vectors, no duplicates |
| 13 | `test_api_server_survives_worker_failure_and_status_stays_available` | real subprocess via the API | worker exits 75 (MemoryError) → API still serves `/embedding-profiles` and `/status/jobs`; run shows the low-memory message and automatic retry; `MemoryError` only in `diagnostic`; Cancel works |
| 14 | `test_app_shutdown_stops_only_its_own_worker` | real subprocess | shutdown kills only the owned worker; bystander alive; OS lock released; row `interrupted`/`app_closed`, intent still `run` |
| 15 | `test_orphaned_worker_exits_when_its_app_dies` | real subprocess, parent killed | lock held while alive; a **second worker** for the same library/profile exits 71; killing the parent ends the worker with 70; lock released |
| 16 | `test_a_worker_lost_while_the_app_runs_is_recovered_without_a_restart` | real subprocess | a `running` row with no live lock holder is recovered by `tick()` (no restart needed) and completes |
| 17 | `test_production_code_does_not_depend_on_psutil` | static | no `app/` module imports psutil; psutil is absent from `uv.lock` |

## Adapted existing tests

- `tests/test_embedding_profiles.py`: the resumable/cancellable test now cancels after one committed batch
  (`batch_size=1`) and asserts on chunks, since batches no longer coincide with papers. The two API tests poll the
  supervised job (`wait_for_index_job`) instead of assuming the build finished inside the POST. They also assert
  `run.state == "completed"` and `percent == 100.0`.
- `tests/test_ask_integration_607_608.py`: unchanged and passing (calls `build_profile_index` directly).

## Defects found by these tests before the real run

1. **sqlite-vec not loaded for the integrity read** (test 12, on its first run). On a library whose vector table
   exists, every resume would have failed with `no such module: vec0`. Fixed in `profile_index._load_sqlite_vec`.
2. **Worker diagnostic overwritten by the supervisor** (test 13). The exit-code note replaced the worker's own
   `MemoryError` report. They are now joined (exit code | worker report | stderr tail), and cleared at each launch so
   a previous attempt's text never mislabels the next.
3. **psutil would have been missing in the packaged app and CI** (found while writing the audit; test 17 guards it).

## Real-model failure injection (controlled continuation)

| Event | Where | Observed |
|---|---|---|
| External kill of the real Arctic worker | 25,525 vectors, worker RSS 615 MB | `retrying` / `interrupted_unknown_cause` within one tick; 5 s later attempt 2 at batch 4; no lost or duplicated vectors |
| Driver ("app") killed with no cleanup | 28,857 vectors | worker exited by itself via the parent watch (no orphan); row left claiming `running` with a dead PID |
| Restart on the final code | — | reconciliation: `running` → `retrying`, count re-derived = 28,857 (equal to the stored vectors), attempt 3 launched automatically |
| External kill on the final code | 29,101 vectors, RSS 586 MB | recovered automatically; attempt 4 at batch 2 |

Counts and timings: `ARCTIC_INDEX_CONTINUATION_RECEIPT.json`.

## Runs

- `tests/test_index_recovery.py`: 17 passed (63 s).
- Targeted set (recovery, profiles, 607+608 integration, frontend assembly, status, migrations, startup migration,
  health, NLI failure/provenance): see `FINAL_VALIDATION_AND_COMMIT_RECEIPT.md`.
- Not run: the full suite (resource limits; Codex's workload).
