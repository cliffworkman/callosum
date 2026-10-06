# Phase 32 / I3 — versioned upstream direction-target semantics (sufficiency-semantics-v3)

Starting HEAD: `8d9930c6d126006bfe3f45f8482acb898b5e9e22` (I1d). The final commit is the I3 commit on
`experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`; a report cannot record its own commit hash, so it is read from
`git log`.

Governing invariant: **relation witnessed != relation direction established.** A relation becomes directional only through a
sentence that the shared classifier targets at the relation, inside that relation's own witness. Proximity never suffices.

Status: complete, offline. No model call, no live run, no pin refresh, no frozen-contract change, no frontend change, no
polarity (I2) work, no binder, sealing, described-entity or construct work.

## 1. Version

| version | direction semantics | containment |
|---|---|---|
| v1 (historical) | first direction word per passage; literal sign only; no target; single-operand fallback in the answer layer | case-sensitive |
| v2 (historical) | identical to v1 for direction | case-insensitive (I1d) |
| **v3 (current)** | target-aware observations (`relation` / `operand:<role>` / `unknown` / `none`); relation summary counts only relation-eligible observations; **single-operand fallback removed**; literal valence includes adverbial forms ("negatively associated") | case-insensitive (I1d) |

`SUFFICIENCY_SEMANTICS_VERSION = sufficiency-semantics-v3`. v1 and v2 are readable only through the explicit historical path, and
strict production accepts only v3. The frozen v9 contract is unchanged.

## 2. Shared classifier (one implementation, no dependency inversion)

- **New, top level:** `experiments/ask_cli_revised/direction_target.py`. The answer-layer copy `answer_plan/direction_target.py` was
  removed with `git rm`, so there is one implementation. Git may record this as a rename or as a delete and an add, depending on similarity.
- It depends only on `overview_evidence` (stems) and `sufficiency_engine` (version constants). Neither layer's
  dependency direction is inverted: the sufficiency layer imports it, and so does the answer layer.
- It also owns the single sentence splitter (`split_sentences`), which `answer_plan/text.py` now delegates to, and the literal-sign
  helper (`literal_direction_sign`) and the direction-word test (`has_direction_word`).
- The move changes no behaviour except where I3 explicitly changes it (section 3). The I1b tests migrated to it with explicit
  versions.

## 3. The removed fallback, and the other v3 changes

- **Removed:** the single-operand fallback. A direction word that is unresolved, in a sentence where exactly one operand appears,
  was attributed to that operand (`single_operand_sentence`). Under v3 that sentence is `unknown` (`single_operand_unbound_sign`).
  Under v1/v2 the fallback is retained exactly as recorded, so historical maps reproduce their recorded behaviour.
- **No domain vocabulary was added** to rescue a result. No attitude, belief, questionnaire, bias or emotion lexicon exists.
- **Adverbial valence:** `negatively associated` / `correlated negatively` now carry a literal sign (`negative`). In the sufficiency
  layer, v2 took the sign only from the exact words `positive`/`negative` (`_direction_sign` is a full-word match), so an adverbial
  relation sign was dropped from the summary. The answer layer already read adverbial forms in its classifier. This is part of the v3
  relation semantics and is recorded here rather than presented as incidental.
- **Comparatives carry no literal sign.** "Higher alpha predicted lower beta" targets the relation, but no sign is derived. Deriving
  a relation sign from comparative polarity would be a separate semantic and was not requested (section 12).

## 4. Direction target schema and provenance

Each v3 direction observation (per instance, per direction-bearing sentence of each physical unit):

| field | meaning |
|---|---|
| `target` | `relation`, `operand`, `unknown`, or `none` (`DIRECTION_TARGETS`) |
| `target_role` | the operand role, present only when `target == operand` |
| `target_reason` | the classifier's deterministic reason code |
| `sign` | the single literal valence of the sentence's direction words, or `None` (never inferred from a magnitude word) |
| `relation_eligible` | True only when `target == relation`, `sign` is not None, and the observation's proposition is within the instance's relation witness set |
| `exact_text` | the classified **sentence** (v2 stored the bare direction word) |
| `proposition_id` | the witness proposition when one exists, else the unit's representative |
| `reported`, `required_sign`, `causal_language_present` | unchanged |

No confidence, score, or model-authored target. The constructor rejects inconsistent combinations: an operand target without a
role, a role on a non-operand target, and an invalid target.

