# Background modernization: failure and recovery contract

**Revised 2026-10-31:** F17–F20 cover the automatic DeBERTa and Arctic preference (Scope §5).

This document states how modernization behaves on every failure path. Its premise: **the user never performs manual
recovery after a restart, an Ask never runs on a partial index, and no committed data is lost.**

**Status:** specification only. Rows marked *existing* are implemented in inc 610; the rest are proposals (B2–B9).

## 1. Invariants
1. **I1, durable truth.** Progress is recomputed from stored rows:
   - vectors: `profile_coverage`;
   - v2-current papers: `papers_with_current_structure`.

   Counters and states are caches. *Existing* for Arctic; a test lies to the counter (999) and reconciliation
   corrects it.
2. **I2, atomic units.**
   - One Arctic batch commits its vectors, identity rows and checkpoint in one transaction (*existing*,
     `profile_index.index_chunk_batch`).
   - One paper's classification is replaced in one transaction (`replace_paper_structure`).
   - Activation is one transaction.
   - Partial units roll back through SQLite.
3. **I3, single ownership.** At most one Arctic worker per library: an OS file lock, released by the OS on any exit.
   PID reuse cannot fake liveness (*existing*, `index_lock.py`). Classification takes a sibling lock.
4. **I4, no partial index served.** Per Architecture §5.
5. **I5, additive only.** Modernization never deletes or rewrites chunks, annotations, citation mappings, source
   components, papers or MiniLM vectors. The only rows it removes:
   - its own orphaned or partial vectors (`repair_partial_vectors`, *existing*);
   - superseded derived `chunk_structure` rows.
6. **I6, the user's intent wins.**
   - A Pause persists across restarts.
   - A manual profile choice is never overridden.
   - Only Cancel or Pause stops automatic resumption.
7. **I7, honest state.** Every state below has a user-facing sentence. A percentage appears only when measured. A
   technical diagnostic is collapsed, bounded and scrubbed of paths and secrets (*existing*, `index_runs._bounded`,
   the worker `_scrub`).

## 2. State machine (one row per stage)
```
model stage:      absent ─► downloading ─► verified
                       └─► waiting_network ─(net back)─► downloading
                       └─► model_invalid (terminal; message; MiniLM unaffected)
classification:   pending ─► running ─► complete   (re-enters pending when a paper becomes stale/new)
arctic index:     inc 610 states: queued, running, pausing, paused, retrying, waiting_resources,
                  interrupted, failed(no_progress|insufficient_memory|model_unavailable|unknown_profile), complete
                  + NEW waiting_disk
activation:       not_ready ─► active(source=modernization) ;  user choice ─► active(source=user)
```

