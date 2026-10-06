# Phase 33 / I2-1 — pure observation-polarity classifier (unwired)

## Heads

- Starting HEAD: `494da028` (I2-0, pushed; origin equal).
- Final HEAD: the I2-1 commit that adds this file (see `git log`).

## Files changed

- New: `experiments/ask_cli_revised/category_polarity.py` (the classifier; pure, unwired).
- New: `experiments/ask_cli_revised/test_category_polarity.py` (the expectations and invariants).
- New: this results artifact.
- Lineage: `CONTRIBUTION-LINEAGE.md` (appended entry; earlier bytes unchanged).

No production module changed. No frozen contract, pin, frontend, or `app/` file changed. No version constant changed: `SUFFICIENCY_SEMANTICS_VERSION` stays v3 and `PLAN_VERSION` stays `answer-plan-step2-v4`.

## Classifier API and schema

```python
classify_category_observation(text: str, term: str, *, competing_terms: tuple[str, ...] = ()) -> dict
```

- Explicit inputs only. No I/O, no model, no network, no version lookup, no domain vocabulary, no mutation.
- Output is a JSON-serialisable dict with stable keys: `classifier` (`observation-polarity/i2-1`), `term`, `competing_terms`, `term_occurrences`, `observation_polarity`, `rule`, `ambiguity`, `matched_surface`, `sentence`, `term_clause`, `contrast_clause`, `contrast_connective`, `finding_cues`, `directional_cues`, `measurement_cues`, `null_cues` (`negation`, `self_null`, `complement`), `competing_terms_in_contrast`, `hedge`, `absence_statement`, `occurrence_results`.
- No score, confidence, or probability key. `contrary_finding` is reserved and never returned (asserted by a test over every input).
- `observation_polarity` is one of `positive_finding`, `null_finding`, `mentioned_only`, `unknown`.

## Cue vocabularies (exact)

- **Negation cues** (`NEGATION_CUES`): not, no, never, neither, nor, without, fail, failed, fails, lack, lacked, lacks. A token ending in `n't` is normalised to `not`.
- **Self-null cues** (`SELF_NULL_CUES`): non-significant, nonsignificant. Treated as null on their own.
- **Complement cues** (`COMPLEMENT_CUES`, significance/effect class): significant, significantly, significance, effect, effects, association, associations, correlation, correlations, difference, differences, relationship, relationships, evidence.
- **Finding/assertion cues** (`FINDING_CUES`): generic past, third-person and base forms of observed, found, showed, shown, demonstrated, revealed, expressed, detected, reported, correlated, associated, predicted, differed, responded, exhibited, identified, produced, reduced, increased, decreased, improved, affected, influenced, altered, changed, lowered, raised (and their base and third-person forms). Valence and magnitude words are excluded.
- **Directional cues** (`DIRECTIONAL_CUES`): the finding cues plus lower, higher, more, less. Used only to decide whether a negation without a complement is unknown rather than procedural.
- **Measurement/procedure cues** (`MEASUREMENT_CUES`, reported, never evidence): measured, assessed, included, recruited, administered, collected, tested, used, examined, reviewed, described, mentioned (and forms).
- **Hedge cues** (`HEDGE_CUES`, reported, never polarity): may, might, could, possibly, perhaps, probably, likely, suggest(s/ed), appear(s/ed), seem(s/ed), tentatively, preliminarily.
- **Absence pattern** (reported, never null): "no studies/study/research/evidence/data" and "did/do/does/has/have not <examine-type verb>".
- **Clause boundaries** (`_BOUNDARY_RE`): comma, semicolon, colon, but, whereas, although, though, while, however, yet. **"and" is not a boundary.** "slight and not significant" stays in one clause.
- **Ellipsis connectives** (for the carryover rule only): but, whereas, although, though, yet.
- **Sentence splitter**: the shared generic `direction_target.split_sentences`. Its clause splitter is not used.

Infinitive guard: a finding or directional cue directly after `to` is excluded (for example "was used to predict"), so procedure is not read as an asserted result. This is fail-closed.

## Exact classification order (per term occurrence)

