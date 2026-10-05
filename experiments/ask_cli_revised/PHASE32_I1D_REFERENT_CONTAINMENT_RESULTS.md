# Phase 32 / I1d — versioned inherited-referent containment (first real sufficiency-semantics change)

Starting HEAD: `144cc965d9a11eec11061925ab22bace252e5774` (I1c). The final commit is the I1d commit on
`experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`; a report cannot record its own commit hash, so it is read from
`git log`.

Status: **complete, offline.** No model call, no live run, no pin refresh, no frozen-contract change, no frontend change, no
polarity, no full I3, no single-operand direction change, no binder, sealing, described-entity or construct work.

## 1. The semantic change, exactly

| version | inherited-referent containment (the only predicate that varies) |
|---|---|
| `sufficiency-semantics-v1` (historical; I1c) | `canonical_text_contains(needle=surface, haystack=quote)` — case-sensitive |
| `sufficiency-semantics-v2` (**current**; I1d) | `canonical_text_contains(needle=surface.casefold(), haystack=quote.casefold())` — Unicode case folding of BOTH sides, then the same canonical containment test |

Not changed by v2, deliberately:

- `canonical_text_contains` itself is unchanged. It is a shared app utility (verification, critical review, propositions,
  sufficiency mapping, tests); changing it would have altered far more than this repair.
- v2 adds no normalisation of whitespace, punctuation, hyphenation, morphology, aliases, acronyms, paraphrase, or Unicode
  compatibility forms. The existing canonical containment already collapses whitespace runs and maps dashes; both were true
  under v1 too, and v2 inherits them unchanged.
- The structural witness algorithm is the same for both versions. Only the inherited-referent predicate varies.

Every other sufficiency behaviour is identical to v1: bindings, operand source, OWN support, the all-inherited guard, `complete`,
recovery, stop-search, direction/effectiveness, and ParentClaims. The semantic diff in section 7 checks this.

## 2. Files changed

| file | change |
|---|---|
| `sufficiency_engine.py` | `SUFFICIENCY_SEMANTICS_V1`, `SUFFICIENCY_SEMANTICS_V2`; `SUFFICIENCY_SEMANTICS_VERSION = V2`; `HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS = {V1}`; `SUPPORTED_...` = current ∪ historical (readable, not current); invariant comment with the v1/v2 record |
| `relation_witness.py` | containment dispatch `_REFERENT_CONTAINMENT` (one predicate per version); `referent_present(..., semantics_version=)`; `witness_instance(..., *, semantics_version)` and `attach_relation_witnesses(..., *, semantics_version)` — required, never defaulted; unknown version raises |
| `sufficiency_identity.py` | three states (`current`, `historical_versioned`, `historical_unversioned`); `read_map_identity(..., accept_historical_versioned=, accept_historical_unversioned=)` (both default False); `applied_containment_version(identity)`; `check_authorization_binding` accepts all states (it checks consistency, not permission) |
| `sufficiency_diagnostic.py` | production attach passes `se.SUFFICIENCY_SEMANTICS_VERSION` (v2), then stamps v2 |
| `answer_plan/relations.py` | `relation_units(..., *, semantics_version)` — required |
| `answer_plan/plan.py` | `PLAN_VERSION` `answer-plan-step2-v2` → **`answer-plan-step2-v3`**; `build_plan(..., *, containment_semantics)` required; the plan records `containment_semantics` |
| `answer_plan/replay.py` | `--allow-historical-versioned` (new) and `--allow-historical-unversioned-map` (existing); records `bound_inputs.answer_containment_semantics`; `verify_replay_authorization` checks it against the bound identity |
| `test_relation_witness.py`, `test_answer_witness_alignment.py`, `test_answer_plan.py`, `test_answer_plan_step2.py` | existing call sites pinned to the current version through local helpers (`_units`, `_attach`, `_upstream`/`_witness`); expected values unchanged. The two plan test files also gained the imports their helpers need |
| `test_sufficiency_semantics_version.py` | I1c identity tests updated to the three-state model (see §4); tests A–I keep their purpose |
| `test_referent_containment_v2.py` (new) | 35 tests: the synthetic matrix, version dispatch, replay identity, tamper, and the preserved witness set |

Not changed: `sufficiency_authoring.py`, `canonical_text_contains`, the frozen v9 contract and review, `hierarchy_contract.frozen.json`,
`e2e_contracts.frozen.json`, the nomination authorizations, `app/frontend/`.

## 3. Version dispatch

- One pure predicate per version, selected by a single dict. The witness algorithm does not fork.
- `semantics_version` is a required keyword on every witness and answer-layer entry point. A caller cannot apply one version's
  behaviour under another's identity by omission.
- An unknown version (for example `sufficiency-semantics-v99`, or the empty string) raises `SemanticsIdentityError` from
  `referent_present`, `witness_instance`, and `attach_relation_witnesses`. It does not fall back to any rule.

