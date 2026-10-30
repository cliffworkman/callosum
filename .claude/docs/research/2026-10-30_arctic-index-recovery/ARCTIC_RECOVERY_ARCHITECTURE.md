# Arctic S indexing — recovery architecture (inc 610)

Branch `integrate/inc607-608-ask`, on top of inc 609 (`b6b8bfe0`). Applies to every non-baseline retrieval profile;
Arctic S is the only one today.

## 1. Why recovery used to need an engineer (findings from the code and the machine)

| Question | Before inc 610 |
|---|---|
| Where did indexing run? | Inside the API server, as a FastAPI `BackgroundTasks` thread (`_run_index_job`). A native crash or OS kill of the model took the whole app down. |
| Input buffering | `pending_chunks_by_paper` loaded ids only, but each step called `embed_chunks` for a whole paper: every chunk's text, one `encode_texts` call, padded to the longest passage in the paper (hundreds of 512-token passages per forward pass for long papers). |
| Model lifetime | One registry runtime in the API process, kept until app exit. |
| Batching | Per paper, unbounded by count (sentence-transformers' internal batch 32, but the whole paper's texts and vectors held at once). |
| Transactions | One `run_write` per paper: correct atomicity, but a large unit. |
| Job state | In-memory `JobStore` only. A dead process left nothing behind; after restart there was no record a build had been running. |
| Interrupted vs paused vs failed | Not distinguishable: the job was `done` (cancelled flag) or `error`, and forgotten on restart. |
| Progress | Volatile per-paper callback counters. Coverage on the Settings panel was correctly derived from stored vectors, but the job knew nothing of it. |
| External termination | No detection. A killed worker thread's job would sit `running` forever, or vanish with the process. |

**What actually stopped the previous two attempts.** The Windows System log has no Resource-Exhaustion-Detector
(event 2004) entries and the Application log has no python crash (1000/1026) entries for the last 2–3 days. The
interruptions were therefore **not OS out-of-memory kills**: the standalone indexing script ran as a child of a
Claude Code background shell, and that shell tree was terminated externally by the harness's memory-pressure
handling. Cause class: external termination. The exact trigger is not evidenced beyond that. The DEV server's
earlier disappearance has the same signature (no OS event); its cause stays **unknown**. No evidence ties it to
indexing-process ownership, though in the old design an in-process index build would have died with it.

A further latent defect was found by the new real-subprocess kill test, not by inspection. Reading the sqlite-vec
virtual table requires the extension to be loaded on that connection. The first version of the new integrity check
did not load it, so **every resume on a library whose vector table already existed would have failed**. Fixed
before the real run (`profile_index._load_sqlite_vec`).

## 2. Design

```
API process (FastAPI)                                   worker process (python -m app.backend.embeddings.index_worker)
┌───────────────────────────────┐   Popen (no shell)   ┌──────────────────────────────────────────────────────────┐
│ routers/embedding_index.py    │ ───────────────────▶ │ OS lock <library>.index-<profile>.lock (held for life)    │
│  start/pause/resume/cancel    │                      │ parent watch (Windows handle wait / POSIX re-parent)      │
│  status ← durable row + vecs  │                      │ claim row by token → repair own unusable rows             │
│ IndexSupervisor (1 per app)   │   exit code          │ pending = chunk ids only                                  │
│  monitor thread, tick()       │ ◀─────────────────── │ loop: intent? memory? → read ≤batch texts → encode        │
│  resource probe + policy      │                      │       (inference_mode) → ONE txn: vectors + checkpoint    │
│  bounded retry / breaker      │                      │ heartbeat thread (15 s)                                   │
│  Status mirror (JobStore)     │                      └──────────────────────────────────────────────────────────┘
└──────────────┬────────────────┘
               │ short run_write units
        SQLite library: embeddings + callosum_vec_embeddings_384 + embedding_index_runs (migration 0086)
```

### Components

| File | Role |
|---|---|
| `app/backend/embeddings/resources.py` | Real OS memory measurement (Windows `GlobalMemoryStatusEx` commit limit and available commit; Linux `/proc/meminfo`; macOS `vm_stat`), worker working set, and a `ResourcePolicy` whose floors scale with the machine. |
| `app/backend/embeddings/index_lock.py` | One live worker per library file and profile, via an OS file lock released automatically on any exit. |
| `app/backend/persistence/schema_index_runs.py`, `alembic/versions/0086_embedding_index_runs.py` | Durable lifecycle row, one per profile per library. |
| `app/backend/embeddings/index_runs.py` | Row reads/writes. The worker's checkpoint is written inside the batch's own transaction. Counts are re-derived from vectors. |
| `app/backend/embeddings/profile_index.py` | Bounded-batch building blocks: ids-only planning, `index_chunk_batch`, `vector_integrity`, `repair_partial_vectors`. |
| `app/backend/embeddings/index_worker.py` | The worker process: exit-code contract, failure classification, parent watch, lock. |
| `app/backend/embeddings/index_supervisor.py` | Launch, watch, classify exits, bounded recovery, startup and live reconciliation, shutdown. |
| `app/backend/api/routers/embedding_index.py` | Endpoints, user-facing messages, Status mirror, lifespan hooks. |
| `app/frontend/js/35i_retrieval_profiles.jsx` | Settings panel: state, message, attempts, Pause/Resume/Cancel, technical details. |
| `tools/run_profile_index.py` | Developer driver over the same supervisor (no separate indexing logic). |

