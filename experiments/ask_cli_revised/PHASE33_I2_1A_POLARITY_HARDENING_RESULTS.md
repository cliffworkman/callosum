# Phase 33 / I2-1a — polarity classifier precision hardening (unwired)

## Heads

- Starting HEAD: `1e94ab57` (I2-1, pushed; origin equal).
- Final HEAD: the I2-1a commit that adds this file (see `git log`).

## Scope

Only the two false-positive repairs named by the I2-1 review: R5 (procedural `found`) and R10 (coordination and negation scope). The classifier remains pure and unwired. No I2-2 wiring, no version bump, no map, recovery, AnswerPlan, model, network, pin, frozen, or frontend change.

Review decisions kept unchanged: bare significance stays mentioned-only; `linked` stays out of the finding lexicon; conservative contrast unknowns stay; there is still no general `and` boundary; measurement verbs and valence/magnitude words are not findings; hedge stays orthogonal; repeated terms stay fail-closed; token-boundary matching stays deferred; `contrary_finding` stays reserved.

## Files changed

- `experiments/ask_cli_revised/category_polarity.py` — the two repairs (below).
- `experiments/ask_cli_revised/test_category_polarity_hardening.py` — new: R10 pairs A–G, `found` pairs 1–9, the frozen holdout battery (22 rows), and keeper tests. Written and frozen before the repair.
- `experiments/ask_cli_revised/test_category_polarity.py` — one test-only change: the production-import guard's exclusion list also names the hardening test file (the guard matched it by its module name).
- This results artifact; lineage entry appended.

No other file changed. `git diff --name-only` lists only these.

## Exact classifier changes

**R5 — `found` is not positive authority.**
1. `found`, `find`, `finds` are removed from `FINDING_CUES`.
2. They are added to `DIRECTIONAL_CUES` only. Their sole remaining effect is that a negation without a significance complement stays unknown ("did not find stress" → unknown), which is the existing conservative behaviour.
3. A structural `_result_found` check restores exactly two result structures, and only these:
   - **P1, result complement:** `found` followed directly by `that` or `to`. ("We found that…", "was found to predict…")
   - **P2, result-noun head:** a result noun (association, evidence, effect, relationship, difference, correlation, and plurals) followed by `of`, `with`, `between` or `for`, then the term, then `found` after the term, with `found` not followed by a locative (in, at, on, within, from, among, into, inside, under, across, throughout, near, by). ("Evidence of stress was found.", "An association with stress was found.")
4. The infinitive guard exempts a cue after `to` when it directly follows `found to` ("was found to predict" → predict counts).

Object-location and procedural uses do not match either pattern: "found in the database", "found the questionnaire", "Researchers found stress".

**R10 — the negation must govern the complement.**
- A null now requires the complement cue to FOLLOW the negation cue, within three tokens, with no breaker in between. Breakers are `and`, `or`, `that`, `which`, `who`.
- Before: any complement within three tokens in either direction, so "significant and not spurious" paired `not` with the earlier `significant`.
- After: "significant and not spurious" has no complement after `not`, so it is not null. It falls to mentioned-only (procedural/mention negation).
- Forward governance still accepts every approved null form: not significant; not statistically significant; no significant difference; no association; no evidence; without significant effect; "may not have significantly reduced".
- `and` is still not a clause boundary, so "slight and not significant" stays one scope.

## R10 minimal pairs (hard requirements, all pass)

| id | sentence (term) | expected | result |
|---|---|---|---|
| A | The effect was not significant. (effect) | null | null |
| B | The effect was significant and not spurious. (effect) | not null | mentioned_only |
| C | Implicit bias was slight and not significant. (implicit bias) | null | null |
| D | Participants showed no significant difference in recall. (recall) | null | null |
| E | There was no association between stress and sleep. (stress) | null | null |
| F | The effect was significant but not robust. (effect) | not null | unknown |
| G | The effect was not significant and not robust. (effect) | unknown | unknown |

Pair B is mentioned-only, not positive: the sentence has no finding predicate, so it could not be positive. Pair F is unknown because the `but not robust` clause is an unattached contrast negation, which fails closed.

