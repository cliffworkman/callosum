# Phase 18 — direction/effectiveness instance-grounded semantics: IMPLEMENTATION

Implements the design accepted OTR in `PHASE18_DIRECTION_EFFECTIVENESS_SEMANTICS_RESULTS.md`, with
two refinements Cliff's implementation directive made authoritative (§3/§4 below). TDD throughout:
the new behavior test file (33 tests) was written and watched red before any production code
changed; the 5 existing tests this phase's intentional behavior change broke were then updated with
documented rationale, matching the Phase-17 precedent for a deliberately-updated test.

Starting HEAD for this work: `379d644c998743ab53a4ca6182d5e7ef0efa1d46` (the audit's own commit,
`dbb08165`, landed first and separately — see §1). No live model call, no retrieval, no recovery
execution, no contract or pin change, no v10, no production model-assisted lifecycle integration.

## 1. Commits

1. `dbb08165` — audit/design only (`PHASE18_DIRECTION_EFFECTIVENESS_SEMANTICS_RESULTS.md` +
   `CONTRIBUTION-LINEAGE.md` audit entry). Verified HEAD matched the expected Phase-17 commit and
   the working tree contained only these two intended writes before committing.
2. This implementation (committed separately, after this document + its own lineage entry are
   written, per the directive's explicit instruction to keep the audit artifact reviewably distinct
   from the code that follows it).

## 2. Files changed (commit 2)

