# Phase 32 / I1c — sufficiency-semantics version identity (zero semantic change)

Starting HEAD: `0f494288174236fefa92b1d8ed7c9ae4edaa415a` (I1b).

Status: **complete, offline, no semantic change.** No model call, no live run, no network, no pin or frozen-contract change,
no frontend change, no referent-containment repair, no I2, no full I3.

## 1. What I1c adds

A version identity for the *code* that produced a diagnostic sufficiency map, separate from the two identities it must not
be confused with:

| identity | what it identifies | where it lives | changed by |
|---|---|---|---|
| frozen contract identity | authored content (frozen v9 contract and review) | `sufficiency_contract.aib_hier_v9.frozen.json` | a new frozen version (Phase 31 §17.3.3) |
| sufficiency-semantics identity (I1c) | mapping, binding, satisfaction, completion, recovery, stop-search, direction/effectiveness **code behaviour** | per-child key in produced maps | bumping `SUFFICIENCY_SEMANTICS_VERSION` |
| code revision | external git provenance | not recorded in the map | — (deliberately; see §9) |

## 2. Files changed

| file | change |
|---|---|
| `sufficiency_engine.py` | constants `SUFFICIENCY_SEMANTICS_VERSION = "sufficiency-semantics-v1"`, `SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS`, `SEMANTICS_VERSION_KEY = "sufficiency_semantics_version"`, with the change-invariant comment. Nothing else changed. |
| `sufficiency_identity.py` (new) | pure module: `stamp_map`, `read_map_identity`, `check_authorization_binding`, `strip_identity`, `SemanticsIdentityError`. |
| `sufficiency_diagnostic.py` | `compute_diagnostic_sufficiency_map` ends with `si.stamp_map(mapped)`. This is the production stamping point. |
| `phase15_c4_semantic_consumption_experiment.py` | its own copy of the mapping loop now stamps through the same `si.stamp_map`. |
| `answer_plan/replay.py` | `--allow-historical-unversioned-map` flag; reads the identity (strict by default); binds it in `bound_inputs.sufficiency_semantics`; self-checks the binding before writing; new `verify_replay_authorization(authorization, smap)`. |
| `test_sufficiency_semantics_version.py` (new) | tests A–I plus two structural guards (§8). 18 tests. |
| `test_relation_witness.py` | pipeline projection now also strips the version key (`si.strip_identity(rw.project_out_i1(mapped))`). |
| `test_direction_target.py`, `test_answer_plan_replay.py` | the preserved-run replay calls pass the explicit historical flag. |

**Deliberately not changed:** `sufficiency_authoring.py`. Its `new_contract` builds authored contracts that feed the frozen
v9 artifact; stamping them would change frozen content. Only produced diagnostic maps are stamped.

## 3. Constant location and stamping path

- Constant: `sufficiency_engine.py`, beside `RELATIONSHIP_VERIFIERS`, with an invariant comment: any future change to
  mapping derivation, binding admissibility, satisfaction, relation completion, recovery, stop-search, or direction/effectiveness
  MUST bump the constant.
- Single stamping path for produced maps: `sufficiency_identity.stamp_map`, called from `compute_diagnostic_sufficiency_map`
  (production) and from the experiment harness copy. Stamping writes the key on every child contract.

## 4. Replay and authorization binding

- Replay reads the map identity with `require_current=True` by default. A historical map is refused with
  `SemanticsIdentityError` (verified: `i1c_strict.log`).
- `--allow-historical-unversioned-map` is the explicit compatibility path. It records `{"status": "historical_unversioned",
  "version": null}`. The preserved Phase-28 map is replayed this way (`i1c_replay/replay_decomposition_authorization.json`
  records exactly that).
- `bound_inputs.sufficiency_semantics` must equal the map identity. `check_authorization_binding` enforces that on write, and
  `verify_replay_authorization` enforces it on read, after recomputing the digest.

## 5. Historical compatibility and fail-closed rules

| condition | result |
|---|---|
| every child carries a supported version | `current` |
| no child carries the key | `historical_unversioned`, only when `require_current=False`; never inferred as current from absence |
| production (`require_current=True`) and key absent | raises |
| some children carry the key, some do not | raises (partial identity), in every mode |
| version not in `SUPPORTED_...` (e.g. `sufficiency-semantics-v99`) | raises |
| mixed versions across children | raises |
| non-string version | raises |
| empty map | raises |
| authorization binding differs from the map | raises |
| authorization digest does not match its body (tampered) | raises |

## 6. Projection parity (zero semantic change)

Projection = remove only the newly introduced version plumbing (`strip_identity`) and, for the relation-witness fields, the
I1 keys as before.

- `strip_identity(post_raw_map) == base_raw_map`, canonical JSON, exact: **True**
- `strip_identity(post_projected_summary) == base_projected_summary`, exact: **True**
- ParentClaims, recovery targets, stop-search: hashes identical to baseline (§7).

The projected-summary SHA changes (`fff5e6fc…` → `9f18227b…`) because that projection keeps the version key, so it is a
hash change by construction, not a semantic change. The strip-then-compare above is the real gate.

## 7. Hashes

| output | I1 baseline | I1c post | changed? |
|---|---|---|---|
| raw map (`map_raw.json`) | `634b36b0…` | `1ffaf371…` | yes, by construction (version stamped) |
| projected map (`pipeline_map_projected.json`) | `fff5e6fc…` | `9f18227b…` | yes, by construction (version key retained in projection) |
| ParentClaims (22) | `1070dde9…` | `1070dde9…` | **no** |
| recovery targets (15) | `e051a8df…` | `e051a8df…` | **no** |
| stop-search state | `cdcd5c4a…` | `cdcd5c4a…` | **no** |

