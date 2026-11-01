# Callosum 0.6.0: blocker matrix

**Revised 2026-10-31** for the steering decisions recorded in `RELEASE_060_SCOPE_AND_READINESS.md` §5 (authorized
decisions A1–A10, outstanding gates G1–G4). Arctic S and DeBERTa are now *automatically preferred* models. MiniLM and
MiniLM2 remain for compatibility, and their retirement is deferred.

**Ordering.** Blockers are ranked by dependency order first, then by user impact.

**Criterion.** A blocker needs a specific user-visible failure or a data-safety risk. Everything else is in
`RELEASE_060_DEFERRED_BACKLOG.md`.

**Columns.**
- "Par." = can be parallelized safely with other workstreams.
- "Frozen?" = changes a frozen scientific contract.

## Summary
| # | Blocker | Kind | Depends on | Par. | Frozen? |
|---|---|---|---|---|---|
| B1 | Release base not integrated; dirty main tree. **Base adopted in the worktree (A1); merge needs separate authorization (G3)** | Data safety / release integrity | — | Release only | No |
| B2 | Model provisioning: no offline-safe, auto-retrying acquisition. **Infrastructure done in inc 615** (pinned byte manifests, restart-safe tracks, bounded backoff, cross-process ownership, offline loading once verified); Arctic auto-provisions in the packaged app; DeBERTa track built but its release gate is unarmed. **Status/UI surface still owed** (coordinator increment) | UX: requires manual recovery | B1 | Yes | No |
| B3 | No automatic detection or start of modernization. **Implemented in inc 617: lifespan coordinator, durable Pause/Resume, backend status contract; focused- and process-tested on disposable libraries, not release-validated; no UI yet (B9)** | UX: 0.6.0 undelivered | B1 | Yes (with B4) | No |
| B4 | Source-role v2 reclassification never runs for users. **Packaging done in inc 613 (`829f35f4`, byte-identical); currentness defect fixed in inc 614 (`01957c6d`, byte-identical, research master 2→0 pending); runs automatically from inc 617's coordinator (packaged app)** | Scientific: feature inert | — | Yes | No (rules unchanged) |
| B5 | Arctic preference with MiniLM fallback and import catch-up (**policy authorized, A2–A4**) | UX: Ask fails without it | B6 | No (with B6) | No |
| B6 | Atomic automatic Arctic activation (**authorized, A3**) | UX / honesty | B3 | No (with B5) | No |
| B7 | No disk-space guard. **Implemented in inc 616 (`0686a5f6`): focused-tested and process-tested with simulated resources; not release-validated** (real low-disk volume run, packaged-runtime checks under B10, and the settings-panel state still owed) | Data safety | B3 | Yes | No |
| B8 | DeBERTa automatic preference: effective-verifier resolution, provenance, gate (**policy authorized, A5; G1 CONDITIONAL accepted by product decision (not a PASS), G2 conditional runtime acceptance (2026-10-31); DeBERTa is the intended preferred verifier; automatic use awaits the four release gates in `model_provisioning/runner.py`: qualification recorded ✔, operation memory guard, verifier provenance/failure, packaged-runtime acceptance**) | Scientific provenance / latency contract | B2 | Yes | **Arming only** (see row) |
| B9 | First-run notice and modernization Status semantics | UX | B3, B6 | Yes | No |
| B10 | Packaging and CI coverage for models, the worker and the upgrade path | Release integrity | B2–B7 | After B2–B7 | No |

---

## B1: Release base not integrated
- **Current behavior.**
  - The 0.6.0 code (incs 607, 609–612) exists only on unpushed `integrate/inc607-608-ask` @ `af53b1d2`. `main` is at
    inc 608 `c9ada5ff`.
  - The main checkout holds uncommitted `app/backend/llm/providers.py`, plus untracked `.claude/docs/legacy_engine/`
    and `experiments/`, from separate work.
  - `tauri.conf.json` is `0.5.16`.