## 5. Relation-level attachment invariant

Relation-level direction requires **all** of the following:

- A. the instance is `relation_witnessed` under the applied version (witness recomputed under v3);
- B. the classified sentence is inside the relation's witness evidence (the observation's proposition is in `witness_ids`);
- C. the classifier targets `relation`;
- D. the relational cue lies between the operands (enforced by the classifier).

The sufficiency layer enforces A–C in `relation_eligible`. The answer layer (`answer_plan/classify.py`) enforces the same conditions
through its witnessed unit, its witness-proposition sentence scan, and the shared classifier's cue check. Operand valence is never
converted into relation direction. A sentence whose proposition is not in the witness is never relation-eligible, even when its
target is `relation`.

## 6. Historical dispatch

- `find_direction_observations(..., semantics_version=)` dispatches. v1 and v2 return the recorded historical builder unchanged. v3
  returns the target-aware builder and requires the operand surfaces. An unknown version raises.
- `classify_sentence(..., semantics_version=)` is required. Under v1 and v2 it keeps the fallback. Under v3 it does not. An unknown
  version raises.
- `compute_direction_and_effectiveness(..., semantics_version=)` is required. It refuses a map already stamped with a different
  version (`SemanticsIdentityError`), so a v2 analysis cannot silently run over a v3 map or the reverse.
- Replay applies one rule set to a map: its own recorded version for a current or historical-versioned map, and the contemporary rule
  explicitly for an unversioned map. The applied rule is recorded in the plan (`containment_semantics`, `direction_semantics`) and in
  the authorization (`answer_containment_semantics`, `answer_direction_semantics`). `verify_replay_authorization` checks both against the
  bound identity. The artifact is never attributed v3.
- **Historical reproduction is exact.** The historical-v2 replay of the preserved map reproduces the I1d reference answer plan:
  relation units, nodes, claim roles, step 2 and parent are identical; Layers 1 and 2 are byte-identical; Layer 3 and `answer_plan.json`
  differ only in identity fields (`plan_version` v3→v4, `plan_sha256`, `replay_authorization_sha256`, and the recorded rules).

## 7. PLAN_VERSION

`answer-plan-step2-v3` → **`answer-plan-step2-v4`**. The plan now records `direction_semantics` alongside `containment_semantics`.
This bump is made in the same increment as the shared-classifier change, so the process gap recorded in I1a is not repeated.

## 8. Synthetic matrix (generic alpha/beta; `entity_x` = alpha, `measure_y` = beta)

| # | sentence | expected | observed (v3) |
|---|---|---|---|
| 1 | Alpha was negatively associated with beta. | relation, negative | relation; literal sign negative |
| 2 | Alpha correlated negatively with beta. | relation, negative | relation; literal sign negative |
| 3 | Higher alpha predicted lower beta. | relation (comparative) | relation; **no literal sign** (see section 12) |
| 4 | Alpha was associated with negative beta evaluations. | operand beta negative; no relation direction | operand `measure_y` |
| 5 | Negative alpha was associated with beta. | operand alpha negative; no relation direction | operand `entity_x` |
| 6 | Alpha was associated with beta, and beta scores were negative. | operand beta; no relation direction | operand `measure_y` |
| 7 | Alpha was associated with beta, and negative results were also reported. | unknown; no relation; no attribution | unknown (`unbound_direction_word`) |
| 8 | Alpha was recorded during the task, and negative results were also reported. (one operand) | unknown (fallback removed) | unknown (`single_operand_unbound_sign`); v2 keeps `operand entity_x` |
| 9 | relation-target sentence, relation not witnessed | no relation direction | target relation, `relation_eligible` False |
| 10 | relation witnessed, direction sentence in a different proposition | no relation direction | target relation, `relation_eligible` False |
| 11 | direction sentence inside the verified witness proposition | may attach | target relation, `relation_eligible` True |
| 12 | all-inherited relation (not witnessed) | no relation direction | `relation_eligible` False |
| 13 | conflicting signs | unknown | unknown (`conflicting_signs`) |
| 14 | no direction word | none; no observation | none; no observation emitted |
| 15 | operand valence survives an unwitnessed relation | operand metadata, not relation | operand `measure_y` negative; `relation_eligible` False |
| 16 | single-operand valence sentence | operand; never a relation target | operand `measure_y` |

