# Callosum 0.6.0: test and packaging plan

> *Publication note (2026-10-31, inc 616 documentation commit): absolute local paths were rewritten to `%USERPROFILE%` form and a session-scratchpad path was replaced by a description before committing. No finding, number or status was changed.*

**Status:** specification. **Revised 2026-10-31** for automatic Arctic and DeBERTa preference (Scope §5).

**Already done:** inc 613's T3-equivalent identity check, which compared the inc-612 tool with the packaged module
on disposable copies of three libraries: byte-identical (`INCREMENT-613-NOTES.md`).

**Rules**
- Correctness tests are separate from performance receipts (LATENCY.md rule 7).
- No new scientific adjudication: there is no new scientific behavior, because classifier rules, retrieval semantics
  and NLI thresholds are unchanged. Scientific smoke tests use already-accepted fixtures and compare
  byte-identically.
- Any receipt that runs real models over a real library needs Cliff's per-experiment authorization (the experiment
  gate) before it runs.

## 1. Fixtures (all existing or derivable read-only)
| Fixture | Source | Use |
|---|---|---|
| F-0084 | A *copy* of the desktop snapshot `%USERPROFILE%\callosum-data\snapshots\desktop-20261029T193838Z\callosum.sqlite` (151 papers, 0084, MiniLM-only, 0 `chunk_structure`). Copied to `.local/`; **never the live DB** | Realistic upgrade path |
| F-v1 | A copy of the research master (v1 `chunk_structure`, mixed chunk versions, annotations, summaries) | Stale-v1 → v2 transition; annotation/citation preservation |
| F-heldout | `%USERPROFILE%\callosum-data\experiments\source-role-heldout-20261030\v2\new_v2.sqlite` (frozen v2 classification) | Byte-identical classifier output after the move (B4) |
| F-replay | The inc-611 replay copy (151/151 current at v2; 236 rescued) | Second identity check |
| F-synthetic | Generated in tests (as `tests/test_sql_batch.py` and the inc-610 tests do) | Unit, kill and disk injection |
| F-4000 | A synthetic library of 4,000 papers × ≈300 short chunks with random text, built in a test temp directory, plus a **fake** encoder for correctness. The real encoder is used only in the authorized receipt in §3.7 | Scale and responsiveness |

