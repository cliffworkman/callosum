# Phase 12 — structured RecoveryTarget architecture, designed (3 rounds) and implemented (2026-10-01)

**Scope:** implement the structured RecoveryTarget architecture Phase 11 classified REDESIGN
NEEDED, per the accepted 3-round design review. No live model calls. No recovery execution. No
retrieval. No new E2E research run. No contract change. No v10. Recovery gate remains OFF
throughout. v9 `combined_hash` unchanged:
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

See `CONTRIBUTION-LINEAGE.md`'s own Phase 12 entry for the attributed design/implementation
narrative; this report is the fuller technical record, matching Phases 9-11's own convention.

## Files changed

| File | Change |
|---|---|
| `sufficiency_recovery_targets.py` | **New.** The generation module: `new_recovery_target`/`new_target_id`, quantifier-aware per-instance/zero-instance/open_list/at_least_n generators, the confidence-aware hint builder, `compute_recovery_targets` (the orchestration entry point). |
| `sufficiency_recovery_targets_inventory.py` | **New.** Offline, no-live-model inventory script: replays Phase 5's own frozen recorded nominations through the current mapper and reports every generated `RecoveryTarget`. |
| `test_sufficiency_recovery_targets.py` | **New.** 38 tests covering every quantifier, scoping, redirection, budget, identity, and leakage property below. |
| `sufficiency_diagnostic.py` | `_stamp_model_dependency_origins` added, wired into `compute_diagnostic_sufficiency_map`'s existing per-child loop. `compute_recovery_candidates` deleted. |
| `sufficiency_mapping.py` | `_propagated_provenance` gains one more carried-forward field, `model_dependency_origins`. `recovery_hint` deleted. |
| `e2e.py` | Gap-building block rewritten to call `compute_recovery_targets` (pre-round, driving `gaps`) and again (post-round, reporting). Output key `sufficiency_recovery_candidates` → `sufficiency_recovery_targets`. |
| `test_sufficiency_diagnostic.py` | `RecoveryCandidateReportingTests` → `RecoveryTargetReportingTests` (new API); `RecoveryHintTests` removed; `StampModelDependencyOriginsTests` added. |
| `test_sufficiency_leakage.py` | Both `recovery_hint`-based leakage tests ported to `recovery_query_hint`. |
| `test_sufficiency_replay_real.py` | Both `compute_recovery_candidates` usages ported to `compute_recovery_targets`. |
| `CONTRIBUTION-LINEAGE.md` | Phase 12 section appended. |

