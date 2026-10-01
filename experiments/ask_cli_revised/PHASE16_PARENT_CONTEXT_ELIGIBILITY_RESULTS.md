# Phase 16 — parent-context multiplicity and parent-instance eligibility: implementation (2026-10-01)

Implements the design accepted in Plan Mode (the `instance.complete` eligibility rule, applied
**uniformly** per Cliff's own researcher decision — no special-casing for the `for_each_
discovered_instance`/c9 shape), with one implementation-level refinement Cliff required
(own-evidence-first must never duplicate per eligible parent) and several real issues found and
fixed during implementation itself, documented below rather than silently absorbed.

## Commits

- `sufficiency_engine.py` / `sufficiency_mapping.py` / `sufficiency_recovery_targets.py` — the
  three production files changed.
- `test_sufficiency_engine.py` / `test_sufficiency_mapping.py` / `test_sufficiency_recovery_
  targets.py` / `test_sufficiency_phase5_replay.py` / `test_sufficiency_phase9_counterfactual_
  replay.py` — new coverage plus the deliberate, documented updates to pre-existing assertions
  the fix correctly overturns.
- This results doc + `CONTRIBUTION-LINEAGE.md` entry.

Starting HEAD: `3231ca33d0c17f1e319f46957627119ec0d63e1b`. v9 `combined_hash` confirmed unchanged
throughout: `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

## Exact code paths changed

- **`sufficiency_engine.py`**: new `eligible_parent_instances(parent_requirement, parent_role)` —
  the ONE shared primitive (role filled AND `instance.complete`), used identically by the mapper
  and the RecoveryTarget layer so they can never disagree about whether a usable parent exists.
- **`sufficiency_mapping.py`**: `_parent_context_binding_for_single_instance` **retired outright**
  (confirmed: `grep` finds zero remaining references in any `.py` file). `map_paired_requirement`
  rewritten as the SOLE parent-context instance-generation path for every quantifier.
  `map_any_requirement`'s parent-context dispatch collapsed from two branches (one per quantifier
  shape) to one. `map_requirement` and `_fork_instances_over_role` both lost their now-dead
  `parent_context_bindings` parameter (the only caller that ever supplied a non-empty value is
  the retired branch).
- **`sufficiency_recovery_targets.py`**: `_first_instance_targets`'s `parent_has_source` check now
  calls `se.eligible_parent_instances` instead of a bare role-filled check. New `_merge_recovery_
  target` helper replaces the old "only `affected_descendants` is merged, everything else silently
  keeps the first value" logic in `compute_recovery_targets`'s own merge loop. A new, narrow,
  `exists`-only suppression in the main per-instance loop.

## `_parent_context_binding_for_single_instance`: retired — confirmed

Yes. `grep -rn _parent_context_binding_for_single_instance experiments/ask_cli_revised/*.py` finds
zero hits. Three test call sites that invoked it directly (none in production code) were migrated
to construct the equivalent propagated binding inline via the still-current `_propagated_
provenance` (exactly what the retired helper did internally for one instance) — these tests
exercise `compute_recovery_targets`'s own dedup/redirect logic over an already-propagated
structure, not mapper eligibility, so the substitution is behavior-neutral for what they actually
test.

## Final parent eligibility primitive / rule

```
eligible_parent_instances(parent_requirement, parent_role) =
    { instance in parent_requirement.instances
      | instance.role_bindings[parent_role].state == "filled"
      AND instance.complete == True }
```

Applied **uniformly** per Cliff's researcher decision (brief §A) — `exists` (c4→c5/c6) and
`for_each_discovered_instance` (c8→c9) alike, with no special-casing of the eligibility rule
itself by quantifier. `instance.complete` is explicitly NOT `compute_stop_search_certified`: a
complete-but-model-dependent instance remains eligible, and its model-dependence propagates
forward unchanged via the existing, untouched `_propagated_provenance` (`upstream_model_
dependent`/`source_lineage`/`model_dependency_origins`) — confirmed by a dedicated test
(`test_complete_model_dependent_instance_is_eligible_not_gated_on_stop_search_certification`).

## Own-evidence-first — exact behavior, and the refinement found necessary

Implemented exactly as brief §E specified: try the child's OWN evidence for the parent-context
role first (via the existing `_bind_role_candidates`); if it yields ≥1 grounded candidate, those
candidates are forked exactly like any other role and the parent is **never consulted at all**
for this role — no per-eligible-parent duplication. Only when own evidence is empty does the
function fall back to `eligible_parent_instances`, forking once per eligible parent.

