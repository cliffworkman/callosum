# Phase 11 — rollback, transitive provenance repair, recovery-targeting audit (2026-10-01)

**Scope:** roll back the falsified Phase 9 nomination prompt, repair the Phase 10-confirmed
transitive-provenance gap, and audit (not implement) recovery targeting for provisional fills. No
live model calls. No contract version change — v9 remains byte-identical throughout. Recovery
stays OFF.

## Commits

See the final commit in the reply (this report is committed in the same commit as the code).

## Files changed

| File | Change |
|---|---|
| `qwen.py` | `nomination_prompt` restored byte-for-byte to the exact Phase 5 (commit `f7be3175`) wording |
| `sufficiency_mapping.py` | New `_propagated_provenance` helper (de-duplicates two previously-identical inline constructions); wired into `map_paired_requirement` and `_parent_context_binding_for_single_instance` |
| `sufficiency_engine.py` | `_instance_completion_is_model_dependent` now also checks `provenance["upstream_model_dependent"]` |
| `test_sufficiency_engine.py` | New `TransitiveProvenanceTests` (11 tests) |
| `test_sufficiency_leakage.py` | Removed `ReformulatedNominationPromptLeakageTests` (tested the now-rolled-back prompt text) |
| `CONTRIBUTION-LINEAGE.md` | Phase 11 section appended |
| `PHASE11_ROLLBACK_AND_PROVENANCE_REPAIR_RESULTS.md` | This report |

No file in `sufficiency_phase9_counterfactual_replay.py`/its test, or `sufficiency_phase5_replay.py`/
its test, was touched — both remain valid as explicitly-labeled historical/counterfactual artifacts
(per instruction G: "historical experiment outputs remain historical").

## A. Disposition of the Phase 9 minimal-referent prompt — rolled back, not preserved

**Exact Phase 10 → Phase 11 mapper diff:** `qwen.nomination_prompt`'s return-statement body is
restored to be byte-for-byte identical to its state at commit `f7be3175` (Phase 5's own commit —
confirmed via `git log` that no commit between `1a378501` and `f7be3175` touched `qwen.py`, so this
is unambiguously the exact text Phase 5's live run used). Only the docstring was rewritten (to
document the rollback); the prompt-building code itself is untouched from the historical version.

**Proof the active prompt is byte-identical to Phase 5's live-tested prompt** (not just a source
diff — the actual function output, called with identical arguments):

```python
from experiments.ask_cli_revised.qwen import nomination_prompt as current_prompt
# historical_prompt extracted and exec'd from `git show f7be3175:.../qwen.py`
a = current_prompt(category_description="a named trait", candidates=candidates)
b = historical_prompt(category_description="a named trait", candidates=candidates)
assert a == b  # True
```

**No third formulation was invented. The Phase 9 prompt is not preserved behind a flag** — it is
retired from the live tree entirely; git history (commit `917f746a`) and
`PHASE9_SINGLE_STAGE_MAPPER_RESULTS.md` preserve its exact text for the record. **The Phase 6/7
second-pass specificity validator was not reintroduced** — `confirm_specific_instances`/
`specificity_prompt`/`specificity_schema`/`verify_specific_instances` remain structurally absent
(re-confirmed below). **v9 was not touched.**

**No new mapping diagnostic was run to "prove" the rollback**, per instruction — Phase 5's own
live run is the already-existing experimental record for this exact prompt. The restored text's
provenance is established by direct extraction from git history and a byte-level output
comparison, not by re-running the experiment.

**All later structural fixes were kept, confirmed unmodified in this phase:** anchor-based dedup,
instance-key derivation, `same_proposition` joint grounding with the full support-set semantics
(Phase 3/4), v9's own `RoleSpec` descriptions (Phase 3's Finding C tightening — never touched),
and the Phase 9 provisional stop-search policy (extended, not replaced, in Part B below).

## B. Transitive model-dependence provenance — fixed

### The representation

`sufficiency_mapping._propagated_provenance(parent_requirement_id, source_binding)` — the single
shared construction both propagation call sites now use:

```python
{
    "candidate_source": "parent_context",   # immediate identity -- UNCHANGED, never overloaded
    "detail": f"from parent {parent_requirement_id!r}: {source_candidate_source}",  # unchanged shape
    "model": source_provenance.get("model"),
    "upstream_model_dependent": (
        source_candidate_source == "model_mapping"
        or bool(source_provenance.get("upstream_model_dependent"))
    ),
    "source_lineage": [*source_lineage, "parent_context"],
}
```

**Requirement 1 (preserve `candidate_source="parent_context"` as immediate identity):** satisfied
— `same_proposition`'s own joint-grounding exemption for parent-context roles still depends on
this exact literal string, untouched.