- **Required behavior.**
  - The release is cut from one reviewed, merged commit, from a clean tree.
  - `providers.py` is byte-identical to its frozen state unless Cliff re-freezes it, per the inc 557/575 precedent.
- **Consequence.** A release from the wrong tree could ship unreviewed synthesis-prompt changes. That would break the
  preregistered qualification freeze and the "Qwen2.5 synthesis preserved" scope.
- **Dependencies:** none.
- **Smallest workstream.**
  1. Develop in the isolated worktree on `integrate/inc607-608-ask` (authorized, A1). Do not touch the main checkout's
     uncommitted work.
  2. Before a release candidate: a reviewed, clean-tree integration into `main` (needs separate explicit
     authorization, G3), then the full `pytest -n auto -q` on the merged commit.
- **Acceptance tests.**
  - Full suite green on the merged commit.
  - `git diff 2f01feef..<release> -- app/backend/llm` is empty.
  - The release is built from a clean worktree (`git status --porcelain` is empty).
- **Par.:** not applicable. Development proceeds on the adopted base; only the release depends on the merge.
- **Frozen?** No.

## B2: Model provisioning
- **Current behavior.**
  - Arctic S loads in the worker (`index_worker.load_profile_model`, `index_worker.py:157`). DeBERTa loads in the
    main process (`routers/embedding_profiles.py:188`, `model_runtime.py:355`).
  - Both pass `local_files_only=False` by default (`SupervisorConfig.local_files_only=False`,
    `index_supervisor.py:55`), so Hugging Face downloads on first use.
  - With no network, the worker exits `EXIT_MODEL` (65), which is **never retried automatically**
    (`index_worker.py:35`, `_on_exit`). The row goes to `failed`, and only a manual Resume clears it.
  - DeBERTa selection returns 409.
  - No step reports download progress, size or offline state.
- **Required behavior.**
  - Model acquisition is a distinct, resumable modernization stage with honest states: downloading, waiting for
    network, verified.
  - It retries automatically when connectivity returns, with bounded backoff and no manual recovery.
  - It runs before any indexing.
  - It verifies the pinned revision. For DeBERTa it also verifies the contract (`verify_nli_checkpoint`).
  - After acquisition, workers run with `local_files_only=True`.
- **Consequence.**
  - An offline first launch, which local-first promises to support, leaves modernization in a terminal `failed` state.
  - DeBERTa cannot be enabled automatically.
  - No silent cloud dependency exists: the model download carries no library content.
- **Dependencies:** B1.
- **Smallest workstream.**
  1. A model-acquisition step in the modernization coordinator, which calls `huggingface_hub.snapshot_download` with
     the pinned revision.
  2. Classify network errors as `waiting_network` (retryable) and distinct from corrupt or contract failures (terminal,
     with a clear message).
  3. Pass `local_files_only=True` to the supervisor thereafter.
- **Acceptance tests.**
  - First launch with the network refused leads to `waiting_network`. Restoring the network leads to downloaded and
    verified, then indexing, with no user action.
  - A corrupt snapshot (truncated safetensors) leads to a terminal error with a message; MiniLM Ask is unaffected.
  - A wrong revision is refused.
  - The packaged-runtime loads of both checkpoints pass on all three OSes (B10).
- **Par.:** yes, against B4 and B7.
- **Frozen?** No. The pinned revisions are unchanged.

## B3: No automatic detection or start
- **Current behavior.**
  - Modernization never starts by itself.
  - `reconcile_index_builds` (`api/app.py:228`) resumes only rows whose intent is already `run`.
  - A fresh 0.6.0 upgrade has no `embedding_index_runs` row, so nothing happens.
- **Required behavior.**
  - At lifespan startup, compute the library's **modernization target** against its state:
    - Arctic S coverage: `profile_coverage`, `profiles.py:137`;
    - per-paper v2 classification: `papers_with_current_structure`, `chunk_structure_repo.py:232`;
    - model availability.
  - When behind, start resource-bounded background work automatically, unless the user paused it.
  - The detection is idempotent and cheap: two COUNT queries and one set query.