## 3. Failure → behavior → recovery
| # | Failure | Detected by | Committed data | Ask meanwhile | Recovery (automatic unless noted) | Status/notice text (gist) |
|---|---|---|---|---|---|---|
| F1 | Normal close mid-batch | Lifespan shutdown → `shutdown_index_builds` kills the owned worker (*existing*, `api/app.py:232`) | All batches but the current one; the current one rolls back | n/a | On next launch, `reconcile_on_startup` re-derives coverage and resumes intent `run` (*existing*) | "Continuing library update: N of M passages" |
| F2 | Forced termination (Task Manager, SIGKILL, power loss) of the app | Tauri Job Object (Windows, `backend.rs:625`) or process-group SIGTERM (Unix, `backend.rs:738`) takes the worker down; the worker's parent watch (`index_worker.py:137`) exits within seconds otherwise | As F1; SQLite WAL recovery on next open | n/a | As F1. A stale `running` row is recovered because the OS lock is free (*existing*, `_recover_unowned`) | Same as F1 |
| F3 | Worker killed alone | `_watch`/`poll` exit code | As F1 | MiniLM (I4) | Classified as an unexplained kill: batch halved, backoff 5 s if it made progress, else 30/120/600 s (*existing*) | "Interrupted; will retry automatically" |
| F4 | Worker hangs | Heartbeat stall 600 s (*existing*) | Up to the last batch | MiniLM | Terminate, then as F3 | Same |
| F5 | Memory pressure | `resources.py` floors (*existing*) | Up to the last batch | MiniLM | `waiting_resources`, then resume; batch halving; at batch 1 with 3 failures, `failed: insufficient_memory` | "Paused: not enough free memory…" |
| F6 | Disk low or full | **New** preflight plus monitor floor; `SQLITE_FULL` → new resource exit code | Up to the last batch; `PRAGMA integrity_check` clean | MiniLM | `waiting_disk`, resumes when the floor clears; **never trips the breaker** | "Paused: needs about X GB free on <drive>" |
| F7 | No network for models | **New** model stage | n/a | MiniLM + MiniLM2 | `waiting_network`, auto-retry; classification still runs | "Waiting for an internet connection to download the retrieval model (≈130 MB)…" |
| F8 | Corrupt, missing or mismatched model | Verify revision/contract; worker exit 65 (*existing*) | n/a | MiniLM + MiniLM2 | **Terminal**: `model_invalid`. One "Try again" action re-downloads. Not looped: a deterministic failure is never retried automatically (*existing* policy) | "The retrieval model could not be verified; your library is unaffected" |
| F9 | DB busy or locked | Worker exit 69; `run_write` retry (*existing*) | n/a | Unaffected | Retry with backoff | (no notice) |
| F10 | Repeated failures without progress | Breaker after 3 (*existing*) | Preserved | MiniLM | `failed: no_progress`. **This is the only state needing a click** (Resume). It cannot be caused by F1/F2/F5/F6/F7 | "Stopped after repeated unsuccessful attempts. Your index is preserved. Retry" |
| F11 | Classification crashes on one paper | **New**: per-paper `try` in the stage loop | Other papers committed; the failing paper keeps its prior rows (stale → ignored) | Unaffected (fail-open) | Record a bounded per-paper failure count in memory. Skip the paper after 2 attempts per session; retry next session | Counted ("1 source could not be classified"), never blocking |
| F12 | Paper deleted during a build | Cascades and `repair_partial_vectors` (*existing*) | Orphan vectors removed | Unaffected | n/a | — |
| F13 | Paper imported during or after a build | Coverage drops | — | MiniLM until catch-up (B5) | `tick()` re-requests intent `run`; classification picks up new papers | "Indexing 1 new paper" |
| F14 | Two app processes on one library | OS lock (*existing*) | — | Both MiniLM, or both Arctic when complete | The second process never launches a worker | — |
| F15 | Downgrade to 0.5.16 after a partial 0.6.0 run | — | Arctic rows and v2 rows are ignored by 0.5.16. Migrations 0085/0086 are additive, so 0.5.16 starts with the head mismatch policy | 0.5.16 behavior | Re-upgrading resumes from storage | (Verify the alembic-head-ahead behavior in the test plan) |
| F16 | Unknown profile key from a newer build | `_recover_unowned` → `failed: unknown_profile` (*existing*) | Preserved | Baseline (`active_retrieval_profile` falls back) | n/a | — |
| F17 | DeBERTa download fails, has no network, or its gate is off | DeBERTa model track (*new*) | n/a | Arctic or MiniLM retrieval unaffected; **MiniLM2 verification**, recorded with `verifier_fallback_reason` | `waiting_network` auto-retry (only when armed); never blocks other stages | "Improved verification will be used once its model is ready" (only when armed) |
| F18 | DeBERTa inference fails during an operation | `NLIInferenceError` (*existing*, inc 609) | No synthesis row written | That operation errors; **no MiniLM2 substitution** | The next operation re-resolves the verifier | "Citation verification failed, so no synthesis was saved" (existing) |
| F19 | Not enough memory for DeBERTa at operation start | `resources.py` precheck (*new*) | n/a | MiniLM2 for this operation, recorded as `insufficient_memory` | Re-checked per operation | Provenance line names MiniLM2 and the reason |
| F20 | Arctic model unavailable or invalid | Model stage, F7/F8 | n/a | MiniLM retrieval, `fallback_reason=model_unavailable` | As F7/F8 | As F7/F8 |