## 2. Unit and integration tests (pytest, CI)
| ID | Test | Blocker | Asserts |
|---|---|---|---|
| T1 | `test_detect_targets_on_0084_shape` | B3 | Detection reports models absent, all papers unclassified and all chunks Arctic-pending; a modern DB reports nothing |
| T2 | `test_coordinator_autostarts_and_respects_pause` | B3 | Startup sets intent `run`; a persisted Pause survives restart; no second worker under a held lock |
| T3 | Packaged derivation identity | B4 | **Done (inc 613):** three-library byte identity, plus `tests/test_structure_backfill_packaging.py` (staged directory, no imports outside the package, CLI wraps the same functions) |
| T3b | `test_currentness_ignores_non_article_chunks` | B4 defect | A paper with a preregistration attachment becomes current after one derivation; a second run re-derives 0 papers; derived rows are unchanged |
| T4 | `test_structure_backfill_no_network` | B4 | Runs under a socket-refusing guard |
| T5 | `test_classification_kill_leaves_no_torn_paper` | B4 | Abort inside a paper's transaction: the paper is wholly previous or wholly v2 |
| T6 | `test_model_stage_waits_for_network_then_proceeds` | B2 | Refused network → `waiting_network`; restored → `verified`; no user action |
| T7 | `test_model_stage_invalid_is_terminal_and_isolated` | B2 | Truncated safetensors or wrong revision → `model_invalid`; MiniLM Ask passes |
| T8 | `test_worker_runs_local_files_only_after_verify` | B2 | Worker argv contains `--local-files-only` (`index_supervisor.py:121`) |
| T9 | `test_effective_profile_falls_back_while_incomplete` | B5 | Arctic target incomplete → Ask succeeds on MiniLM; provenance `fallback_reason`; no Arctic vector is read |
| T10 | `test_import_after_activation_never_breaks_ask` | B5 | Activate, import one paper: Ask succeeds (MiniLM), catch-up runs, next Ask uses Arctic |
| T11 | `test_user_choice_keeps_608_fail_closed` | B5 | `source=user` with an incomplete Arctic index still raises `IncompleteEmbeddingIndexError` (the existing 608 test remains) |
| T12 | `test_activation_atomic_and_rechecked` | B6 | Remove one vector just before activation: no flip; complete: exactly one flip; a user's manual MiniLM is never overridden |
| T13 | `test_disk_floor_waits_without_breaker` | B7 | Fake `disk_usage` below the floor → `waiting_disk`, failures-without-progress unchanged, resume on space |
| T14 | `test_sqlite_full_maps_to_resource_exit` | B7 | Injected `database or disk is full` → resource exit; `integrity_check` ok |
| T15 | `test_modernization_is_additive` | I5 | Fingerprints of `chunks`, `annotations`, `citation_mappings`, `source_components`, `source_representations`, `papers` and MiniLM `embeddings` are unchanged after full modernization of F-v1 and F-0084 copies |
| T16 | `test_progress_from_storage_and_no_fake_eta` | B9 | The Status mirror shows N of M from coverage; ETA is absent until a batch has completed |
| T17 | `test_status_single_row_across_stages_and_restart` | B9, invariant #5 | One `embedding_index_jobs` row; navigation payload has no paths or URLs |
| T18 | Existing suites unchanged | — | `test_embedding_profiles.py` (AST isolation ≥6 call sites), inc-610 failure/retry tests, `test_reference_exclusion.py`, `test_source_role_repair.py`, `test_truncated_generation.py`, `test_sql_batch.py`, the NLI contract tests |
| T19 | `check_whatsnew_coverage.py`, `tools/qa/build_surface_map.py check`, `check_line_budget.py`, `tach check`, `ruff format --check`, `ruff check` | B9, B10 | All green |
| T20 | `test_effective_verifier_gate_off_uses_minilm2` | B8 | Gate constant false (the shipped default until G1/G2): MiniLM2 is effective; provenance `preferred_verifier=deberta`, reason `not_qualified` |
| T21 | `test_effective_verifier_prefers_verified_deberta` | B8 | Gate on, snapshot verified, memory ok: DeBERTa is effective; thresholds identical; provenance names DeBERTa |
| T22 | `test_no_minilm2_substitution_after_deberta_failure` | B8, inc 609 | Injected DeBERTa inference failure: the job errors, no row is written, no MiniLM2 statuses appear; the next job re-resolves |
| T23 | `test_deberta_track_never_blocks_arctic_or_classification` | B2, A6 | A DeBERTa download failure leaves Arctic indexing, classification and Ask running |
| T24 | `test_user_explicit_verifier_and_retrieval_choice_respected` | A3, A5 | Explicit MiniLM/MiniLM2 choices persist after the preferred models become available; a forced incomplete Arctic fails closed with a path to automatic selection |
| T25 | `test_no_repeat_download_or_verification` | B2 | A second launch with verified snapshots makes no network call and repeats no checkpoint verification when file sizes and mtimes are unchanged |
| T26 | `test_minilm_dependencies_untouched` | Scope §7 | Paper/axis embeddings, axis scoring thresholds and the stance-feature verifier are unchanged by modernization (fingerprint and identity checks) |

## 3. Process-level tests (local scripts under `.claude/`, plus CI where feasible)
1. **New install.**
   - Empty DB, then import 3 fixture PDFs.
   - Expected: models downloaded and verified; papers classified; Arctic built; activation; Ask uses Arctic.
   - No banner text about "upgrading" (copy check).
2. **Upgrade.**
   - The F-0084 copy goes through migrations 0085 and 0086, then auto-start.
   - The banner shows once and is dismissible.
   - Ask works throughout on MiniLM, then on Arctic.
3. **Interrupted modernization, normal close.**
   - Close the app mid-index and relaunch.
   - Expected: resumes from vectors; coverage never decreases; no click.
4. **Interrupted modernization, forced termination.**
   - Kill the Tauri process tree, then separately kill only the worker, then kill during classification.
   - Expected after relaunch: automatic resume; `vector_integrity` clean; no orphan worker
     (`Get-Process`/`ps` checks the `index_worker` module); the OS lock is free.
5. **Low disk.**
   - A small loopback or VHD volume holding a DB copy, filled to just above the floor.
   - Expected: `waiting_disk`; free space; resume; integrity check passes.
6. **Responsiveness receipt.** With the Arctic worker running on F-0084, record p50/p95 for:
   - Library list;
   - opening a PDF;
   - one Ask (MiniLM effective);
   - one import.

   Compare with the same actions with the worker paused. Report it; the acceptance threshold is agreed with Cliff.
   *Requires experiment-gate authorization.*
7. **4,000-paper scale.** On F-4000 with the fake encoder (CI-safe):
   - detection cost < 1 s;
   - the coordinator tick is cheap;
   - classification and indexing complete and resume across 3 forced kills;
   - batching never binds more than `SQL_VARIABLE_BATCH` parameters (inc 573).

   One authorized real-encoder receipt on a copy records throughput, peak worker RSS and DB growth per 1,000 chunks,
   and validates the Scope §4 estimates.
