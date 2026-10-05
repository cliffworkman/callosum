# Phase 32 — I1: additive relation-witness metadata (results)

**Status: implemented, verified offline, and approved for commit under the revised gates (§12).**
The earlier hold is resolved. D6 is decided in favour of the Phase-31 §7 semantics, and the universal cross-check gate is
replaced by the revised gate in §7.

## 0. Starting and final state

- Starting HEAD: `e886bf731d7b471f8dfea24802f232020aae4f54` (Phase 31 commit), branch
  `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`, local == origin, tree clean at start.
- The I1 commit hash is given in the Phase-32 handback, not in this file, since a file cannot contain the hash of the commit that adds it.

## 1. Exact files changed

| file | change |
|---|---|
| `experiments/ask_cli_revised/sufficiency_diagnostic.py` | +4 lines: import `relation_witness as rw`; one call `rw.attach_relation_witnesses(mapped, sealed)` at the end of `compute_diagnostic_sufficiency_map` |
| `experiments/ask_cli_revised/relation_witness.py` | new: pure module. No network, no model, does not read or write `complete` |
| `experiments/ask_cli_revised/test_relation_witness.py` | new: 32 tests (synthetic invariant, legacy characterization, preserved-artifact regression, pipeline parity) |
| `experiments/ask_cli_revised/PHASE32_I1_RELATION_WITNESS_RESULTS.md` | new (this file) |
| `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` | one appended Phase 32 section; earlier entries byte-identical |

Not changed: frozen contracts, nomination authorizations, hierarchy and e2e contracts, pins, `app/frontend/` (including
`20_synthesis.jsx`), `answer_plan/` (the answer layer, including `relations.py`), `complete`, recovery, stop-search, direction,
rendering. Scratch harnesses live in `.local/phase32/` (gitignored) and are not part of the commit.

## 2. Runtime schema added (relational instances only)

A relational instance is an instance of a requirement with two or more required roles, the same set the answer layer's
relation units cover. Non-relational instances receive **no** new keys. Each relational instance gains:

- `relation_witnessed`: bool.
- `witness_ids`: sorted proposition ids that witness the relation (empty unless witnessed).
- `witness_provenance`: a deterministic dict with
  - `rule`: `"operand_source_witness"` (a label, not a version);
  - `own_roles`, `inherited_roles`: sorted role names, classified by operand source;
  - `own_support`: `{role: sorted support ids}` for each OWN operand;
  - `inherited_referents`: `{role: parent exact_text checked}` for each INHERITED operand;
  - `candidate_ids`: sorted intersection of OWN supports;
  - `candidate_checks`: per candidate `{proposition_id, admissible, inherited_referent_present: {role: bool}}`;
  - `failure_reason`: `null` when witnessed, else one of `incomplete_operands`, `no_own_operand`, `no_single_proposition`,
    `no_admissible_candidate`, `inherited_referent_absent`.

No confidence or score field exists. A test asserts this.

## 3. Invariant implemented (Phase-31 §7, authoritative per D6)

Operand source: OWN = binding source is not `parent_context`; INHERITED = binding source is `parent_context`.

`relation_witnessed` iff:
- **A.** at least one OWN operand exists, and
- **B.** one admissible verified proposition `p` (a) belongs to every OWN operand's admissible support set, and (b) contains every
  INHERITED referent surface by the existing canonical containment rule, using the parent binding's verbatim `exact_text`
  (not normalised).

Enforced in code:
- The parent proposition id never witnesses. Candidates come only from OWN supports, so a proposition reached only through
  parent context is never a candidate unless the child's own mapping admits it.
- No distributed witness: a single `p` must satisfy all operands.
- Admissibility: `status == "verified"`; a continuation join is admissible only if every recorded anchor has `verbatim: true`.
  All 54 sealed propositions in the preserved ledger are `verified`; its 6 joins carry verbatim anchors.
- Model nomination is never a witness: only sealed propositions and bindings are read.
- All-inherited guard: with no OWN operand the relation is never witnessed, however the inherited surfaces co-occur.

## 4. Six synthetic cases (generic alpha/beta, no question vocabulary)