## `found` minimal pairs (hard requirements, all pass)

| id | sentence (term) | expected | result |
|---|---|---|---|
| F1 | The sample was found in the database. (sample) | mentioned | mentioned |
| F2 | The document was found in the archive. (document) | mentioned | mentioned |
| F3 | We found that stress predicted recall. (stress) | positive | positive |
| F4 | Stress was found to predict recall. (stress) | positive | positive |
| F5 | No association with stress was found. (stress) | null | null |
| F6 | Evidence of stress was found. (stress) | positive | positive |
| F7 | Researchers found stress. (stress) | mentioned | mentioned |
| F8 | The participant found the questionnaire online. (questionnaire) | mentioned | mentioned |
| F9 | An association with stress was found. (stress) | positive | positive |

F6 was decided by the structural rule before implementation: a result-noun head with `of` and the term, `found` after the term, not locative. It is not tuned.

## Residual battery, before and after (the original 15, unchanged)

Before = I2-1 classifier. After = I2-1a. Expectations are the intuitive readings, written before the I2-1 run and not changed.

| id | expected | I2-1 (before) | I2-1a (after) | status now |
|---|---|---|---|---|
| R1-lowered | positive | positive | positive | ok |
| R2-did-not-lower | unknown | unknown | unknown | ok |
| R3-not-associated | null | unknown | unknown | conservative (kept) |
| R4-significant-alone | positive | mentioned | mentioned | FN-looking (kept, by decision A) |
| R5-found-in-database | mentioned | **positive** | mentioned | **repaired** |
| R6-and-clause-null | null | null | null | ok |
| R7-not-reduced-by | unknown | unknown | unknown | ok |
| R8-did-not-find | unknown | unknown | unknown | ok |
| R9-two-negations | unknown | unknown | unknown | ok |
| R10-not-spurious | positive | **null** | mentioned | **repaired** (not null; mentioned is the review-accepted outcome) |
| R11-linked-procedural | unknown | mentioned | mentioned | FN-looking (kept, by decision B) |
| R12-but-not-nausea | positive | unknown | unknown | conservative (kept) |
| R13-raised-then-contrast | positive | unknown | unknown | conservative (kept) |
| R14-was-significant-only | positive | mentioned | mentioned | FN-looking (kept, by decision A) |
| R15-to-predict-procedural | mentioned | mentioned | mentioned | ok |

