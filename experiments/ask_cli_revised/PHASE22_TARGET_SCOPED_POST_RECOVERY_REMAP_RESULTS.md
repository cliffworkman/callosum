# Phase 22 — target-scoped post-recovery model remapping

**Offline-first implementation. No live model call, no network retrieval, no live recovery
experiment. One existing recovery gate; no second feature flag.**

## Authoritative state

- Starting HEAD: `e1e50c23ac463b6463e1071dd9d1011ee189a76b`, matching the brief's expected
  `e1e50c23` exactly. Working tree clean.
- Frozen v9 `combined_hash` reconfirmed unchanged:
  `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.
- Phase 21 remains CLOSED, infrastructure PASS, one live run only — untouched by this phase.

## Lifecycle implemented

```
U1 (unchanged): ALL_ELIGIBLE -> immutable U1 receipt snapshot
compute RecoveryTargets (gated on sufficiency_recovery_gate_enabled -- the ONLY gate)
one recovery round (unchanged)
seal recovered evidence (unchanged)
derive exact finite fresh-request set F:
    post-recovery dry enumeration (candidate-construction only, fake client, no network)
    + project_fresh_request_keys (pure, uses the REAL U1 map for historical lookups)
U2: prior_receipts = U1 snapshot, authorization = exact_request_set_policy(F)
    -> full stateless remap, fresh calls only for F, held-fixed elsewhere
