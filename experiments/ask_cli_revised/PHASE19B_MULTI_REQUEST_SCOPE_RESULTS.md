# Phase 19b — multiple model requests under one authorization scope

**NO LIVE MODEL CALL. NO RETRIEVAL. NO RECOVERY EXECUTION. NO CONTRACT CHANGE. NO v10. NO PIN
RE-FREEZE. NO c12 EXCLUSION. NO Phase-22 TARGETING IMPLEMENTATION.** Phase 21's authorization remains
unused; zero live calls have been made against the real q_aib question at any point across Phase 21
or Phase 19b.

## Origin: the Phase-21 preflight discovery

Phase 21 ("one bounded, production-shaped live initial model-assisted sufficiency validation") was
never run. Its dry-run preflight — a fake client exercising the exact production call chain against
the real preserved q_aib evidence — raised `RequestFingerprintMismatch` on real `c12`
(`suff:intervention-effectiveness`) before any live call was attempted. The preflight did its job:
it caught a real infrastructure gap before it could burn one of the Phase-21 budget's 15 fresh live
calls on a crash.

Cliff's decision (STOP CONFIRMED): do not exclude c12, do not run a partial 10-child live
validation. Repair the gap first, then restart Phase 21 from a clean, full-contract state with the
original one-run/no-retry rule intact. This is that repair.

## The false invariant Phase 19 carried forward unexamined

Phase 19's `ModelNominationScope = (child_id, requirement_id, role)` implicitly assumed **one
authorization scope = at most one model-facing request** per mapping pass. That assumption is false
for a `multi_instance=True`, no-parent-context requirement with more than one real candidate unit:
`build_multi_instances` (`sufficiency_mapping.py`) partitions such a requirement's units into one
provisional instance per unit, and `map_requirement`'s per-instance loop then calls
`_fork_instances_over_role` — and so `_bind_role_candidates` — once per instance, **offering a
different, disjoint candidate pool each time, to the identical `(child_id, requirement_id, role)`
scope.** `resolve_nomination`'s fingerprint check (keyed only by scope) saw the second request's
different candidate set as a within-pass attempt to re-resolve an already-memoized scope with a
contradictory fingerprint, and raised.

Confirmed real, not a fake-client artifact: `c12` in the preserved 2026-09-30 T5C sealed ledger has
exactly two real units (`U1`, `U5`) feeding its `multi_instance=True, quantifier="exists",
parent_context_roles=[]` requirement. The same structural shape (`multi_instance=True`, zero or more
`model_nomination_only` roles, no parent context, ≥2 units) was found structurally latent — present
in the contract shape but not yet triggered by real evidence volume — in `c8` and `c11` too.

## The fix: authorization scope vs. request context

Two different facts were conflated under one key. **Authorization scope**
`(child_id, requirement_id, role)` answers "is a model call for this role of this requirement on
this child permitted at all" — a policy/budget question, unchanged. **Request context** answers "is
this the SAME physical request as a prior one, or a sibling with its own disjoint candidate pool" —
an identity question Phase 19 never asked.

`sufficiency_model_scope.new_model_nomination_key(scope, request_context=None)` returns the
composite `(scope, request_context)` tuple now used everywhere `in_pass_receipts`/`prior_receipts`
are keyed. `request_context` is **the caller's own pre-fork `root_key`** — `map_requirement`'s
existing loop variable, `None` for a non-partitioned requirement, one real unit's own `unit_id` per
iteration for a `build_multi_instances`-partitioned one. This is deliberately **not** the
final/rederived `instance_key` (`sufficiency_engine.derive_instance_key`): that key changes across
role-forks within one instance (by design — it's content-derived, computed only after every role has
been bound), and using it as the memoization key would have broken Mechanism-A (role-fork)
deduplication, which depends on every fork of one original instance sharing the identical key so a
repeated candidate-pool request collapses to one physical call. `root_key` is fixed before forking
ever starts, so it is exactly the value that is constant across a role-fork but distinct across a
real partition.