| # | case | expected (§7) | observed | failure_reason |
|---|---|---|---|---|
| 1 | parent supplies alpha; child OWN beta proposition asserts alpha relates to beta | witnessed | witnessed, `witness_ids=["C1"]` | — |
| 2 | parent supplies alpha; child OWN beta proposition mentions beta only | not witnessed | not witnessed | `inherited_referent_absent` |
| 3 | parent proposition mentions alpha and beta; child evidence does not establish the relation | not witnessed | not witnessed; `P3` not a candidate | `inherited_referent_absent` |
| 4 | alpha and beta in separate child propositions | not witnessed | not witnessed | `inherited_referent_absent` |
| 5a | verified joined child proposition contains both operands | witnessed | witnessed, `witness_ids=["J"]` | — |
| 5b | identical join with an unverified anchor | not witnessed | not witnessed | `no_admissible_candidate` |
| 6 | all operands inherited; child passage co-mentions both; no verifier | not witnessed | not witnessed | `no_own_operand` |

Additional invariant tests (all passing): unfilled required operand → `incomplete_operands`; two OWN operands in separate
propositions → `no_single_proposition`; two OWN operands in one proposition → witnessed; support-id order and duplicate support
ids do not change the result; provenance is deterministic and JSON-serialisable; no score or confidence field; non-relational
instances receive no I1 keys; attaching changes only the three I1 keys (`complete` and bindings unchanged); the parent's
proposition witnesses only when the child's own mapping independently admits it.

## 5. Projection parity (hard gate, passing)

**Projection** `π`: remove exactly `relation_witnessed`, `witness_ids`, `witness_provenance` from every instance of every
requirement. Serialise with `sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str` and hash with SHA-256.

**Pipeline parity** (`.local/phase32/harness.py`): the real mapping, direction/effectiveness, ParentClaim ledger, recovery and
stop-search functions, on the preserved sealed ledger, with a deterministic fake nomination client named
`fake-phase32-harness`. The mapper copies that name into provenance, so it is part of the baseline identity. No network, no model.

| output | pre-I1 baseline (HEAD e886bf73) | post-I1 (final code) | result |
|---|---|---|---|
| projected map `π(map)` | `fff5e6fc2129f038a0cd0cb1de34f478feef3bbdfa8ce10f1fe9c951890f2074` | same; projected file byte-identical | **identical** |
| ParentClaims (22) | `1070dde97a216522946dbe2e642715a2644aeb239435e01eee9406c8ed0520fe` | same | **identical** |
| recovery targets (15) | `e051a8df84c1eb042dacb56b790647f04ecfea675cf68fced1b710a846cbf92e` | same | **identical** |
| stop-search state | `cdcd5c4ad68badf112bc582bb5e03c31a88c1dbd7215f219ecd896ccc5ceccf5` | same | **identical** |
| raw map (includes I1 keys) | `fff5e6fc…` (no I1 keys existed) | `634b36b01bf69da68f42b0436a4a4a3fe59539a28b8a2713495cade2bddd41b6` | changed by construction (19 of 25 instances carry I1 keys) |

Determinism: the baseline harness, run with `PYTHONHASHSEED` 0, 1 and 2, produced identical projected output. The parity is also a
pytest regression, `test_pipeline_projection_matches_pre_i1_baseline`, which passes.

**Preserved live map** (`17_sufficiency_map.json`, Phase-28 Attempt 2): `π(attach(map)) == map` canonically (True). Canonical raw
hash before `2bb96a232ff9a673d70c0484030043bbcb3f8a881c0dd8c6becc1b76b08d1517`, after
`b473b53537ee4e00b92114ea697777bca24ce0e9f7742cad0108fea3c1706b19`. The preserved file itself was not rewritten, so its
file-level SHA-256 is unchanged (`28478500e485137cd6930b8010d274bb1da3afd48e7f4a6208dd183610d9ca0b`).

## 6. Phase-30 replay parity (hard gate, passing), preserved map + I1 fields

Replay re-run with the pre-I1 code (baseline) and on a run directory holding the preserved 11/13c/15a plus the map with I1 fields.

| artifact | result |
|---|---|
| `deterministic_layer1.md` (Layer 1, rendered answer) | **byte-identical** |
| `deterministic_layer2.md` (Layer 2, supporting evidence) | **byte-identical** |
| `deterministic_layer3.md` (Layer 3, audit) | differs only in `plan_sha256` and `replay_authorization_sha256` |
| `comparison_against_phase29_hand_audit.md` | byte-identical |
| `answer_plan.json` | differs only in `plan_sha256`, `inputs.sufficiency_map_sha256`, `inputs.replay_authorization_sha256` |
| `answer_plan_audit.json` | differs only in `plan_sha256` and the `replay_plan_deterministic` detail, which records the plan hash |
| `replay_decomposition_authorization.json` | differs only in `authorization_sha256` and `bound_inputs.sufficiency_map_sha256` |

