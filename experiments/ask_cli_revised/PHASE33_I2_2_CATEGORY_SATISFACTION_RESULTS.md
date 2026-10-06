# Phase 33 / I2-2 — v4 category satisfaction, goal-aware completion, and recovery

Status: **v4 is implemented for category instances only.** Live answer behaviour is **not** ready for I2-3 (see the verdict at the end). No live search, no model call, no network, no pin refresh, no frozen-contract change, no frontend change, no `PLAN_VERSION` change.

## Heads

- Starting HEAD: `6795a744` (I2-1b).
- Branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
- Final HEAD: the I2-2 commit that adds this file (see `git log`).

## Files changed

Modified:
- `sufficiency_engine.py` — v4 constants, category constants, `is_category_requirement`, `category_goal_satisfied`, `goal_gate` in `recompute_instance`, goal gate computed in `recompute_requirement`.
- `sufficiency_mapping.py` — the single authorized importer of `category_polarity`; v4 category mapping; `_category_observations`, `_representative_observation`; v4 direction-observation dispatch; v4 fail-closed for non-cardinality explicit terms.
- `sufficiency_recovery_targets.py` — `semantic_goal_unsatisfied` reason, v4 target branch, `search_obligations`, `completed_target_ids`, query hint.
- `direction_target.py` — `_SINGLE_OPERAND_FALLBACK[V4] = False` (= v3 rule).
- `relation_witness.py` — `_REFERENT_CONTAINMENT[V4]` = v2/v3 containment.
- `e2e.py` — the early initial-only `structured_search` is replaced by obligations (initial plus raw final under v4); `completed_target_ids` passed to the final target computation. Nothing between the old and new positions read `structured_search` (checked).
- `test_sufficiency_semantics_version.py` — current pin moved to v4; v3 added to historical; identity assertions updated deliberately.
- `test_sufficiency_semantics_threading.py` — unsupported-version probe moved from v4 to v5.
- `test_category_polarity.py` — the I2-1 "unwired" guard replaced by an AST-based exact-authority guard; module title updated.

New:
- `test_sufficiency_v4_category_satisfaction.py` — 25 tests (satisfaction A–J, terminality 1–8 with 8b, version identity, v3 no-classifier spy, v4 positive control, dispatch parity, non-category engine and recovery parity, vocabulary guard).
- `PHASE33_I2_2_CATEGORY_SATISFACTION_RESULTS.md` (this file).

Unchanged by design: `category_polarity.py` (classifier), `answer_plan/` (including `PLAN_VERSION = answer-plan-step2-v4`), the zero-evidence functions (`is_genuinely_empty`, `is_zero_evidence_terminal`, `ResolvedEmptyOutcome`, `build_resolved_empty_outcomes`) — confirmed by a grep of the diff.

## v3 vs v4 semantic definition

| Aspect | v3 (historical, readable) | v4 (current) |
|---|---|---|
| Category binding | first admissible literal match in unit order (`_bind_role_candidates`) | every admissible literal observation collected; representative chosen by precedence |
| Category satisfaction | a binding exists (`filled` ⇒ `complete`) | `complete` also requires ≥1 `positive_finding` observation |
| Null / mention / unknown | satisfy (any binding) | recorded as observations; do not satisfy presence |
| Recovery for bound-but-unsatisfied category | none (filled ⇒ no target) | `semantic_goal_unsatisfied` single-role target |
| Terminality | initial structured targets only | initial plus raw-final targets; completed semantic targets suppressed by target id |
| Non-category subsystems | unchanged | identical to v3 (checked, see parity) |

## Wiring seam

Exactly one production importer of the classifier: `sufficiency_mapping.py` (`from experiments.ask_cli_revised import category_polarity as cp`). Enforced by an AST guard, `test_only_the_v4_mapping_seam_imports_the_classifier` (the importer set must equal `{"sufficiency_mapping.py"}`), which resolves real import statements rather than substrings. The engine's comments legitimately name the vocabulary, so a substring guard would be wrong.

`map_cardinality_requirement(..., semantics_version)` dispatches to `_map_category_requirement_v4` under v4 only. v3 never reaches `cp`; a spy test proves it (`test_v3_category_mapping_never_calls_the_classifier`), and a positive-control spy proves v4 does call it.

