# Phase 33 / I2-1b — result-complement authority (unwired)

## Heads

- Starting HEAD: `b3152580` (I2-1a, pushed).
- Final HEAD: the I2-1b commit that adds this file (see `git log`).

## Review decision implemented

`found that <C>` and `found to <C>` are **result-complement introducers**. They are not finding predicates. Authority comes only from the complement, which must independently establish its own classification. This removes the broad P1 positive authority that I2-1a had left in place.

## Exact P1 semantic change

For a clause where `found` is followed by `that` or `to` (the first such `found` is the introducer):

1. The complement starts after the introducer (skipping an optional copula `be`).
2. The complement is searched for an authoritative finding/assertion predicate under the existing closed `FINDING_CUES` (with the infinitive guard applied within the complement).
3. If the complement has one → **positive_finding** (`result_complement_finding_predicate`).
4. If the term clause contains a negation, the existing local-null rule governs the whole clause first; a complement that independently satisfies it is **null_finding** (no special `found` null rule was created).
5. If the complement has no authoritative finding predicate and no null → **unknown** (`result_complement_unauthorized`). A result is being reported; its implication for presence cannot be determined. It is not positive, and it is not mentioned-only.

Predicate authority that sits BEFORE the introducer is not counted: "Stress predicted sleep, and we found that recall was high" gives the complement "recall was high" no authority.

The audit output records the complement text in `result_complement` (null where no introducer exists). The schema key is present on every return path.

## P1 / P2 precedence

- If `found` begins a complement (`found that` / `found to`): **P1 only**. P2 is not consulted for that clause.
- Otherwise: P2 (result-noun head, linked by of/with/between/for, before the term; `found` after the term; not followed by a locative) may apply, as in I2-1a.

Consequence: "The effect of stress was found to be small." goes through P1 and becomes unknown. P2 cannot rescue it, because a result-noun head is present but `found to` takes precedence.

P2 is otherwise unchanged and narrow. Retained: "Evidence of stress was found." and "An association with stress was found." → positive; "No association with stress was found." → null (null precedence); "Evidence of stress was found in the archive." → mentioned (locative exclusion).

## Explicit H05 / H17 expectation revisions (post-I2-1a review decisions)

These were not classifier bugs found after implementation. They are deliberate review decisions and are recorded here and in `test_category_polarity_result_complement.py::REVIEW_REVISIONS`.

| id | sentence | I2-1a frozen expectation | I2-1b review expectation | I2-1b result |
|---|---|---|---|---|
| H05 | The effect of stress was found to be small. | positive | **unknown** | unknown |
| H17 | Stress was found to be unrelated to recall. | positive | **unknown** | unknown |

The superseded I2-1a expectations are kept in `test_category_polarity_hardening.py::HOLDOUT` for audit. The frozen expectations did their job: they made the breadth visible.

## `found that` matrix (frozen before the change; all match)

| id | sentence (term) | expected | result | rule |
|---|---|---|---|---|
| T-A | We found that stress predicted recall. | positive | positive | result_complement_finding_predicate |
| T-B | We found that stress was associated with recall. | positive | positive | result_complement_finding_predicate |
| T-C | We found that stress was in the database. | unknown | unknown | result_complement_unauthorized |
| T-D | We found that stress was measured. | unknown | unknown | result_complement_unauthorized |
| T-E | We found that stress was negative. | unknown | unknown | result_complement_unauthorized |
| T-F | We found that stress was not significant. | null | null | local_null_same_clause (existing rule) |
| T-G | We found that no significant association with stress was observed. | null | null | local_null_same_clause (existing rule) |

Before (I2-1a): T-C, T-D and T-E were positive (3 mismatches of 7). After: 0 mismatches.

## `found to` matrix (frozen before the change; all match)

| id | sentence (term) | expected | result | rule |
|---|---|---|---|---|
| O-A | Stress was found to predict recall. | positive | positive | result_complement_finding_predicate |
| O-B | Stress was found to be associated with recall. | positive | positive | result_complement_finding_predicate |
| O-C | Stress was found to increase recall. | positive | positive | result_complement_finding_predicate |
| O-D | Stress was found to be unrelated to recall. | unknown | unknown | result_complement_unauthorized |
| O-E | The effect of stress was found to be small. | unknown | unknown | result_complement_unauthorized |
| O-F | Stress was found to be negative. | unknown | unknown | result_complement_unauthorized |
| O-G | Stress was found to be measured. | unknown | unknown | result_complement_unauthorized |
| O-H | Stress was found to not significantly affect recall. | null | null | local_null_same_clause (existing rule) |

