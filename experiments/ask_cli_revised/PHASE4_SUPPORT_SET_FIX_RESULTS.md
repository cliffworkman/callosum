# Phase 4 — generic support-set fix for the Phase 3 finding (2026-09-30)

No live model calls, no v8 change, no v9 RoleSpec wording change, no recovery, no new E2E
anywhere in this increment. Starting HEAD `416e7a52` (verified before any change).

## Commit

`036b431b` — `fix(ask-sufficiency): same_proposition joint-grounding uses a binding's full support set`

## 1–2. Inspection and fix

`sufficiency_engine._verify_same_proposition` (before): `{role_bindings[r]["proposition_id"] for r
in roles}` — required literal string equality across every role's own single `proposition_id`,
with no notion of the Phase 3 `supporting_proposition_ids` provenance field at all.

New `_support_set(binding)`: `set(supporting_proposition_ids or [])` unioned with the binding's own
primary `proposition_id`. New `_verify_same_proposition`: true iff
`set.intersection(*[_support_set(role_bindings[r]) for r in roles])` is non-empty — the N-way
generalization of "all roles cite the identical proposition." A binding without
`supporting_proposition_ids` degrades to exactly `{proposition_id}`, byte-identical to the
original check.

**Verified before implementing, not assumed:** c1's actual support sets were pulled and checked —
`{p11,p2} ∩ {p11,p2} ∩ {p2} = {p2}`, genuinely non-empty. This is real, recorded proposition
support overlap, not a same-anchor loosening; the fix proceeded per instruction #4's own
condition rather than needing to stop.

## 3–4. Backward compatibility and the anchor boundary

Confirmed by the full existing suite passing with **zero test changes**: every legacy
(deterministic, or pre-Phase-3-shaped) binding's support set is exactly `{proposition_id}`, so
`_verify_same_proposition` behaves identically to before. `_verify_same_proposition` never
receives an anchor — `sufficiency_engine.py`'s `RoleBinding` representation carries no anchor field
at all — so anchor co-occurrence is structurally incapable of leaking into this check, with no new
guard needed to enforce it.

## 5. Adversarial tests — `SupportSetSamePropositionTests` (5 tests, all pass)

- `test_primary_selection_order_cannot_change_truth_when_support_sets_are_identical` — two
  orderings of which proposition became primary (from the identical `{p11,p2}` support pair)
  agree.
- `test_bindings_with_one_shared_supporting_proposition_pass` — a deterministic binding on `p2`
  and a collapsed binding whose primary is `p9` but whose support includes `p2` jointly ground.
- `test_disjoint_support_sets_fail_even_when_conceptually_from_one_anchor` — two bindings with
  genuinely non-overlapping support (`{p1,p3}` vs `{p7,p9}`) fail, regardless of any anchor
  relationship the scenario might stipulate.
- `test_legacy_bindings_without_supporting_proposition_ids_retain_original_behavior` — same-id and
  different-id legacy cases both reproduce the pre-fix result exactly.
- `test_relational_requirement_does_not_fill_from_anchor_co_occurrence_alone` — two independently
  bound, unrelated-support propositions never complete a relational pairing.

## 6. Replay of Phase 2's recorded outputs (again, no model call)

| Child | Requirement | Phase 2 actual state | Phase 3 (pre-fix) state | **Phase 4 (fixed) state** | Phase 2 #inst | **Phase 4 #inst** |
|---|---|---|---|---|---|---|
| c1 | neural-manifestation | `filled` | `partially_filled` | **`filled`** | 4 | **1** |
| c4 | specific-region | `filled` | `filled` | `filled` | 2 | **1** |
| c5 | brain-behavior | `filled` | `filled` | `filled` | 5 | **2** |
| c6 | brain-attitude | `filled` | `filled` | `filled` | 5 | **2** |
| c8 | trait-construct | `partially_filled` | `partially_filled` | `partially_filled` | 8 | **4** |
| c9 | trait-scale-pairing | `partially_filled` | `partially_filled` | `partially_filled` | 8 | **4** |
| c2, c3(×2), c6-cov, c10, c11, c12 | (all) | unchanged | unchanged | unchanged | unchanged | unchanged |

**Every one of the 13 requirements now matches Phase 2's own actual live `state` exactly.** Only
instance counts differ from Phase 2, and only ever downward (correctly deduplicated). **c8→c9
propagation confirmed still 4→4** — unaffected by this fix, since the trait bindings involved were
never in a same_proposition conflict to begin with (c9's own `named_scale_or_instrument` role
stays honestly missing either way).

**No unexpected semantic delta.** The ONLY behavioral change from this fix, across the entire
replay, is c1's state (and it changed back to what Phase 2's own live run actually reported — this
fix makes the corrected accounting agree with the original live result, not diverge from it).

## 7. v8 / v9 confirmation

```
v8 combined_hash (unchanged): 9de276b19d2e5afee5f532d64c6a678de6e59a9f41f37198fa00409c5f3094ac
v9 combined_hash (unchanged): 9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586
```

Both confirmed via `git diff --stat` on both frozen-contract files: **empty, no changes**. This
increment touched only `sufficiency_engine.py`'s verifier logic — no RoleSpec, no
`category_description`, no contract-visible field anywhere.

## 8. Regression results

- Targeted sufficiency suite (9 files): **178 passed**.
- `contract_directed/`: **619 passed**.
- Full `experiments/ask_cli_revised` tree: **2011 passed** (+5 from Phase 3's 2006), **11 skipped**,
  **2 failed** — the same 2 pre-existing, unrelated `hierarchy_contract.py` pin-drift failures,
  reproduced unchanged yet again.

## Recommendation

**Is the generic support-set issue resolved? Yes.** c1 (and, by the same generic mechanism, any
future case with the identical shape) now returns to its correct, evidence-supported state; the
fix is proven generic (not c1-specific) by the adversarial tests, and proven non-anchor-loosening
by both direct tests and the fact that the verifier structurally never receives anchor
information.

**Is v9 now ready for your review/approval and one separately authorized live nomination rerun?
Yes.** The structural layer (instance identity, dedup, joint-grounding) is now internally
consistent against Phase 2's own real evidence, with no open structural finding. The only thing a
live v9 rerun would newly test is whether the Finding-C wording actually changes model behavior —
which, per this increment's own stated limitation, nothing offline can answer.

No live rerun performed. Stopping here, per instruction.