Hash changes (expected, reported, not parity failures):

| hash | old | new |
|---|---|---|
| `plan_sha256` | `d965a6144377de37f2c688df3cd59a7f8c2354c54c3103b1dfbe61f2207d6c0c` | `43474527ae40623ea609da98b0effb3b9c7a0376513f845baaede8d9a6bed234` |
| `sufficiency_map_sha256` (replay-bound, file bytes) | `28478500e485137cd6930b8010d274bb1da3afd48e7f4a6208dd183610d9ca0b` | `5bc42e27d39c04d29d84b67a29ee73bcf9433b88f530a0cd7e2c510ace2f80a6` |
| `replay_authorization_sha256` | `74ecd832ea88fce183e7c72762a926d84c61e77578ce73e20885389671a61509` | `4ed0e5a542354a8b24c9b72c53a6c476489814cc1f75090ad7b45211bf493e85` |

The AnswerPlan node and facet states, claim roles, ParentClaim ids and payloads, relation units, and Layer 1 and 2 text are all
unchanged. The new run-directory map file differs from the preserved file by serialisation as well as by I1 content, which is
why §5's canonical comparison is the parity statement.

## 7. Cross-check against the Phase-30 answer-layer witness

**Revised gate (replaces the withdrawn universal-equality gate).**
- **A. Preserved-artifact cross-check, hard gate.** Upstream and Phase-30 witness booleans must agree on every preserved
  Phase-28 relational instance, and witness ids must agree wherever both report witnessed.
  **Result: 0 boolean disagreements and 0 id disagreements across 36 relational instances (passing).**
- **B. Synthetic semantic characterization.** Where the two algorithms differ by design, the difference is recorded as a
  characterization test. It is not an I1 implementation failure, and §7 is not altered to make the legacy layer agree.

**Why the universal gate was withdrawn.** Phase 30's `answer_plan/relations.py` intersects supports over all operands,
including inherited ones, so it requires the parent proposition to be shared. §7 treats inherited operands as referent identity
only. The two implementations encode different inherited-operand semantics, so requiring equality everywhere was too strong.

**Legacy-semantic characterization tests** (`test_relation_witness.py`, all passing, no expected failures):

| characterization | upstream §7 | legacy Phase-30 | test |
|---|---|---|---|
| 1. inherited alpha + child OWN beta proposition asserting the alpha–beta relation | witnessed | not witnessed | `test_legacy_characterization_inherited_referent_with_child_own_proposition_upstream_witnessed_legacy_not` |
| 2. verified joined child proposition establishing the same relation | witnessed | not witnessed | `test_legacy_characterization_verified_joined_child_proposition_upstream_witnessed_legacy_not` |
| 3. all-inherited operands sharing one parent proposition | not witnessed | witnessed | `test_legacy_characterization_all_inherited_shared_parent_upstream_not_witnessed_legacy_is` |

Agreement tests cover the cases where the semantics coincide (case 2, case 3, case 4, unverified join 5b, all-inherited with
distinct parent propositions); all agree.

These divergences are the reason a later answer-layer alignment increment (I1a) is required.

## 8. Witnessed and unwitnessed sets on the preserved map (final)

Relational instances: 36. Witnessed: 6. Unwitnessed: 30.

**Witnessed (6), the corrected empirical set:**
- `c4` region instance `…e60509ac4c8b`, witnessed by `p11`, its own passage, both operands OWN.
- `c8` trait instances ×5 (`…d6d8a8225859`, `…360f15addd4a`, `…ad0452a402ec`, `…c660cdb1a0de`, `…b077fe124a0e`), each witnessed by
  `p41`, because both of their OWN operands are supported by the rating passage.

**Engine-complete but NOT witnessed (4), unchanged from the Phase-28 expectation:**
- `c5 brain-behavior` ×2 (`…8a1c59aaa360`, `…6948ec530e13`), `inherited_referent_absent`.
- `c6 brain-attitude` ×2 (`…08aa35e6e926`, `…2674ba934ce3`), `inherited_referent_absent`.