**One real, necessary scoping refinement, found during implementation, not anticipated in the
accepted design**: own-evidence-first is tried for every parent-context shape **except**
`for_each_discovered_instance`. Attempting it unconditionally broke six real tests (synthetic
fixtures in `test_sufficiency_engine.py`/`test_sufficiency_diagnostic.py`, plus — more
seriously — the REAL recorded Phase 2/5/9 replay fixtures, which raised `RecordedNominationReplay
Error` because the new own-evidence call for c9's own `individual_difference_trait_or_construct`
role is a genuinely new model query shape Phase 2's historical trace never recorded at all). Root
cause: `for_each_discovered_instance`'s own semantics is "mirror exactly what the parent
discovered" — incompatible with the child ALSO independently re-discovering the identical role
from its own candidate pool (which often overlaps with the parent's, since units can be shared).
c9's own `sufficiency_authoring.py` comment is explicit and pre-dates Phase 16: it "does not ask
again which traits relate to the bias" — this refinement preserves that deliberate prior
commitment rather than silently overriding it. Dispatched on the already-generic, domain-agnostic
`instance_quantifier` field — not a q_aib-specific name check.

## Multiplicity / forking behavior

- **Zero eligible, own evidence empty, `for_each_discovered_instance`**: zero instances
  (unchanged from before Phase 16 — `for_each`'s own semantics genuinely means "none discovered").
- **Zero eligible, own evidence empty, any OTHER shape (e.g. `exists`)**: exactly ONE base
  instance with the parent role explicitly `missing` — **a real bug caught and fixed during this
  phase's own re-verification**, not anticipated in the accepted plan, which had stated "no
  change from today" for this case without checking it concretely. My first implementation
  produced ZERO instances here too, which silently also skipped testing the requirement's OTHER
  role(s) against the child's own evidence — a real evidence-blind regression, not merely
  cosmetic (caught because it broke the Phase-15 harness's own byte-identity verification gate
  against `phase13_result.json`, not by inspection). Fixed to build exactly one base instance,
  matching what the retired `map_requirement`-based fallback path always did. Two new tests lock
  this in directly (`test_zero_eligible_parents_still_tests_the_childs_other_role_against_its_
  own_evidence`, `test_for_each_discovered_instance_with_zero_eligible_parents_is_still_zero_
  instances`).
- **Exactly one eligible (own evidence empty)**: one instance, as before.
- **Multiple eligible (own evidence empty)**: one child instance PER eligible parent — never
  `instances[0]`, never selection by list order.

## Canonical ordering

`eligible_parent_instances` returns its result sorted by `instance_key`, never raw list order.
The eligible SET itself is a pure per-instance filter with no cross-instance state, so the
semantic result (which instances get built, what they contain, the aggregate state) is provably
order-invariant regardless of this sort — the sort exists for stable serialized output only.

## c8→c9 before/after (real data, `sufficiency_phase5_replay.replay()`)

**Before**: c9 `partially_filled`, 4 instances — paired against all four of c8's own discovered
trait instances, each generating its own "which scale measures this trait" obligation.

**After**: c9 `missing`, **0 instances**. Confirmed directly: every one of c8's real 4 instances
has `individual_difference_trait_or_construct` filled but `relationship_to_bias_manifestation`
genuinely `missing` (not merely unverified) — `instance["complete"] == False` for all four. Under
the uniform eligibility rule, zero are eligible, so c9 correctly propagates nothing. The real
unresolved obligation (confirmed via `compute_recovery_targets`) remains exactly where it belongs:
two targets owned directly by c8 itself (`missing`/`individual_difference_trait_or_construct` and
`missing`/`relationship_to_bias_manifestation`), unchanged from before this phase. Zero c9-owned
or c9-triggered targets remain (confirmed: the Phase-12 inventory script's own target count drops
from 24 to **20**, exactly the four c9-owned targets this closes, nothing else).

## Phase-15 c4/c5/c6 before/after (real recorded nomination, replayed offline — no new live call)

**Before** (the live result as originally recorded): c4 forks into RTPJ (incomplete) + amygdala
(complete); `instances[0]` was RTPJ (the model listed it first); c5 AND c6 both inherited RTPJ.

**After** (same recorded nomination output, replayed through the fixed code): c4 still contains
**both** instances (RTPJ incomplete and visible, amygdala complete) — nothing is hidden. c5 and c6
now inherit **only** the amygdala. Confirmed with the real recorded 3-nomination output in **both**
list orders (forward and reversed) — identical result either way, closing the exact adversarial
gap Phase 15 exposed. Locked in permanently as `test_real_phase15_recorded_nomination_end_to_end_
c6_inherits_amygdala_only` (the real raw nominations hardcoded as a frozen literal — no dependency
on any `.local/` artifact).

## Mixed-instance `exists` RecoveryTarget — before/after

**Before**: c4 (aggregate `state=="filled"` via the amygdala instance) ALSO generated a
`relationship_unverified` target for the incomplete RTPJ sibling — a real, previously-unexamined
gap (no prior phase had ever produced a mixed-completeness `exists` instance set).

**After**: that target is suppressed — `exists` needing only one complete instance means an
incomplete sibling's own gap is not itself a recovery obligation once satisfied. The satisfying
(amygdala) instance's own `provisional_corroboration` obligation is unaffected (it is `instance[
"complete"]==True`, so the new `exists`-scoped skip never applies to it). Scoped narrowly: `for_
each_discovered_instance`/`at_least_n` are explicitly untouched (every instance's completion
still genuinely matters to those aggregates) — confirmed by a dedicated test (`test_suppression_
is_scoped_to_exists_never_for_each_discovered_instance`).

## `dependency_origins` merge — behavior, and a real finding

`_merge_recovery_target` now unions/deduplicates **both** `affected_descendants` (as before) and
`dependency_origins` (previously silently kept whichever generation call was seen first).

**A real disagreement was found and resolved while implementing the "stop and report on any other
field disagreeing" guard** — not hypothetical, confirmed by running the EXISTING real-shape test
(`test_multiple_descendants_sharing_one_upstream_dependency_deduplicate`): `trigger_child_id`
genuinely differs between the parent's own direct pass (`trigger_child_id="p"`) and a redirected
descendant's pass (`trigger_child_id="c1"`) for the identical `target_id`. Resolved by treating
`trigger_child_id` as a third benign, already-superseded bookkeeping field (its information is
fully subsumed by the now-unioned `affected_descendants`), kept at its pre-existing "first call
wins" value, documented explicitly in `_merge_recovery_target`'s own docstring — not silently
absorbed into the strict-equality check, and not a reason to touch target identity (none of the
five identity-bearing fields `new_target_id` hashes ever disagreed in any real or synthetic case
found this session).

## New/changed tests

- `test_sufficiency_engine.py`: new `EligibleParentInstancesTests` (7 tests); one existing test's
  direct call to the retired helper replaced with an inline equivalent.
- `test_sufficiency_mapping.py`: `PairedMappingTests` fixture made complete-by-default with an
  explicit `relation_filled` toggle; new `test_incomplete_parent_instance_with_filled_role_does_
  not_propagate` (the deliberate behavior-change lock-in brief §B asked for); `test_parent_
  context_alone_never_completes_a_requirement` rewritten onto the new mechanism; new
  `ParentEligibilityForkingTests` (16 tests covering matrix items 1/3/4/5/6/7/8/13/16/17 plus the
  zero-eligible-parent regression and the real Phase-15 end-to-end replay with its reversed-order
  companion).
- `test_sufficiency_recovery_targets.py`: new `test_parent_backed_for_each_with_an_incomplete_
  parent_defers_upstream` (matrix item 19); new `MixedInstanceExistsRecoveryTests` (3 tests,
  matrix item 15); new `RecoveryTargetMergeTests` (5 tests, matrix item 18); two existing tests'
  direct calls to the retired helper replaced with a small shared `_propagate` test helper.
- `test_sufficiency_phase5_replay.py` / `test_sufficiency_phase9_counterfactual_replay.py`: the
  two real-data c8→c9 expectations updated with explicit, documented rationale (matrix item 9),
  never silently.

## Regression

Full sufficiency family (12 files): **294 passed**. Full `experiments/ask_cli_revised/` tree:
**2127 passed, 11 skipped, 2 failed** — both failures reproduced identically against unmodified
HEAD (confirmed via `git diff --stat`: neither `hierarchy_contract.py` nor `test_hierarchy_e2e.py`
appears in this phase's diff), the same two pre-existing issues Phase 12's own hand-back already
disclosed (hierarchy pin-drift; a `--preflight-only` readiness-code mismatch). v9 `combined_hash`
confirmed byte-identical throughout. `ruff format`/`ruff check` clean on every file this phase
touched (one pre-existing, untouched F841 in `test_sufficiency_mapping.py` confirmed outside
every diff hunk). No live model call, no retrieval, no recovery execution, no contract or pin
change, no production model-assisted lifecycle integration.

## Newly discovered issues (all found and resolved during implementation, documented above)

1. Own-evidence-first, applied unconditionally, silently swaps a parent-context inheritance for
   an untested-by-replay independent re-discovery on the `for_each_discovered_instance` shape —
   fixed by scoping it away from that quantifier (see above).
2. The accepted plan's own "zero eligible parents → no change from today" claim was concretely
   wrong for the non-`for_each` shape: a literal zero-instance implementation silently stops
   testing the requirement's OTHER role(s) too — fixed to build one base instance, matching prior
   behavior exactly (see above).
3. `trigger_child_id` is a real, confirmed field that can legitimately disagree across merging
   calls sharing one `target_id` — resolved as a third benign/superseded field (see above).

## Is parent-context semantics now CLOSED?

**Yes**, for the three real v9 uses (c4→c5, c4→c6, c8→c9) and for the general mechanism: a single
eligibility rule, a single instance-generation path, order-invariance proven adversarially on
real data in both directions, multiplicity handled generically, provenance preserved unchanged,
and the one related RecoveryTarget gap (mixed-instance `exists`) closed in the same pass. Not
touched, and explicitly out of scope per the brief: C2 re-sealing locality/stability (§N) and
production model-assisted lifecycle integration (§O) — both remain open, separate concerns.

## Recommended next phase

**C2 RE-SEALING STABILITY / LOCALITY** — no implementation evidence from this phase surfaced a
blocker requiring it to precede anything else; Cliff's own proposed ordering (parent-context
correctness → C2 re-sealing → production lifecycle integration) is confirmed sound and unchanged.