`request_context` threads through unchanged: `map_requirement` passes its own `root_key` as
`request_context` to `_fork_instances_over_role`, which relays it unchanged to every
`_bind_role_candidates` call for every fork of one instance (so all of a role-fork's duplicate
requests still collapse to the SAME `(scope, request_context)` key and one physical call), which
relays it unchanged to `resolve_nomination`. `map_cardinality_requirement` and
`map_paired_requirement` were **not** touched — they never pass `request_context`, so every call
site that predates Phase 19b observes `request_context=None`, byte-identical to before this phase.

`RequestFingerprintMismatch`'s invariant narrows accordingly: a mismatch now fires only when the
SAME `(scope, request_context)` composite key is resolved twice in one pass with two different
fingerprints — never across two different request_contexts sharing one scope, which is exactly the
real, legitimate shape this phase exists to support.

## Why this is narrow, not a redesign

- `model_dependency_origins` is **unchanged** — its schema and semantics (`child_id`,
  `requirement_id`, `role`, `instance_key`) are exactly as they were. Linking it to
  `request_context` is explicitly deferred to Phase 22, a researcher decision made before
  implementation started: `RecoveryTarget.scope` already carries a different, POST-fork
  `instance_key`, merely adding `root_key` to dependency-origins would not by itself solve Phase-22
  targeting, and that linkage deserves its own design informed by real post-recovery behavior, not
  a speculative addition now. A test (`test_a_model_dependency_origins_shape_is_unchanged_by_this_
  phase`) pins this explicitly: `set(origin) == {"child_id", "requirement_id", "role",
  "instance_key"}` and `"request_context" not in origin`.
- No contract change, no v10, no pin re-freeze. The frozen v9 `combined_hash` is unchanged
  (reconfirmed below).
- Production changes are confined to exactly two files: `sufficiency_model_scope.py` (the
  composite-key plumbing) and `sufficiency_mapping.py` (passing `root_key` through as
  `request_context`). `e2e.py`, `qwen.py`, `sufficiency_diagnostic.py`, `sufficiency_engine.py`,
  `sufficiency_recovery_targets.py`, and every contract/hierarchy file are untouched.

## U1 / U2 behavior under the fix

**U1 (initial pass, `ALL_ELIGIBLE` policy):** a physical model call happens once per distinct
`(scope, request_context)` key actually reached — i.e. once per real unit of a partitioned
requirement, not once per scope. Replaying the real preserved q_aib T5C evidence against a fake
client with no exclusions: all 11 children complete with no crash; `c12` produces exactly 4 distinct
composite-key receipts (2 roles × 2 units, `request_contexts == {"U1", "U5"}`), each receiving only
its own request's accepted nominations, never a sibling's — confirmed by direct inequality assertion
between `c12`'s `U1`-keyed and `U5`-keyed `intervention` receipts. A role-fork of one instance (the
pre-existing Phase 19 mechanism, unchanged) still collapses to one physical call, since every fork of
one instance shares the same `request_context`.

**U2 (held-fixed post-recovery remap, `exact_scope_set_policy(set())` + `prior_receipts` = U1's
own receipt snapshot):** zero fresh physical calls. Every existing `(scope, request_context)` key
replays its own correct prior receipt from the snapshot; a request_context not present in U1's
snapshot (e.g. a target newly in-scope only after recovery) gets no prior receipt and would make a
fresh call rather than silently borrowing a sibling's — exercised directly in both the synthetic
test matrix and a real-evidence test (`test_u2_never_borrows_a_sibling_request_contexts_receipt`).

## Tests

- `test_sufficiency_model_scope.py::RequestContextTests` (7, new): same-scope-different-context
  legitimacy, mismatch still raised for a genuinely repeated context with a changed fingerprint,
  repeated resolution of one context still memoizes, order-independence, an empty-candidate request
  never suppresses a sibling nonempty one, a mechanical failure on one request never poisons a
  sibling, and U2's zero-fresh-call behavior on a new post-recovery context.
- `test_sufficiency_mapping.py::MapRequirementPhase19bMultiInstancePartitionTests` (3, new):
  synthetic c8-shaped (one role, two units) and c11/c12-shaped (two roles, two units) partitions
  complete without crashing and produce correctly isolated per-unit bindings and receipts; a
  held-fixed U2 rebuild of the c8 shape makes zero additional calls.
  `MapRequirementPhase19ForkMemoizationTests` and every other pre-existing Phase-19 fixture pass
  unmodified except for the mechanical `scope` → `new_model_nomination_key(scope)` key-shape update
  (10 call sites across both test files) their own dict-keyed assertions needed once the receipt
  store's key became composite.