recompute direction/effectiveness, stop-search, RecoveryTargets (unchanged, re-run as-is)
STOP (one round only, no iteration)
```

When `sufficiency_recovery_gate_enabled=False`: `recovery_targets_initial` is never computed
(pre-initialized to `None`), F is never derived, `exact_request_set_policy(frozenset())`
authorizes nothing — byte-identical in effect to Phase 20b/21's own `exact_scope_set_policy(set())`,
now expressed through the one unified, request-granular policy kind.

## Request-context provenance (the identity layers, preserved distinct)

`instance["request_context"]` is stamped once in `map_requirement`, immediately after `root_key`
is known and before any role is bound or forked — a top-level field on the instance itself, never
only on one role's binding, so it survives even when every role stays `missing`/
`fresh_no_candidates`. Deliberately **not** added to `se.new_instance`'s own signature — a single
assignment in `map_requirement` was sufficient; `map_paired_requirement`/
`map_cardinality_requirement`-produced instances simply never set it, degrading correctly to `None`
via `.get(...)`.

`model_dependency_origins` (both the canonical stamping site,
`sufficiency_diagnostic._stamp_model_dependency_origins`, and the inline fallback construction in
`sufficiency_recovery_targets._provisional_corroboration_targets_for_instance` — a real consistency
gap this implementation found and fixed, since the fallback path is what several of this module's
own existing hand-built test fixtures exercise) now reads `request_context` from the owning
instance and includes it as a fifth field: `{child_id, requirement_id, role, instance_key,
request_context}`. Parent-context propagation (`_propagated_provenance`) needed **zero** changes —
it already forwards the whole `model_dependency_origins` list verbatim, so the new field rides
along for free through every propagation hop.

This intentionally changes the provenance shape Phase 19b deliberately deferred. The Phase-19b
regression test that pinned the old 4-field shape
(`test_a_model_dependency_origins_shape_is_unchanged_by_this_phase`) is renamed and updated to
assert the new, intentional 5-field shape
(`test_a_model_dependency_origins_shape_carries_request_context_as_of_phase_22`).

## `exact_request_set_policy`

A new, **separate** policy kind in `sufficiency_model_scope.py` — never an overload of
`exact_scope_set_policy`'s own `scopes` field, so a policy's authority level (whole-scope vs.
exact-request) stays obvious from its `kind` alone. `is_authorized_for_fresh_call` gains an
optional `request_context=None` parameter; `all_eligible`/`exact_scope_set` both ignore it
(byte-identical pre-Phase-22 behavior for every existing caller); `exact_request_set` checks
`(scope, request_context) in policy["request_keys"]`. `resolve_nomination`'s own call site threads
`request_context` through — no change to the raw model protocol, no change to receipt/fallback
semantics.

## `project_fresh_request_keys` — the exact F projection

A pure function in `sufficiency_recovery_targets.py` (no model call, no mutation, no hidden
state). Two routes:

1. **Reconsideration** — a `provisional_corroboration` target's own `dependency_origins` already
   name the exact historical `(scope, request_context)`. Multiple targets sharing one origin
   collapse to one key by ordinary set membership.
2. **Discovery** — every other reason. `sufficiency_model_scope.model_scopes_for_recovery_target`
   (unchanged, Phase 19) derives the semantic scope(s); then:
   - **Instance-scoped** target: resolve ONLY the named instance via the REAL U1 map
     (`sufficiency_map_initial` — never the post-recovery dry map), never a sibling. Included iff
     that instance's own role is not yet `filled`.
   - **Scope-wide** target (no single instance to name): if the role is already `filled` on *any*
     existing instance for the requirement, every existing request is excluded — only a genuinely
     new post-recovery context may enter. Otherwise every existing-and-unfilled instance's key,
     plus every new one, enters.

**`InitialKeys`/`PostRecoveryKeys` are consulted only to find genuinely new requests
(`PostRecoveryKeys - InitialKeys`)** — every historical question is answered directly from the real
U1 map, never inferred from key-set membership alone.

### Why the initial map, never the dry map, for historical lookups

Traced precisely during the design pass: the post-recovery dry pass's own final mapped instance
tree is **not** model-output invariant — `map_requirement`'s own role-forking produces a different
number of final instances depending on how many nominations a client accepts, and a fake client
(always `[]`) never forks. Only the **set of reachable `(scope, request_context)` keys and their
candidate rows** are invariant for the mechanisms currently in use (confirmed by direct trace of
`map_requirement`, `_fork_instances_over_role`, and `map_paired_requirement`'s own-evidence-first
dispatch — each fixes candidate rows and request identity before any role is processed,
independent of nomination outcome). `project_fresh_request_keys` therefore uses the REAL U1 map
exclusively for "does an existing instance already have this role filled," and the dry pass
exclusively for "what post-recovery keys exist that the U1 map never saw."

### Dry-pass safety boundary — proven, not assumed

`_sufficiency_post_recovery_request_inventory` (`e2e.py`) runs the real, unmodified
`compute_diagnostic_sufficiency_map` with a counting-only fake client. **Safe (model-output
invariant) for every mechanism currently in real use**: ordinary single/multi-instance mapping,
`build_multi_instances` partitioning, role-fork multiplicity (collapses to one physical call via
existing memoization regardless of fork count), and `map_paired_requirement`'s own-evidence-first
dispatch (the child's own-evidence attempt is always made, unconditionally; "consulting the parent"
on failure is a pure read of an already-computed binding, never a new request).

**A real, previously-undocumented structural gap was found while proving this, not assumed away:**
`map_cardinality_requirement` (`all_requested_categories`) has no per-term `request_context`
concept at all — every `requested_category_terms` entry shares the bare `(child_id, requirement_id,
role)` composite key with `request_context=None`. If this role were ever `model_nomination_only`
with more than one requested term, two structurally distinct requests would collide on the
identical memoization key — the same class of identity collision `build_multi_instances` had
before Phase 19b. **Dormant, confirmed never triggered** (no currently declared v9 scope is
cardinality-shaped). Rather than build a full fix for an unexercised shape, `map_cardinality_
requirement` now refuses deterministically, before any model call, whenever this exact unsupported
combination is detected (`nomination_context is not None` + `model_nomination_only` +
`model_nomination_permitted` + `len(requested_category_terms) > 1`). The proper fix — a per-term
`request_context`, analogous to Phase 19b's own fix — is backlogged, not built here.

## Real structural shapes, resolved precisely

| Shape | Target | Resolution |
|---|---|---|
| **c8** (real) | `individual_difference_trait_or_construct`, filled on all 4 real instances, labelled "missing" by `_first_instance_targets`'s own blanket joint-completion framing (the sibling `relationship_to_bias_manifestation` role never completes) | **Excluded from F** — the real U1 map shows the role already `filled` everywhere; only a hypothetical new context (`U7`) would enter |
| **c11** (real) | zero instances, zero history | **Only genuinely new post-recovery keys** matching the derived scope may enter |
| **c12** (real) | two real request contexts (`U1`/`U5`), instance-scoped targets | A target naming `U1` resolves to **exactly** `U1` via the real map; `U5` is never looked up for it at all |
| **c5/c10** (real) | one instance, genuinely unfilled, `request_context=None` | **Included** directly |
| **c6** (real) | two distinct `provisional_corroboration` targets tracing to one shared upstream nomination | **Collapse to one key** by ordinary set membership |
| **parent-context redirection** (synthetic, c4→c5/c6-shaped) | downstream target caused by an upstream model-dependent fill | Projects to the **upstream** `(scope, request_context)`; the downstream child never gets its own key merely for triggering the search |

All six proven directly against `project_fresh_request_keys` with real q_aib role/requirement
shapes (9 dedicated tests in `test_sufficiency_recovery_targets.py`), not toy data alone.

## Offline real-lifecycle replay (required audit result)

A genuine end-to-end scenario was run through the real `execute()` path (real frozen v9 contract,
real hierarchy, a fake — never live — client, no network): recovery broadens c5's own candidate
pool from 1 to 2 propositions (a custom client declines under 2 candidates, accepts at ≥2).

- **Gate ON:** U2 fires a genuine **targeted remap** — `by_status: {"fresh_no_candidates": 6,
  "held_fixed_replay": 3, "fresh": 2}`, `fresh_request_count: 8` (== `|F|`, confirmed exactly). At
  least one request was held fixed (locality preserved) and at least one made a real new call (the
  capability is not a no-op). c5's own requirement ends up `filled` on both roles. The fresh call
  was confirmed offered the **full, broadened** candidate pool (≥2 rows), never a recovered-only
  subset.
- **Gate OFF, identical evidence** (the harness seals the same broadened evidence regardless of
  gate state — proving the gate, not evidence availability, decides reconsideration): U2 stays
  **fully held fixed**, `by_status: {"held_fixed_replay": 11}`, `fresh_request_count: 0`, zero
  additional calls beyond U1's own 5 — byte-identical to Phase 20b/21's own behavior.

Three dedicated tests in `test_hierarchy_e2e.py::TargetedPostRecoveryRemapIntegrationTests`, every
number empirically confirmed by direct execution against the real contract, never hand-derived.

## Hard call-budget invariant

`e2e.py`'s own U2 construction now asserts, after the real mapping call completes, that every
receipt whose status represents a physical fresh attempt (`fresh`, `fresh_no_candidates`,
`fresh_failed_fallback_to_prior`, `fresh_failed_no_valid_prior`) has a key inside the precomputed
`F` — raising `RuntimeError` otherwise. This should be structurally impossible (authorization is a
pure membership check), and the assertion never fired across the full offline replay suite.

## Receipt history

Unchanged design, already correct: `sufficiency_u1_receipts_snapshot` remains the immutable U1
historical record; U2's own `in_pass_receipts` is the final-pass record, persisted separately under
the existing `"initial"`/`"final"` trace keys (`18_sufficiency_model_assist.json`). No destructive
overwrite, no new cross-run cache.

## One-round convergence

Unchanged from the accepted design: one recovery round, one targeted U2, then STOP. A
`provisional_corroboration` target that remains model-dependent after the one allowed attempt would
reappear identically if `compute_recovery_targets` were run a third time — this is reported
honestly (the same `target_id`, same semantic map state), never silently cleared. No iterative
recovery loop was built.

## Direction/effectiveness, stop-search

Confirmed by direct re-read and by the e2e suite's own existing, unmodified assertions:
`compute_direction_and_effectiveness` and `compute_stop_search_certified` both already re-run
unconditionally over whatever `sufficiency_map_final` becomes — zero Phase-22 changes needed to
either.

## Regression

- Targeted new-test suites: `ExactRequestSetPolicyTests` (5) + 1 extended `AuthorizationPolicyTests`
  test, `FreshRequestKeyProjectionTests` (9), 3 dormant-cardinality-guard tests, `Targeted
  PostRecoveryRemapIntegrationTests` (3) — 21 new tests, all passing.
- Full `experiments/ask_cli_revised` tree: **2343 passed** (2322 at Phase-21 HEAD + this phase's own
  21 net-new committed tests — the Phase-19b test rename and the Phase-20b fixture-assertion update
  each net to zero), **2 failed** (the identical pre-existing pin-drift pair every phase since
  Phase 16 has documented, independently reconfirmed unrelated), **11 skipped**.
- Frozen v9 `combined_hash` reconfirmed unchanged:
  `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