**Pre-implementation grep (blocker #1, closed):** `sufficiency_recovery_candidates`'s old output
key had exactly one non-test, non-doc consumer — `e2e.py` itself (the line that wrote it). No
external file parsed the key or its shape. Renaming the key and changing its shape was safe.

## Final RecoveryTarget schema

```python
def new_recovery_target(
    *, search_child_id, trigger_child_id, requirement_id, target_roles, reason, goal_mode, scope,
    category_descriptions, relationship_context=None, dependency_origins=None,
    affected_descendants=(), deficit_hint=None,
) -> dict
```

- `reason` (closed, 6 values): `missing | partial | relationship_unverified |
  provisional_corroboration | open_list_breadth | cardinality_deficit`.
- `goal_mode` (closed, 5 values): `single_role | any_of_roles | relationship | breadth |
  cardinality` — drives both target identity and hint-template dispatch; no `disjunctive` boolean.
- `scope`: `{"kind":"none"}` | `{"kind":"instance","instance_key":...}` |
  `{"kind":"cardinality_deficit"}`.

## Target identity payload

```python
{"search_child_id", "requirement_id", "reason", "goal_mode", "target_roles": sorted(...), "scope"}
```
→ `json.dumps(sort_keys=True)` → SHA-256 → first 16 hex chars, prefixed `f"{search_child_id}::"`
for log/test readability (mirrors `sufficiency_engine.derive_instance_key`'s own established
pattern). Excluded from identity: `trigger_child_id`, `affected_descendants` (two descendants
sharing one upstream obligation must produce the *same* id — proven directly,
`test_trigger_child_and_affected_descendants_never_affect_identity`), and `deficit_hint` (one
attempt is intentionally shared across a shrinking `at_least_n` gap,
`test_deficit_excludes_the_changing_count_from_identity`).

## Provenance representation

```python
{"child_id": str, "requirement_id": str, "role": str, "instance_key": str | None}
```
stamped once, at the point a `model_mapping` binding is first created, by
`sufficiency_diagnostic._stamp_model_dependency_origins` (called from
`compute_diagnostic_sufficiency_map`'s per-child loop — never from `sufficiency_mapping.py`,
which stays fully child-agnostic). Carried forward unchanged (never re-minted) by
`sufficiency_mapping._propagated_provenance` at every `parent_context` hop, however deep.
`child_id` is explicit, not reconstructed from a naming convention — `requirement_id` global
uniqueness is **not** an engine-enforced invariant (`sufficiency_engine.new_requirement`/
`new_contract` validate nothing about it; `sufficiency_authoring.py`'s own docstring states its
hand-authored id convention is explicitly not the permanent mechanism). `instance_key` is present
because a multi-instance parent (e.g. `open_list` discovering several distinct trait instances)
can supply more than one independently model-dependent origin to the same downstream role name —
proven directly against the real data (see Inventory, `c6` below) and by two dedicated adversarial
tests.

## Query-hint rules

`recovery_query_hint(target, mapped_contract_by_child)` dispatches on `goal_mode` alone (one
switch, never re-deriving disjunctive/relational-ness a second time — proven,
`test_goal_mode_drives_hint_template_with_no_parallel_branch`):

| goal_mode | template |
|---|---|
| `single_role` | `category_descriptions` joined `"; "`, optionally `"{subject} associated with {context}"` when a relational, clean, short-enough sibling role is resolved |
| `any_of_roles` | `category_descriptions` joined `" or "` (disjunctive) |
| `relationship` | `"evidence connecting {subject} with {context}"` or `"evidence establishing a relationship involving {subject}"` |
| `breadth` | `"additional or different instances of {subject}"` |
| `cardinality` | `"additional instances of {subject}"` |

**Confirmation-bias guard:** a target's own guessed `exact_text` is structurally never read by
`category_descriptions` construction — proven directly,
`test_direct_model_dependent_fill_produces_corroboration_with_no_guessed_value`. **Confidence-aware
relationship context:** a sibling role's concrete value is offered only when its own provenance
shows no model dependence, direct or transitive, **and** its `exact_text` is ≤80 characters
(`_MAX_CONTEXT_EXACT_TEXT_LENGTH`) — added mid-implementation after the offline inventory (below)
surfaced a real `achieved_outcome_predicate`-sourced role returning a whole passage as `exact_text`,
which is not a "short phrase." Otherwise the sibling role downgrades to its own
`category_description`.

## Budget behavior

Two orthogonal axes, unchanged from the design: (1) the existing, untouched per-requirement
`SearchStatus`/`compute_recovery_needed` gate (requirement-wide eligibility); (2)
`compute_recovery_targets`'s own `target_id`-keyed dedup (one entry per unique semantic obligation
per call). The current single-round architecture needs no additional cross-call attempt ledger —
`compute_recovery_targets` is called once pre-round (driving `gaps`) and once post-round
(reporting), each a fresh, complete computation; persisting attempts across *repeated* calls (a
future multi-round increment) remains an explicit, disclosed scope boundary, matching the
pre-existing code's own disclosed boundary for `SearchStatus` itself.

## Deviations from the accepted (round-3) design

Four, all found only by building and testing against real code/data — **none were speculative; each
has its own regression test and, where applicable, is independently confirmed by the offline
inventory**:

