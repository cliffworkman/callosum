# Increment 617 — Automatic background modernization coordinator

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), on `b3efb3c8`.
Local only: not pushed, not merged.

Authorized by the 2026-10-31 "Increment 617: Automatic Background Modernization Coordinator" instruction. It implements
release blocker **B3** and the automatic-run half of **B4**. Status: **implemented, focused-tested, process-tested with
simulated resources; not release-validated; no UI.**

## Implemented
- **`app/backend/modernization/classification.py`** (new): `SourceRoleClassifier`. It derives source-role v2
  classification for pending papers through the packaged inc-613 derivation (`derive_paper`), one paper per
  transaction. Pending = live papers with classified (article-role) chunks that are not current under the inc-614
  predicate. Each pass is bounded (`papers_per_pass`, 50), re-reads the user's intent between papers, and checks
  memory (`ResourcePolicy`) and disk (`disk_guard.check`) before writing. Stop reasons: `paused`, `shutdown`,
  `waiting_resources`, `waiting_disk`, `database_busy`. A paper that raises is rolled back and remembered for the
  session, keyed by a fingerprint of its chunks, so it is not retried every check. It is retried when its chunks
  change or the app restarts. Reference metadata is read once per pass from the local cache. No network access, no
  re-extraction.
- **`app/backend/modernization/coordinator.py`** (new): `ModernizationCoordinator`. It runs one background thread per
  app. Leadership is the OS lock `<library>.modernization.lock`; only the leader classifies or schedules, and other
  processes only report. Each check:
  1. reads a cheap aggregate signature (chunk count/max id/version length, classified population, `chunk_structure`
     rows, live papers). Expensive coverage queries run only when it changes, plus a 30-minute safety refresh;
  2. honors a durable Pause;
  3. asks the existing inc-610 supervisor to `start` the Arctic S build only when vectors are missing, the checkpoint
     is **verified** (inc 615), the run is not active or `failed`, and the user has not paused or cancelled it (unless
     modernization was resumed after that);
  4. runs one classification pass.

  Delay: 0 while papers remain, 60 s retry on a shortage, otherwise 60 s idle. A fully modernized library does no
  work and no busy loop.
- **`app/backend/modernization/__init__.py`** (new): gating and model status. Enabled in the packaged app
  (`CALLOSUM_APP_DATA_DIR`) or with `CALLOSUM_MODERNIZATION=1`; `CALLOSUM_DISABLE_MODERNIZATION=1` wins. Source
  checkouts and tests are off by default, like inc-615 provisioning. Model status reads the inc-615 track state only
  (no hashing, no network).
- **`app/backend/api/routers/modernization.py`** (new) + `api/app.py`: `start_modernization` after
  `start_model_provisioning` in the lifespan, `stop_modernization` first on shutdown (before provisioning and index
  workers stop). `GET /modernization`, `POST /modernization/pause`, `POST /modernization/resume`.
- **`app/backend/pdf_processing/structure_backfill.py`:** extracted `derive_paper(conn, paper_id, references)` from
  `backfill()`, so the CLI and the coordinator share one derivation. Same writes, same stats; the 16 derivation tests
  pass unchanged.
- **`app/backend/embeddings/index_lock.py` + `index_supervisor.py`: launch lease (race fix).** With two app processes
  on one library, a second supervisor could see a `running` row whose worker had not yet taken its OS lock (still
  importing). It would relabel the row interrupted and launch a second worker. The launching process now holds
  `<library>.index-<key>.launch.lock` from before the launch until it observes the exit. `_owned_elsewhere` (worker lock
  or lease held by another process) gates both `_maybe_launch` and `_recover_unowned`. The lease is released on exit,
  on shutdown and on a failed launch. A file-less database gets a no-op lock.
- **QA route 97** extended with the three endpoints and their assertions.

## Scheduling contract
| Situation | Classification | Arctic indexing |
|---|---|---|
| Disabled (source checkout / env) | none; `state: disabled` | none |
| Another process leads | none here; `owned_elsewhere` | none here |
| `intent: paused` | stops between papers; `paused`, `needs_user` | supervisor asked to pause an active build; never started |
| Model not verified | runs | `waiting_for_model`; no start, no load, no download |
| Model verified, vectors missing, no row | runs | `start` once; the supervisor owns everything after |
| Row active (queued/running/retrying/waiting_*) | runs | left to the supervisor's own recovery |
| Row `failed` | runs | not restarted (inc-610 circuit breaker); Resume only |
| Row `paused`/`cancelled` by the user | runs | not restarted, even after import or restart, unless resumed later |
| Import after completion | new papers pending | new chunks missing → one new `start` |
| Low memory / low disk / DB locked | `waiting_resources` / `waiting_disk` / `database_busy`, retry in 60 s | supervisor's inc-610/616 waits |
| One paper raises | that paper rolled back, `failed_papers`, others continue | unaffected |