Sentence scope first: only the sentence containing the occurrence is read. Then the term clause (the clause containing the occurrence) is classified:

1. A `not only`, `not less` or `no less` pair in the term clause: **unknown** (`not_only_construction`).
2. Two or more negation cues (negation plus self-null counted together): **unknown** (`multiple_negation_cues`).
3. A self-null cue and no negation cue: **null** (`self_null_adjective`).
4. One negation cue:
   - a complement cue within three tokens: **null** (`local_null_same_clause`);
   - otherwise, if a finding or directional cue is present: **unknown** (`negation_without_significance_complement`);
   - otherwise: **mentioned_only** (`procedural_or_mention_negation`).
5. No negation in the term clause. Examine the immediately following clause:
   - if it is negated and mentions no competing term, and the term clause has a finding cue:
     - narrow ellipsis (the connective is but/whereas/although/though/yet, and the clause is exactly `not` plus one complement cue): **null** (`narrow_ellipsis_null`);
     - otherwise **unknown** (`unresolved_contrast_negation`);
   - if it is negated, mentions no competing term, and the term clause has no finding cue: **unknown** (`unattached_contrast_negation`).
6. Otherwise a finding cue in the term clause: **positive** (`local_finding_predicate`); none: **mentioned_only** (`no_finding_predicate`).

Repeated occurrences (two or more of the term in the text): **unknown** (`repeated_term_occurrence`), with each occurrence's own result in `occurrence_results`. No occurrence is selected. Absent term: **unknown** (`term_absent`). A term spanning a clause boundary: **unknown**.

Term matching is case-insensitive substring, the same as the current mapper. The token-boundary repair is not in I2-1.

## Ellipsis rule

Only the narrow pattern carries a finding predicate across a clause boundary: the term clause has a finding cue, and the immediately following clause, reached through an ellipsis connective, is exactly `not` plus one complement cue. "Treatment reduced pain, but not significantly." → null for pain. Any other carryover is unknown. The contrast-negation test does not depend on the carried predicate's type, so a negated clause with its own subject is unknown, not positive.

## Approved matrix (A–P): hard requirements, all pass

| row | expected | result | rule |
|---|---|---|---|
| A-null | null | null | narrow_ellipsis_null |
| A-pos | positive | positive | local_finding_predicate |
| B-null | unknown | unknown | unattached_contrast_negation |
| B-pos | positive | positive | local_finding_predicate |
| C-null | unknown | unknown | unattached_contrast_negation |
| C-pos | positive | positive | local_finding_predicate |
| D-val ("negative evaluations", expressed) | positive | positive | local_finding_predicate |
| D-val-term ("negative") | positive | positive | local_finding_predicate |
| D-val2 ("were negative") | mentioned | mentioned | no_finding_predicate |
| E-proc | mentioned | mentioned | procedural_or_mention_negation |
| F-p36 explicit (competing `implicit`) | positive | positive | local_finding_predicate |
| F-p36 implicit | null | null | local_null_same_clause |
| G | unknown | unknown | negation_without_significance_complement |
| H (hedged) | null | null | local_null_same_clause, hedge true |
| I (negation in next sentence) | positive | positive | local_finding_predicate |
| J-null / J-pos (each observation alone) | null / positive | null / positive | self/local null; local finding |
| K | unknown | unknown | multiple_negation_cues |
| L | unknown | unknown | not_only_construction |
| M | mentioned | mentioned | procedural_or_mention_negation, absence true |
| N (measured / assessed / included) | mentioned | mentioned | no_finding_predicate |
| O | unknown | unknown | unresolved_contrast_negation |
| P | null | null | local_null_same_clause |

The aggregation in J is not implemented here: each observation is classified alone, as required.

## Adversarial minimal pairs: all pass

| pair | expected | result |
|---|---|---|
| association positive / no association found | positive / null | positive / null |
| negative evaluations observed / evaluations were negative | positive / mentioned | positive / mentioned |
| measured / found to predict | mentioned / positive | mentioned / positive |
| did not predict / no predictive effect was found | unknown / null | unknown / null |
| may predict (hedged) / may not significantly predict (hedged) | positive / null | positive / null |
| not only significant but large / negation in an unrelated sentence | unknown / positive | unknown / positive |