Operand targets are never relation-eligible, even when witnessed (tested).

## 9. Cross-domain twins

| domain | sentence | expected | observed |
|---|---|---|---|
| architecture | Building height was negatively associated with occupant satisfaction. | relation | relation |
| architecture | Buildings with negative facade ratings were common. | facade (object valence), not relation | operand `facade` |
| architecture | Buildings with negative facade ratings were rated highly. | (see note) | unknown, `ambiguous_operand_target` |
| language | Word frequency positively predicted recall. | relation | relation |
| language | Negative word ratings were associated with recall. | word valence; not a negative relation | operand `word` |

The third architecture row is a deliberate fail-closed case, not a defect. "highly" stems to "high", which is in the existing direction
stem list. A sentence with two direction-bearing words, one of them unresolved, is ambiguous, so the classifier does not choose the
nearest operand. This exposes a real limitation of the existing stem list, which counts magnitude words as direction words. It is
recorded in section 12.

## 10. Preserved Attempt-2 forensic diff (the c6 trace)

Only two direction-declared requirements exist on the preserved map: c5 (relational, sign None) and c6 (relational, `negative`
observed on two unwitnessed instances). Witnessed set and effectiveness are unchanged (section 11).

**c6 exact result.**

| item | v2 (recorded) | v3 |
|---|---|---|
| sentence (instance 1 and 2) | "Nevertheless, we found evidence for the ‘anomalous-is-bad’ stereotype in explicit negative attitudes about people with facial anomalies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire)." | same |
| sign | negative | negative (recorded as provenance) |
| operands realised in the sentence | `attitude_type_or_measure` = "Explicit Bias Questionnaire" only (`named_brain_region_or_network` = "the specific amygdala response" is absent) | same |
| old target (sufficiency) | none (untargeted) | `unknown`, `single_operand_unbound_sign` |
| old target (answer layer, I1d) | operand `attitude_type_or_measure` via the single-operand fallback | `unknown`, `direction_target_unresolved` |
| relation summary (sufficiency) | `negative` (counted from two unwitnessed instances) | empty (not relation-eligible) |
| relation attachment | none (I1b had already suppressed it: unwitnessed) | none |
| direction claim (answer layer) | `value_level`, layer 1, sign negative, subject "Explicit Bias Questionnaire" | `suppressed`, layer 2, `direction_target_unresolved` |
| ParentClaim | `direction_or_effectiveness::97e9b66f0fd3c1c2` | removed (section 11) |

The sentence is still in the evidence: the c6 passage is still displayed in Layer 1 (once), now as category evidence for the attitude
measure. What changed is the claim that the questionnaire measure is itself negatively valenced, which the sentence does not establish
with deterministic structure. That is the expected candidate outcome; it is not a regression.

**c5.** The sign-less observation's sentence changed from the bare word "more" to the full sentence, and its target is `unknown`
(`single_operand_unbound_sign`). Its summary was empty before and is empty after, so no claim changes.

## 11. Sufficiency diff, v2 vs v3, on the same binding set

Two binding sets: the preserved map (`run_i1`) and the deterministic fake-client harness (19 relational instances). In each, the
direction stage ran under v2 and under v3 on copies of the same mapped binding set.

| check | preserved Attempt-2 | harness (fake client) |
|---|---|---|
| mapping without direction fields (bindings, completion, witnesses, provenance) | identical | identical |
| witness fields | identical | identical |
| effectiveness observations and summaries | identical | identical |
| recovery targets | identical | identical |
| stop-search | identical | identical |
| ParentClaims | **21 → 20**: c6 direction claim removed; all 20 shared claims byte-identical | **22 → 20**: c5 and c6 direction claims removed |
| direction observations | gain target fields; c6 observations `unknown`; c5 observation `unknown` | c5 and c6 observations `unknown` |
| direction summary | c6 `negative` → empty | c5 and c6 → empty |
| projected map (direction fields retained) | changed (direction fields) | changed (direction fields) |

The projected-map change is limited to the direction fields. With direction fields removed, the mapping is identical.

## 12. AnswerPlan diff (I1d reference → I3)

Replays of three run directories built from the preserved map (`.local/phase32/i3/runs/`):