**Pause / Resume / Cancel.**
- **Modernization Pause** is durable (`library_settings`). It stops both classification and automatic indexing, and
  pauses an active build that has intent `run`.
- **Modernization Resume** stamps `modernization_resumed_at`. A paused or cancelled build whose row predates the stamp
  becomes restartable, and papers that failed before it are retried.
- **Settings Pause and Cancel of the build** are honored: an explicit cancel is never restarted immediately or after a
  restart. Settings' manual Resume still works, including while modernization is paused (a manual action is
  respected).
- **Ordinary interruptions** (app closed, killed, a crashed worker) never need a manual resume. The supervisor's
  inc-610 recovery and the next leader's classification pick them up.

## Status contract (`GET /modernization`)
`enabled`, `disabled_reason`, `intent`, `coordinating_here`, `checked_at`, plus three separate groups:
- `classification`: `state`, `derivation_version`, `papers_with_classified_chunks`, `papers_current`,
  `papers_pending`, `papers_failed_this_session`, `papers_without_classified_chunks`, `automatic_recovery`,
  `needs_user`, `detail`.
- `indexing`: `profile`, `state`, eligible/indexed/missing chunks (from the run row while active, otherwise from
  `profile_coverage`), `run_state`, `run_intent`, `run_failure_kind`, `automatic_recovery`, `needs_user`.
- `model`: `track`, `state`, `verified`, `automatic_provisioning`.

There is no combined percentage, no ETA, and no path, passage or exception text.

## Not changed (scope limits)
- No automatic profile switching (B5/B6): MiniLM stays effective and no preference is written (tested).
- DeBERTa is not activated and its gates are not armed.
- No change to thresholds, source-role rules, retrieval ordering or Qwen2.5 synthesis. `app/backend/llm` is untouched.
- No Help, screenshot, banner, Status row or settings UI.

## Residuals (recorded in the blocker matrix)
- A build already queued with intent `run` (e.g. a manual Build) can still be launched while the model is unverified
  and download through Hugging Face. This is the pre-existing inc-610 path.
- Classification is not mirrored into the Status popover (B9). The Settings panel does not poll `waiting_disk`.
- A full disk can block status and intent writes: a new release-validation item.

## Key technical detail
- **Why the coordinator calls `start` instead of writing intent `run` (the matrix's step 2).** A `run` row written
  while the checkpoint is unverified would let the supervisor launch a worker with `local_files_only=False`, which
  downloads through Hugging Face, the duplicate download inc 615 exists to prevent. Scheduling only after
  verification keeps one acquisition path.
- **"Resumed after".** A paused or cancelled row is restartable by the coordinator only if
  `row.updated_at <= modernization_resumed_at`. No new counter: both values are stored truth.
- **Settled failures.** After a pass leaves only remembered failures, the coordinator records the signature. It does
  not re-run classification until the stored rows change, Resume clears it, or the 30-minute refresh fires. That
  removes the loop without hiding the failure (`failed_papers`, count, detail).

## Manual verification script
1. Copy a 0.5.16 library to a scratch folder. Start `CALLOSUM_MODERNIZATION=1 CALLOSUM_DB_URL=sqlite:///<copy>
   uvicorn app.backend.api.app:app --port 8890`.
2. `GET /modernization`: classification `running`, then `complete`; indexing `waiting_for_model` unless Arctic is
   provisioned, otherwise a build appears in Settings → Retrieval model and in Status.
3. `POST /modernization/pause`, restart the server: `intent` stays `paused`; nothing runs. `POST
   /modernization/resume`: both continue from stored rows.
4. Start a second server on the same copy (another port): it reports `coordinating_here: false`.
5. Library, Ask and Settings stay responsive throughout. Ask still uses MiniLM.

## Pytest
- `tests/test_modernization.py`: **25 passed**, three consecutive runs (about 50 s with `-n 4`).
- Regression: index recovery, disk guard, embedding profiles, model provisioning, structure currentness, source-role
  migration, chunk structure, migrations, frontend assembly: **197 passed** (after updating one test stand-in for the
  new `_Live.lease` field).
- Full suite: see the commit report (known pre-existing demo/website failures listed separately).