### Lifecycle states (`embedding_index_runs.state`)

`queued → running → completed`, with `pausing → paused`, `pausing → cancelled`, `waiting_resources`, `retrying`,
`interrupted` and `failed`. `intent` (`run` / `pause` / `cancel`) records the user's wish separately from what
happened, so a pause survives an app restart and a crash is never mistaken for a pause.

### Worker exit-code contract

| Code | Meaning | Supervisor response |
|---|---|---|
| 0 | No pending work left | `completed` only if coverage re-derived from vectors is complete; otherwise retry (new passages appeared) |
| 3 | Pause/cancel intent honoured between batches | `paused` / `cancelled` |
| 65 | Model unavailable, corrupt, or contract mismatch | `failed`, never retried automatically |
| 69 | Database busy after `run_write` retries | retry with backoff |
| 70 | Orphaned (its app died) | seen only by a later reconciliation |
| 71 | Another worker holds the lock / not the row owner | `failed` (`not_owner`) |
| 75 | Free memory under the pause floor before a batch, or an allocation failure | batch halved; `waiting_resources`; relaunch only when start headroom returns |
| anything else | Killed, crashed, stalled, unexpected | `retrying`, cause unknown unless evidenced; batch halved (a silent kill is often the OS reclaiming memory) |

### Bounded recovery

- `failures_without_progress` counts exits with no new committed vector. Any progress resets it, and the next attempt
  starts after 5 s.
- Backoff without progress is 30 s, then 120 s, then 600 s. At 3 failures the run goes to `failed` (circuit breaker):
  `insufficient_memory` if it was already at one passage per batch, otherwise `no_progress`. Only the user's Resume
  (`start`) clears it.
- Waiting for memory launches nothing, so it consumes no budget and cannot thrash.
- Stall detection: no heartbeat for 600 s → terminate own worker → retry.
- Pause/cancel: the worker sees the intent before its next batch; if it hasn't left after 120 s, the supervisor
  terminates it (committed work is unaffected).

### Reconciliation (the case cleanup code cannot cover)

`reconcile_on_startup()` runs in the FastAPI lifespan before serving. `tick()` also applies the same per-row
recovery to any `running`/`pausing` row this supervisor holds no worker for. For each such row:

1. Unknown profile, or a changed pinned model version → `failed` with an explanation (never resumed onto a
   different recipe).
2. Lock still held → a live worker of another Callosum process; leave it, never start a second.
3. Otherwise the worker is gone. Re-derive `eligible` and `indexed` from the `embeddings` table, clear the
   worker identity, and record `interrupted_unknown_cause` (or the worker's own reported kind).
4. `intent=run` → `retrying` now (the default policy resumes automatically, because the user started the build);
   `pause`/`cancel` stay paused/cancelled.
5. The next worker first runs `repair_partial_vectors`, which removes this profile's rows that have no stored
   vector (or no chunk), so they are re-embedded rather than counted.

App exit (`shutdown`) terminates the owned worker and records `interrupted` / `app_closed`. No background service
outlives the app.

## 3. Scientific comparability (unchanged recipe)

The worker loads the profile through the same registry call and wrapper as before (`load_profile_model`, the same
arguments as `resolve_profile_embedding_model`). Revision, CLS pooling, max sequence 512, `whitespace-v1`
normalization, the empty document prefix, the query prefix, `normalize_embeddings=True`, 384 dimensions and float32
storage are all unchanged; the contract check still runs on the first encode. Only the number of passages per
forward pass changes. Measured on the real checkpoint (see `LOW_MEMORY_RESOURCE_MEASUREMENTS.md`): batch sizes 1,
8 and 32 differ from the stored vectors by at most 1.06×10⁻⁷ per component (cosine ≥ 0.99999988). That is
float-summation-order noise, not a semantic change. The thread count (4) affects summation order the same way.

## 4. Packaging

The worker is the backend's own interpreter (`sys.executable`) running a module from the source root with
`cwd` set to it. That is the same way the packaged app launches uvicorn (`backend.rs`: `python -m uvicorn`,
`current_dir(source_root)`). It uses no new dependency: `psutil` was removed from the design after it was found
in the dev environment but **not** in `uv.lock`, the lock the immutable packaged runtime is built from. Adding it
would change the runtime id and need a new runtime release. Windows gets `CREATE_NO_WINDOW |
BELOW_NORMAL_PRIORITY_CLASS`; POSIX gets `nice 5`. Not yet run in a packaged build (see limitations).

## 5. Limitations

- Not exercised in a packaged desktop build, on macOS, or on Linux. The macOS memory probe (`vm_stat`) and POSIX
  parent watch are tested only by construction and parser checks.
- One build per library at a time (the `JobStore` mirror allows one active job); with a single non-baseline profile
  this is not limiting.
- Auto-resume on launch is the policy for a build the user started; there is no Settings toggle to disable it. The
  user's Pause is durable instead.
- Batch size only shrinks within a build (stability over peak throughput); a manual Resume does not restore it.
- `app/backend/api/app.py` is at exactly 600 lines (the cap).
