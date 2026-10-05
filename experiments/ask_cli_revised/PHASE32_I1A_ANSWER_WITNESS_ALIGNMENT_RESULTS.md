# Phase 32 — I1a: answer-layer relation-witness alignment (results)

**Status: implemented and verified offline. Committed only if the gates in §11 pass.**

## 0. Starting and final HEAD

- Starting HEAD: `ed476da7b468dad95cdb3c6aef87dfa48ed4f9fb` (I1 commit). Branch
  `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`, local == origin, clean at start.
- The I1a commit hash is given in the handback, not in this file, since a file cannot contain the hash of the commit that adds it.

## 1. Exact files changed

| file | change |
|---|---|
| `experiments/ask_cli_revised/answer_plan/relations.py` | rewritten to derive witnesses through `relation_witness.witness_instance`; validates stored upstream metadata; separates witnessing from renderability |
| `experiments/ask_cli_revised/answer_plan/plan.py` | one line: `rel.relation_units(smap, sealed)` (the sealed ledger is already a parameter of `build_plan`) |
| `experiments/ask_cli_revised/relation_witness.py` | `support_ids` made public (single definition shared with the answer layer); module documentation updated |
| `experiments/ask_cli_revised/test_answer_plan.py` | the proposition fixture now carries the sealed `status: "verified"` that real rows always have; the direction test is split into a witnessed case (documents the attachment) and a value-level case (unchanged intent) |
| `experiments/ask_cli_revised/test_relation_witness.py` | I1 legacy-characterization tests converted to agreement tests with hand-written expectations; preserved cross-check now compares ids and metadata anomalies |
| `experiments/ask_cli_revised/test_answer_witness_alignment.py` | new: 21 I1a tests (semantics, historical maps, metadata validation, preserved sets) |
| `experiments/ask_cli_revised/PHASE32_I1A_ANSWER_WITNESS_ALIGNMENT_RESULTS.md` | new (this file) |
| `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` | one appended Phase 32 I1a section; earlier entries byte-identical |

Not changed: frozen contracts, nomination authorizations, hierarchy and e2e contracts, pins, `app/frontend/`, `complete`, recovery, stop-search, the direction rule in `classify.py`, rendering prose.

## 2. Old answer-layer semantics (Phase 30, `relations.py` at HEAD)

- Witness = intersection of `support` over **all** filled operands, **including** `parent_context` operands. Parent support therefore had to be shared by the child's own evidence.
- No admissibility check on the candidate proposition; no referent containment.
- Status: `witnessed` iff the intersection is non-empty and `complete`; `unwitnessed_complete` iff `complete` without a witness; otherwise `incomplete`.

## 3. New aligned semantics

- Witness comes from `relation_witness.witness_instance`, the section-7 rule: at least one OWN operand; one admissible verified child proposition supports every OWN operand and realises every INHERITED referent surface by canonical containment; no distributed witness; the parent proposition id never witnesses; an all-inherited relation never witnesses; an unverified join never witnesses.
- Status keeps the same vocabulary, but **renderability is separate from witnessing**: `witnessed` requires the witness **and** all operands filled **and** `complete`. A witnessed but incomplete relation is `incomplete`, never `unwitnessed_complete`.
- Stored upstream metadata is validated, not trusted. A disagreement, a stale provenance reason, or a malformed record marks the unit `metadata_check` (`disagrees` or `malformed`) and sets `status = "incomplete"` (fail closed). The unit key is added only on an anomaly, so consistent preserved output is unchanged.
- Historical maps without I1 fields follow the same derivation. Their units are identical to those of stamped maps.

## 4. Code sharing (no duplicate of the rule)