The steering's original expectation listed only c4 as witnessed. That was incomplete. The five c8 instances are accepted as valid
I1 output (§9), and the corrected witnessed set above is the recorded result.

## 9. The c8 result: structural witness versus binding validity

The five c8 `U23` instances are valid I1 output. They are not suppressed, special-cased, or excluded by the algorithm.

- `relation_witnessed` is a **structural evidentiary property conditional on the currently authorized operand bindings**. It
  says both bound operands have same-passage support in `p41`.
- It does **not** certify that those operand bindings are semantically correct.
- The scientific defect is that the trait operand is mis-typed: ratings **of faces** were bound as traits **of perceivers**.
  That belongs to the later `described_entity` / measurement-subject work (audit §9), not to I1.
- The answer layer still renders the c8 node as not established, because the Phase-30 measurement-subject check refuses it.

**Explicit distinction:** witness validity is conditional on operand-binding validity. A witnessed relation is not a
scientifically valid relation unless its operands are also correctly bound.

## 10. Scientific gain

**Zero.** Layer 1 and Layer 2 are byte-identical. No answer text, node state, claim, or recovery decision changed. The c8
witnesses are structural only: Phase 30 already reports them as witnessed, and the answer layer still refuses to state them.

## 11. Tests and pre-existing failures

Offline launcher: `.local/phase32/nonet_pytest.py` refuses all socket connection and name resolution, then calls pytest.
No model endpoint is required.

**I1 module** (`test_relation_witness.py`): **32 passed, 0 xfailed.** It contains no expected failures, and no known semantic
difference is committed as one. Ruff format and lint clean on all new files.

**Affected sufficiency and answer-plan tests** (`test_sufficiency_*.py`, `test_answer_plan*.py`, and the I1 module): **567 passed**
(run without the socket-refusal launcher; the broader run below uses it).

**Broader `ask_cli_revised` offline suite under network refusal (final, after the characterization revision):** **3 failed, 2648 passed, 11 skipped, 0 xfailed** in 163 s. The failure set is identical to the pre-change baseline (the same three test ids). The delta is exactly the 32 I1 module tests (2616 + 32 = 2648).

**Pre-existing baseline** (pre-change, HEAD e886bf73, same launcher): 3 failed, 2616 passed, 11 skipped. The three failures are
unrelated to I1:
- `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`
  (a network call is refused under the launcher).
- `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`
  (`pin drift: hierarchy_contract.py changed since the pins were generated`).
- `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`
  (`AssertionError: 3 != 0`).

Post-change, first full run (before the characterization-test revision): 3 failed, 2646 passed, 11 skipped, 2 xfailed. The
failure set was identical to the baseline. The revision then removed the 2 xfails, giving the final figure above.

## 12. Gate summary and commit

| gate | result |
|---|---|
| projection parity (hard gate) | **pass**: projected map, ParentClaims, recovery, stop-search identical to pre-I1 |
| Layer 1 byte parity | **pass** |
| Layer 2 byte parity | **pass** |
| preserved cross-check (hard gate) | **pass**: 0/36 boolean disagreements, 0 id disagreements where both witnessed |
| synthetic legacy divergences | recorded as passing characterization tests, not failures |
| no new failures beyond the pre-existing baseline | see §11 |
| ParentClaims / recovery / stop-search unchanged | **pass** (projection parity) |
| frozen contracts, nomination authorizations, frontend | **untouched** (`git diff` empty) |
| scientific gain | zero |

## 13. Recommendation for I1a (not implemented here)

**I1a: answer-layer relation-witness alignment.** Make `answer_plan/relations.py` implement the authoritative §7 own/inherited
witness semantics and the all-inherited guard.

Expected effect on the preserved run:
- zero change to witness booleans and ids on all 36 relational instances;
- zero Layer-1 and Layer-2 change;
- ideally zero node or facet state change;
- characterization cases 1 and 2 (the divergences above) become witnessed consistently;
- characterization case 3 (the latent all-inherited shared-parent case) becomes not witnessed consistently.

I1a is a separate gated increment, because I1 itself promised zero answer-layer behaviour change. The I1 characterization tests
become agreement tests and should be updated in that increment.

**I2 remains NOT READY** until I1a is complete and the sufficiency semantic-version mechanism (audit §17) is approved and
implemented. Phase 31 §17 defines the design; nothing about it is implemented here.