- `test_sufficiency_phase19b_real_v9_replay.py` (11, new; the mandatory release-gate file): loads
  the real frozen v9 contract/`parent_of` and the real preserved 2026-09-30 T5C sealed ledger, runs
  a full U1 pass across **all 11 children with no exclusions** against a fake/recorded client (never
  live), and asserts: no crash; `c12`'s real two-unit shape produces exactly the two expected
  request_contexts with 4 isolated receipts; role-fork duplicates still collapse to one physical
  call; the direction/effectiveness pass completes over the resulting map; `compute_recovery_targets`
  can inspect it; a held-fixed U2 rebuild makes zero fresh calls and correctly replays every existing
  request_context's own receipt, never a sibling's; and `model_dependency_origins`'s shape is
  unchanged by this phase.

A real bug was found and fixed in the TEST fixtures themselves while building the synthetic c8-shape
test, not in production code: `canonical_text_contains` (the deterministic grounding gate every
nomination must pass) is case-sensitive, and an initial fixture's scripted nomination text
("disgust sensitivity", lowercase) didn't literally match its passage's sentence-initial
capitalization ("Disgust sensitivity was..."), silently producing a `missing` binding for that unit
alone — the other unit succeeded, so the test failed on an asymmetric result rather than erroring
outright. Fixed by rewording the fixture passage so the trait name appears mid-sentence, matching the
case the scripted text already used; no production code was touched by this fix.

## Regression

- `test_sufficiency_mapping.py` + `test_sufficiency_model_scope.py` +
  `test_sufficiency_phase19b_real_v9_replay.py`: **165 passed**.
- Broader named surfaces (`test_sufficiency_diagnostic.py`, `test_sufficiency_recovery_targets.py`,
  `test_sufficiency_engine.py`, `test_sufficiency_direction_effectiveness.py`,
  `test_sufficiency_freeze.py`, `test_hierarchy_contract.py`, `test_hierarchy_e2e.py`): **286
  passed, 2 failed** — both pre-existing and unrelated to this phase, independently reconfirmed by
  stashing this phase's entire working-tree diff and re-running the same two tests against the
  clean, committed Phase-20b HEAD (`304ad5ad`): both fail identically there (a `hierarchy_contract.py`
  pin-drift rejection and an `e2e.main --preflight-only` exit-code assertion — neither file is
  touched by Phase 19b).
- Full tree (`pytest experiments/ask_cli_revised -q`): **2322 passed, 2 failed (the same pre-existing
  pair above), 11 skipped**.
- Frozen v9 `combined_hash` reconfirmed exactly unchanged:
  `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.
- `ruff format --check` + `ruff check`: clean on every touched/new file.

## Production file scope (confirmed)

Exactly two production files changed: `sufficiency_model_scope.py`, `sufficiency_mapping.py`.
`e2e.py`, `qwen.py`, `sufficiency_diagnostic.py`, `sufficiency_engine.py`,
`sufficiency_recovery_targets.py`, and every contract/hierarchy file: **zero changes**, confirmed by
`git status --porcelain` showing only the four modified files + two new (untracked) test/diagnostic
files listed below.

## Phase-21 status (unchanged)

Not started. Zero live calls have been made against the real q_aib question at any point, in Phase
21 or Phase 19b. The Phase-21 authorization is unused. The preflight's discovery of this gap is
itself the successful result of running that preflight as designed — Phase 21 is not labeled FAIL,
and its authorization is not consumed by this repair work.

The Phase-21 harness (`phase21_live_initial_model_assist_validation.py`) remains **untracked**,
diagnostic-only material. It is not committed as part of Phase 19b, per explicit instruction — it
was used only to exercise the production-shaped path with a fake client (never network/live) during
this investigation; the reusable deterministic coverage it needed has been moved into the committed
pytest fixtures above instead (`test_sufficiency_phase19b_real_v9_replay.py` in particular), rather
than relying on the harness itself as a release gate.

Phase 21 is now **ready to restart** from a clean, full-contract state (no c12 exclusion, no partial
run) with the original one-run/no-retry rule intact, once Cliff authorizes it.