- `relations.py` imports `relation_witness.witness_instance`, `support_ids` and `operand_source`. It contains no second copy of the witness logic.
- The independent cross-check of I1 is no longer independent: both sides call the same function. What replaces it:
  - **Stored-vs-derived validation** at answer time, for every relational instance, including the preserved run (§6).
  - **Hand-written expectations** in the tests. They are written from the §7 rules and are not read back from either implementation.
  - **Byte-level preserved-run parity** (§7). This is the primary behavioural gate.

## 5. The three former divergence cases, now agreement tests

| case | §7 result (hand-written) | I1 legacy (before) | I1a answer layer (after) |
|---|---|---|---|
| 1. inherited alpha + child OWN beta proposition asserting the relation | witnessed, `["C1"]` | not witnessed | **witnessed, `["C1"]`**, status `witnessed` |
| 2. verified joined child proposition with both operands | witnessed, `["J"]` | not witnessed | **witnessed, `["J"]`**, status `witnessed` |
| 3. all-inherited operands sharing one parent proposition | not witnessed | witnessed | **not witnessed**, status `unwitnessed_complete` |

The legacy characterization tests were removed once the aligned implementation passed the same generic fixtures. They are now
agreement tests (`test_upstream_and_answer_layer_both_implement_the_section7_expectation`,
`test_all_inherited_shared_parent_is_not_witnessed_by_either_layer`).

## 6. Upstream-versus-answer-layer agreement (preserved map)

- Relational instances: **36**.
- Boolean disagreements: **0**. Witness-id disagreements: **0**.
- Units carrying a `metadata_check` anomaly: **0**.

## 7. Preserved witnessed and unwitnessed sets (answer layer)

- **Witnessed (6):** c4 region `…e60509ac4c8b` by `p11`; c8 trait ×5 by `p41`.
- **Unwitnessed, engine-complete (4):** c5 brain-behavior ×2; c6 brain-attitude ×2.

These sets are identical before and after I1a. They are recorded here as the preserved regression, and no logic is tuned toward them.

**Witness validity remains conditional on operand-binding validity.** The c8 witnesses are structural. The trait operand is
still mis-typed (ratings of faces bound as traits of perceivers), which is the described-entity work, not I1a. Rendering is
unaffected: the answer layer still refuses to state node 5.

## 8. Preserved-run parity (zero effect, hard gate)

Replay on the preserved map with I1 fields (`.local/phase32/run_i1/`), baseline (pre-I1a, HEAD `ed476da7`) versus post-I1a:

| artifact | result |
|---|---|
| `deterministic_layer1.md` (Layer 1) | **byte-identical** |
| `deterministic_layer2.md` (Layer 2) | **byte-identical** |
| `deterministic_layer3.md` (Layer 3) | **byte-identical** |
| `answer_plan.json` (node states, facet states, claim roles, relation units, ParentClaim ids and payloads) | **byte-identical** (structural difference count 0) |
| `answer_plan_audit.json` | **byte-identical** |
| `replay_decomposition_authorization.json` | **byte-identical** |
| `comparison_against_phase29_hand_audit.md` | **byte-identical** |

Because the plan and authorization files are byte-identical, `plan_sha256` and the replay authorization hash are unchanged
from the I1 values (`43474527ae40623ea609da98b0effb3b9c7a0376513f845baaede8d9a6bed234` and
`4ed0e5a542354a8b24c9b72c53a6c476489814cc1f75090ad7b45211bf493e85`).

The pipeline projection parity from I1 still holds on the final code: projected map `fff5e6fc…`, ParentClaims `1070dde9…`,
recovery `e051a8df…`, stop-search `cdcd5c4a…`, all identical to the pre-I1 baseline. The projected pipeline file is byte-identical.

## 9. Historical compatibility

- Synthetic: the unit from a map without I1 fields equals the unit from a stamped map, and carries no `metadata_check`.
- Preserved: units computed without stored metadata equal units computed with it (test `test_preserved_units_are_identical_with_and_without_stored_metadata`).

## 10. Metadata validation (fail closed)