- **Consequence.** Without it, 0.6.0 is a no-op for every existing user (§3 of the Scope document).
- **Dependencies:** B1.
- **Smallest workstream.**
  1. A `modernization` coordinator, a small new module (for example `app/backend/modernization/coordinator.py`),
     invoked from the lifespan next to `reconcile_index_builds`.
  2. It writes intent `run` on the existing `embedding_index_runs` row for `arctic-s`, through
     `index_runs.upsert_requested`, and enqueues reclassification (B4).
  3. A user's explicit Pause persists as intent `pause`, and the coordinator never overrides it.
- **Acceptance tests.**
  - A 0.5.16-shaped database (0084, MiniLM-only, no `chunk_structure`) upgraded starts both stages within one
    startup tick.
  - A fully modernized database starts nothing.
  - A paused library stays paused across restarts.
  - Two app processes on one library start one worker (the existing OS lock).
- **Par.:** yes, with B4.
- **Frozen?** No.
- **Update 2026-10-31, inc 617.** The findings above are the original audit and are kept as found.
  - **Implemented.** `app/backend/modernization/` (coordinator + classifier) started from the lifespan after
    `reconcile_index_builds`; enabled in the packaged app (`CALLOSUM_APP_DATA_DIR`) or with `CALLOSUM_MODERNIZATION=1`,
    off with `CALLOSUM_DISABLE_MODERNIZATION=1`. Startup does no synchronous work; one OS lock
    (`<library>.modernization.lock`) elects one coordinator per library across processes.
  - **Deviation from step 2 of the workstream, on purpose.** The coordinator does **not** write intent `run` on
    the index row itself. It asks the existing supervisor to `start` only when vectors are missing, the Arctic
    checkpoint is **verified** (inc 615), the row is not active/failed, and the user has not paused or cancelled
    it. A fresh row written while the model is unverified would let the inc-610 worker download weights through
    Hugging Face, which inc 615 forbids.
  - **Durable intent.** `library_settings.modernization_intent` (`auto`/`paused`) and `modernization_resumed_at`.
    A Settings Pause or Cancel of the build is never restarted automatically unless modernization is resumed after it.
  - **Validation level.** Focused-tested: yes (`tests/test_modernization.py`, 25 passed, three consecutive runs).
    Process-tested: yes, with simulated resources (a real second process leads and is killed mid-paper; real index
    worker processes for shutdown/restart and the two-supervisor race). Release-validated: **no** (packaged app on a
    real upgraded library, B10).
  - **Race found and fixed.** A second app process could mistake a still-starting worker (no worker lock yet) for a
    dead one and launch a duplicate. The launching process now holds `<library>.index-<key>.launch.lock` from
    before launch until it observes the exit.
  - **Residual.** A build already queued with intent `run` (e.g. a manual Build in Settings) can still be launched
    by the supervisor while the checkpoint is unverified, downloading through Hugging Face: the pre-existing inc-610
    path, not changed here. Classification is reported by `GET /modernization` but is not mirrored into the Status
    popover (B9).

## B4: Source-role v2 never runs for users
**Progress.** Packaging completed in inc 613 (`829f35f4`). The derivation now lives in
`app/backend/pdf_processing/structure_backfill.py`, and its output is byte-identical to the inc-612 tool on three
library copies (`INCREMENT-613-NOTES.md`). **Open:** (a) the currentness defect below, and (b) running it
automatically (B3).

**Currentness defect (found in inc 613; pre-existing).** `papers_with_current_structure`
(`chunk_structure_repo.py:232`) requires a current row for *every* chunk, while the derivation covers article-role
chunks only. A paper with a preregistration attachment can therefore never become current. On the research master,
papers 25 and 61 are re-derived on every run. Fix: restrict the predicate to `ARTICLE_DOCUMENT_ROLES`. No derived row
changes. It must land before the coordinator, or progress never completes and the job loops.