## 4. Current, historical-versioned, historical-unversioned — behaviour

| map | strict (production) | `--allow-historical-versioned` | `--allow-historical-unversioned-map` | AnswerPlan containment applied |
|---|---|---|---|---|
| all children `v2` | accepted, `current` | accepted, `current` | (not needed) | v2 |
| all children `v1` | **refused**, "not current" | accepted, `historical_versioned`, v1 recorded | refused | **v1** (the map's own recorded version) |
| no version key | **refused**, "not accepted" | refused | accepted, `historical_unversioned`, version null | **v2, applied explicitly and recorded as `answer_containment_semantics`**; the map is not labelled v2 |
| `v99` / unknown | refused, "unsupported" | refused | refused | — (fail closed in every mode) |
| mixed or partial | refused | refused | refused | — |

Membership in `SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS` is never read as currency. v1 is supported (readable) and historical;
only v2 is current.

For an unversioned artifact, the contemporary rule is applied, and that application is recorded in the replay identity
(`answer_containment_semantics: sufficiency-semantics-v2`). The artifact is not attributed a version it does not record.

## 5. PLAN_VERSION bump

`answer-plan-step2-v2` → `answer-plan-step2-v3`, bumped in this increment because AnswerPlan witness semantics changed (I1b
convention). The plan also records `containment_semantics`, so the rule applied is visible in the output, not only in the
identity hash. The I1a process gap is not repeated.

## 6. Synthetic v1/v2 matrix

Generic alpha/beta fixtures: the parent supplies the entity referent (inherited), the child's own measure is `beta score`
supported by one candidate proposition. Expectations were written from the specification before the run.

| case | inherited surface | candidate quote | v1 | v2 | note |
|---|---|---|---|---|---|
| 1 same case | `alpha region` | `the alpha region predicted beta score.` | witnessed | witnessed | identical full result under both versions |
| 2 sentence-initial capitalisation | `alpha region` | `Alpha region predicted beta score.` | not | **witnessed** | the repair |
| 3 reverse case difference | `Alpha Region` | `the alpha region predicted beta score.` | not | **witnessed** | the repair |
| 4 punctuation difference | `alpha region` | `alpha-region predicted beta score.` | not | not | not normalised, as specified |
| 5 whitespace run | `alpha region` | `the alpha  region predicted beta score.` | witnessed | witnessed | already true under v1: the existing canonical containment collapses whitespace runs; nothing added |
| 6 referent absent modulo case | `alpha region` | `the gamma region predicted beta score.` | not | not | not witnessed in both |

Further checks, all under v2 unless stated:

- **Same-case results identical:** the full result dict for case 1 is equal under v1 and v2.
- **Only casing fixtures differ:** cases 2 and 3 differ; cases 1, 4, 5, 6 do not.
- **All-inherited guard:** a case-insensitive co-mention with no own operand is not witnessed (`no_own_operand`).
- **Distributed evidence:** the referent appears only in a different proposition; not witnessed (`inherited_referent_absent`).
- **Parent proposition:** the parent contains both operands in any case; it is never in the witness (`P1` absent from `witness_ids`).
- **Verified join:** a join whose referent differs only by case is witnessed under v2 only with all anchors verbatim. Unverified
  anchors remain inadmissible under both versions.
- **Dispatch:** `referent_present` returns the version's verdict; unknown versions fail closed across all three entry points;
  the entry points cannot be called without a version.

## 7. Semantic diff (explicit, not hashes alone)

Script: `.local/phase32/i1d/semantic_diff.py`; output `.local/phase32/i1d/semantic_diff.json`. It attaches witnesses under v1 and
under v2 to the **same** mapped binding set, then compares everything.

| check | preserved Attempt-2 (36 relational instances) | deterministic fake-client harness (19 relational instances) |
|---|---|---|
| mapped semantics identical except the witness fields and version key | **yes** | **yes** |
| witness fields changed (any instance) | **0** | **0** |
| casing census: referent/quote pairs whose v1 and v2 verdicts differ | **0** | **0** |
| relation units identical | yes | yes |
| ParentClaim ledger identical | yes | yes |
| recovery targets identical | yes | yes |

Bindings, operand source, OWN support sets, the all-inherited guard, relation structure, `complete`, requirement states,
direction/effectiveness, and mapping output are identical under the two versions. Nothing new is witnessed, so no downstream
state changes.

**Finding, reported rather than tuned:** on both the preserved map and the harness map, no inherited referent differs from its
candidate quote by case alone. The casing defect is real (a sentence-initial referent is refused under v1), but it has no
measurable consequence on either witness set. The expected preserved set (c4 witnessed; c8 ×5 witnessed; c5 ×2 and c6 ×2
engine-complete but unwitnessed) is unchanged, and it is not forced.

## 8. Preserved Attempt-2 replay

Run: `.local/phase32/run_i1/` (the preserved map with I1 fields, no version key) with `--allow-historical-unversioned-map`. Baseline:
`.local/phase32/i1c_replay/` (I1c).

| output | result |
|---|---|
| Witness set | 6 witnessed of 36 relational instances (c4 `…e60509ac4c8b` by p11; c8 ×5 by p41); 4 engine-complete unwitnessed (c5 ×2, c6 ×2). **No instance changed.** |
| `deterministic_layer1.md` | **byte-identical** to I1c |
| `deterministic_layer2.md` | **byte-identical** to I1c |
| `deterministic_layer3.md` | identity lines only: `plan_version` (v2→v3), `plan_sha256`, `replay_authorization_sha256` |
| `answer_plan.json` (structural diff) | `plan_version`, `plan_sha256`, `inputs.replay_authorization_sha256`, and the new `containment_semantics` key. Nodes, relation units, claim roles, disagreements, parent, step2 are **unchanged** |
| authorization | binds `sufficiency_semantics: {historical_unversioned, null}` and `answer_containment_semantics: sufficiency-semantics-v2` |

Substantive output is unchanged, as the zero witness change predicts. Every substantive change that could have occurred would have
traced to the casing rule; none did.

## 9. Deterministic harness

Run under the new production code: `.local/phase32/harness_i1c.py i1d_post`.

| output | I1c (`i1c_post`) | I1d (`i1d_post`) | result |
|---|---|---|---|
| claims (ParentClaims, 22) sha | `1070dde9…` | `1070dde9…` | identical |
| recovery targets (15) sha | `e051a8df…` | `e051a8df…` | identical |
| stop-search sha | `cdcd5c4a…` | `cdcd5c4a…` | identical |
| raw map | — | identical except the version value | the only change is `v1` → `v2` |
| projected map sha | `9f18227b…` | `5229b31f…` | changed only because the version value is kept in the projection; with the version key stripped the two projections are identical |

The harness witness set is not the scientific oracle, and it is not compared against Attempt-2 witnesses. Its witness fields are
identical under v1 and v2 (section 7).

## 10. Downstream effects

- **ParentClaims:** no change (sha identical on both maps).
- **Recovery:** no change (sha identical on both maps).
- **Stop-search:** no change. Computed directly with `compute_stop_search_certified` for every requirement under v1 and v2: identical on the
  preserved map (13 requirements, 10 certified) and on the harness map (13 requirements, 6 certified).
- **Direction boundary:** no new witnessed relation exists, so the I1b single-operand fallback is not exercised by any new relation.
  The fallback is unchanged. It is not repaired here.

## 11. Tests and pre-existing failures

- **Targeted set** (`test_referent_containment_v2.py` 35, `test_sufficiency_semantics_version.py` 18, `test_relation_witness.py`,
  `test_answer_witness_alignment.py`, `test_direction_target.py`, `test_answer_plan.py`, `test_answer_plan_step2.py`,
  `test_answer_plan_replay.py`, `test_sufficiency_*.py`): **678 passed, 0 failed, 0 skipped**. The preserved-artifact tests ran.
- **Broader offline suite** under the network-refusing launcher (`.local/phase32/nonet_pytest.py`):
  **2741 passed, 11 skipped, 3 failed** (161 s). The 3 failures are the same pre-existing failures as the I1c baseline, by name:
  `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`,
  `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`, and
  `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`.
  No new failure. The pass count rose from 2706 (I1c) by exactly the 35 new I1d tests.
- **Lint:** `ruff check` and `ruff format --check` pass on all touched files.

Test-engineering note: the first migration of the witness tests put a helper `_witness` on top of an existing `_witness` in one
file, which silently rerouted calls. It was caught by the failing run and fixed by renaming the migrated helper to `_upstream`
in that file only. Separately, the plan test helpers referenced `rel` and `rw` without importing them; ruff reported this as
F821 and the imports were added. Both were found by the gates, not assumed.

## 12. Anti-fitting statement

- The rule was specified before any run and is confined to casing. Its synthetic expectations were written from the specification,
  not from the code's output.
- Where the specification was conditional ("unless the existing canonical containment already normalises this"), the expectation
  follows the existing canonical behaviour (case 5, whitespace), and the result is recorded as already true under v1, not as a new
  repair.
- When the repair turned out to have **zero** measurable effect on both witness sets, that is reported as the finding. The rule was
  not widened, narrowed, or re-scoped to create an effect, and the expected preserved set was not forced.
- The synthetic tests are generic (alpha/beta). The preserved run is a check, not the only test.

## 13. READY / NOT READY

- **Full direction-target I3:** READY to begin, under the same versioning path (`sufficiency-semantics-v3` when its semantics
  change). Its design must close the single-operand fallback. Nothing in I1d blocks it: I1d changed no witness.
- **I2 (polarity / goal-specific satisfaction):** NOT READY. It follows I3.
- **Live E2E:** NOT authorized. Direction semantics are not yet repaired, and this increment is offline only.
