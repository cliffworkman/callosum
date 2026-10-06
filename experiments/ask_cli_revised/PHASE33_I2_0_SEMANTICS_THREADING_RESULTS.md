# Phase 33 / I2-0 — explicit semantics-version threading (zero semantic change)

## Heads

- Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
- Starting HEAD before the audit commit: `3c06123f28b7d6dc9a8b3f041c8eafa4458bcba3`.
- Phase 33 audit commit (docs only, pushed): `6442f75f`.
- Final HEAD: the commit that adds this file and the I2-0 code (its hash is recorded in the lineage entry and in `git log`).

## Files changed

Production (threaded or re-plumbed):
- `sufficiency_engine.py` — `require_supported_semantics_version` (fail-closed gate); `recompute_requirement` and `recompute_instance` take a required keyword-only `semantics_version`.
- `sufficiency_identity.py` — `stamp_map(mapped, *, semantics_version)`; no default.
- `sufficiency_diagnostic.py` — `compute_diagnostic_sufficiency_map(..., *, semantics_version)`; witness attach and stamping use the passed version.
- `sufficiency_mapping.py` — `map_any_requirement`, `map_requirement`, `map_paired_requirement`, `map_cardinality_requirement`, `_bind_role_candidates`, `_fork_instances_over_role` take required keyword-only `semantics_version`; dead wrapper `_bind_role_from_units` deleted (zero callers, rule #5).
- `sufficiency_recovery_targets.py` — `compute_recovery_targets`, `terminal_search_status`, `_gate_status`, `_targets_for_instance`, `_incomplete_instance_targets` take required keyword-only `semantics_version`.
- Production drivers (explicit current constant): `e2e.py`, `phase13_c4_recovery_experiment.py`, `phase15_c4_semantic_consumption_experiment.py`, `phase21_live_initial_model_assist_validation.py`, `phase23_live_recovery_targeted_u2_remap_validation.py` (adds the `se` import), `sufficiency_model_nomination_diagnostic.py`, `sufficiency_recovery_targets_inventory.py` (adds the `se` import).
- `parent_synthesis_test_support.py` — test support; explicit historical v3.

Tests (explicit historical v3 at every threaded call; behaviour assertions unchanged):
- `test_hierarchy_e2e.py`, `test_parent_empty_outcome.py`, `test_referent_containment_v2.py`, `test_relation_witness.py`, `test_sufficiency_diagnostic.py`, `test_sufficiency_direction_effectiveness.py`, `test_sufficiency_empty_result_terminal.py`, `test_sufficiency_engine.py`, `test_sufficiency_mapping.py`, `test_sufficiency_phase19b_real_v9_replay.py`, `test_sufficiency_recovery_targets.py`, `test_sufficiency_replay_real.py`, `test_sufficiency_semantics_version.py`.

New: `test_sufficiency_semantics_threading.py` (19 tests).

Lineage: `CONTRIBUTION-LINEAGE.md` (appended entry; earlier bytes unchanged).

No frozen contract, pin artifact, frontend file, or `app/` file changed. `git diff --name-only` lists only `experiments/ask_cli_revised/` paths.

## Mapping call graph threaded

`compute_diagnostic_sufficiency_map` → `map_any_requirement` → `map_requirement` | `map_paired_requirement` | `map_cardinality_requirement` → `_bind_role_candidates` ← `_fork_instances_over_role`; each mapper → `recompute_requirement` → `recompute_instance`; `compute_diagnostic_sufficiency_map` → `rw.attach_relation_witnesses` and `si.stamp_map`.

Recovery: `compute_recovery_targets` → `_gate_status` and `_targets_for_instance` → `_incomplete_instance_targets`; `terminal_search_status`.

Functions that now require an explicit `semantics_version`: all of the above. Each validates it through `se.require_supported_semantics_version`, which accepts only the readable set (v1, v2, v3) and rejects anything else with `ValueError`. Where a dispatch point exists, the validation runs before any work; `_bind_role_candidates` and `recompute_requirement` validate at their own entry, so a bypassed caller still fails closed.

## Which call sites select current production semantics

Only the top-level production drivers pass `se.SUFFICIENCY_SEMANTICS_VERSION` explicitly: `e2e.py` (7 threaded calls), `phase13` (3), `phase15` (3), `phase21` (4), `phase23` (1), `sufficiency_model_nomination_diagnostic.py` (2), `sufficiency_recovery_targets_inventory.py` (1). That is 21 selections in total.

Every test and test-support call requests `se.SUFFICIENCY_SEMANTICS_V3` explicitly (298 call sites). These tests assert pre-I2 behaviour; in I2-2 the reviewer decides which move to the current constant.

Internal threading inside the lower modules (18 call sites) forwards the parameter from the enclosing function. The transform fails if a call has no enclosing `semantics_version` and no file default, so no internal call can fall back silently.

## Proof that no lower semantic function silently defaults to current

1. No lower entry point has a default for `semantics_version` (keyword-only, required). Omission raises `TypeError` naming `semantics_version`. Test: `test_omitting_the_version_fails_at_the_api_boundary` (10 entry points).
2. Unsupported versions (`v9`, empty, `None`, `3`) raise `ValueError` at each dispatch entry. Test: `test_unsupported_versions_fail_closed` (4 values × 9 entries). Historical v1 and v2 are accepted; v4 (not yet readable) is rejected.
3. The lower modules `sufficiency_mapping.py`, `sufficiency_recovery_targets.py`, and `sufficiency_diagnostic.py` contain no `SUFFICIENCY_SEMANTICS_VERSION` reference (only the read-side `HISTORICAL_…VERSIONS` set). Test: `test_lower_semantic_modules_never_select_the_current_constant`.
4. Every production driver's threaded calls pass `se.SUFFICIENCY_SEMANTICS_VERSION` explicitly. Test: `test_production_drivers_pass_the_current_constant_explicitly` (AST scan).
5. Spies prove that explicit v3 reaches every lower entry point (`map_any`, `map_requirement`, `map_paired`, `map_cardinality`, `_bind_role_candidates`, `_fork_instances_over_role`, `recompute_requirement`, `recompute_instance`, `stamp_map`, `attach_relation_witnesses`), that each one receives exactly v3, and that every produced map is stamped v3. Test: `test_explicit_v3_reaches_every_lower_entry_point_and_stamps_the_map`.

## Projection and byte parity (pre-change versus post-change)

The pre-change baseline was captured on the unchanged tree (HEAD `3c06123f`) by an offline, network-free script. It runs `compute_diagnostic_sufficiency_map` over the preserved Attempt-2 sealed ledger and the verified v9 contracts with no model client, then records the canonical outputs. The post-change run uses explicit v3. Each output is canonical JSON (sorted keys, `ensure_ascii=False`).

| output | pre-change vs post-change |
|---|---|
| mapped diagnostic map (all bindings, instances, category mappings, witness metadata, direction/effectiveness summaries, complete/state/reason, stamp) | byte-identical |
| recovery targets | byte-identical |
| stop-search certified, recovery-needed, recovery-needed-when-completed | byte-identical |
| terminal search status (empty outcomes) | byte-identical |
| ParentClaim ledger | byte-identical |
| relation units | byte-identical |

The same six outputs are also byte-identical for the second preserved run (`q-aib-hierarchical-t5c`). The committed `test_sufficiency_semantics_threading` test pins the Attempt-2 digests (sha256 of canonical text) as explicit-v3 assertions, not as generated pin artifacts.

AnswerPlan replay (`answer_plan.replay`, preserved Attempt-2 run, explicit historical-unversioned flag, output to scratch):

| file | pre-change vs post-change |
|---|---|
| `deterministic_layer1.md` | byte-identical |
| `deterministic_layer2.md` | byte-identical |
| `deterministic_layer3.md` | byte-identical |
| `answer_plan.json` | byte-identical |
| `answer_plan_audit.json` | byte-identical |
| `comparison_against_phase29_hand_audit.md` | byte-identical |
| `replay_decomposition_authorization.json` | byte-identical |

## Preserved replay, ParentClaim, recovery and stop-search parity

Covered by the capture above: the preserved replay's Layers 1 to 3 and JSON outputs, the ParentClaims (`claims`), recovery targets (`targets`), stop-search and recovery-needed states, and the terminal empty status. All are byte-identical. No `plan_version`, `sufficiency_semantics_version`, or `complete`/`state`/`reason` value changed.

## Test counts

Targeted groups (`offline_pytest` launcher, network refused): new I2-0 file, mapping, engine, recovery, diagnostic, semantics-version, referent containment, relation witness, answer witness alignment, direction target (v1 and v3), answer plan (plan, step 2, replay), phase19b and replay-real, empty-result terminal, parent empty outcome, direction effectiveness, hierarchy e2e: **660 passed, 1 failed** (the pre-existing `test_hierarchy_e2e` preflight failure, §Pre-existing).

Full ask_cli_revised offline suite:

| run | passed | failed | skipped | deselected |
|---|---|---|---|---|
| pre-change baseline (HEAD `3c06123f`) | 2778 | 3 | 11 | 2 |
| post-change, final | 2797 (2778 + 19 new) | 3 | 11 | 2 |

The 2 deselected tests are the endpoint-guard mechanics tests excluded by the launcher by design. Their absence is the reason the I3 lineage reports 2780 (2778 + 2 = 2780). No new failure, and the eight `E` assertion lines of the three pre-existing failures are identical before and after.

## Pre-existing failures (unchanged, not caused by I2-0)

1. `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`
2. `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`
3. `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`

These match the I1 baselines by name. They are not touched by I2-0.

Other pre-existing observations, recorded and not fixed here:
- The committed `experiments/ask_cli_revised/phase30_replay/*` (Layers 2 and 3 and the JSON) predate the current code: for example `plan_version` reads `answer-plan-step2-v1`. The byte baseline for I2-0 is a fresh pre-change replay, and the committed copies are not regenerated.
- The untracked `.local/phase32/*` harness scripts still call the old signatures. They are local scratch and are not part of the repository; they need the same explicit keyword if re-run.
- The frozen v9 file's `status` label still reads `UNREVIEWED_CANDIDATE` although the review record names the same combined hash.

## Hooks and lint

- `ruff format --check` and `ruff check` pass on all 27 changed Python files (`ruff==0.9.6`, the pinned version). Two import-order and two undefined-name findings from the transform were fixed before the run.
- The docs-only audit commit passed the normal hooks without `--no-verify` (the line-budget hook only inspects staged Python or JSX).
- The I2-0 commit: see the commit attempt recorded in the lineage entry. The line-budget hook's only failure is the pre-existing `app/frontend/js/20_synthesis.jsx` (615 lines, frontend untouched). Under the explicit authorization for this commit only, `--no-verify` is used only if that is the sole failure.

## Semantic and scientific gain

Zero. No `complete`, state, reason, recovery, terminality, stop-search, ParentClaim, AnswerPlan, or rendering output changes. `SUFFICIENCY_SEMANTICS_VERSION` stays v3 and `PLAN_VERSION` stays `answer-plan-step2-v4`. No pin, frozen contract, or frontend file changes.

## Not done (by instruction)

No polarity classifier (I2-1). No category observations, no change to first-match, no v4 bump, no AnswerPlan semantics, no live recovery, no model call, no live E2E. Token-boundary term matching remains deferred.

## READY / NOT READY

- I2-0: complete; committed on this branch as the I2-0 commit (see `git log`), and pushed to origin.
- I2-1 (pure polarity classifier, unwired, stop for review): **READY for review** once I2-0 is accepted. Not started.
- I2-2 and I2-3: NOT READY until the I2-1 evidence is reviewed.
- Any live run: NOT READY.