- **Current behavior.**
  - `chunk_structure` is written only by `tools/backfill_chunk_structure.py::backfill()` (`:292`).
  - `tools/` is **not packaged**: `app/desktop-shell/packaging/stage_source.py:23` stages only `app/backend`,
    `alembic` and `integrations`.
  - Ingest writes no classification.
  - The installed desktop library has 0 rows; the research master has 23,875 stale v1 rows, which are ignored.
- **Required behavior.**
  - In the background, every live paper with chunks gets a current `chunk-structure-v2` classification: per paper,
    committed, resumable and idempotent. The backfill already guarantees this.
  - Newly ingested papers are classified afterwards.
  - It is cache-only: it reads existing `external_api_cache` (Crossref) and `reference_instances` and adds **no new
    egress**.
- **Consequence.** The 607/611 narrow-path bibliography demotion and in-region prose protection never act for users.
  Behavior equals 0.5.16 (fail-open, no regression), but the scoped "safe source-role versioning" is undelivered.
  In papers scope, bibliographies of anchored papers stay retrievable: the v1 held-out evaluation showed this before
  `ref_region` existed.
- **Dependencies:** B1.
- **Smallest workstream.**
  1. Move the pure-orchestration parts of `backfill()` into `app/backend`, for example
     `app/backend/pdf_processing/structure_backfill.py`. These are `load_reference_metadata`,
     `infer_reference_region`, `doi_owners` and the per-paper loop.
  2. Keep each file under 600 lines.
  3. Reduce `tools/backfill_chunk_structure.py` to a thin CLI over it.
  4. **Make no rule, threshold or derivation change.** `DERIVATION_VERSION` stays `chunk-structure-v2`.
  5. Run it in-process on a low-priority thread, or in the supervised worker. It is CPU-light and needs no model.
     Checkpoint by committing each paper.
- **Acceptance tests.**
  - Byte-identical `chunk_structure` output to the tool on the held-out `new_v2.sqlite` copy and on the inc-611
    replay copy. Compare fingerprints; this is not a new scientific evaluation.
  - A kill mid-run, then relaunch, leaves no partially classified paper. `replace_paper_structure` is a transaction
    per paper; assert it.
  - A new ingest gets classified within one coordinator tick.
  - No network call: run under a socket-refusing guard.
- **Par.:** yes, against B2 and B7.
- **Frozen?** **No**, provided the output is byte-identical. Any rule change would reopen the held-out gate.

## B5: An active non-baseline profile breaks Ask after any import
- **Current behavior.** All ingest paths embed MiniLM only:
- `attach_pdf_to_paper` → `embed_chunks` (`pdf_processing/ingest.py:219,291`);
- `ensure_papers_indexed` (`embeddings/admission.py`);
- Zotero, scan and capture.

  Once Arctic S is selected:
  - one imported paper makes `profile_coverage().complete` false;
  - every Ask then raises `IncompleteEmbeddingIndexError` (`query_ranking.py:45`, `profiles.py:192`) until someone
    manually rebuilds.
  - The supervisor does not notice new pending chunks after a run completes.
- **Required behavior.**
  - Ask never uses a partial index and never stops working because of an import.
  - Resolve the *effective* retrieval profile per Ask:
    - the target profile when its coverage is complete;
    - otherwise the complete MiniLM baseline, recorded in provenance and shown as "using MiniLM while N new passages
      are indexed".
  - The coordinator re-requests indexing whenever coverage drops (catch-up mode).
- **Consequence.** Without it, the common action of adding a paper disables Ask. A partial-index fallback would
  silently bias retrieval toward indexed papers, which the 608 design explicitly forbids.
- **Dependencies:** B6 (the same resolution point).
- **Smallest workstream.**
  1. Change `_retrieval_model` (`routers/summaries.py:439`) and its faceted counterpart to resolve the effective
     profile from coverage instead of raising, when the target was set by modernization.
  2. Provenance already records the profile that ran (inc 609).
  3. Coordinator tick: if the target is incomplete and not paused, set intent `run`.