Before (I2-1a): O-D, O-E, O-F, O-G were positive (4 mismatches of 8). After: 0 mismatches.

## P1 precedence and P2 narrowness (frozen; all match)

| id | sentence (term) | expected | result |
|---|---|---|---|
| P2-evidence-of | Evidence of stress was found. | positive | positive |
| P2-association-with | An association with stress was found. | positive | positive |
| P2-significant-effect-of | A significant effect of stress was found. | positive | positive |
| P2-large-effect-of | A large effect of stress was found. | positive | positive |
| P2-locative-archive | Evidence of stress was found in the archive. | mentioned | mentioned |
| P2-null-no-association | No association with stress was found. | null | null |
| P1-over-P2-effect-small | The effect of stress was found to be small. | unknown | unknown |

Before: 1 mismatch (the P1-over-P2 row). After: 0.

## New frozen complement holdout (frozen before the change; run once after)

| id | sentence (term) | frozen expectation | result |
|---|---|---|---|
| CH01 found that + finding | We found that stress reduced recall. | positive | positive |
| CH02 found that + measurement | We found that stress was assessed in the sample. | unknown | unknown |
| CH03 found that + bare adjective | We found that stress was large. | unknown | unknown |
| CH04 found to + finding | Stress was found to correlate with recall. | positive | positive |
| CH05 found to be + finding | Stress was found to be correlated with recall. | positive | positive |
| CH06 found to be + adjective | Stress was found to be weak. | unknown | unknown |
| CH07 found to be + adjective | Stress was found to be independent of recall. | unknown | unknown |
| CH08 P2 result-noun, no complement | A large effect of stress was found. | positive | positive |
| CH09 P2 locative exclusion | Evidence of stress was found in the archive. | mentioned | mentioned |
| CH10 null inside found-that | We found that no significant effect of stress was observed. | null | null |
| CH11 found that + finding (passive) | We found that recall was reduced by stress. | positive | positive |
| CH12 found to be + procedural | Stress was found to be recorded in the database. | unknown | unknown |
| **CH13 predicate before introducer** | Stress predicted sleep, and we found that recall was high. | unknown | **positive** |
| CH14 found to + increase | Stress was found to increase recall. | positive | positive |
| CH15 found that, clause with null after comma | We found that stress was in the sample, and that the effect was not significant. | unknown | unknown |
| CH16 found that positive, then contrast negation | We found that stress predicted recall, but the effect was not significant. | unknown | unknown |

Mismatches: 1 of 16.

**CH13 is a frozen-expectation error, reported, not edited.** The sentence contains a comma, so the term clause for "stress" is "Stress predicted sleep". That clause has its own finding predicate ("predicted") and no introducer, so the contract makes it positive. My frozen expectation of unknown assumed the predicate would be read across the comma, which the clause rule does not do. The classifier's output is the contract-consistent reading. I did not change the frozen label after seeing the result; I'm recording the mismatch and its cause.

## Before/after deltas (every row whose output changed)

| battery | id | before | after | why |
|---|---|---|---|---|
| original holdout (I2-1a) | H05 | positive | unknown | explicit review revision |
| original holdout (I2-1a) | H17 | positive | unknown | explicit review revision |
| complement holdout | CH02 | positive | unknown | complement carries no authority (frozen expectation was unknown) |
| complement holdout | CH03 | positive | unknown | same |
| complement holdout | CH06 | positive | unknown | same |
| complement holdout | CH07 | positive | unknown | same |
| complement holdout | CH12 | positive | unknown | same |
| found-that matrix | T-C | positive | unknown | same |
| found-that matrix | T-D | positive | unknown | same |
| found-that matrix | T-E | positive | unknown | same |
| found-to matrix | O-D | positive | unknown | same |
| found-to matrix | O-E | positive | unknown | same |
| found-to matrix | O-F | positive | unknown | same |
| found-to matrix | O-G | positive | unknown | same |
| precedence | P1-over-P2-effect-small | positive | unknown | P1 precedence |