**Requirement 2 (structured, machine-readable upstream provenance, no `detail` parsing):**
satisfied — `upstream_model_dependent: bool` is the primary signal; `detail` remains free text for
human readability only and is never read by any correctness-bearing code (proven directly in
`test_certification_is_unaffected_by_corrupting_the_detail_string`, which both mangles `detail`
and inspects `_instance_completion_is_model_dependent`'s own source for any `"detail"` reference).

**Requirement 3 (transitive across arbitrary depth):** satisfied — `upstream_model_dependent` is
computed as `(immediate source is model_mapping) OR (immediate source's own upstream_model_
dependent)`, a recursive OR that propagates through any number of hops with zero special-casing
per depth. Proven for 1-hop and 2-hop chains (`test_one_hop_propagation_remains_provisional`,
`test_two_hop_propagation_remains_provisional`).

**Requirement 4 (preserve ancestry, not just a lossy boolean):** satisfied — `source_lineage`
accumulates every hop's own immediate `candidate_source`, oldest first (e.g.
`["model_mapping", "parent_context", "parent_context"]`), at the cost of one list append per hop.

**Requirement 5 (`compute_stop_search_certified` treats a binding as model-dependent when
immediate OR upstream says so):** satisfied — `_instance_completion_is_model_dependent` now
checks `candidate_source == "model_mapping" OR provenance.get("upstream_model_dependent")`.