## `category_observation` schema

Per term, a list stored at `instance["category_observations"]`, one entry per admissible literal unit, in unit order:

`term`, `proposition_id`, `unit_id`, `exact_text` (the literal term surface), `source_passage`, `observation_polarity` (`positive_finding` | `null_finding` | `mentioned_only` | `unknown`; `contrary_finding` reserved, never emitted), `rule`, `ambiguity`, `classifier` (version), `competing_terms`, `classifier_audit` (term clause, contrast clause, competing-term flags, result complement), `guard` (the unit's passage flags, carried through unchanged).

## Aggregation rule

All observations are kept. Satisfaction = at least one `positive_finding`. Unit order never decides polarity. Null observations for the same term are retained and visible, not discarded.

## Representative rule

For the compatibility binding `role_bindings[role]`: first positive, else first null, else first mentioned_only, else first unknown; ties by unit order. A binding is `filled` iff at least one admissible observation exists. Its provenance records `observation_polarity` and `classifier_rule`. The representative never decides satisfaction.

## Goal rule

`recompute_instance(..., goal_gate=True)` under v4 computes `complete = required/alternative roles filled AND category_goal_satisfied(instance)`. The gate applies only where `is_category_requirement` holds (every role is `explicit_category_terms` and the quantifier is `all_requested_categories`). A v4 category instance without `category_observations` raises `ValueError` (fail closed). Non-category requirements never set `goal_gate`.

## Recovery reason and target identity

- Reason: `semantic_goal_unsatisfied` (added to `REASONS`).
- Emitted for a v4 category instance whose binding is `filled` but whose goal is unsatisfied: single role `category_evidence`, scope = instance scope plus `semantic_goal: established_presence`.
- Identity: `new_recovery_target` payload `{search_child_id, requirement_id, reason, goal_mode, target_roles, scope}`; `target_id = search_child_id :: sha256[:16]`. Two terms yield two distinct targets (tested).
- Query hint: "evidence that {subject} was found or established".

## Terminality (target-scoped)

- `structured_search_outcomes(obligations, log)` gives each target a state: `not_attempted` (no log row), `completed` (one row with a completing reason: `recovery_added_evidence` or `recovery_no_new_evidence`), `not_completed` (otherwise).
- `compute_recovery_targets(..., completed_target_ids=…)` skips a `semantic_goal_unsatisfied` target whose id is completed. Non-semantic targets (`missing`, `partial`, `relationship_unverified`) are never suppressed by completion.
- The e2e completed set is the set of target ids with state `completed` over the obligation union.
- Documented behaviour, flagged for review: a completed round that added evidence but still yields only a null suppresses further semantic targets for that instance in this run (test 3). This bounds the obligation to one completed round, the same bound used for other obligations. It is a decision, not a silent default.

## Obligation union

`search_obligations(initial, raw_final, semantics_version)`: v1–v3 return the initial targets unchanged; v4 returns initial plus raw-final targets keyed by target id (`setdefault`, nothing fabricated). A target first exposed by the final map has no log row, so it is `not_attempted` and stays recoverable (test 6, which also proves v3 excludes it).

## Zero-evidence parity

Zero-evidence code untouched (grep of the diff: no hits for `is_genuinely_empty`, `is_zero_evidence_terminal`, `ResolvedEmptyOutcome`, `build_resolved_empty_outcomes`). Tests 8 and 8b: a zero-evidence category yields only `missing` targets, never a semantic target, and completion never suppresses them; a bound null is never genuinely empty and never zero-evidence terminal.

## Stop-search parity

`compute_stop_search_certified` is unchanged. Its inputs change for category instances only, because `state` now reflects satisfaction: a null-only category is no longer `filled`, so it cannot certify stop.

## v4 parity for non-category subsystems

- Dispatch tables: `direction_target._SINGLE_OPERAND_FALLBACK[V4] == [V3]` (False); `relation_witness._REFERENT_CONTAINMENT[V4] is [V3]`.
- Engine and recovery: a non-category atomic requirement gives identical `recompute_requirement` and `compute_recovery_targets` output under v3 and v4 (test `test_v4_leaves_a_non_category_requirement_identical_to_v3`).
- Preserved runs: `relation_units` and `terminal_empty` are byte-identical v3 vs v4 for both attempt2 and t5c (0 changed leaves in the structured diff).

## Preserved-run forensics (c3 / c6, category requirement `implicit-explicit-coverage`)

Attempt2 (`phase28-live-parent-synthesis-attempt2`):
- c3 `implicit`: v3 bound from p36 (the sentence "…their implicit biases were slight and not significant."). v4 representative is the same proposition, polarity `null_finding`, rule `local_null_same_clause`. Instance `partially_filled` / `incomplete_instance`. The requirement moves `filled` → `partially_filled` / `category_missing`. A `semantic_goal_unsatisfied` target is added for `implicit`. **This is the intended correction.**
- c3 `explicit`: unchanged binding (p8, a prior-work-framed sentence, `local_finding_predicate`, positive). Satisfied in v4. Caveat (I4, not I2): p8 is literature framing, so the mapping counts it as presence and attribution is not established here.
- c6 `explicit`: v3 bound from p17 (`repeated_term_occurrence`). v4 classifies p17 as **unknown** (repeated term, fail-closed) and the representative moves to p52 ("providing direct evidence that explicit beliefs can influence the social evaluation of faces."), a positive, literature-framed sentence. c6 `explicit` stays satisfied, but via p52.
- c6 `implicit`: missing in both (p36 is not in c6's candidate pool). Unchanged.

T5c:
- c3 `explicit`: p8 positive, satisfied. Unchanged.
- c6 `explicit`: v3 bound from p17. v4 classifies p17 as **unknown** (repeated term). **No positive remains**, so c6 `explicit` is no longer satisfied and the requirement moves `partially_filled` → `missing`. A `semantic_goal_unsatisfied` target is added for `explicit`. **This is a real satisfaction loss; see findings.**

## v3 / v4 semantic diff (structured, from the preserved-run captures)

Attempt2 (28 changed map leaves, 1 target added, 3 stop-recovery leaves, 5 claim leaves):
- map: `category_observations` added for c3 and c6; representative provenance (`observation_polarity`, `classifier_rule`) for c3 and c6; c3 instance `complete`/`state`/`reason` and requirement `state`/`reason` (filled → partially_filled); c6 representative `proposition_id`, `guard`, provenance (p17 → p52); `sufficiency_semantics_version` stamps for all children.
- targets: one added, `c3::3730b17593f9733d` (`semantic_goal_unsatisfied`, `implicit`, single role).
- stop_recovery: c3 `reason`, `recovery_needed`, `state` changed.
- claims: two claim ids changed (see ParentClaim section), one admissible proposition id and one value proposition id changed, `model_dependency.stop_search_certified` changed.
- relation_units: 0. terminal_empty: 0.

T5c (23 changed map leaves, 1 target added, 1 stop-recovery leaf, 0 claim leaves):
- map: `category_observations` for c3 and c6; c3 representative provenance (same p8 binding, provenance only); c6 explicit: the binding stays `filled` on p17 (provenance now `unknown`, rule `repeated_term_occurrence`), but the instance is incomplete (`complete` False, `state` partially_filled, `reason` incomplete_instance) because the goal gate is unsatisfied; requirement `state` moves to `missing`/`category_missing`; version stamps.
- targets: one added, `c6::9f20269d0db5244d` (`semantic_goal_unsatisfied`, `explicit`, single role).
- stop_recovery: c6 `state` changed.
- claims: 0. relation_units: 0. terminal_empty: 0.

## ParentClaim diff

- Attempt2: two claim ids changed. c3 `category_list` `9fd341f1bbff788b` → `351d34bff55b518f` (the c3 claim's values/support now record the null-bearing category set). c6 `role_value` `c33c4ccf244a45a8` → `cb9192d62bbccd00` (proposition p17 → p52). Both are expected consequences of the representative and observation change, not new evidence.
- T5c: claim set identical (7 vs 7, 0 changed leaves).

## PRE-I2-3 AnswerPlan behaviour (replay, attempt2 only)

Replay: both maps run through `answer_plan.replay` in scratch copies of the attempt2 run directory (v3 recomputed map vs v4 map). Output: `answer_plan.json`, `answer_plan_audit.json`, `deterministic_layer1–3.md`. **Not run:** the same replay for t5c (I did not locate a t5c run directory with its sealed artifacts). The t5c answer-layer effect is inferred from the map diff and is unverified.

Observed attempt2 replay changes (52 changed JSON leaves):
- Node 5 (the implicit/explicit facet) status `partial` → `not_established`; facet state `partial` → `not_established`; its single statement goes 1 → 0 (the allowed-statement list drops `4B:0`, consistent with this, though I did not separately confirm the id-to-node mapping); `layer2.passages` 1 → 0; `limitation_decisions` 27 → 0; `displayed_render_count` 1 → 0.
- Claim role for c6 `role_value`: `primary`/`layer1` → `suppressed`/`layer2`, value_result `ok: True` → `False` with reason `attribution_unknown`, because the representative p52 is literature framed.
- Disclosure text: "The retrieved evidence does not establish implicit attitude findings." → "…does not establish implicit and explicit attitude measures." (the disclosure's category grouping changed; this is pre-existing AnswerPlan wording logic showing a shifted category set; not repaired here).
- Parent: `node_state_counts` `partial` 4 → 3, `not_established` 5 → 6; allowed statement list 9 → 8 entries.
- Claim id changes propagate into nodes 2 and 5 (`category_list` and `role_value` ids).
- `containment_semantics` and `direction_semantics` stamps → v4; `plan_sha256` changed; `PLAN_VERSION` unchanged (`answer-plan-step2-v4`).

Net PRE-I2-3 effect on the attempt2 answer: node 2's category claim id changes with the c3 null. I did not separately inspect the rendered c3 text, so the visible c3 effect is unverified. The c6 explicit facet loses its rendered passage and drops to `not_established`, because the only positive representative is literature-framed and therefore suppressed. **The answer layer currently regresses on attempt2.** I2-3 must not proceed until this is decided.

## Tests

- `test_sufficiency_v4_category_satisfaction.py`: 25 passed (after fixing two fixture errors: a contract wrapper and the wrong module for two predicates; no expectation was changed).
- `test_category_polarity.py` (the guard replacement is included): 61 passed.
- Polarity hardening (21) and result-complement (25) suites: passed in the targeted run.
- Targeted sufficiency suites (version, threading, mapping, recovery, engine): passed in the same targeted run; see the full suite count below.
- Full experiments offline suite (final, after the fix round): **2929 passed, 11 skipped, 2 deselected, 3 failed**. The 3 failures are exactly the pre-existing ones listed below. Baseline 2904 + 25 new I2-2 tests = 2929. The earlier 21-failure and 13-error run is superseded (see triage above).

## Full-suite regression triage (first full run) and fixes

My first full offline run after the v4 change was **not clean**: 21 failed and 13 errored, against an I2-1b baseline of 2904 passed with three known failures. I had not run `test_direction_target_v3.py` or the replay suites in my targeted set, and I reported the targeted result as if it were the full picture. Each group was traced to a cause:

1. **Dispatch regression (my bug, 10 failures in `test_direction_target_v3.py`).** `find_direction_observations` routed any version in `HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS` to the pre-I3 v1/v2 helper. I had added v3 to that set (correct for the identity reader), so v3 lost its `target` key and its operand check. Fix: the historical branch now matches only `V1`/`V2` explicitly. The identity reader (`sufficiency_identity.py`) is the only other historical-set consumer and is correct as written (historical versions need an explicit flag).

2. **Identity mismatch in recorded replays (18 `SemanticsIdentityError`).** Recorded replays of the preserved v9 run map under an explicit v3 (their recorded semantics) but ran the direction pass under `SUFFICIENCY_SEMANTICS_VERSION`, which is now v4. The identity check refused the mix. This was correct fail-closed behaviour exposing a test that depended on the constant equalling v3. Fixes:
   - `test_sufficiency_replay_real.py` and `test_sufficiency_phase19b_real_v9_replay.py`: the direction pass uses V3 where their mapping is V3.
   - `run_recorded_v9` (new, in `sufficiency_phase2_replay.py`): a single shared recorded-replay driver that pins V3. Phase2, phase5 and phase9 replays call it. The production driver `sufficiency_model_nomination_diagnostic.run` is **unchanged**. My first attempt added a `semantics_version` keyword to that driver; the I2-0 threading guard rejected it, because production drivers must pass the literal current constant at each threaded call. The guard is correct, so the recorded-replay path moved instead of the guard.
   - `test_hierarchy_e2e.py::test_the_integrated_run_matches_calling_the_deterministic_mapper_directly`: the integrated run is current, so the direct call is now current too. Its previous V3 direct call could never equal a v4 integrated run.

3. **Locked v9 baseline under v4 (measured, not absorbed).** The phase5 and phase9 tests lock the preserved v9 per-child states. They now reproduce those states under pinned V3. Under v4, a scratch run (`v4_locked_baseline_delta.py`, patched to v4) changes exactly **one** of the twelve locked requirements: `c6 implicit-explicit-coverage` goes from `partially_filled` (instance count 2) to `missing`, which is the repeated-term loss already documented. `c3 implicit-explicit-coverage` stays `partially_filled` with count 2, and every other locked child is unchanged.

Files changed in the fix round (on top of the list above): `sufficiency_mapping.py` (the dispatch line), `sufficiency_phase2_replay.py` (the shared driver and its `se`/`sd` imports), `sufficiency_phase5_replay.py` and `sufficiency_phase9_counterfactual_replay.py` (call the shared driver; minimal diffs, no formatter reflow), `test_sufficiency_replay_real.py`, `test_sufficiency_phase19b_real_v9_replay.py`, `test_hierarchy_e2e.py`. `sufficiency_model_nomination_diagnostic.py` is back to HEAD, untouched.

Two lint notes: `sufficiency_phase5_replay.py` has an I001 import-order complaint that is **pre-existing at HEAD** and left alone (no drive-by reformat).

## Pre-existing failures (unchanged)

The three long-standing failures are unchanged and not caused by this increment:
- `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`
- `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`
- `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`

## Anti-fitting and vocabulary

- The classifier (`category_polarity.py`) has no question, model, or frozen-contract identifiers: `test_the_classifier_vocabulary_carries_no_question_or_model_identifiers` (`q_[a-z]+`, `aib_hier`, `sufficiency_contract`) and the I2-1 domain-word guard both pass.
- New synthetic fixtures use generic terms only (alpha, beta, gamma).
- No classifier tuning happened in I2-2. The repeated-term rule that produced the c6 loss was left exactly as I2-1 defined it.

## Scientific gain and loss (honest accounting)

Gain:
- c3 `implicit` is no longer certified as satisfied by a sentence that says the bias was "not significant" (a null). Recovery is now warranted for it.

Loss / risk, not fixed:
- c6 `explicit` in t5c loses its only positive representative because the repeated-term fail-closed rule classifies p17 unknown. A satisfaction is lost, not merely re-labelled.
- In attempt2, c6 `explicit` is kept only through a literature-framed sentence (p52), which the answer layer then suppresses. The rendered answer loses that facet.
- c3 `explicit` (p8) and c6 `explicit` (p52) are satisfied by prior-work framing at the mapping layer. Attribution is I4, not I2; I2-2 does not establish own-study presence.

## Findings for review before I2-3

1. **Repeated-term fail-closed rule** (I2-1 `repeated_term_occurrence` → unknown) removes the only positive for c6 `explicit` in t5c. Decision needed: whether repeated-term occurrences should be classified per occurrence rather than failing closed. Not tuned here.
2. **Representative precedence** picks a literature-framed positive (p52, c6 attempt2; p8, c3) over nothing, and the answer layer then suppresses it. Decision needed: how an attribution-prior positive should bind a presence requirement at mapping time versus the answer layer (I4 territory).
3. **Completed-round terminality** (test 3): a completed round that added only a null terminates the semantic obligation for the run. Confirm this bound, or require a different terminal representation.
4. The AnswerPlan replay was run for attempt2 only; the t5c answer effect is unverified.

## READY / NOT READY for I2-3

**NOT READY.** The mapping-level change is correct for the c3 null case, and the classifier and seam are as specified. But the answer-layer replay on attempt2 regresses (c6 `explicit` facet to `not_established`), and t5c has a satisfaction loss from the repeated-term rule. I2-3 changes exactly how these render, so it must not start until findings 1 and 2 are decided. I did not begin I2-3 and did not change `PLAN_VERSION`.

## Lineage

`CONTRIBUTION-LINEAGE.md` has an I2-2 entry appended; earlier entries are unchanged.