Every change is a positive → unknown demotion, and each is a direct consequence of the complement-authority rule. No row moved to positive or to null. The approved matrix (25 rows), the adversarial pairs (12), the cross-domain twins (9), the R10 pairs (7), and the found pairs (9) are all unchanged. The original residual battery is unchanged at 7 mismatches of 15 (same rows, same outputs).

## Residual battery and holdout, before and after

Residual (original 15, unchanged expectations): mismatches 7 before, 7 after. No row changed output.

Original holdout (22 rows, frozen in I2-1a): mismatches 0 before, 2 after. The two are H05 and H17, the deliberate review revisions above.

## Remaining confident positive or null classifications

None in the review batteries is positive or null without contract justification. Every remaining positive rests on a finding predicate in the term clause or in the complement (including CH13, whose predicate is in the term clause), or on a structurally narrow P2 result-noun head. Every null rests on the local same-clause negation rule or the narrow ellipsis.

Two positives are worth review, not blockers:
- **P2 "A large effect of stress was found."** The P2 structure is retained as the review asked. It is positive on structure, and the magnitude word is not evidence; the result-noun head is.
- **Complement predicate breadth.** Any entry in `FINDING_CUES` inside a complement now grants authority ("increase", "correlate", "associated"). This is the intended generic rule, but the lexicon is the review's responsibility.

## Retained conservative unknowns (accepted)

- Result-complement unauthorized: T-C, T-D, T-E, O-D, O-E, O-F, O-G, H05, H17, CH02, CH03, CH06, CH07, CH12, P1-over-P2.
- Contrast unknowns from I2-1: R3, R12, R13, CH15, CH16, H06, H11, H16 (repeated term), H19.

## Retained false-negative-looking cases (accepted)

- Bare significance: R4 ("Stress was significant."), R14 ("Building type was significant.") → mentioned, by decision A.
- `linked`: R11 ("…not reliably linked to sleep.") → mentioned, by decision B.
- R10 ("The effect was significant and not spurious.") → mentioned, not positive. It is the review-accepted outcome; it is listed so it is not mistaken for a positive.

## Proof the classifier remains unwired

- Static guard `test_module_is_not_imported_by_any_production_path` passes. Its exclusion list names only the classifier and its three test files.
- `grep` over `experiments`, `app` and `tools` for `category_polarity` finds only the classifier and its tests.
- No sufficiency, recovery, engine, plan, or replay module imports it.

## Byte parity (zero runtime change)

- Mapping, recovery, terminal status, stop-search, ParentClaims, relation units: **12 of 12** byte-identical to the I2-0 pre-change baseline (Attempt-2 run and t5c run).
- Phase 30 replay (Layers 1–3, `answer_plan.json`, audit, authorization, hand audit): **7 of 7** byte-identical.

## Tests

- New I2-1b file (`test_category_polarity_result_complement.py`): **25 passed** (found-that 7, found-to 8, precedence 7, review-revision record, adjective-never-positive, audit field).
- I2-1a hardening (21) and I2-1 original (61): **82 passed**, unchanged expectations.
- Full offline `ask_cli_revised` suite under the network-refusing launcher: **2904 passed, 3 failed, 11 skipped, 2 deselected** (I2-1a total 2879, plus 25 new).
- Pre-existing failures, unchanged and not caused by this change: `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`; `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`; `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`.

Test-only changes: the production-import guard's exclusion list now names the complement test file (the same scoping fix as before). No assertion was loosened.

## Semantic and scientific production gain

**Zero.** The classifier has no runtime authority and no production caller.

## Recommendation for I2-2

**READY for I2-2 review; NOT wired.**

The acceptance criterion holds: no confident positive or null classification in the review batteries lacks contract justification. The known issues are documented and conservative: a frozen-expectation error (CH13, reported, not edited), the P2 and complement-breadth points for review, and the accepted false negatives. Wiring still requires explicit I2-2 approval; this increment does not wire it, bump any version, or change recovery or AnswerPlan. No live run is authorized.