- **Acceptance tests.**
  - With Arctic active, import one PDF. The next Ask succeeds on MiniLM, provenance says so, and the UI note is
    visible.
  - After catch-up the next Ask uses Arctic S.
  - `IncompleteEmbeddingIndexError` is still raised for an explicitly forced profile, so the 608 test is kept.
  - The AST isolation test still passes.
- **Par.:** no; build it together with B6.
- **Frozen?** No. The retrieval semantics per profile are unchanged; only the choice of complete index changes.

## B6: No atomic automatic activation
- **Current behavior.**
  - Activation is a manual radio (`POST /embedding-profiles/select`, `routers/embedding_profiles.py:121`), refused
    with 409 when incomplete.
  - DeBERTa selection is manual (`:180`).
- **Required behavior.**
  - When the target generation becomes complete (Arctic coverage complete and the model verified), activation
    happens in one write transaction:
    1. re-check `profile_coverage` inside the same `run_write`;
    2. write `library_settings.retrieval_embedding_profile` (`set_active_retrieval_profile`, `profiles.py:112`);
    3. NLI: no setting is written; the verifier is resolved per operation (B8, Architecture §5a).
  - An Ask that started before the flip finishes on the profile it resolved at start, which provenance records.
- **Consequence.** Without it, a fully built index is never used. With a non-atomic flip, a race with an import could
  activate an incomplete index; B5's per-Ask resolution covers this.
- **Dependencies:** B3.
- **Smallest workstream.**
  1. A coordinator `activate_if_complete()` that reuses the existing select validation.
  2. Mark the setting as `source=modernization` in `library_settings`: a second key, no migration.
  3. Hold to the rule: **a user's explicit manual choice is never overwritten** by a later modernization.
- **Acceptance tests.**
  - On completion, the setting flips exactly once.
  - Deleting one vector just before activation means no flip.
  - A user who manually selected MiniLM after an automatic flip stays on MiniLM.
- **Par.:** no; build it with B5.
- **Frozen?** No.

## B7: No disk-space guard
- **Current behavior.**
  - `resources.py` measures memory only. Nothing checks free disk.
  - A 4,000-paper library adds an estimated 1.6–3.7 GB, plus WAL growth.
  - SQLite returns `SQLITE_FULL`. The batch transaction rolls back, so committed data is safe, but the worker
    classification does not recognize the error. It counts as a failure without progress, trips the circuit breaker
    to `no_progress`, and shows a misleading "repeated unsuccessful attempts".
- **Required behavior.**
  - A preflight estimate before the stage starts, plus a runtime floor checked by the supervisor's monitor
    (`index_supervisor.py:330`).
  - Below the floor, the state is `waiting_disk`, a retryable state like `waiting_resources`, with an honest message
    naming the amount needed.
  - It resumes automatically once space is available.
  - It never deletes the MiniLM generation or user data to make room.
- **Consequence.** Filling the user's disk endangers other applications and the WAL/checkpoint of the library itself.
- **Dependencies:** B3.
- **Smallest workstream.**
  1. `shutil.disk_usage` on the database directory. This is stdlib, so no `psutil` is involved.
  2. Floor: `max(1 GB, 2 × estimated remaining bytes for the next N batches)`, plus the full estimate shown in the
     notice.
  3. Map `sqlite3.OperationalError: database or disk is full` to a new worker exit code. This is resource-class, so
     it never trips the breaker.
- **Acceptance tests.**
  - A simulated low disk (a fake `disk_usage`) leads to `waiting_disk`, with no breaker trip. Freeing space leads to
    a resume.
  - An injected `SQLITE_FULL` in the worker leads to the same outcome, and the database passes `PRAGMA
    integrity_check`.
  - The estimate is shown before the start.