| tampering | result |
|---|---|
| flag contradicts derivation | `metadata_check = disagrees`, status `incomplete`, claim not witnessed |
| stale `witness_ids` | `disagrees`, `incomplete` |
| stale `failure_reason` in provenance | `disagrees`, `incomplete` |
| `witness_ids` not a list | `malformed`, `incomplete` |
| only one of the two keys present | `malformed` |
| stale stored ids present, derivation consulted | unit carries the **derived** ids (`["C1"]`), not the stale value |

## 11. Tests and gates

| gate | result |
|---|---|
| I1 and I1a modules | **53 passed** (32 I1 + 21 I1a) |
| answer-plan tests (`test_answer_plan.py`, `_step2.py`, `_replay.py`) | **53 passed** (includes the new direction-case split) |
| affected sufficiency tests plus the above | **589 passed** |
| preserved offline replay | **byte-identical** on all seven answer outputs (§8) |
| projection parity | **exact** (§8) |
| ParentClaims, recovery, stop-search | **unchanged** (§8) |
| Layer 1 and Layer 2 | **byte-identical** |
| frozen contracts, nomination authorizations, pins, frontend | **untouched** |
| broader `ask_cli_revised` offline suite under network refusal | **3 failed, 2670 passed, 11 skipped** (in 189 s) |
| failure set versus pre-change baseline | **identical** (the same three test ids) |

Pre-existing failures (unchanged, unrelated to I1a, present at HEAD before any Phase-32 change):
- `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`
- `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts` (pin drift)
- `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`

Count arithmetic: 2616 (pre-change baseline) + 32 (I1) + 21 (I1a) + 1 (direction-case split) = 2670.

Lint and format: ruff check and ruff format clean on every changed Python file.

## 12. One consequence found and not resolved here: direction attachment through a newly witnessed relation

Aligning the witness to section 7 widens which relations are witnessed. The direction rule in `classify.py` attaches a
direction to any witnessed relation whose witness shares a proposition with the direction observation. That rule is unchanged.

Concrete synthetic case: the inherited referent `alpha` is realised in the child passage "Explicit negative attitudes toward
alpha were found with the beta questionnaire." The relation is now witnessed, so the sign "negative" attaches to the relation.
The sign actually describes the attitude toward `alpha`, not the relation between `alpha` and the questionnaire. This is failure
D's over-attachment. The legacy rule happened to block it, because the parent proposition was not shared.

- The preserved run is **unaffected**: its direction observations are on unwitnessed relations, and parity is byte-identical.
- The test `test_direction_attaches_only_through_a_witnessed_relation_and_names_its_subject` now asserts the attachment that
  section-7 witnessing produces, with an explanatory comment. A separate test covers the value-level path, where the referent
  is not realised.
- The design answer is the direction target (I3): the sign's object is determined, so a relation-level direction is attached only
  when the sign modifies the relation rather than one operand. That is a semantic change, so it is out of I1a's scope.

**Decision needed before I2:** whether I3 (direction target) must land before any aligned witness is used for direction claims.
On the preserved data this is not yet a live issue. It becomes live once real data contains a child passage that re-finds an
inherited referent alongside a valence sign.

## 13. Scientific gain

**Zero on the preserved run.** Layer 1, Layer 2 and Layer 3 are byte-identical, and no node, facet, claim or ParentClaim changed.
The alignment changes which synthetic relations are witnessed. It does not produce a new scientific answer on the preserved run.

## 14. Recommendation

- **I1a: READY for commit under the gates in §11**, with the direction consequence in §12 documented.
- **I2: NOT READY.** Two prerequisites remain, in order:
  1. Decide whether direction-target work (I3) must precede any aligned direction claims (§12).
  2. Approve and implement the sufficiency semantic-version identity (audit §17) before any polarity or completion change, per the
     instruction that versioning must not be combined with I2.
- I1a does not authorize I2. Nothing in I2 (polarity, completion, recovery, measured-null) has been started.
