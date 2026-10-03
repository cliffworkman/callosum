# Phase 26 — offline parent claim-ledger + deterministic rendering (no model, no production wiring)

**Starting HEAD:** `0353c8b868c9e2078ee938fa14558b3da8a04bb5` (Phase 25's own design-audit commit) —
exact match, verified before any edit. **Clean tree before and after** (`git status --porcelain`
empty pre-edit). **Frozen v9 `combined_hash` reconfirmed unchanged throughout:**
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`, read directly from
`sufficiency_contract.aib_hier_v9.frozen.json`. **No live model call, no network retrieval, no
production S2 wiring, no `e2e.py`/`topology.py` change, no sufficiency semantic change, no
contract/pin change.**

## 1. Files changed

**New (all under `experiments/ask_cli_revised/`), zero tracked files touched** (confirmed by
`git diff --stat` against HEAD: empty):

| File | Lines | Role |
|---|---|---|
| `parent_synthesis_ledger.py` | 520 | `build_claim_ledger`, `build_gap_report`, `semantic_claim_key`, `new_claim_id`, `sufficiency_map_hash` — pure |
| `parent_synthesis_render.py` | 161 | `render_answer`, `construction_record` — deterministic, no model client |
| `parent_synthesis_audit.py` | 50 | `audit_parent_synthesis` — re-derive-and-compare, mirrors `overview_audit.py` |
| `parent_synthesis_test_support.py` | 213 | shared fixtures, incl. the real-content `real_c12_fixture()` |
| `test_parent_synthesis_ledger.py` | 609 | 31 tests |
| `test_parent_synthesis_render.py` | 201 | 16 tests |
| `test_parent_synthesis_audit.py` | 97 | 5 tests |

**Expected-zero-change files, confirmed untouched by direct `git diff --stat`:** `e2e.py`,
`topology.py`, `overview.py`, `overview_guards.py`, `overview_evidence.py`, `sufficiency_engine.py`,
`sufficiency_mapping.py`, `sufficiency_diagnostic.py`, `sufficiency_recovery_targets.py`,
`sufficiency_model_scope.py`, `hierarchy_contract.py`, `qwen.py`, both frozen contracts, both pin
files.

## 2. The Phase-25 dedup-key correction (authorized, implemented exactly as specified)

Implemented `semantic_claim_key(*, claim_kind, role, category_description, proposition_id,
exact_text)` as the canonical 5-tuple — role is part of the key. `test_s_role_collision_is_
distinguished` locks this in directly: the identical `(category_description, proposition_id,
exact_text)` bound to two different roles produces two different keys. Documented as a Phase-26
clarification of Phase 25's prose (`parent_synthesis_ledger.py`'s own module docstring), never a
redesign — Phase 25's §8/§9 prose already *stated* the correct rule ("same proposition + DIFFERENT
role → separate ParentClaims"); only its one literal key formula in §9 had dropped `role`.

## 3. A second, grounded refinement found necessary during implementation (not in the original brief)

Phase 25's design text said a relational claim comes from "`kind="relational"`" instances. Reading
`sufficiency_engine.py`'s own module-level comment before implementing
(`REQUIREMENT_KINDS = (...)  # descriptive labels only; state computation dispatches on
role_completion + instance_quantifier, never on kind`) showed this would have been the WRONG
dispatch signal — `kind` is deliberately inert. The implemented rule instead derives
"relational-shaped for this instance" structurally: **`instance["complete"] and
len(own_evidence_roles(role_completion, bindings)) >= 2`** — the exact condition
`recompute_instance` itself already used to decide whether `_joint_grounded` needed to run. This is
not a redesign of the sufficiency engine (nothing there changed); it is choosing the one dispatch
signal the engine's own authors say is load-bearing over the one they say is not. Confirmed correct
against real data: `c4`'s requirement is literally authored `kind="atomic"` yet its 8 real instances
are each a genuine complete, jointly-grounded 2-role pairing (§9 below) — under a naive
`kind=="relational"` check, all 8 would have been wrongly treated as atomic role-value facts and
rendered as if the region and "bears on bias" finding were two independent, uncorrelated claims.

## 4. A real bug found and fixed during implementation (not anticipated in either brief)

First implementation of category-list combination grouped candidates by `(role,
category_description)` **globally**, spanning different requirements. `test_v_proposition_id_is_
the_only_citation_identity...` (two different single-instance requirements sharing one role name
and category_description, different propositions) failed: the two unrelated facts silently
combined into one `category_list`. Re-reading Phase 26's own §11 found the explicit, missed
condition: **"same requirement"** is listed as a precombination precondition, not merely "same
role/category anywhere." Fixed by scoping category-list combination to `(child_id,
requirement_id)` first (within-requirement, within-role identity fold → list combination), with
the cross-requirement identity fold (rule D) applied **afterward**, and only to the resulting
**standalone** atomic values — never to an already-pre-combined `category_list` (`_build_atomic_
claims`'s own docstring states both scopes explicitly). This also fixed the test without changing
the test's own intent. See `test_l_siblings_under_a_list_like_quantifier_fold_into_one_category_
list_claim` / `test_w_a_non_list_like_quantifier_does_not_combine_siblings` /
`test_d_identical_fact_from_sibling_requirements_folds_with_joint_provenance` for the three
scenarios this scoping fix had to keep simultaneously correct.

## 5. `ParentClaim` schema (implemented exactly per Phase 25 §8, as corrected above)

```python
{
    "claim_id": str,                      # new_claim_id(): sha256 of the canonicalized claim, minus itself
    "claim_kind": "role_value" | "relational" | "category_list" | "direction_or_effectiveness",
    "child_ids": list[str],                # sorted
    "requirement_ids": list[str],          # sorted
    "instance_keys": list[str | None],     # sorted, None-last (mirrors sufficiency_engine's own policy)
    "role": str | None,                    # the single role for role_value/category_list; None for relational/direction_or_effectiveness
    "category_description": str | None,    # from RoleSpec.category_description -- NEVER from exact_text
    "values": [{"proposition_id": str, "exact_text": str, "role": str}],  # sorted (role, proposition_id, exact_text)
    "admissible_proposition_ids": list[str],  # sorted; the only legitimate citation set
    "direction_or_effectiveness": dict | None,  # Phase 18's summarize_observations() view, verbatim, when claim_kind is that
    "model_dependency": {"any": bool, "stop_search_certified": bool | None},
    "conflict_or_heterogeneity": dict | None,
}
```

`unresolved_gap` is **not** a `ParentClaim` variant — confirmed: `CLAIM_KINDS` has four members
only, and gaps live in their own, separate `UnresolvedGap` structure (§9 below). No confidence
score, no per-child Overview text field, and no field exists merely for convenience (`_finalize_
claim` validates `claim_kind` against the closed `CLAIM_KINDS` tuple, raising on anything else —
an internal-bug guard, never reachable from real input data).

## 6. Atomic role-value claims (Phase 25/26 §7)

One `ParentClaim` per filled, non-parent-context (`se.own_evidence_roles`) role binding on an
instance that is either incomplete, or complete with exactly one own-evidence role. Never
reconstructed from passage text, never asked of a model, never substituted with outside knowledge —
`exact_text`/`proposition_id` come straight from the binding. `test_a_single_filled_role_becomes_
a_role_value_claim`, `test_g_partial_requirement_surfaces_only_its_filled_own_evidence_role`.

## 7. Partial requirements (§8)

A partially-filled instance's own filled, own-evidence role(s) surface as atomic claims; the
missing role never does, and — critically — no relational claim is ever built from an incomplete
instance, regardless of how many own-evidence roles happen to be filled on it.
`test_x_a_partial_relational_requirement_never_becomes_a_relational_claim` proves the generic
boundary directly: two required roles, one filled, zero jointly-grounded → one atomic claim, zero
relational claims.

## 8. Relational claims (§9)

Built **only** from a `complete` instance whose own-evidence role count is 2+ — the condition
`recompute_instance` already used to run `_joint_grounded`. Admissible evidence is
`sufficiency_engine.relationship_witness_support_ids` **unchanged**, never a naive union of each
role's own support — confirmed on real data (`c1`'s complete instance: `brain_region_or_network`
→ `p11` with `supporting_proposition_ids=['p11','p2']`, `neural_manifestation_evidence` → `p2`
alone; witness intersection is `{p2}` only, and the built relational claim's own
`admissible_proposition_ids` is exactly `['p2']`, confirmed by direct read of the real Phase-23
artifact before writing the fixture). A relational claim is one indivisible unit: its own dedup
identity is the full sorted tuple of every own-evidence role's `(role, proposition_id, exact_text)`
— two relational claims fold **only** when every role's value agrees; a single differing role value
(the real `c4` shape: 8 distinct regions, each paired with the identical "bears on bias" text) keeps
them as 8 separate relational claims, never merged, never listed together (relational claims are
never category-list-combined — that combination is explicitly scoped to atomic `role_value` facts
only, per §11). `test_d_a_complete_jointly_grounded_instance_becomes_one_relational_claim`.

## 9. Parent-context handling (§10)

A `parent_context`-sourced role is excluded by `own_evidence_roles` before any claim/candidate is
ever built from it — it can supply a region's *identity* to a child's own instance but never
contributes its own `proposition_id` to that child's claim's citation set.
`test_k_parent_context_evidence_is_never_cited_as_the_childs_own` builds a genuine two-child
parent/child pair and asserts the parent's own `p1` never appears in the child's claim's
`admissible_proposition_ids` — reusing `_support_set`/`relationship_witness_support_ids`'s already-
existing exclusion, never a new parent-specific rule.

## 10. Category-list claims (§11)

Pre-combined **within one requirement, within one role** (the real §4 correction), when 2+ distinct
`(proposition_id, exact_text)` values exist for that role AND the requirement's own `instance_
quantifier` is in `LIST_LIKE_QUANTIFIERS = {"for_each_discovered_instance", "all_requested_
categories", "open_list", "exists"}`. `exists` is included as an **explicitly audited** addition,
cited to `sufficiency_recovery_targets.py`'s own rule #3 (a `model_nomination_only` role can fork an
`exists` requirement into multiple final instances) and confirmed on real data: `c1`'s own
`brain_region_or_network` requirement is literally `instance_quantifier="exists"` yet produces a
real 6-member category list in the Phase-23 replay (§17). `at_least_n` is deliberately **not**
audited in — no real-data precedent was found, and `test_w_a_non_list_like_quantifier_does_not_
combine_siblings` locks in that two complete `at_least_n` instances stay two separate claims as a
disclosed v1 scope boundary.

## 11. Direction/effectiveness claims (§14)

Consumes `requirement["direction_summary"]`/`effectiveness_summary"]` — Phase 18's `summarize_
observations` output — **verbatim**, never recomputed: `observed_values`, `consensus_value`,
`has_within_instance_conflict`, `has_across_instance_heterogeneity`, `complete_instance_keys`,
`instance_keys_with_observations`, `instance_keys_missing_observations`, `conflicted_instance_keys`
all pass through into `claim["direction_or_effectiveness"]` unchanged. A claim is built only when
the summary shows at least one real observation (`instance_keys_with_observations` or `conflicted_
instance_keys` non-empty) — a declared-but-never-observed field produces no claim, only a gap.
`admissible_proposition_ids` is the union of every contributing complete instance's own observation
proposition ids (both consensus and conflicting observations are citable background).
`test_e_conflicting_directions_preserve_heterogeneity_never_collapse_to_consensus` and
`test_consensus_effectiveness_claim_carries_the_full_orthogonal_view` (the latter against the real
c12 fixture) both pass.

## 12. Deduplication (§13)

Implemented exactly the five required cases: (A) identical `(role, category_description,
proposition_id, exact_text)` folds with joint `child_ids`/`requirement_ids`/`instance_keys`
(`test_d_identical_fact_from_sibling_requirements_folds_with_joint_provenance`); (B) same
proposition/text, different role, never folds (`test_s_role_collision_is_distinguished`, §2); (C)
same value, different relationship/context — covered structurally by (D)'s own `category_
description` check (`test_e_same_value_different_role_or_category_never_folds`); (D) sibling
requirements may fold only when `claim_kind + role + category_description + proposition_id +
exact_text` all agree; (E) independent corroboration (the real c10/c11 "Hadza" named by `p36` and
`p69`) is preserved as two distinct members of one category list, never collapsed to one proposition
(confirmed directly in the real replay, §17).

## 13. Gap report (§15)

`build_gap_report(sufficiency_recovery_targets, sufficiency_map_final=None)` projects the exact
7-field minimal schema (`target_id`, `search_child_id`, `requirement_id`, `target_roles`, `reason`,
`goal_mode`, `category_descriptions`) for every target, sorted by `target_id` for deterministic
output. No suppression logic is invented. **A real, pre-existing, out-of-scope gap was found while
implementing this** (not fixed — no sufficiency semantic change is in Phase-26 scope): `empty_
result_semantically_allowed` is authored onto every requirement (`sufficiency_engine.new_
requirement`'s own parameter, set `True` on exactly one real v9 requirement) but is **never read
anywhere** in `sufficiency_recovery_targets.py` (confirmed by grep: zero references outside the
authoring/engine files) — so a requirement that explicitly declares "an empty result is fine here"
can still generate a `RecoveryTarget`, and therefore a gap-report entry, today. `build_gap_report`
correctly does **not** invent a suppression rule to compensate (that would be exactly the
"manufacturing a gap-closing behavior the engine itself doesn't have" the brief warned against) —
it reports the engine's real, current behavior faithfully, gap and all. `sufficiency_map_final`,
when supplied, is used only as an integrity cross-check (every gap's `requirement_id` must resolve
in the map, or `build_gap_report` raises — proven by `test_a_dangling_requirement_id_fails_loud_
when_a_map_is_supplied`), never to re-derive or suppress anything.

## 14. Sealed-proposition validation (§21)

Every `proposition_id` a claim would cite is resolved against `sealed["verified_propositions"]`
before the claim is built; an unresolvable id raises `ValueError` naming the exact child/
requirement/role, never silently drops provenance or fabricates a citation
(`test_unresolvable_proposition_id_fails_loud`). The real Phase-23 replay (§17) completed end-to-
end with **zero** such exceptions across the whole 11-child map — a genuine, non-trivial integrity
confirmation on real production data, not merely a passing unit test.

## 15. Per-child Overview independence (§24) / `proposition_id` vs `unit_id` (§25)

`test_build_claim_ledger_signature_takes_no_overview_record` asserts the function's own parameter
list is exactly `["sufficiency_map_final", "sealed", "parent_of"]` — structurally incapable of
receiving a per-child Overview record. `test_v_proposition_id_is_the_only_citation_identity_child_
local_ids_never_collide` builds two independent children whose citation identity differs only by
`proposition_id`, confirming no child-local alias (`U1`, `U2`, ...) is ever consulted — the ledger
reads `sealed["verified_propositions"]`'s own `proposition_id` field directly, never an `overview_
evidence.build_units`-assigned per-child number.

## 16. The c12 upstream-error fixture (§20, §28 fixture R)

`parent_synthesis_test_support.real_c12_fixture()` reproduces the real, frozen Phase-23
`c12#suff:intervention-effectiveness` requirement verbatim (every `exact_text`, every role
assignment, including the confirmed-wrong `target_manifestation` value "bias toward people of
color," Phase 23a §3a finding #21) through the real `sufficiency_engine.recompute_requirement` +
`sufficiency_diagnostic.compute_direction_and_effectiveness` — not hand-faked state.
`test_r_the_real_c12_wrong_value_is_reproduced_verbatim_never_corrected` and `test_the_c12_wrong_
value_renders_unflagged_and_unfixed` both confirm: the relational claim's `target_manifestation`
value is the exact wrong text, cited to the exact real passage (`p1` in the fixture's own local
numbering), with no suppression, no flag, no "fix" — proving by construction, not merely by
instruction, that parent synthesis cannot become a second, silent semantic adjudicator (Phase 25
§17's own success criterion).

## 17. Real Phase-23 frozen replay — available and run (§28)

The real, frozen Phase-23 artifacts **are present in this worktree**
(`.local/e2e-runs/phase23-live-recovery-targeted-u2-remap-validation-20261003T020939Z/`) — unlike
the absence Phase 18's own audit found in an earlier worktree. A read-only, offline script (no
`execute()`, no model, no network) loaded `phase23_result.json`'s own `sufficiency_map_final`/
`recovery_targets_final` and `run/11_verified_ledger.json` as `sealed`, and ran `build_claim_
ledger`/`build_gap_report` directly.

**Claim ledger: 24 claims** — 10 relational, 8 role_value, 5 category_list, 1 direction_or_
effectiveness. Zero exceptions (every cited proposition resolved).

**Gap report: 33 gaps** — 13 partial, 10 provisional_corroboration, 7 missing, 3 relationship_
unverified.

**`c12` representation:** exactly as fixture R predicts — 1 relational claim (the real wrong
`target_manifestation` preserved), 1 `direction_or_effectiveness` claim (`consensus_value=
"supported"`, matching the real `effectiveness_summary` exactly), 2 standalone role_value claims
(the `U19` alternate-outcome text from `p34`, and the `U30` off-topic COVID-passage intervention
from `p45` — both surfaced plainly, neither fixed nor flagged), 1 gap (`provisional_corroboration`
on `intervention`/`target_manifestation`) — matching Phase 23a's own six-way pathway taxonomy (§3a)
claim-for-claim.

**`c8` representation:** 1 role_value claim (`relationship_to_bias_manifestation` from `U1`/`p8`)
+ 1 category_list claim (`individual_difference_trait_or_construct`, 4 members, all from the `U6`
contexts' own `p20` bindings — `admissible_proposition_ids` correctly also includes `p9`, an
anchor-dedup-collapsed `supporting_proposition_ids` sibling on each of the 4 real bindings,
independently confirmed by direct read of the raw JSON before trusting the ledger's own output) + 2
gaps (both roles "missing" — confirmed this is **not** a contradiction: `c8` is
`instance_quantifier="open_list"` with 5 real instances, and the 2 recorded targets name a
different, still-undiscovered instance scope for each role, exactly matching Phase 23a's own
"missing-scope" framing in §7 of that document, not "the role has zero values").

**`c11` representation:** 1 category_list claim (`culture_or_population`, 2 members — both real
"Hadza" quotes from `p36`/`p69`, correctly NOT collapsed to one, §12 case E) + 4 gaps (culture
missing on one instance, measure missing/partial on two others) — matching Phase 23a's own §9
assessment that c11's culture half improved while its measure half never did.

**Direction/effectiveness preservation:** the one `direction_or_effectiveness` claim in the whole
real map (`c12`'s own) carries `consensus_value="supported"`, `has_within_instance_conflict=False`,
`has_across_instance_heterogeneity=False` — byte-identical to the real `effectiveness_summary`
field already present in `phase23_result.json`, confirming the claim-construction pass changed
nothing about Phase 18's own already-correct derived view.

**Provenance resolvability:** confirmed structurally — the replay could not have completed without
raising had any of the real map's cited `proposition_id`s failed to resolve against the real sealed
ledger (§14); it completed cleanly.

## 18. Deterministic renderer (§17/§18)

`parent_synthesis_render.render_answer(claim_ledger, gap_report, *, sealed=None)` — `sealed` is an
additive, optional third parameter (not in Phase 25/26's own pseudocode, added because showing a
real cited passage genuinely needs it; omitting it reproduces a fully provenance-complete answer
using each claim's own short `exact_text` spans). Four literal templates, deliberately unfluent per
§18's own instruction: `"{category_description}: {exact_text}."` (role_value/category_list, the
latter joining members with `"; "`), `"A reported relationship ({role: exact_text; role: exact_text
...})."` (relational — every role shown, nothing inferred between them), and a direction/
effectiveness template that states `consensus_value` plainly when one exists and otherwise lists
every observed value **and** names which instances disagree or conflict, never collapsing either.
Qualified/heterogeneous findings (`has_within_instance_conflict` or `has_across_instance_
heterogeneity`) are routed to their own section and **never** appear in the main Overview
(`test_heterogeneous_direction_claim_appears_under_qualified_never_in_overview`,
`test_consensus_direction_claim_appears_in_overview_not_qualified`). The real c12 wrong value
renders unflagged, exactly as the ledger carries it (§16).

## 19. Construction record / hash (§22)

```python
{
    "version": "parent-synthesis-v1",
    "sealed_ledger_hash": str, "sufficiency_map_final_hash": str,
    "claim_ledger": [...], "gap_report": [...],
    "realization_state": "deterministic_only",   # the only value Phase 26 ever produces
    "fallback_used": True,
    "parent_synthesis_hash": str,                 # computed LAST, over everything above
}
```

No fake model metadata (`test_no_fake_model_metadata` asserts `model`/`think`/`call`/`prompt` are
absent as keys). `realization_state` is always `"deterministic_only"` in Phase 26 — the brief's own
pseudocode offered `deterministic_only / not_run` as alternatives, but no principled distinction
between them exists yet (the deterministic renderer always "runs," even over an empty ledger);
introducing a second, currently-meaningless value was judged worse than naming the one real state
honestly. Phase 27 can add `"model_realized"` additively without a schema break. `sufficiency_map_
hash`/`sealed_ledger_hash` are threaded in by the caller (not computed internally), keeping this
module a pure function of its own arguments.

## 20. Audit / re-derivation (§23)

`parent_synthesis_audit.py` (50 lines) — the full re-derive-and-compare seam, not deferred:
`audit_parent_synthesis(sufficiency_map_final, sealed, sufficiency_recovery_targets, record)`
re-runs `build_claim_ledger`/`build_gap_report`/`sufficiency_map_hash` and compares each to the
stored record, plus an independent hash-of-hash check (rebuilding `construction_record` from the
record's own claim/gap lists and comparing `parent_synthesis_hash`). Every check runs through the
same `_check()`-swallows-exceptions pattern `overview_audit.py` already established — a malformed
record fails the audit, never crashes it (`test_a_malformed_record_fails_the_audit_never_crashes_
it`). No realization-stage vocabulary appears anywhere in this file, deliberately: that is Phase
27's own audit surface, not pulled forward here.

## 21. Readability choice (§29)

The literal `"{category_description}: {exact_text}."` template (role_value/category_list) plus the
explicit per-role join for relational claims was chosen over a more "flowing" per-child-subtree
prose shape — not because the flowing shape is wrong, but because Phase 26 owns no model and must
not invent connective prose between independently-true facts (exactly the risk §18 warns against).
This is recorded as a rendering choice only, per the brief's own instruction: it does not touch
`ParentClaim` shape, claim ids, citation provenance, combination semantics, or the gap report, and
Phase 27's own bounded editorial pass remains free to produce more natural prose from the identical
ledger without this file changing at all.

## 22. Test counts

**New, focused:** 31 (`test_parent_synthesis_ledger.py`) + 16 (`test_parent_synthesis_render.py`)
+ 5 (`test_parent_synthesis_audit.py`) = **52 passed**, 0 skipped, 0 failed. `ruff check` and
`ruff format --check` clean on all 7 new files.

**Full regression** (`pytest experiments/ask_cli_revised -q`): **2402 passed, 11 skipped, 3
failed.** All 3 failures were independently reproduced **identically** against the exact Phase-25
HEAD with all 7 new Phase-26 files moved out of the tree entirely (not merely reverted — physically
absent, confirmed via `git status --porcelain` showing a bit-for-bit clean tree) — proving none of
the three is caused by this phase:

1. `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_
   model_facing_text_with_no_side_effects` — `rc=3 != 0`: the known, long-standing hierarchy
   pin-drift rejection on the real (non-test) `load_contract_for_live` path, named by every phase
   since before Phase 19b.
2. `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_
   preserved_artifacts` — the same pin-drift family.
3. `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_
   tree_and_is_marked_unscored` — **not previously named in this session's phase docs**; the real
   traceback is `httpx.ConnectError: [WinError 10061] No connection could be made because the
   target machine actively refused it` against a loopback Ollama endpoint. This matches an
   already-recorded, pre-existing, environment-dependent issue (a test in this suite performs a
   real `GET` against the shared Ollama port unless a JUNO tunnel/socket-refusing launcher is
   active) — not a regression, and not something this phase's purely-additive, model-free files
   could cause or fix. This also explains the one-less-than-Phase-24's-reported-baseline pass
   count (2350 vs. 2351 on the clean baseline): the discrepancy is this same pre-existing flake,
   intermittent across environments/sessions, never a code regression between Phase 24/25 and now
   (confirmed: Phase 25 made zero code changes).

## 23. v9 hash / pin drift

`sufficiency_contract.aib_hier_v9.frozen.json`'s `combined_hash` reconfirmed byte-identical
throughout: `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`. Pin drift (§27 of
the brief): unaffected and unworsened, per the identical disposition every prior phase has
recorded — every Phase-26 fixture is a literal dict or an injected `sealed`/`sufficiency_map_final`,
never routed through `load_contract_for_live`.

## 24. Newly discovered issues

1. **(Fixed, during implementation, Section 4 above.)** Category-list combination was first scoped
   too broadly (across requirements); corrected to the brief's own explicit "same requirement"
   condition.
2. **(A grounded design refinement, Section 3 above, not a defect.)** Relational-vs-atomic
   dispatch uses `own_evidence_roles` count, never the authored `kind` label, because
   `sufficiency_engine.py` itself documents `kind` as non-load-bearing.
3. **(Found, documented, explicitly NOT fixed — no sufficiency semantic change in scope, Section
   13 above.)** `empty_result_semantically_allowed` is authored but never consulted by
   `sufficiency_recovery_targets.py`, so a requirement that explicitly permits an empty result can
   still generate a gap-report entry today.
4. **(Pre-existing, confirmed unrelated, Section 22 above.)** A third, previously-unnamed, real,
   environment-dependent test failure (`RunTopologyGuardTests`'s own loopback-Ollama `httpx.
   ConnectError`) — independently reproduced on the clean Phase-25 baseline with this phase's files
   completely absent.

## 25. Phase 26 status

**CLOSED.** Every item in the brief's §33/§34/Hand-back lists is implemented, tested (offline,
including against real frozen production data), and documented above. The deterministic layer
makes it mechanically impossible (not merely discouraged) to: merge different semantic roles
(§2/§12 case B), invent a cross-requirement relation (§5/§8, Phase-25's own core invariant), cite a
child-local `U#` as global evidence (§15), lose proposition provenance (§14), collapse
heterogeneity/conflict (§11/§18), turn a partial relation into a complete relational claim (§7),
hide an unresolved `RecoveryTarget` (§13), silently correct an upstream semantic error (§16),
depend on per-child Overview prose (§15), or depend on traversal order (every ledger-construction
test above holds under reversed/shuffled input order, by construction of `_fold`'s own key-based
accumulation rather than positional logic) — while still producing a readable deterministic answer
(§18) over real production data (§17).

## 26. Phase 27 readiness

**READY.** The claim ledger, gap report, construction record, and audit seam are all in place and
proven against both synthetic adversarial fixtures and the real frozen Phase-23 state. Phase 27's
own scope is now narrow and well-bounded: one new `parent_synthesis.py` orchestration module
wiring (a) the existing resident `bound.supervisors["S"]` for one bounded realization call per
hierarchical run (reusing `overview_guards.screen`/the batched local-NLI pattern, scoped to each
claim's own `admissible_proposition_ids` rather than a per-child unit pool, per
`PHASE25_BOUNDED_PARENT_SYNTHESIS_DESIGN_AUDIT.md` §18), (b) the zero-retry deterministic fallback
this phase already built as the on-failure path, and (c) the `e2e.py` hierarchy-arm integration
itself, behind its own independent, default-off flag. No part of Phase 26's own surface is expected
to change to support it.