- `historical_v2`: direction and witnesses recomputed under v2, stamped v2; replayed with `--allow-historical-versioned`.
- `unversioned_v3`: the preserved map as recorded; replayed with `--allow-historical-unversioned-map` (contemporary v3 applied and recorded).
- `current_v3`: direction and witnesses recomputed under v3, stamped v3; replayed strictly.

| category | historical_v2 vs I1d | unversioned_v3 vs I1d | current_v3 vs I1d |
|---|---|---|---|
| witness units (`relation_units`) | identical | identical | identical |
| node/facet states | identical | changed: c6 direction claim suppressed | changed: c6 direction claim absent |
| direction claims | identical | c6: `value_level` → `suppressed` (`direction_target_unresolved`) | none |
| operand-level valence | identical | removed (c6 "Explicit Bias Questionnaire") | removed |
| ParentClaims | identical (`parent` identical) | c6 direction claim (suppressed) present in answer layer | absent |
| Layer 1 | byte-identical | byte-identical | byte-identical |
| Layer 2 | byte-identical | 2 lines changed (below) | byte-identical |
| Layer 3 | identity lines only | substantive: direction claim role, facet role list (below), identity | substantive: direction claim removed from facet, facet role list (below), identity |
| hashes / identity | `plan_version`, `plan_sha256`, `replay_authorization_sha256` | same, plus `containment_semantics`/`direction_semantics` | same, plus identity |

**Layer 1: no change in any replay.** The c6 passage remains displayed once (`Explicit Bias Questionnaire` appears once in Layer 1 in both
the reference and `current_v3`).

**Layer 2 (`unversioned_v3`), exact before/after.** Before: `-- The same sentence is stated under another item. Source passage (Workman et al., 2021): …Explicit Bias Questionnaire).` After: `+- Not stated as an answer to this item. Source passage (Workman et al., 2021): …Explicit Bias Questionnaire).` The passage is still listed in Layer 2 with the same source text. Only its reason text changed, because the historical stored direction summary still creates a suppressed claim in this mode. The current-version replay has no such change (0 Layer 2 lines changed).

**Layer 3, exact before/after (`unversioned_v3`).**
- before: `` `c6#suff:implicit-explicit-coverage` \| partial \| category_evidence \| … `` ; after: `` `c6#suff:implicit-explicit-coverage` \| partial \| attitude_type_or_measure, category_evidence \| … ``
- before: `` - `direction_or_effectiveness::97e9b66f0fd3c1c2` role=value_level layer=layer1 reasons=- children=['c6'] ``; after: `` … role=suppressed layer=layer2 reasons=['direction_target_unresolved'] … ``