## Cross-domain twins (same rules): all pass

Clinical/treatment, agriculture, education (with and without a competing sibling term), materials science, and language/cognition. No runtime domain branch exists; the module source contains no domain vocabulary (asserted).

## Repeated-term behaviour

Two occurrences of a term in a text return unknown with `rule = repeated_term_occurrence`, and report each occurrence's classification in `occurrence_results`. The classifier does not choose the occurrence that gives the preferred result (tested: "Anxiety was measured. Anxiety predicted sleep." → unknown, with mentioned and positive reported per occurrence).

## Property and invariant tests (all pass)

- Deterministic output; JSON round-trip; no float value; no confidence/score/probability key.
- `contrary_finding` never emitted (over every test input).
- Letter-case change alone does not change polarity (uppercase and lowercase variants).
- Negation in an unrelated sentence does not change the term's result (either order).
- Adding a valence word alone cannot turn mentioned-only positive.
- Adding a measurement verb alone cannot turn mentioned-only positive.
- Adding a local finding predicate can.
- Procedural negation cannot become null merely because of "not".
- Hedge toggle alone does not change polarity.
- Absence statements are scope, not null.
- Empty term refused; absent term reported.
- Static guards: the module imports no sufficiency or plan module, contains no `SUFFICIENCY_SEMANTICS` or `PLAN_VERSION`, performs no I/O or network call, and contains no domain vocabulary.
- **Unwired guard:** no file under `experiments/ask_cli_revised` other than the classifier and its test mentions `category_polarity`; no `app/` or `tools/` file does either.

## Residual battery (generated before the first run; reported, not asserted)

Expectations were the intuitive reading, written before the module was implemented or run. Results: **7 match, 8 mismatch, out of 15**.

| id | sentence (term) | expected | got | rule | lexical cause |
|---|---|---|---|---|---|
| R1-lowered | Drug X lowered anxiety scores. | positive | positive | local_finding_predicate | matched (`lowered` is a finding cue) |
| R2-did-not-lower | Drug X did not lower anxiety scores. | unknown | unknown | negation_without_significance_complement | matched |
| R3-not-associated | Drug X was not associated with anxiety scores. | null | **unknown** | negation_without_significance_complement | **FN-looking/conservative**: a negated finding verb without a complement noun is not null (by contract) |
| R4-significant-alone | Stress was significant. | positive | **mentioned** | no_finding_predicate | **FN-looking**: bare `significant` is not a finding cue |
| R5-found-in-database | The sample was found in the database. | mentioned | **positive** | local_finding_predicate | **FP-looking**: `found` used procedurally; lexical ambiguity of a finding verb |
| R6-and-clause-null | Anxiety predicts sleep and stress was not significant. (stress) | null | null | local_null_same_clause | matched |
| R7-not-reduced-by | Anxiety was not reduced by sleep. | unknown | unknown | negation_without_significance_complement | matched |
| R8-did-not-find | Participants did not find stress. | unknown | unknown | negation_without_significance_complement | matched |
| R9-two-negations | Stress was not measured and was not significant. | unknown | unknown | multiple_negation_cues | matched |
| R10-not-spurious | The effect was significant and not spurious. (effect) | positive | **null** | local_null_same_clause | **FP-looking**: `and` is not a boundary (required so that "slight and not significant" stays whole); the negation governs `spurious`, which the window cannot tell |
| R11-linked-procedural | Stress was low and not reliably linked to sleep. | unknown | **mentioned** | procedural_or_mention_negation | **FN-looking**: `linked` is not a cue; a negated relation verb with no cue is classed as procedural |
| R12-but-not-nausea | Sleep was affected, but not stress. (sleep) | positive | **unknown** | unresolved_contrast_negation | **conservative**: the negated clause has no complement cue, so carryover fails closed |
| R13-raised-then-contrast | Fertilizer raised yields, whereas irrigation did not. | positive | **unknown** | unresolved_contrast_negation | **conservative**: contrast clause has its own subject with no complement cue |
| R14-was-significant-only | Building type was significant. | positive | **mentioned** | no_finding_predicate | **FN-looking**: bare significance is not a finding predicate |
| R15-to-predict-procedural | The model was used to predict sleep. | mentioned | mentioned | no_finding_predicate | matched (infinitive guard) |