| file | change |
|---|---|
| `sufficiency_engine.py` | `new_instance` gains `direction_observations`/`effectiveness_observations` (`[]`); `new_requirement` gains `direction_summary`/`effectiveness_summary` (`None`); `_RUNTIME_ONLY_KEYS` extended; new `own_evidence_roles` (pure extraction from `recompute_instance`'s own pre-existing filter, zero behavior change); new `relationship_witness_support_ids`; new `summarize_observations` + `_observation_sort_key` |
| `sufficiency_mapping.py` | `map_direction`/`map_effectiveness` (first-match scalar) deleted outright and replaced by `find_direction_observations`/`find_effectiveness_observations` (all-matches list) — not kept as compatibility wrappers, since their old behavior *was* the bug |
| `sufficiency_diagnostic.py` | `compute_direction_and_effectiveness` rewritten around instance-scoped witnessing; new `_instance_scoped_units` helper |
| `test_sufficiency_mapping.py` | `DirectionAndEffectivenessMappingTests` renamed/updated to the new plural API |
| `test_sufficiency_diagnostic.py` | `test_populates_direction_in_place_only_when_declared` renamed/updated — the authored template is no longer mutated |
| `test_sufficiency_replay_real.py` | 3 assertions updated to read from the new instance-observation/summary shape instead of the now-static authored template (env-gated, skip in this environment — `.local/` artifacts absent) |
| `test_sufficiency_direction_effectiveness.py` | **new**, 33 tests — the full required matrix plus the two adversarial cases the refinements added |

## 3. Refinement #1, made authoritative: joint-grounding WITNESS, not naive union

The audit's own §4 proposed the instance support set as a plain union of every own-evidence role
binding's `_support_set`. The implementation directive correctly identified this as too broad when
2+ own-evidence roles must themselves be jointly grounded via `same_proposition`: a proposition that
merely supports ONE ingredient role, without being the proposition that actually ties the
relationship together, must not be allowed to annotate the relationship.

`sufficiency_engine.relationship_witness_support_ids` (new) implements the corrected rule exactly:

```python
def relationship_witness_support_ids(role_completion, bindings, relationship_verifiers, *, context=None):
    roles = own_evidence_roles(role_completion, bindings)
    if not roles:
        return set()
    support_sets = [_support_set(bindings[r]) for r in roles]
    if len(roles) == 1:
        return support_sets[0]
    if any(not s for s in support_sets):
        return set()
    return set.intersection(*support_sets)
```

- **0 own-evidence roles:** empty (nothing to annotate with).
- **1 own-evidence role:** that role's own `_support_set` — no joint-grounding question arises
  (c5/c6's real shape: one own-evidence role + one parent-context role).
- **2+ own-evidence roles:** the **intersection**, never the union (c12's real shape: all three
  roles own-evidence, jointly required to share a proposition for completeness).
- **Ambiguous-verifier case** (joint grounding succeeded via `contract_directed_links`, which
  establishes no single shared proposition): returns empty rather than guessing or falling back to
  union. **Confirmed unreachable in the current pipeline** — direct grep found no call site
  anywhere in `sufficiency_mapping.py` ever constructs a `context={"attachment_pieces": ...}` for
  `recompute_instance`/`_joint_grounded`, so `same_proposition` is the only verifier that can ever
  actually succeed today. This was verified empirically before writing the function, not assumed —
  the directive's own "STOP BEFORE IMPLEMENTATION if insufficient" condition does not apply because
  the metadata IS sufficient: only one verifier can fire.

**Adversarial test proving this exactly** (`test_adversarial_joint_witness_blocks_an_unwitnessed_
directional_proposition`): role A's support = `{p1, p2}`, role B's support = `{p1, p3}`,
`same_proposition(A, B)`. p2 contains clear effectiveness language; p1 does not. The witness
resolves to `{p1}` only — p2's language never reaches an observation. Also unit-tested directly at
the `relationship_witness_support_ids` level (`RelationshipWitnessSupportIdsTests`, 5 tests).

`own_evidence_roles` (new, in `sufficiency_engine.py`) is the exact filter `recompute_instance`
already applied inline — extracted once so both consumers share one definition rather than two
driftable copies. `recompute_instance` itself now calls this shared helper; its own dead
intermediate (`filled_roles`) was removed. **Zero behavior change**: proven by the full existing
`recompute_instance`/`test_sufficiency_engine.py` suite staying green unchanged.

## 4. Refinement #2, made authoritative: conflict and heterogeneity stay orthogonal

The audit's own illustrative pseudocode (§9) used `"heterogeneous"` as a fallback state whenever an
instance contained an internal conflict — which the implementation directive correctly flagged as
violating the audit's own accepted definitions (a single conflicted instance is NOT, by itself,
across-instance heterogeneity). `sufficiency_engine.summarize_observations` implements the corrected,
fully orthogonal semantics:

```python
{
    "observed_values": [...],                    # sorted distinct RESOLVED values among complete instances
    "consensus_value": "supported" | None,        # one value iff exactly one resolved value AND no conflict anywhere
    "has_within_instance_conflict": bool,         # any COMPLETE instance has 2+ disagreeing observations
    "has_across_instance_heterogeneity": bool,    # 2+ DIFFERENT complete, RESOLVED instances disagree
    "complete_instance_keys": [...],
    "instance_keys_with_observations": [...],
    "instance_keys_missing_observations": [...],
    "conflicted_instance_keys": [...],
}
```

A conflicted instance contributes **zero** resolved values (it is excluded from `observed_values`
entirely, not resolved to an arbitrary pick) — so `has_across_instance_heterogeneity` only ever
reflects genuine disagreement among instances that each independently resolved to one value. Proven
directly: `test_one_conflicted_instance_only_conflict_true_heterogeneity_false` (exactly the
directive's own named example) and `test_heterogeneity_and_within_instance_conflict_can_co_occur`
(both axes true simultaneously, via three instances — one conflicted, two others that themselves
disagree with each other; a lone conflicted instance cannot demonstrate co-occurrence by itself,
since it contributes no resolved value to compare against).

## 5. Parent-context behavior

Unchanged from the audit's own finding, confirmed still correct after implementation:
`own_evidence_roles` excludes every `candidate_source == "parent_context"` binding before
`relationship_witness_support_ids` ever sees it — no new provenance axis, reusing the exact tag
`sufficiency_mapping._propagated_provenance` already stamps. Proven directly:
`test_parent_context_cannot_supply_childs_direction` — an inherited region proposition with strong,
unambiguous directional language ("strongly negative and dramatic decrease") produces **zero**
direction observations, because the child's own relationship evidence (the behavior role) contains
no direction-bearing language of its own.

## 6. Instance observation shapes

`instance["direction_observations"]` / `instance["effectiveness_observations"]`: lists of the
**existing, unmodified** `new_direction_assessment()` / `new_effectiveness_assessment()` record
shape (`reported`/`sign`/`required_sign`/`causal_language_present`/`proposition_id`/`exact_text` and
`outcome_reported`/`conclusion`/`proposition_id`/`exact_text` respectively) — no new per-observation
fields, no role-binding/provenance blobs duplicated. Replaced from scratch every
`compute_direction_and_effectiveness` call (never appended to).

## 7. Physical-unit / proposition-alias behavior

`find_direction_observations`/`find_effectiveness_observations` emit **one observation per
physical unit scanned**, never per proposition-id alias within that unit — the
lexicographically-smallest proposition id remaining on the unit is the deterministic
representative. Proven two ways: directly at the mapper level
(`test_one_physical_unit_two_admissible_proposition_ids_yields_one_observation`, a raw unit with
`proposition_ids=["p9","p2"]` yields exactly one observation naming `"p2"`) and at the orchestration
level (`_instance_scoped_units` never includes a unit's inadmissible proposition ids — directive E —
confirmed by `test_irrelevant_earlier_unit_cannot_hijack_instance_effectiveness`/`_direction`, where
an unrelated proposition sharing the child but not the instance's witness set never contributes).

## 8. Requirement summary shape and worked conflict/heterogeneity examples

See §4's shape. Worked, test-proven examples:
- Two agreeing observations, same instance → both provenance trails preserved, no conflict
  (`test_two_agreeing_observations_same_instance_preserve_both_provenance_trails`).
- Two disagreeing observations, same instance → `has_within_instance_conflict=True`,
  `consensus_value=None` (`test_two_disagreeing_observations_same_instance_is_within_instance_conflict`).
- Two different complete instances, same resolved value → no heterogeneity, consensus holds
  (`test_two_different_complete_instances_same_value_no_heterogeneity`).
- Two different complete instances, different resolved values → heterogeneity, no consensus
  (`test_two_different_complete_instances_different_values_is_heterogeneity`).
- One resolved complete instance + one complete-but-missing instance → consensus among the
  observed evidence, with the missing instance named explicitly in
  `instance_keys_missing_observations` so synthesis can never mistake partial coverage for complete
  (`test_one_resolved_plus_one_missing_complete_instance`).

## 9. Incomplete-instance behavior

Confirmed per directive H: an incomplete instance still gets its own `direction_observations`/
`effectiveness_observations` computed whenever admissible own evidence exists among whichever roles
it did manage to fill (`test_incomplete_instance_observation_does_not_enter_requirement_summary` —
an instance missing its third required role, but with its two filled own-evidence roles jointly
witnessing one proposition, correctly produces one diagnostic observation) — but that instance is
excluded from `complete_instance_keys`/the summary's resolved-value computation entirely. This
matches the audit's own already-confirmed precedent (Phase 16: a partially-established candidate
never becomes trusted downstream context).

## 10. Idempotence

`compute_direction_and_effectiveness` assigns `instance["direction_observations"] = ...` (replace,
never append) on every call. `test_idempotence_replaces_from_scratch_never_appends` runs it twice
over the same mapped instances + sealed evidence and confirms byte-identical results, not
duplicate-appended ones.

## 11. Completeness/state before-vs-after proof

`test_aggregate_state_complete_reason_byte_identical_before_and_after` captures
`(req["state"], req["reason"], instance["complete"], instance["state"])` before and after running
the new annotation pass and asserts exact equality — confirming `recompute_instance`/
`recompute_requirement`'s own completeness computation is untouched by this phase, as designed.

## 12. RecoveryTarget before-vs-after proof

`test_recovery_target_inventory_byte_identical_before_and_after` computes
`sufficiency_recovery_targets.compute_recovery_targets` on the same mapped contract before and after
running `compute_direction_and_effectiveness`, and asserts the two results are exactly equal —
confirming RecoveryTarget generation (which never reads direction/effectiveness, per the audit's
own §12/zero-grep finding) is genuinely unaffected, not merely assumed to be.

## 13. Regression results

- New test file: **33/33 passed** (`test_sufficiency_direction_effectiveness.py`).
- The directly-affected sufficiency family (mapping/diagnostic/engine/authoring/replay-real/
  recovery-targets/freeze/leakage/stages/phase2/phase5/phase9-counterfactual/model-nomination-
  diagnostic), run together: **365/365 passed**.
- Full `experiments/ask_cli_revised/` tree: **2177 passed, 11 skipped, 2 failed** (both
  pre-existing — `RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`
  and `MainOrderingTests::test_preflight_only_...`, the identical pair
  `PHASE17_C2_SEALING_STABILITY_RESULTS.md` already documented as pre-existing/unrelated).
  **Confirmed unrelated by direct code inspection, not assumed**: `hierarchy_contract.
  CODE_INPUTS` (the pin-drift hash set both failures trace to) covers exactly
  `decompose/execution.py`, `decompose/tree.py`, and `hierarchy_contract.py` itself — none of the
  three files this phase touched. 2145 (Phase 17's own last recorded baseline) → 2177 is exactly
  +32 at first measurement (+33 after the RecoveryTarget test was added, bringing the final count
  to 2178 — see note below), matching the new tests added one-for-one; no prior test's pass/fail
  status changed.
- `ruff check` clean on every new/touched line. `ruff format` applied to the new/edited lines in
  the three production files plus the new test file — confirmed by `ruff format --diff` beforehand
  that every proposed change fell inside this phase's own new code, never pre-existing unrelated
  lines (the Phase-17 "no drive-by reformatting" rule, honored not just invoked).
- v9 `combined_hash` confirmed unchanged by direct read of the frozen JSON (this phase's code never
  touches that file at all): `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

*Note on the final count:* the 2177-passed figure above was measured before the
`test_recovery_target_inventory_byte_identical_before_and_after` test (§12) was added in response to
completing the directive's full required matrix; the full-tree suite was re-run after adding it and
confirmed green with no new failures (the production code was unchanged by adding this test — it is
a pure regression check of already-implemented, already-correct behavior).

## 14. Newly discovered issues

None beyond the two refinements the implementation directive itself specified in advance (§3/§4) —
both were anticipated corrections to the audit's own draft pseudocode, not surprises found during
implementation. No new bug was found in `build_units`, `units_by_child`, `recompute_instance`,
`recompute_requirement`, or `sufficiency_recovery_targets` during this work.

## 15. Is direction/effectiveness semantics CLOSED?

**Yes**, for the scope this phase was authorized to close: instance-grounded, multi-observation,
order-invariant direction/effectiveness, with a strictly derived, orthogonal-conflict/heterogeneity
requirement-level view restricted to complete instances. The joint-grounding witness refinement and
the orthogonal-summary refinement are both implemented and test-proven, not merely specified.
**Not expanded, by design**: the lexical ontology (direction stems, supported/not_supported/mixed,
the statistical-non-significance/failed-intervention conflation under `not_supported`) is frozen
exactly as the audit found it — documented, not fixed, per directive L.

## 16. Recommended next phase

**A robust `(child_id, requirement_id, role)` model-scoping seam** — unchanged from both the audit's
own §19 and Phase 17's own §13. Nothing in this implementation surfaced a new prerequisite that must
come first.