**The facet-role change is traced, not assumed.** `_dedupe_node` collapses identical normalized sentences within a node and carries the
values of the duplicates forward onto the kept render. Under v3 the c6 valence render (the direction claim's sentence) is gone, so the
identical passage's surviving render is the category render, and that render carries the `attitude_type_or_measure` value of the sentence.
The facet's role list therefore reports the role that now owns the displayed sentence. It is an audit-facet change with no effect on
Layer 1 text.

Identity-only changes: `plan_version`, `plan_sha256`, `replay_authorization_sha256`, `inputs.replay_authorization_sha256`, and the new
`containment_semantics` / `direction_semantics` keys.

## 13. Effectiveness parity

Effectiveness observations and summaries are identical under v2 and v3 on the preserved map (`test_effectiveness_is_identical_under_v2_and_v3…`)
and on the harness. The effectiveness path (`find_effectiveness_observations`, `summarize_observations` with no filter) is unchanged. The
shared summary function gained one optional keyword; the default behaviour is the same. Direction and effectiveness share the instance
loop and the summary helper, and that sharing is covered by the parity test rather than assumed.

## 14. Tests and pre-existing failures

- New, `test_direction_target_v3.py`: 37 tests. The 16 specified cases, the four cross-domain twins (plus a fail-closed twin), sufficiency-level
  relation eligibility (witness, proposition membership, unwitnessed, all-inherited, operand-unwitnessed, non-relational), summary and
  ParentClaim filters, constructor invariants, versioned dispatch and fail-closed errors, shared-implementation identity, effectiveness parity,
  and the preserved c6 classification.
- Migrated, `test_direction_target.py` (I1b): the shared implementation with explicit versions. The single-operand test is split into a v3
  test (unknown) and a v2 historical test (operand). Assertions for the other I1b cases are unchanged.
- Updated for the preserved outcome, with the reason stated in each test:
  - `test_answer_plan_replay.py::test_direction_is_only_ever_a_value_level_sentence_with_its_subject`: asserts no value-level valence on the
    preserved map, and keeps the subject invariant for any valence that renders.
  - `test_direction_target.py::test_preserved_direction_claim…`: asserts c6 `suppressed`, `unknown`, `direction_target_unresolved`.
  - `test_answer_plan.py::test_direction_is_value_level_…`: **fixture sentence changed** from "Explicit negative attitudes were found with the
    beta questionnaire." to "Negative beta questionnaire scores were found.". The original is the single-operand pattern the removed fallback
    attributed, so it no longer establishes value-level valence under v3. The new sentence ties the sign to its operand structurally, which
    keeps the test's purpose (a value-level statement that names its own subject).
  - `test_relation_witness.py::test_pipeline_projection_matches_pre_i1_baseline` split into two tests. v2 reproduces the pre-I1 baseline exactly
    (proving the legacy path is intact). v3 pins the mapping-without-direction hash (identical to v2), recovery and stop-search (identical to
    the baseline), and the new projection and ParentClaim hashes, with the two removed direction claims asserted by kind and count.
- Pinned to v2 (historical builder): `test_sufficiency_direction_effectiveness.py` (two tests), `test_sufficiency_mapping.py` (two tests).
- Migrated call sites: all 14 callers of `compute_direction_and_effectiveness` pass the current version explicitly.

Verification gates run for this increment:
- targeted: I3 new tests, I1b migrated tests, I1/I1a/I1c/I1d tests, sufficiency tests, answer-plan tests, parent-synthesis tests:
  **866 passed** in the first pass, and the two remaining legacy-pin failures were fixed and re-run (98 passed in the mapping file);
- preserved offline replay: the three replays in section 12 complete;
- deterministic same-binding comparison: section 11 (preserved and harness);
- broader offline suite under network refusal: see section 14a.

## 14a. Full offline suite

Result: **2780 passed, 11 skipped, 3 failed** (278 s). The 3 failures are the same pre-existing failures as the I1c and I1d baselines, by name (section 15). No new failure. The pass count rose from 2741 (I1d) by 39: the 37 new I3 tests, one extra from splitting the pipeline projection test in two, and one extra from splitting the single-operand classifier test.

## 15. Pre-existing failures

The same three failures as the I1c and I1d baselines, unchanged by name:
- `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`
- `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`
- `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`

## 16. Anti-fitting statement

- The specification was written before the classifier change, and the synthetic expectations were fixed from it. Two expectations were
  checked against the classifier's behaviour and not adjusted to match it. Case 3 (comparative) is target `relation` with no sign, which is
  the honest reading of the rule. Twin 3 ("highly") is fail-closed, because the existing stem list counts a magnitude word.
- The c6 outcome is an expected candidate outcome, not a regression, and it was not tuned to preserve the old statement. The classifier was not
  changed to recover the single-operand attribution, and no domain lexicon was added.
- Test changes that touch preserved behaviour are listed in section 14 with their reasons. The `test_answer_plan` fixture change replaces a
  sentence that exercised the removed fallback; it does not weaken the subject invariant.
- Zero or near-zero effects were reported as they occurred (Layer 1 unchanged in every replay; witness, effectiveness, recovery and
  stop-search unchanged on both binding sets).

## 17. READY / NOT READY for I2

**READY to begin I2 (observation polarity and goal-specific satisfaction), subject to two recorded follow-ups** that I2 must not paper over:

1. **Comparative relation sign.** A comparative pair ("higher X predicted lower Y") targets the relation but carries no sign, so it is never
   relation-eligible and never summarised. Deriving a relation sign from comparative polarity is a separate, deliberate semantic. It needs its
   own decision and version, and it should not be introduced inside I2.
2. **Magnitude words in the direction stem list.** The existing stems count magnitude words ("high", "more", "less") as direction words, which
   can make an otherwise clear sentence fail closed (twin 3). Whether those stems should be direction-bearing is a semantic decision for the
   shared module, not a fix to smuggle into I2.

I2 must not begin until those are recorded as decisions. Live E2E remains **not** authorized. Direction semantics are now repaired upstream,
but the comparative sign and magnitude-stem questions are open, and the preserved run has no relation-eligible direction to validate against.