## Production file scope (confirmed)

Exactly as the audit's own §31 expected: `sufficiency_mapping.py`, `sufficiency_diagnostic.py`,
`sufficiency_model_scope.py`, `sufficiency_recovery_targets.py`, `e2e.py`. **Zero changes** to
`sufficiency_engine.py`, the raw Qwen protocol, the frozen contract, the hierarchy contract, or
Phase-18 direction/effectiveness logic — confirmed by `git status --porcelain`.

## Newly discovered issues

1. A real consistency gap in `_provisional_corroboration_targets_for_instance`'s own inline
   origin-construction fallback (used when a binding was never routed through `_stamp_model_
   dependency_origins` first) — it minted origins without `request_context`, which several of this
   module's own existing hand-built test fixtures exercise. Fixed to read the same field, from the
   same place, as the canonical stamping site.
2. The dormant `map_cardinality_requirement` multi-term identity gap (documented above) — confirmed
   real, confirmed dormant, guarded fail-loud, backlogged rather than fully fixed.
3. The U2 stage-log binding's `"kind"` was previously a fixed string regardless of what actually
   happened this pass (`"sufficiency_model_assist_held_fixed"` even when, under this phase's own
   design, fresh calls could occur). Now honestly conditional on whether `F` is non-empty, with an
   added `fresh_request_count` field for inspectability.

## Status

**Phase 22 is CLOSED.** The design is implemented, offline-proven against both real q_aib
structural shapes and a genuine end-to-end broadened-evidence scenario through the real `execute()`
path, with zero live model calls and zero network retrieval anywhere in this phase.

**One bounded live recovery + exact-request U2 remap validation is READY**, pending separate
authorization, mirroring the Phase-20/21 precedent: prove the integration offline first (done),
then gate one bounded live experiment as its own dedicated next phase.