Classification of the residuals:
- **False-positive-looking:** R5 (`found` as a procedural verb), R10 (coordination with `and`, forced by the boundary contract).
- **False-negative-looking:** R4 and R14 (bare `significant` is not a predicate), R11 (negated relation verb not in the lexicon).
- **Conservative unknowns** (defensible under fail-closed): R3, R12, R13.
- None of the eight is a violation of the written contract. R10 is the only one that exposes a genuine structural tension (the window rule with no `and` boundary). It is recorded, not tuned around.

## Changes made after the first empirical pass, and why

1. **Test-only fix:** the invariant "no confidence/score/probability" first string-matched the whole JSON, and failed on the echoed input word "algebra scores". The assertion now checks the output keys. The classifier was not changed.
2. **Before the first run (recorded for transparency):** `lower` moved from the finding cues to the directional-only set, because magnitude words are never evidence predicates. This was done before the battery was run.

No tuning was done to satisfy a residual. No cue was added after the first run.

## Proof the classifier remains unwired

- The static guard test (`test_module_is_not_imported_by_any_production_path`) passes.
- `grep` over `experiments`, `app` and `tools` for `category_polarity` finds only the classifier and its test.
- The sufficiency, recovery, engine, AnswerPlan and replay modules are unchanged (the diff touches only the two new files and the lineage).

## Production and replay byte parity

Re-captured after the I2-1 files were added:
- Offline mapping capture for the preserved Attempt-2 run and the t5c run: mapped map, recovery targets, terminal status, stop-search and recovery states, ParentClaims, and relation units: **12 of 12 byte-identical** to the I2-0 pre-change baseline.
- Preserved Phase 30 replay (Layers 1–3, `answer_plan.json`, audit, authorization, hand-audit comparison): **7 of 7 byte-identical** to the pre-change baseline.

## Test counts

- New I2-1 tests: **61 passed** (approved matrix, adversarial pairs, cross-domain, invariants, repeated term, absent term, empty term, static guards).
- I2-0 threading, sufficiency mapping/engine/recovery, answer-plan (plan, step 2, replay), and preserved v9 replay subset: **301 passed**.
- Full offline `ask_cli_revised` suite under the network-refusing launcher: **2858 passed, 3 failed, 11 skipped, 2 deselected** (2797 at I2-0 plus the 61 new tests).

## Pre-existing failures (unchanged, not caused by I2-1)

1. `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`
2. `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`
3. `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`

The same three as the I2-0 baseline, by name.

## Semantic and scientific production gain

**Zero.** The classifier has no runtime authority and no production caller. Mapping, completion, recovery, terminality, cardinality, ParentClaims and AnswerPlan are byte-identical to I2-0.

## Limits of the closed-vocabulary approach (for review)

- A closed finding list cannot separate procedural from scientific uses of a finding verb (R5). Widening it for recall would reintroduce the valence problem the contract removes.
- Bare significance is not an assertion in this lexicon (R4, R14). Adding it is a lexicon decision for review, not a classifier fix.
- The window rule cannot see coordination without an `and` boundary (R10). A coordination-aware scope is a structural extension, not a lexicon change.
- Carryover is deliberately narrow: most contrast-negation cases are unknown (R12, R13, O). That is the intended fail-closed behaviour.
- Term matching remains substring (for example "pain" in "painful"). The token-boundary repair is deferred.

## Recommendation

**READY for review, NOT READY to wire.**

- I2-2 may be considered only after this classifier's lexicon and the residual list are reviewed. The review should decide whether bare significance counts as a finding (R4, R14), whether to add a coordination-aware scope (R10), and whether the procedural-finding ambiguity (R5) is acceptable as a documented limit.
- I2-2 must not begin on the strength of the 61 passing tests alone; the residual list is part of the evidence.
- No live run is authorized.