8. **DeBERTa latency and memory receipt (B8, G2).** Plus, only if authorized, the G1 offline re-score at 0.55/0.55 on
   the existing Phase 34 labelled pairs through the app's verification path (Scope §6). Neither is a new adjudication.
   - One fixture synthesis on CPU: MiniLM2 vs DeBERTa, warm and cold.
   - Record peak RSS concurrent with the index worker.
   - *Authorization required.* This measures a shipped configuration; it is not a model comparison for selection.

## 3a. Inc 621 receipts (2026-11-01; local evidence under `.local/validation-621/`)
- **Done with stand-ins:** rendered-browser acceptance on disposable libraries; upgrade path on a copy of F-0084 with real
  classification over 151 papers, then a stand-in encoder over a 10-paper, 1,446-passage subset.
- **Added to §3.7's scale receipt:** record `GET /embedding-profiles` and `GET /modernization` latency.
- **Still owed:** every row of §4; a real low-disk volume with status writes refused; two real app processes; real Arctic
  indexing (authorized receipt only); the panel at mobile width; the 0.6.0 notice under a real version bump.

## 3b. Inc 630 and 631 (2026-11-03)
- **Done:** release candidate step 1's equivalent for the integration branch, the full suite on the locked stack, in an
  isolated account: PASS on `c7c645fe` (3,831 passed, 14 expected skips; `INCREMENT-630-NOTES.md`). It ran `pytest -n 2`
  on Windows from a source clone, not on a merged commit; step 1 below still applies to the merged commit.
- **Not done by it:** any row of §4. The real Arctic S and DeBERTa snapshot tests skipped.
- **Planned:** `RELEASE_060_PACKAGED_MODEL_QUALIFICATION_PLAN.md` stages §4's model rows on Windows first (P1 runtime
  load, P1b DeBERTa packaged acceptance, P2 app behaviour, P3 worker lifecycle, P4 installer).

## 4. Packaging (three OSes; extend existing workflows)
Extend `app/desktop-shell/packaging/smoke_test_backend.py` and `.github/workflows/desktop-shell-{windows,macos,linux}.yml`.

| Check | Windows | macOS (arm64, x64) | Linux (amd64 `.deb`) |
|---|---|---|---|
| Packaged runtime loads Arctic S @pinned and DeBERTa @pinned (download in CI, then `local_files_only=True` reload); DeBERTa contract `verify_nli_checkpoint` passes **without `sentencepiece`/`protobuf`** (verified locally on Windows in this audit) | ✓ | ✓ | ✓ |
| Tiny parity probe vs the CI dev environment (3 texts, 2 pairs; cos ≥ 0.99999, |Δp| ≤ 1e-3) | ✓ | ✓ | ✓ |
| `SubprocessLauncher` starts `python -m app.backend.embeddings.index_worker` from the staged `callosum-src` (`stage_source.py` layout) and indexes 1 batch | ✓ | ✓ | ✓ |
| App exit kills the worker: Windows Job Object; Unix process-group SIGTERM (worker inherits the group; no `start_new_session`) | ✓ | ✓ | ✓ |
| Upgrade from an F-0084-shaped fixture through migrations to head with auto-start | ✓ | ✓ | ✓ |
| HF cache location writable (default `~/.cache/huggingface`); no `HF_HOME` assumption | ✓ | ✓ | ✓ |
| The new runtime ID, if `uv.lock` changes, must be published before the app branch (inc 570 rule). **Preferred: no dependency change.** The audit found DeBERTa works without adding `sentencepiece`/`protobuf` | n/a | n/a | n/a |
| `psutil` absent from `app/` (existing test) | ✓ | ✓ | ✓ |

**Release candidate (only after B1–B10 are accepted, and only on Cliff's explicit approval):**
1. Full `pytest -n auto -q` on the merged commit.
2. The three platform workflows green.
3. `python tools/bump_version.py 0.6.0`.
4. A `whatsnew.json` 0.6.0 entry.
5. A tag.

None of this is done in this audit.

## 5. Scientific smoke tests (existing accepted fixtures only)
- **Classifier identity:** T3 (F-heldout, F-replay fingerprints).
- **Retrieval identity under MiniLM:** the 607/611 replay harness (`replay.py after`) on the replay copy reproduces
  the frozen inc-611 selections: WL15 5399; WL18 58052/56894; D_q2/D_p2 56618; SP18 unchanged.
- **Arctic identity:** the existing inc-610 receipt. Batch size does not change vectors (≤1.06e-7). Re-run only the
  existing assertion.
- **NLI contract:** the existing DeBERTa label/arch/tokenizer tests and the fail-closed tests (inc 609).
- **Synthesis unchanged:** `test_truncated_generation.py`; the `providers.py` freeze check.
- **No new adjudication** unless one of these identities fails, which would mean the scientific behavior changed.