Mismatches against the intuitive expectations: 8 → 7. The R10 mismatch changed from a null (dangerous) to mentioned (safe, and the review's accepted outcome). Both repairs are visible in the table.

## Holdout battery (frozen before the repair; reported, not asserted)

The 22 expectations were written and committed before the repaired classifier existed. Before-state outputs of the I2-1 classifier were recorded once, to show the defect; the repair was then designed from the pre-registered hard pairs and the structural rule, not from these outputs. The repaired classifier was then run once. No iteration on the holdout.

| id | expected | I2-1 (before) | I2-1a (after) |
|---|---|---|---|
| H01 samples found in freezer | mentioned | positive | mentioned |
| H02 found the instructions | mentioned | positive | mentioned |
| H03 found in every participant | mentioned | positive | mentioned |
| H04 found the data in repository | mentioned | positive | mentioned |
| H05 effect found to be small | positive | positive | positive |
| H06 not found to predict | unknown | unknown | unknown |
| H07 sample was found (period) | mentioned | positive | mentioned |
| H08 stress and anxiety found in sample | mentioned | positive | mentioned |
| H09 significant association with stress found | positive | positive | positive |
| H10 no significant association with stress found | null | null | null |
| H11 two negations (found) | unknown | unknown | unknown |
| H12 significant and not spurious | mentioned | null | mentioned |
| H13 significant and found in sample | mentioned | positive | mentioned |
| H14 strong and not significant | null | null | null |
| H15 not significant and found to predict | null | null | null |
| H16 not reduced, and found to predict | unknown | unknown | unknown (repeated term; see note) |
| H17 found to be unrelated to recall | positive | positive | positive |
| H18 researchers found that not significant | null | null | null |
| H19 did not find stress in sample | unknown | unknown | unknown |
| H20 predicted, but found in database | positive | positive | positive |
| H21 findings for stress found in archive | mentioned | positive | mentioned |
| H22 evidence of stress found in archive | mentioned | positive | mentioned |

Holdout mismatches: **before 10 of 22, after 0 of 22.**

Note on H16: the term "recall" occurs twice in that sentence, so it is classified as a repeated-term unknown (fail-closed). The holdout was frozen as unknown, and the result matches.

## Confident false-positive-looking classifications that REMAIN

1. **H17 "Stress was found to be unrelated to recall." → positive.** The P1 pattern (`found to`) accepts any complement, including a negative result phrased as an adjective ("unrelated"). The pattern cannot tell a result report from a procedural "was found to be contaminated" either. This is the broadest remaining positive authority. A stricter P1 (requiring a finding predicate after `to`) would demote H05 and H17. Those two expectations were frozen as positive before the repair, so they were NOT changed. The stricter variant is recorded as a decision for review, not applied.
2. **H05 "The effect of stress was found to be small." → positive.** Same P1 breadth: a magnitude result is accepted as positive. The valence/magnitude rule forbids magnitude words as evidence predicates, but here the authority comes from the result structure, not the magnitude word.

No other confident false positive remains in the residual or holdout batteries. No positive classification was added by this repair: the set of positive outputs across both batteries only shrank (residual: R5 removed; holdout: H01, H02, H03, H04, H07, H08, H13, H21, H22 removed; none added).

## Conservative unknowns (kept, by decision B)

R3 (`not associated` with no complement noun), R12 and R13 (negated following clause with its own subject), H06 and H19 (negated `found`/`predict` without complement), H11 (two negations), H16 (repeated term), R2, R7, R8, R9.

## False-negative-looking cases intentionally retained

- R4 and R14: bare `significant` is not a finding predicate (decision A).
- R11: `linked` is not in the lexicon (decision B).
- R12 and R13 are conservative unknowns rather than negatives; their intuitive reading is positive, which the contract does not allow without a broader carryover.

## Proof the classifier remains unwired

- Static guard `test_module_is_not_imported_by_any_production_path` passes. Its exclusion list names only the classifier and its two test files.
- `grep` over `experiments`, `app` and `tools` for `category_polarity` finds only the classifier and its tests.
- No production module, sufficiency module, plan module, or replay module imports the classifier.

## Byte parity (zero runtime change)

After the repair, the offline capture and the Phase 30 replay were re-run and compared with the I2-0 pre-change baseline:
- Mapping, recovery, terminal status, stop-search, ParentClaims, relation units: 12 of 12 files byte-identical (Attempt-2 run and t5c run).
- Phase 30 replay (Layers 1–3, `answer_plan.json`, audit, authorization, hand audit): 7 of 7 byte-identical.

## Tests

- I2-1a hardening file: **21 passed** (R10 pairs A–G, `found` pairs 1–9, holdout well-formedness, keepers for bare significance, `linked`, and domain vocabulary).
- I2-1 original file (approved matrix, adversarial pairs, cross-domain, invariants): **61 passed**, unchanged expectations.
- Full offline `ask_cli_revised` suite under the network-refusing launcher: **2879 passed, 3 failed, 11 skipped, 2 deselected** (I2-1 total 2858, plus 21 new).
- Pre-existing failures, unchanged and not caused by this repair: `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`; `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`; `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`.

## Semantic and scientific production gain

**Zero.** The classifier has no runtime authority and no production caller.

## Recommendation for I2-2

**NOT READY to wire yet; READY for the review decision.**

- Decide P1 breadth (H05, H17): keep the current structure and accept the two documented false positives, or adopt a stricter P1 that requires a finding predicate after `found to`. The stricter variant would change two pre-registered expectations, so it needs its own explicit decision, not a silent edit.
- Once that decision is made, I2-2 can consider wiring. The residual false negatives (bare significance, `linked`) and conservative unknowns are documented limits, not blockers.
- No live run is authorized.