1. Provisional corroboration is checked **per instance**, never gated on the requirement's own
   aggregate `state=="filled"` (the round-3 design's own framing). Deferring until the whole
   requirement completes could defer a real corroboration need forever for a multi-instance
   requirement with one perpetually-incomplete sibling (the real `c9` shape). See
   `_targets_for_instance` / `test_multiple_descendants_sharing_one_upstream_dependency_deduplicate`
   and its own extended rationale in the module docstring.
2. Scoping follows `len(requirement["instances"])` at runtime, never the authored `multi_instance`
   flag — `sufficiency_mapping._fork_instances_over_role` can fork a `multi_instance=False`
   requirement into multiple final instances whenever a `model_nomination_only` role yields more
   than one grounded candidate, confirmed by the real `c6` replay result (below). See
   `test_two_independently_model_dependent_instances_do_not_collapse`.
3. Provisional-corroboration origin grouping keys by `(requirement_id, instance_key)`, not
   `requirement_id` alone — the same `c6` shape would otherwise have collapsed two genuinely
   distinct corroboration needs into one target.
4. Relationship-context scaffolding gained a length bound (80 chars) — surfaced by the offline
   inventory itself (`c12`), not anticipated in any design round.

No other part of the accepted architecture changed. `open_list`'s own exclusion from provisional
corroboration (round 2/3's explicit retraction of round 1's claim) was **preserved as-is**, not
silently re-opened, even though the same per-instance mechanism built for deviation 1 could in
principle also apply there — documented in `_targets_for_instance`'s own docstring as a deliberate
scope boundary, not a technical limitation.

## Tests / results

- `test_sufficiency_recovery_targets.py`: **38 passed** (every quantifier; required-vs-alternative
  conjunctive/disjunctive; `relationship_unverified`'s exact `own_evidence_roles` exclusion of
  unused alternatives; zero-instance discovery including upstream deferral; multi-instance scoping
  including the runtime-fork case; direct/one-hop/two-hop redirection; shared-origin dedup across
  descendants; distinct-origin non-collapse; `at_least_n` deficit/corroboration mutual exclusion
  and deficit-count identity-independence; confidence-aware context including the length-bound
  fix; target-identity stability and contract-hash independence; leakage).
- Full sufficiency-family suite (10 files, including this one): **245 passed**.
- Full `experiments/ask_cli_revised/` tree: **2097 passed, 11 skipped, 2 failed**. Both failures
  independently confirmed pre-existing and unrelated to this phase, by direct `git stash`
  comparison against unmodified HEAD:
  - `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`
    — a `hierarchy_contract.py` pin-drift failure in a file this phase never touched; the same
    failure class Phase 6/9/11's own full-tree runs already reported.
  - `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`
    — reproduced identically on baseline HEAD via `git stash`/re-run before restoring this phase's
    work.
- `ruff check` / `ruff format --check`: clean on every file this phase touched or created. Two
  pre-existing lint findings remain, confirmed outside any line this phase edited (a `zip()`
  missing `strict=` in `sufficiency_mapping.map_requirement`, and an unused `overview_evidence`
  import inside `test_sufficiency_replay_real.py`'s untouched
  `test_guard_fields_are_evidence_metadata_never_a_blanket_filter`) — left alone per minimal-diff
  discipline.
- v9 `combined_hash`: confirmed byte-identical before and after, via direct
  `load_frozen_contract()` read:
  `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

## Offline inventory (Phase 5's recorded outputs, replayed — no live model call)

`sufficiency_recovery_targets_inventory.py` replays `sufficiency_phase5_replay.replay()`'s already
-tested, scripted reproduction of Phase 5's own frozen recorded nominations through the *current*
mapper (which now also stamps `model_dependency_origins`) and feeds the result into
`compute_recovery_targets`. **24 targets** were generated. Full JSON is reproducible by running
`python -m experiments.ask_cli_revised.sufficiency_recovery_targets_inventory`; the compact table:

| target_id | reason | search_child | trigger_child | roles |
|---|---|---|---|---|
| c10::201dad5f | missing | c10 | c10 | bias_evidence_in_population |
| c10::bb45b436 | missing | c10 | c10 | named_culture_or_population |
| c11::58757c7f | missing | c11 | c11 | operationalization_or_measure |
| c11::b07b5fa5 | missing | c11 | c11 | culture_or_population |
| c12::019d4235 | partial | c12 | c12 | target_manifestation |
| c12::0c5ffab0 | missing | c12 | c12 | intervention |
| c12::988dfc3b | missing | c12 | c12 | target_manifestation |
| c12::bb70077d | partial | c12 | c12 | intervention |
| c12::e88a9086 | missing | c12 | c12 | observed_effect_or_outcome |
| c1::9e48b8aa | provisional_corroboration | c1 | c1 | brain_region_or_network |
| c2::6fede658 | relationship_unverified | c2 | c2 | behavior_or_behavioral_measure, behavioral_manifestation_evidence |
| c2::c9f6363b | relationship_unverified | c2 | c2 | behavior_or_behavioral_measure, behavioral_manifestation_evidence |
| c3::0ff295b8 | missing | c3 | c3 | category_evidence (instance "implicit") |
| c4::0c3e1a39 | **provisional_corroboration** | **c4** | **c4** (merged with c6) | named_brain_region_or_network |
| c5::22fa1417 | partial | c5 | c5 | behavior_or_behavioral_measure |
| c6::90646ddc | missing | c6 | c6 | category_evidence (instance "implicit") |
| c6::adce70c3 | provisional_corroboration | c6 | c6 | attitude_type_or_measure (instance A) |
| c6::ff512152 | provisional_corroboration | c6 | c6 | attitude_type_or_measure (instance B) |
| c8::2319dd98 | missing | c8 | c8 | individual_difference_trait_or_construct |
| c8::74f276a2 | missing | c8 | c8 | relationship_to_bias_manifestation |
| c9::09faf545 | partial | c9 | c9 | named_scale_or_instrument (instance 1 of 4) |
| c9::1b9c0748 | partial | c9 | c9 | named_scale_or_instrument (instance 2 of 4) |
| c9::3d016672 | partial | c9 | c9 | named_scale_or_instrument (instance 3 of 4) |
| c9::70a8977c | partial | c9 | c9 | named_scale_or_instrument (instance 4 of 4) |

**What this confirms against real data, not synthetic fixtures:**

- **`c9` does NOT redirect upstream.** All four of its discovered trait-scale pairings produce a
  **local** `partial` target for their own missing `named_scale_or_instrument` role, each correctly
  scoped to a distinct `instance_key`. This directly confirms the concrete doubt raised before
  implementation (c9 is `partially_filled` because its own local scale role is missing, not because
  its inherited trait needs corroboration) — c8↔c9 redirection, as originally proposed, **does not
  exist in the real preserved state**.
- **`c4→c6` redirection does genuinely exist.** `c6`'s own relational `brain_attitude` requirement
  inherits `c4`'s `named_brain_region_or_network` via `parent_context`; `c4`'s own direct
  provisional-corroboration target and `c6`'s redirected one share the identical `target_id` and
  correctly merge (`affected_descendants` includes both).
- **`c6` independently proves deviation #2/#3 against real data**, not just the synthetic test: two
  separate, correctly-non-collapsed targets for two distinct model-nominated attitude measures on
  one `multi_instance=False` requirement.
- **`c2` reproduces its own historically-documented shape**: two `relationship_unverified`
  instances, matching the project's own prior finding (Phase 5/6/9) that c2's genuine "visual
  attention" instances legitimately fail joint-grounding against a different proposition than their
  manifestation evidence.

## Recommended first live experiment

Selected **only** from targets that actually appear above, per the stated priority (smallest
interpretable; exercises genuinely new machinery; falsifiable; no fabricated state):

**`c4::0c3e1a39` → the real c4→c6 redirected provisional-corroboration target.**

- **Why this one, not another:** it is the only target in the real inventory that exercises
  redirection at all (the architecture's single most novel mechanism), and it does so together with
  the confirmation-bias guard (the hint must read "a specific NAMED brain area," never the model's
  current guessed region name) and real dedup (`affected_descendants=["c4","c6"]`, proving one
  search serves both the direct and redirected need) — three load-bearing properties in one small,
  real, already-generated target. It is smaller in scope than attempting the `c2` relational case
  (which would need a new joint-grounding verifier path, not a retrieval change) and more
  informative than any of the purely-local `missing`/`partial` targets (c3/c8/c10/c11/c12/c9),
  which exercise no new machinery beyond what `recovery_hint` could already express.
- **What would falsify the architecture, concretely:** (a) the executed query is built from `c6`'s
  own subquestion text or mentions `c6`'s pairing language, rather than `c4`'s own
  "specific-region" question (a redirection failure); (b) the query contains the model's current
  guessed region name rather than only "a specific NAMED brain area" (a confirmation-bias-guard
  failure); (c) running it twice — once reached via `c4`'s own pass, once via `c6`'s redirect —
  produces two separate searches instead of one shared, deduplicated attempt.
- **Not run.** This requires a live model call and live retrieval against the real library, which
  this phase was explicitly scoped to exclude. Proposed as the next, separately-authorized
  increment's first action.

If the maintainer prefers a *non*-redirection first experiment (to isolate variables before adding
redirection to the mix), `c6::adce70c3`/`c6::ff512152` (the direct, non-redirected multi-instance
corroboration pair) is the next-best real candidate — it still exercises the confirmation-bias
guard and real per-instance-key discrimination, just not redirection.