- **Par.:** yes.
- **Frozen?** No.
- **Update 2026-10-31, inc 616 (`0686a5f6`).** The findings above are the original audit and are kept as found.
  Validation level, kept distinct on purpose:

  | Level | Status |
  |---|---|
  | Implemented | **Yes**: preflight before launch, check before every batch, running hard stop (256 MB), `SQLITE_FULL`/`ENOSPC` → exit 74, `waiting_disk` with a 60 s recheck, outside the breaker, Pause authoritative, restart-safe, numbers-only `disk` field (migration 0087) |
  | Focused-tested | **Yes**: `tests/test_index_disk_guard.py`, 14 passed, all three acceptance tests above included |
  | Process-tested | **Yes, simulated**: a real worker subprocess exits 74 on a fake low disk and on a genuine SQLite full (`PRAGMA max_page_count`), and recovers after an app restart. No real disk was filled |
  | Release-validated | **No**: needs a real low-space run on a small dedicated volume, packaged-runtime checks (B10), and the settings panel treating `waiting_disk` as active |

  **Floor correction.** Step 2's `max(1 GB, 2 × next N batches)` lets the reserve and the in-flight need overlap, so
  a large batch term eats into the reserve and WAL growth is uncovered. Implemented instead:
  `1 GB reserve + 64 MB WAL allowance + 2 × next 4 batches × 2,048 B` (1,662 B per passage measured on a synthetic
  library, rounded up). About 1.07 GB at the default batch of 8: only the next bounded step, never the whole build.
  **Shipping condition:** automatic model downloads and indexing must not ship without visible, truthful progress
  reporting (invariant #5); the Status popover already shows `waiting_disk`, the settings panel does not yet.
  **Still open after inc 617:** the Settings retrieval panel does not poll while a build is `waiting_disk`, so its
  numbers go stale until reopened (the Status popover polls).
  **Release-validation item (added after inc 616):** a full disk can also block the supervisor's own status writes
  (`index_runs.update_run`, `last_disk_check_json`) and, from inc 617, the coordinator's intent writes. Validate on a
  real nearly-full volume that the app keeps serving reads, that a failed status write is retried rather than lost
  silently, and that nothing reports progress it could not record.

## B8: DeBERTa automatic preference (revised 2026-10-31)
**Decision (authorized, A5).** DeBERTa is the automatically preferred NLI verifier once its gates are satisfied. Users
never need to select it. MiniLM2 is the compatibility verifier until then.

- **Current behavior.**
  - DeBERTa is opt-in through Settings and verified on selection (`routers/embedding_profiles.py:180-197`). It has
    no embedding fallback and fails closed (inc 609).
  - The effective verifier is whatever `library_settings.verification_nli_profile` says (`nli_profiles.active_nli_profile`, `:84`).
  - The thresholds (support ≥ 0.55, contradiction ≥ 0.55) are MiniLM2-calibrated and labelled as such.
  - There is no latency or memory receipt on the app path.
- **Required behavior.**
  1. **Resolve the effective verifier once, before each operation.** Use DeBERTa only when all of these hold:
     - the pinned snapshot is present;
     - `verify_nli_checkpoint` passed for that snapshot (label order, `deberta-v2` architecture, `DebertaV2*`
       tokenizer, revision);
     - the release gate constant `DEBERTA_AUTOMATIC_PREFERENCE_QUALIFIED` is true (G1 and G2);
     - a free-memory precheck passes, using `resources.py` against the measured DeBERTa peak plus a reserve.

     Otherwise use MiniLM2.
  2. **Never substitute after start.** A DeBERTa inference failure inside an operation fails that operation
     (`NLIInferenceError`, with no row written, as inc 609 does today). The *next* operation re-resolves.
  3. **Provenance.** Each run records:
     - `verification_nli` = the verifier that actually ran;
     - `preferred_verifier` = DeBERTa;
     - `verifier_fallback_reason`: `not_provisioned`, `not_verified`, `not_qualified`, `insufficient_memory` or
       `user_choice`.

     MiniLM2 verification is never labelled DeBERTa.
  4. **User choice.** An explicit user selection of either verifier is honored and never overwritten.
  5. **Thresholds, label contract and statuses stay unchanged.**
- **Consequence.**
  - Without (1) and (3), users would not get the improved verifier automatically, or worse, a fallback could be
    presented as DeBERTa verification.
  - Without the gate constant, DeBERTa would be activated beyond what the evidence supports (§6 of the Scope
    document).
- **Dependencies:** B2 (provisioning); G1 and G2 for arming automatic preference.
- **Smallest workstream.**
  1. `effective_nli_profile(conn, app)` in `nli_profiles.py`, called where `resolve_support_scorer` is called today
     (`routers/summaries.py`).
  2. Extend `verification_nli_provenance` with the two new fields.
  3. Add the gate constant, defaulting to false, pinned by a test.
  4. Gate DeBERTa's automatic download on the same constant (Scope §5.2).
- **Acceptance tests.**
  - Gate off: MiniLM2 is effective, with fallback reason `not_qualified`.
  - Gate on, model present and verified: DeBERTa is effective.
  - Gate on, model absent: MiniLM2 with `not_provisioned`, and Arctic and classification are unaffected.
  - Injected DeBERTa inference failure: the job errors, no row is written and no MiniLM2 result appears. The next
    job re-resolves.
  - A user's explicit MiniLM2 choice is kept after DeBERTa becomes available.
  - The provenance line shows the actual verifier and the reason.
- **Par.:** yes.
- **Frozen?** No contract text changes. **Arming** the gate changes which verifier produces every user's
  verified/contradicted/flagged statuses at MiniLM2-calibrated thresholds. That is release decision G1 (Scope §6),
  not something implementation may decide.

## B9: First-run notice and Status semantics
**Update 2026-10-31, inc 617.** `GET /modernization` now provides the backend contract this blocker's UI needs:
separate `classification`, `indexing` and `model` groups, each with `state`, `automatic_recovery` and `needs_user`,
stored-row counts, no combined percentage and no ETA. No banner, Status row or panel consumes it yet.
**Shipping condition (kept):** automatic downloads and modernization must not ship without accurate, visible,
nonblocking status and progress reporting.

- **Current behavior.**
  - The Status row is "Retrieval index build" (`routers/status.py:53`) and navigates to Settings.
  - Pause/Resume/Cancel exist only in `js/35i_retrieval_profiles.jsx`.
  - There is no 0.6.0 `whatsnew` entry.
  - There is no Status row for reclassification or model download.
- **Required behavior.**
  - A nonblocking, dismissible 0.6.0 banner, through the existing `whatsnew.json` mechanism with an `actionKind` that
    navigates to the modernization panel. It states:
    - what is happening;
    - the estimated time and disk;
    - that the library stays usable;
    - that it resumes automatically.
  - **One** Status row, "Library modernization (Local AI)", with an honest stage (downloading model / classifying
    sources / indexing N of M passages) and measured progress. The ETA comes from measured throughput only.
  - Pause/Resume are reachable by clicking the row, which navigates to Settings.
  - In-popover buttons are optional; see the deferred backlog.
  - No wizard.
- **Consequence.** Without it, a one-to-two-day background job is invisible or confusing. Invariant #5 requires a
  Status entry for AI work.
- **Dependencies:** B3, B6.
- **Smallest workstream.**
  1. Relabel and extend the `embedding_index_jobs` mirror to carry the stage.
  2. Add a `whatsnew` entry plus an action key, and a Help corpus update.
  3. Extend QA route 97.
- **Acceptance tests.**
  - The banner shows once per version and does not block.
  - Status shows one row through the whole process, across restarts.
  - Clicking the row lands on the panel with Pause and Resume.
  - No percentage appears when there is no measurement.
  - `check_whatsnew_coverage.py` and the QA surface map pass.
- **Par.:** yes.
- **Frozen?** No.

## B10: Packaging and CI coverage
- **Current behavior.**
  - `smoke_test_backend.py` does not load Arctic or DeBERTa.
  - The worker subprocess (`SubprocessLauncher`, `index_supervisor.py:95`) launches `sys.executable -m
    app.backend.embeddings.index_worker` with `cwd=_SOURCE_ROOT`. It has been exercised from a source checkout, but
    is unverified in the packaged layout on macOS and Linux.
  - Worker ownership at app exit relies on two mechanisms, neither tested in CI:
    - Windows: the Job Object (`backend.rs:625`, `limit_kill_on_job_close`);
    - Unix: process-group SIGTERM (`backend.rs:738`), plus the worker's parent watch (`index_worker.py:137`).
- **Required behavior.** Each of the three desktop CI workflows:
  - loads both pinned checkpoints in the packaged runtime;
  - spawns and stops one index worker;
  - runs one upgrade from a 0084 fixture database.
- **Consequence.** A packaging-only failure would surface for users as a terminal modernization error or an orphaned
  worker.
- **Dependencies:** B2–B7.
- **Smallest workstream:** extend `app/desktop-shell/packaging/smoke_test_backend.py` and the
  `desktop-shell-{windows,macos,linux}.yml` jobs. See the Test plan §4.
- **Acceptance tests:** listed in the Test plan §4.
- **Par.:** after B2–B7.
- **Frozen?** No.

---

## Implementation sequence (per the 2026-10-31 directive, §9)
Each step is a separate local increment with focused tests, disposable databases, interruption and idempotence
checks, and a local commit only after tests pass.

| Step | Content | Blockers | Status |
|---|---|---|---|
| 1 | Package the source-role v2 derivation, with output unchanged | B4 (packaging) | **Done: inc 613 `829f35f4`** |
| 2 | Model acquisition, verification and offline recovery (Arctic; DeBERTa behind its gate) | B2 | **Done: inc 615** |
| 2a | The currentness predicate restricted to article roles | B4 (defect) | **Done: inc 614 `01957c6d`** |
| 3 | Disk-space protection and resource-aware scheduling | B7 | **Implemented: inc 616 `0686a5f6`** (focused- and process-tested with simulated resources; release validation owed) |
| 4 | Automatic modernization coordinator (detect, auto-start, Pause intent) | B3 | **Implemented: inc 617** (focused- and process-tested with simulated resources; release validation and UI owed) |
| 5 | Arctic S preference, MiniLM fallback, import catch-up, atomic activation | B5, B6 | — |
| 6 | Automatic DeBERTa preference: per-operation memory precheck, effective verifier, provenance, fail-closed, verifier-keyed ETA, cautious `contradicted` wording. Gate constant exists (inc 615, unarmed) | B8 | — |
| 7 | Nonblocking first-launch notice and unified modernization Status | B9 | — |
| 8 | Restart recovery, activation, catch-up and 4,000-paper workload tests | B10 (part) | — |
| 9 | Bounded DeBERTa latency/memory acceptance (G2), plus the G1 re-score | G1, G2 | **Done: receipts `G1_DEBERTA_EXACT_THRESHOLD_RECEIPT.md` (CONDITIONAL), `G2_DEBERTA_CPU_RESOURCE_RECEIPT.md` (CONDITIONAL GO)** |
| 10 | Full regression, packaging and upgrade validation; then merge (G3) | B1, B10 | Needs authorization |

**Verdict: CONDITIONAL GO** to continue implementation of steps 2–8. **NO-GO for release** until B1–B10 are accepted
and G1–G4 are resolved, or until Cliff decides to ship with automatic DeBERTa preference disarmed.

## Pending dedicated reviews (recorded after inc 616; unchanged by inc 617)
Neither is resolved by refreshing a receipt, and neither was declined.
- **Demo coverage.** `tools/qa/check_demo_experience_coverage.py` fails on drift accumulated since the inc-576 review
  (about 29 routers). It needs a dedicated demo review; inc 617 adds `/modernization`, which the demo does not serve.
- **Website coverage.** `tools/qa/check_website_coverage.py` fails on 11 frontend/help files changed since the inc-603
  review. `www/shots/synthesis_current.png` predates the inc-609 provenance line and needs re-capture in that review.
- **Help text.** Help describes memory waits but not disk waits (inc 616) or background modernization (inc 617).
  Left for the UI increment, per the instruction not to alter Help inside the coordinator increment.
