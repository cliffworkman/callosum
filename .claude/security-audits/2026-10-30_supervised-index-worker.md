# Security audit — supervised, recovering embedding-profile index builds (inc 610)

**Date:** 2026-10-30 · **Branch:** `integrate/inc607-608-ask` (local, unpushed) · **Triggers:** three new endpoints
(`POST /embedding-profiles/{key}/index/{pause,resume,cancel}`) and changed responses (`index_run` on profiles, `run`
on index jobs); a new child process (the index worker); a new file-write path (the per-library lock file and a
temporary stderr log); a new table (migration 0086); a net-new feature over 3+ files. No new external fetch, no new
third-party dependency (psutil was deliberately *removed* from the design, because the packaged runtime's lock does
not ship it), and no auth change.

## Threat review

- **Process creation / command injection.** The worker argv is `[sys.executable, "-m", <fixed module>, ...]` with
  no shell. Every option is server-side: `--db-url` comes from the app's own configuration (`app.state.db_url`),
  never from a request; `--profile` is a key that `get_profile` has already validated against the fixed `PROFILES`
  map (unknown → 404, baseline → 400); the token is `uuid4().hex`; batch size, thread count and parent PID are
  ints. `cwd` is the fixed source root. The module name is a constructor constant (production never takes it from
  input; only tests pass the fake worker module).
- **Killing processes.** The supervisor terminates only a `Popen` handle it created. Reconciliation never kills: it
  infers liveness from the OS lock and leaves a held lock alone. Tests and QA confirm a bystander process survives
  worker kills and app shutdown. The developer tool's `--kill-after-chunks` kills only its own supervised worker.
- **Ownership / duplicate workers.** An exclusive OS lock on `<library>.index-<profile>.lock` (msvcrt / fcntl) is
  held for the worker's life and released by the OS on any exit, including a hard kill. A second worker for the
  same library and profile exits with `EXIT_NOT_OWNER` (tested with a real second process). The durable row also
  checks a per-launch token before accepting a checkpoint, so a superseded worker cannot overwrite the row.
- **Orphans.** The worker exits if its parent dies. On Windows it waits on a process handle, which pins the
  parent's identity against PID reuse; on POSIX it detects re-parenting. Verified for real: killing the driver
  process ended its worker within seconds, with no cleanup code run.
- **File paths.** The lock path is derived from the configured SQLite path plus a validated profile key and lives
  beside the library. The stderr log is created with `mkstemp` in the temp directory, read for a ≤1,500-byte tail on
  exit, and deleted.
- **Output encoding / disclosure.** User-facing `message` and `failure_detail` are fixed strings chosen by code.
  `diagnostic` (shown only under "Technical details") is bounded to 1,500 characters and carries the exit code,
  exception class/message, and stderr tail, with the user's home directory replaced by `~`. It never carries
  passage text: the worker logs none, and errors reference ids and model names only. It may carry SQL statement text
  with model names (seen in testing), which is not library content. React renders it as text.
- **Resource exhaustion (the point of the change).** One worker per library/profile, running at below-normal
  priority (Windows) or `nice 5` (POSIX), with a bounded thread count. Memory floors scale with the machine; the
  worker leaves before a batch when free memory is under the pause floor, and the supervisor terminates its own
  worker under the stop floor. A circuit breaker stops after 3 attempts without new vectors. A model that fails to
  load is never retried automatically. Waiting for memory launches nothing, so it cannot loop.
- **Data integrity.** Vectors, identity rows and the progress checkpoint commit in one short transaction per batch.
  Repair deletes only this profile's identity rows that have no usable vector (or whose chunk is gone): the
  predicate is pinned to the profile's `model_name` + `model_version`, and the MiniLM rows were fingerprinted
  byte-identical before and after the real run. Completion is always re-derived from the `embeddings` table.
- **Egress.** Unchanged. The worker loads the same pinned checkpoint the in-process path used. A first use may
  still fetch pinned weights (as before); the controlled run used `local_files_only` plus `HF_HUB_OFFLINE=1`.
- **SQL.** New queries use bound parameters. The only interpolated identifier is the sqlite-vec table name, built
  from an int dimension, the same pattern `vector_store.py` already uses.
- **Remote access.** The new endpoints sit behind the existing `AccessControlMiddleware` like every other route.
  They are POST, so `CALLOSUM_READ_ONLY=1` rejects them.

## Negative-path checks (concrete results)

| Check | Result |
|---|---|
| Unknown profile key on pause/resume/cancel | 404 (`_buildable`) |
| Baseline profile | 400 |
| Pause/cancel with no build ever started | 409 |
| Worker killed externally (TerminateProcess / SIGKILL) | detected; `retrying`, `interrupted_unknown_cause`; committed vectors kept; bystander process alive |
| Real Arctic worker killed externally at 25,525 vectors | detected; resumed automatically at batch 4; no duplicate rows |
| Driver (app) killed, no cleanup | worker exited via parent watch; row left `running`; next start reconciled it to `retrying` from stored vectors |
| Second worker on the same library/profile | exits `EXIT_NOT_OWNER` (71) |
| Model missing (`OSError` on first batch) | `failed`, `model_unavailable`, no automatic retry; raw text only in `diagnostic` |
| Persistent `MemoryError` | batch 2→1, then `failed` / `insufficient_memory` after 3 attempts; manual Resume completes |
| Low memory before start | `waiting_resources`, attempts unchanged, no launch until headroom returns |
| Identity row without vector | repaired (deleted and re-embedded); MiniLM rows byte-identical |
| psutil import in production code | none (test-enforced); not in `uv.lock` |
| Ratcheted bandit gate (`tools/run_bandit.py`) | passes; new findings are each annotated `# nosec <rule>` with the reason (fixed-argv subprocess B404/B603, `worker_token: None` false-positive B105, int-derived vec table name B608) |

**Security Audit: PASS**