### Inc 622: F8 implemented
The inc-621 F8 deviation below is closed. Implemented behaviour, which refines the row above:
- "Try again" re-downloads only the files that failed, then re-verifies the whole pinned manifest and static contract.
  Files that pass keep their bytes. A contract-only failure fetches nothing and returns to `invalid`.
- It appears for `invalid`, and for a retryable state on a track with no automatic runner. It never appears for a normal
  download or wait on a track that has its runner.
- A failed retry stays visible and actionable, and is never repeated without another click. Network and resource waits
  inside a retry recover by themselves, keeping the retry's force.
- The retry is independent of Pause: it neither needs Resume nor lifts Pause. Scheduling after a repair applies all
  existing conditions, so Pause, Cancel and explicit retrieval or verifier choices stand.
- A repaired DeBERTa stays behind its release gates.
- Tested with mocked network only. A real transfer and `force_download` over a corrupt blob are release-validation items.

### Inc 621 evidence notes
- **F6, status writes refused too** (simulated: every write raises `database or disk is full`; no disk filled). Browsing
  and both status reads stayed 200, both monitor threads survived, integrity stayed ok, and work finished 4.6 s after
  writes returned. Two honest gaps: the row keeps saying "Building" with a frozen count, because the state saying
  otherwise cannot be written, and `POST /modernization/pause` returns 500, so that Pause is not recorded. Normally the
  disk guard stops work well before this point. Release-validation obligation; the display is a deferred improvement.
- **Vector missing with no chunk change** (outside normal paths: a restored or damaged index). Ask fails safe to MiniLM
  (`test_completed_run_row_does_not_prove_coverage`) and `GET /embedding-profiles` says so at once, but the modernization
  summary stays "complete" until reconciliation (at most 30 minutes; repaired 1.1 s once due), and its retrieval line
  showed Arctic S throughout the 17.7 s observed. Deferred improvement.
- **F8 deviation (closed by inc 622; kept as the record of inc 621).** The row above promises one "Try again" action. None exists: the panel says "There is no in-app repair
  yet; please report this." Safe (MiniLM continues, nothing loops, shown in Status), but that library stays on MiniLM.
  Product decision owed before release: build the action or amend this contract.
- **F14** is pinned by in-process and worker-process lock tests; not yet run as two real apps with a browser attached.

## 4. Interrupted-transaction recovery
- SQLite WAL guarantees that an uncommitted batch or paper is absent after a crash.
- **On startup, before resuming, the coordinator runs:**
  1. `vector_integrity` (*existing*, `profile_index.py:91`), then `repair_partial_vectors` (`:153`). These remove
     this profile's identity rows without a stored vector, and vectors without an identity row or chunk.
  2. A classification consistency check: a paper is v2-current only if every chunk has a v2 row matching
     `raw_sha`/`chunk_version`. That check is `papers_with_current_structure`. A torn paper is impossible under I2
     but is still treated as pending.
- No other repair runs. In particular, **nothing touches MiniLM rows.**

## 5. What the user must never have to do
- Recover after a normal close, a crash, a forced kill, a reboot, an offline period or low disk.
- Re-select a profile after a completed build.
- Rebuild after importing papers.
- Open a wizard.

The only clicks that can exist:
- **Pause/Resume:** optional, the user's own intent.
- **Retry** after F8 or F10, which are genuine deterministic failures where looping would waste resources.

## 6. Responsiveness contract
- The worker runs out of process at reduced priority.
- Classification runs on one background thread with short transactions.
- The coordinator tick is O(two COUNT queries plus one set query).
- **No modernization work runs on a request thread.** Ask, import, Library browsing and the PDF viewer must stay
  within their existing latency envelopes. This is measured in the test plan §3.6 as a receipt, not a new benchmark
  study.