Harness: `.local/phase32/harness_i1c.py` (gitignored). Pinned `fake-phase32-harness` nomination client, as in I1.

## 8. Tests

`test_sufficiency_semantics_version.py` (18 tests):

- A: stamped map carries the version on every child; constant and key values.
- B: same inputs produce identical output.
- C: a map without the field is `historical_unversioned`, never `current`.
- D: production refuses a missing version; partial identity errors; empty map errors.
- E: unknown future version fails closed; mixed versions fail closed; non-string version fails closed.
- F: a replay on a current map binds `{"status":"current","version":"sufficiency-semantics-v1"}`; verification passes.
- G: tampered version fails closed (digest check); a forged digest over a tampered body fails closed (binding check); the strict replay refuses the unversioned preserved map.
- H: stripping only the version key recovers the exact pre-I1c structure, and the version is really serialised.
- I: the version causes no change to relation units, ParentClaim ledger, recovery targets, or stop-search.
- Two structural guards: the authored frozen contract carries no version key; the invariant comment is present in the engine.

Preserved-artifact tests (F, G-strict, I) ran against the gitignored Phase-28 artifacts and did not skip.

**Results.**

- Targeted: `test_sufficiency_semantics_version.py`, `test_relation_witness.py`, `test_answer_witness_alignment.py`,
  `test_direction_target.py`, `test_answer_plan.py`, `test_answer_plan_step2.py`, `test_answer_plan_replay.py`,
  `test_sufficiency_*.py`: **643 passed, 0 skipped**, run from repo root with `PYTHONPATH=.`.
- Broader offline suite (`experiments/ask_cli_revised`, under `.local/phase32/nonet_pytest.py`, which refuses sockets and DNS):
  **3 failed, 2706 passed, 11 skipped** (222 s).
- The 3 failures are the same 3 pre-existing failures as the I1b baseline, by name:
  - `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`
  - `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`
  - `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`
  No new failure.

**Lint.** `ruff check` and `ruff format --check` pass on all nine touched files. One import-order fix (I001) was applied to
three source files, and an E731 lambda was rewritten as a `def` in the new test file.

## 9. Layer 1/2 and Layer 3/JSON parity on the preserved replay

Replay run directory: `.local/phase32/run_i1/` (preserved Phase-28 Attempt-2 artifacts plus I1 fields; 17 map sha
`5bc42e27…`, the same file the I1 results document cites). Replay with `--allow-historical-unversioned-map`.

- `deterministic_layer1.md`: **byte-identical** to the I1b baseline.
- `deterministic_layer2.md`: **byte-identical** to the I1b baseline.
- `deterministic_layer3.md`: differs only in identity lines. `plan_sha256` `7e990ae2…` → `fc8c8754…`;
  `replay_authorization_sha256` `4ed0e5a5…` → `a77958ee…`.
- `answer_plan.json`: structural diff against the I1b baseline differs only at `/plan_sha256` and
  `/inputs/replay_authorization_sha256`. Both are identity hashes that now cover the bound identity.

The authorization binds `{"status": "historical_unversioned", "version": null}`, which is correct for the explicitly historical
replay. No current-version replay of the preserved map was run, because the preserved map is historical by definition.

## 10. Witness parity (preserved map)

On the preserved map (`run_i1/17_sufficiency_map.json`), I1c changes no witness result:

- relational instances: 36. Witnessed: 6. Unwitnessed: 30.
- Witnessed: c4 `…e60509ac4c8b` (`p11`); c8 ×5 (`…d6d8a8225859`, `…360f15addd4a`, `…ad0452a402ec`, `…c660cdb1a0de`,
  `…b077fe124a0e`; all `p41`).
- Engine-complete but unwitnessed (the four recorded disagreements): c5 ×2 (`…8a1c59aaa360`, `…6948ec530e13`) and c6 ×2
  (`…08aa35e6e926`, `…2674ba934ce3`).

These match the I1 results document exactly.

**Caveat, reported rather than hidden.** The harness pipeline map (`i1c_base`/`i1c_post`, used only for the zero-change
projection gate) is a deterministic re-derivation with the fake nomination client. It has 25 instances, 19 of them relational,
and a different binding set. On that map c5 and c6 are witnessed on `p12` and `p17`. Those witness outcomes are a property of
the fake-client pipeline, not of the live Attempt-2 map, and must not be read as the preserved witness set. I1c's claim is only
that the harness map is unchanged by the version stamp, which §6 establishes.

## 11. Explicit statements

- **Semantic / scientific gain of I1c: zero.** No mapping, binding, completion, recovery, stop-search, direction or ParentClaim
  output changed. The version key is plumbing.
- **Code revision is external git provenance and is deliberately not recorded in the map.** Recording a commit hash would make
  the map self-referential and make its bytes depend on the dirty-tree state at run time. Replay authorizations record the
  semantics version; reviewers resolve the commit through git.
- Authored contract content is unchanged. The frozen v9 contract, its review, and the pins are byte-identical to HEAD.

## 12. Readiness

- **READY** to begin the first versioned semantic repair: the narrow inherited-referent containment repair (case-sensitive
  containment is not accepted as final). Any change to containment semantics must bump `SUFFICIENCY_SEMANTICS_VERSION` and go
  through the same identity path.
- **NOT READY**: full direction-target I3 (single-operand attribution is not accepted as final) and I2
  (polarity/goal-specific satisfaction). I3 must land before I2.
- No live E2E before direction semantics are repaired.