**Requirement 6 (optional roles still don't taint):** unchanged and re-confirmed — `completion_
roles(role_completion)` already excludes `optional_roles`, so a propagated, model-dependent
*optional* binding is never inspected at all
(`test_optional_propagated_model_dependent_binding_does_not_taint`).

**Requirement 7 (no contract/hash change):** satisfied — this is purely binding-provenance/
runtime-state; `frozen_view`'s `_RUNTIME_ONLY_KEYS` already excludes `instances` entirely, so
nothing about this change is hashable (proven directly,
`test_propagated_provenance_never_affects_the_frozen_contract_hash`).

### c8 → c9 reproduction: before / after

Using the exact synthetic shape from Phase 10's own audit:

| | Before (Phase 10, unfixed) | After (Phase 11, fixed) |
|---|---|---|
| Propagated binding `candidate_source` | `"parent_context"` | `"parent_context"` (unchanged) |
| Propagated binding's structured ancestry | *(none existed)* | `upstream_model_dependent=True`, `source_lineage=["model_mapping", "parent_context"]` |
| Child requirement state | `filled` | `filled` (unchanged — semantic sufficiency is untouched) |
| `compute_stop_search_certified(child)` | **`True`** (false certification) | **`False`** (correctly provisional) |

`test_phase10_c8_to_c9_shape_previously_unsafe_now_provisional` locks this in.

## C. Adversarial provenance tests (11 new, `TransitiveProvenanceTests`, all passing)

| # | Test | Proves |
|---|---|---|
| 1 | `test_direct_model_mapping_required_role_is_provisional` | direct `model_mapping` → provisional (restated alongside the Phase 9 suite) |
| 2 | `test_one_hop_propagation_remains_provisional` | model_mapping → parent_context child → provisional |
| 3 | `test_two_hop_propagation_remains_provisional` | model_mapping → parent_context → parent_context grandchild → still provisional |
| 4 | `test_fully_deterministic_ancestry_can_certify` | clean ancestry → certifies normally |
| 5 | `test_mixed_ancestry_stays_provisional_when_the_model_dependent_role_is_required` | mixed deterministic+model ancestry, model-dependent role required → provisional |
| 6 | `test_optional_propagated_model_dependent_binding_does_not_taint` | optional inherited model-dependent binding never taints |
| 7 | `test_immediate_candidate_source_is_always_parent_context_regardless_of_ancestry` | immediate identity never overloaded |
| 8 | `test_structured_ancestry_survives_deepcopy_and_recomputation` | survives `deepcopy` + `recompute_requirement` |
| 9 | `test_certification_is_unaffected_by_corrupting_the_detail_string` | no `detail` parsing anywhere in the certification path |
| 10 | `test_propagated_provenance_never_affects_the_frozen_contract_hash` | hash independence |
| — | `test_phase10_c8_to_c9_shape_previously_unsafe_now_provisional` | the exact Phase 10 reproduction, before/after |

## D. Recovery-targeting audit (code-traced, no implementation)

Traced the complete path from `compute_recovery_needed` through actual query construction, reading
real code at every step, never inferring from names:

1. **`sufficiency_diagnostic.compute_recovery_candidates`** (`sufficiency_diagnostic.py:156`)
   computes `{child_id: [requirement_id, ...]}` — the one place a per-*requirement* list exists.
   Its only consumer is `e2e.py:502`, which assigns it to `recovery_candidates` and places it
   **only** in the final output dict as `"sufficiency_recovery_candidates"` (`e2e.py:634`) — a
   **reporting-only field**, computed from `sufficiency_map_final` (built *after* the recovery
   round already ran). It never feeds back into anything that drives recovery.

2. **The actual recovery-triggering check** is a *separate*, simpler computation at `e2e.py:402-
   415`: for each pre-existing obligation `row` not already a gap, if `any(compute_recovery_
   needed(req, fresh_status) for req in child_contract["requirements"])`, the **entire pre-
   existing obligation `row`** (keyed by `field_id` = the child id) is appended to `gaps`
   unchanged. This is a **child-level boolean gate** — it knows *that* some requirement in this
   child needs recovery, but discards *which* requirement, *which role*, and *why* (missing vs.
   provisional) the instant it decides to append `row`.

3. **`sufficiency_mapping.recovery_hint`** — the one function that *could* build a role-aware,
   benchmark-neutral recovery phrase from a requirement's own missing-role `category_description`s
   — **has zero production call sites**, confirmed by `grep` across every non-test file in the
   tree. It exists, is tested, and is never invoked.

4. **The actual query construction** (`__main__.py:507`):
   ```python
   query = qwen.recovery_query(
       subquestion=subquestion["text"], obligation_note=gap.get("display") or gap.get("note", "")
   )
   ```
   `subquestion["text"]` is the child's own *original*, pre-sufficiency sub-question text.
   `gap.get("display")`/`gap.get("note", "")` read fields off the **same unchanged obligation
   `row`** from step 2 — populated by the pre-existing obligation-judging machinery, with **no
   sufficiency-specific content whatsoever**. `recovery_hint` is never called anywhere in this
   chain.

### Answering the concrete sub-questions

| Question | Answer (code-traced) |
|---|---|
| Does recovery targeting only enumerate missing/partial roles? | **No — it doesn't reach role granularity at all.** It operates at the whole-*child* level; "some requirement needs recovery" collapses to "re-run this child's existing obligation query," with role/requirement identity discarded. |
| Does it understand completion-critical model-sourced roles as needing corroboration? | **No.** Only `compute_recovery_needed`'s single boolean is consulted (via `any(...)`); no role, reason, or provenance detail survives into the query. |
| If dependence arrives through `parent_context`, does recovery know whether the target belongs to the child or its upstream parent? | **No.** The mechanism is anchored to `row["field_id"]` — the child currently being evaluated — with no logic anywhere to redirect to an ancestor child, even when a child's *entire* provisionality is inherited. |
| Would a c2-style false fill produce a useful behavior-focused recovery query, or merely "recovery needed"? | **Merely "recovery needed."** The query uses c2's own pre-existing generic subquestion/obligation text — nothing behavior-specific, nothing naming what's actually uncertain. |
| Would a c9-style completion correctly target corroboration of the upstream trait, or redundantly search a deterministic local role? | **Neither, precisely.** It would re-run c9's own generic subquestion/obligation query — not "redundant" in the sense of re-asking about the deterministic scale role specifically, but **blind** to the fact that the real uncertainty lives in c8's own trait nomination. No corroboration of the upstream trait is attempted. |

## E. Classification: **REDESIGN NEEDED**

The existing recovery-gap representation (a bare obligation `row`, keyed only by child `field_id`,
carrying pre-existing `display`/`note` text) has **no slot** for: which role is provisional, why
(missing vs. model-dependent-but-filled), whether the dependence is direct or transitive, or which
child should actually be re-searched when dependence is inherited. These are not fields that can be
mechanically bolted on — expressing them requires genuine design decisions:

- **How to phrase a role-specific corroboration query** from a `category_description` (`recovery_
  hint` is a candidate starting point, but it has never been validated against a real query-
  construction path, and wiring it in changes what gets searched for — a scope decision, not
  plumbing).
- **Whether and how to redirect a provisional child's recovery to its upstream parent** — this
  changes which child's search budget is spent, interacts with the existing per-child obligation/
  subquestion architecture, and has no existing precedent in this codebase to extend from.
  `source_lineage` currently records *candidate-source types* ("model_mapping", "parent_context"),
  not *originating child ids* — tracking the latter (needed for redirection) is itself a design
  choice about what "useful ancestry" should contain, not a mechanical addition.
- **Whether a provisional-but-filled requirement should get a *different* recovery budget/policy**
  than a `missing`/`partially_filled` one (the current bounded-single-attempt shape was chosen in
  Phase 9 by analogy to `open_list`, but whether that's the right budget for *this* purpose is a
  judgment call, not inspectable from existing code).

**Per instruction, none of this was implemented.** The smallest-scope sketch above is offered for
researcher review, not as a committed design.

## F. Design principle — restated, not re-litigated

Phase 9's stop-search split is not invalidated by Phase 10's poor mapper performance — if anything,
Phase 10 strengthens its motivation: a mapper that is sometimes wrong is exactly the case the split
exists for. This phase's own finding (REDESIGN NEEDED for targeting) does not argue against that
architecture either — it identifies the second, still-missing half: provisional dependence is now
correctly *preserved* (Part B), but nothing yet *acts* on it meaningfully (Part D/E). Recovery
safety needs both; this phase closes the first and documents the second as open.

## G. Recorded / offline validation

No live model calls anywhere in this phase. The restored prompt's correctness was validated by
direct extraction from git history (`f7be3175`) and a function-output comparison — not a new live
run. All provenance tests are synthetic fixtures. Phase 10's own recorded outputs were not replayed
as if they came from the restored prompt — they remain the historical record of the *rolled-back*
formulation's live behavior, cited only as the motivating evidence for the rollback.

## H. Regression

| Suite | Result |
|---|---|
| Targeted sufficiency suite (11 files) | **223 passed** |
| `experiments/ask_cli_revised/contract_directed/` (full) | **619 passed** |
| `experiments/ask_cli_revised/` (full tree) | **2056 passed, 11 skipped, 2 failed — the same 2 pre-existing, unrelated `hierarchy_contract.py` pin-drift failures Phase 6/9's own full-tree runs reported, reproduced unchanged** (confirmed: that file was never touched this phase either). Net +9 over Phase 10's 2047, exactly matching 11 new `TransitiveProvenanceTests` − 2 removed `ReformulatedNominationPromptLeakageTests`. |

## v9 byte-identity confirmation

```
git diff HEAD -- experiments/ask_cli_revised/sufficiency_contract.aib_hier_v9.frozen.json
```
→ empty, both before and after every change in this phase. `combined_hash`:
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586` — unchanged. No v10 created.

## Newly discovered issue

**`sufficiency_mapping.recovery_hint` is dead code at the production level** — fully implemented,
fully tested, and never called from anywhere in the live pipeline. This was not previously flagged
explicitly as such; Phase 11's audit is the first time its actual (non-)usage was traced end-to-
end. Not removed in this phase (its removal or wiring-in is itself part of the Part D/E design
question, deliberately left for researcher review rather than decided unilaterally here).
Additionally: `compute_recovery_candidates`'s own per-requirement detail is computed but
*discarded* into a reporting-only output field, never consulted by the actual recovery trigger —
two independently-computed, redundant recovery-need checks exist in `e2e.py` today (the inline
`any(...)` at line ~410, and the richer-but-unused `compute_recovery_candidates` call at line
~502), a concrete illustration of the same underlying gap.

## Answers to the four questions

**1. Is the empirically strongest mapper restored?**

Yes. `qwen.nomination_prompt` is byte-for-byte identical (verified by direct function-output
comparison, not just source inspection) to the exact text Phase 5's live diagnostic tested and
found strongest (8 correct / 1 incorrect / 0 ambiguous of 9, 0 false negatives). No third
formulation exists; the Phase 9 text is not preserved behind any flag.

**2. Is transitive stop-search provenance now correct?**

Yes, for the dimension it was built to fix: `upstream_model_dependent`/`source_lineage` correctly
survive arbitrary propagation depth, verified adversarially (1-hop, 2-hop, mixed, optional-role-
exemption, hash-independence, no-detail-parsing) and against the exact Phase 10 reproduction
(`True` → `False`, confirmed). This closes the specific gap Phase 10 found; it does not claim
anything beyond that scope.

**3. Can provisional filled requirements currently drive a meaningful recovery query?**

**No.** Code-traced, not inferred: `compute_recovery_needed`'s boolean reaches only a child-level
gate; the actual recovery query is built from the child's own pre-existing, sufficiency-blind
subquestion/obligation text. `recovery_hint` — the one function built to answer this need — has
zero production call sites. A c2-style false fill or a c9-style inherited-dependence completion
would both currently produce the *same generic* recovery behavior any other gap on that child
would, with no role-specific or ancestry-aware targeting at all.

**4. What exactly remains before ONE sufficiency-directed recovery experiment?**

A **REDESIGN** of the recovery-gap representation and query-construction path — specifically: (a)
a requirement/role-aware gap shape (not just a child-level boolean) carrying which role is
provisional and why; (b) a decision on whether and how to redirect a provisional child's recovery
to an upstream parent when the dependence is inherited, which requires extending the current
`source_lineage` (candidate-source types) to also track originating *child ids*; (c) a decision on
whether `recovery_hint` (or a successor) should actually drive query construction, and validation
that doing so produces a genuinely more targeted query than the current generic obligation text.
All three are semantic design choices requiring researcher sign-off, not mechanical plumbing — none
were implemented in this phase, per instruction. **No recovery was run.**
