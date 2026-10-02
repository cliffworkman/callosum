# Phase 19 — robust model-nomination scoping + receipt infrastructure (SCOPE A)

This document combines the audit and the implementation it authorized, since — unlike Phase 18 —
the audit itself was conducted entirely in Plan Mode (read-only: no code, no commit) and lives at
`~/.claude/plans/pasted-content-id-ec13-new-architectura-snappy-storm.md`, outside this repo. This
is therefore the first durable, repo-committed Phase-19 artifact, and it carries both halves.

Starting HEAD for this work: `7a59512f35f1ba500d47b950994e9dd0569e24e6` (the Phase 18
implementation commit — verified exactly, before any change). No live model call, no retrieval, no
recovery execution, no contract or pin change, no v10, no production model-assisted lifecycle
wiring: `e2e.py` is untouched, confirmed by `git diff --stat` showing zero changes to it.

## 1. Audit summary (read-only, Plan Mode; full text in the plan file above)

Traced the complete model-nomination call graph against this exact HEAD and confirmed, by direct
code reading (not inference): production `e2e.py` supplies no `model_client` anywhere (grep-
confirmed, zero occurrences), so it performs zero model-assisted sufficiency nomination today.
The one real model invocation in the whole codebase is `sufficiency_mapping.nominate_with_model`'s
own `model_client.nominate_sufficiency_role(...)` call. `(child_id, requirement_id, role)` was
confirmed sufficient as a production scope identity because a nomination's actual model-facing
request never varies by instance — forking is a deterministic *consequence* of one nomination's
own output size, never a precondition for making the call. This also surfaced a real, confirmed
latency defect in the *existing* fork-handling code: when an earlier role forks an instance into N
copies, a later `model_nomination_only` role in the same requirement re-invokes
`nominate_with_model` once per fork with byte-identical inputs — N redundant calls for one logical
task. `child_id` was found to be threaded nowhere below `compute_diagnostic_sufficiency_map`'s own
per-child loop variable (confirmed directly against `sufficiency_engine.new_requirement`'s return
shape — no `child_id` key exists on an individual requirement dict at all, only on its owning
`SufficiencyContract`).

## 2. Implementation — files changed

| file | change |
|---|---|
| `sufficiency_model_scope.py` | **new** — `ModelNominationScope` (plain 3-tuple) builder + generic enumerator; `request_fingerprint` (canonical, order-insensitive SHA-256); `all_eligible_policy`/`exact_scope_set_policy`/`is_authorized_for_fresh_call`; `new_nomination_receipt`/`new_nomination_context`; `resolve_nomination` (the one orchestration checkpoint: memoization, authorization, held-fixed replay, mechanical-failure fallback); `model_scopes_for_recovery_target` (RecoveryTarget → scope projection). Dependency-free of `sufficiency_mapping.py`/`sufficiency_recovery_targets.py` by design (dependency inversion via injected callables), mirroring `sufficiency_engine.py`'s own position below the mapper. |
| `sufficiency_mapping.py` | `_candidate_rows_for_role` extracted from `nominate_with_model`'s own inline logic (pure refactor, zero behavior change, confirmed by the full pre-existing `NominateWithModelTests` suite staying green). `_prior_receipt_is_admissible` (new). `child_id`/`requirement_id`/`nomination_context` threaded as optional, defaulted-`None` keyword params through `_bind_role_candidates` → `_fork_instances_over_role` → `map_requirement`/`map_paired_requirement`/`map_cardinality_requirement` → `map_any_requirement`. The ONE integration checkpoint lives inside `_bind_role_candidates`: when `nomination_context is None` (every pre-Phase-19 caller), it calls `nominate_with_model` directly — byte-identical legacy behavior; only when a caller explicitly supplies `nomination_context` does it construct a scope and route through `sufficiency_model_scope.resolve_nomination`. A new `nomination_receipt_status` provenance key is added ONLY on this new path, never propagated through `_propagated_provenance` (deliberately minimal, per the audit's own §O instruction). |
| `sufficiency_diagnostic.py` | `compute_diagnostic_sufficiency_map` gains an optional `nomination_context=None` kwarg, threaded alongside the already-existing per-child `child_id` loop variable into `map_any_requirement`. |
| `test_sufficiency_model_scope.py` | **new**, 55 tests — the full infrastructure module's own behavior, including the exhaustive real-v9-contract inventory (loaded directly from the already-frozen JSON, no live run / env var needed). |
| `test_sufficiency_mapping.py` | +22 tests — scope threading, memoization (the real per-fork redundancy fix, proven through the actual `map_requirement` fork mechanics, not just the bare orchestrator), authorization, prior-receipt validity (stale proposition / ungrounded text / now-inadmissible guard), broadened-candidate-set semantics for both authorized and held-fixed scopes, descendant propagation, and the structural "no descriptive-string authorization" proof. |
| `test_sufficiency_diagnostic.py` | +5 tests — end-to-end scope threading through the real per-child loop, `model_dependency_origins` preserved under the new path, and round-trip idempotence (a second, fully held-fixed pass replaying the first pass's own receipts reproduces an identical mapped tree). |

No other file was touched. `sufficiency_recovery_targets.py`, `hierarchy_contract.py`, and `e2e.py`
are byte-identical to HEAD (confirmed by `git diff --stat` showing no entry for any of them).

## 3. The mechanical proof the audit's hypothesis required (§D)

The audit's own §3/§8 named a hypothesis, not a proof: that two invocations of the same
`(child_id, requirement_id, role)` scope within one mapping pass are always byte-equivalent
requests, and can therefore safely collapse to one physical call. This is now proven mechanically,
not assumed: `request_fingerprint` canonicalizes `category_description` + the exact
`{proposition_id, passage}` rows offered (sorted by `proposition_id`, so mere ordering is never
mistaken for a difference) into a SHA-256 digest; `resolve_nomination` compares this fingerprint on
every repeated resolution of the same scope within one pass and raises `RequestFingerprintMismatch`
loudly if they ever disagree — it does not silently reuse a mismatched receipt. Across this
session's full test run (including a real reconstruction of a genuine multi-fork q_aib-shaped
requirement — one role nominates two cultures from one passage, forking the instance, and a SECOND
`model_nomination_only` role is then reached once per fork with identical inputs), the fingerprint
never once disagreed, and the raw model-client call count for the second role dropped from N (one
per pre-existing fork) to exactly 1, with identical downstream mapped results confirmed against the
pre-Phase-19 repeated-call pattern. The hypothesis holds for the current mapper; it is now an
enforced invariant, not an assumption.

## 4. Scope boundary respected

- `_bind_role_candidates`'s legacy branch (`nomination_context is None`) is unchanged: it calls
  `nominate_with_model` directly, never constructs a scope, never touches
  `sufficiency_model_scope.py` at all.
- `compute_diagnostic_sufficiency_map`'s two real production call sites remain `e2e.py`'s own
  (unmodified) — `e2e.py` was not edited in any way.
- No authorization policy, receipt, or scope comparison exists outside the one checkpoint in
  `_bind_role_candidates` — confirmed by inspection (`sufficiency_mapping.py` has exactly one
  `import ... sufficiency_model_scope` call site) and by the structural "no descriptive-string
  comparison" test, which proves two roles sharing an identical `category_description` are
  authorized completely independently by their `(child_id, requirement_id, role)` tuple alone.
- `sufficiency_model_scope.py` contains zero q_aib-specific vocabulary in its executable code
  (confirmed by `enumerate_model_nomination_scopes`/`model_scopes_for_recovery_target` operating
  generically against any `{child_id: SufficiencyContract}` or `RecoveryTarget`-shaped dict, proven
  first against a synthetic non-q_aib contract before the real v9 inventory is used as a
  corroborating, not load-bearing, check).

## 5. Exhaustive v9 model-nomination scope inventory (mechanical, offline, zero model calls)

Loaded directly from the already-frozen `sufficiency_contract.aib_hier_v9.frozen.json` (no
preserved-run environment variable needed) via the new generic
`enumerate_model_nomination_scopes`. **15 scopes across 11 children**, all pairwise distinct:

| child_id | requirement_id | role | multi_instance | parent_context_roles | quantifier |
|---|---|---|---|---|---|
| c1 | c1#suff:neural-manifestation | neural_measure_or_modality | False | — | exists |
| c1 | c1#suff:neural-manifestation | brain_region_or_network | False | — | exists |
| c2 | c2#suff:behavioral-manifestation | behavior_or_behavioral_measure | False | — | exists |
| c4 | c4#suff:specific-region | named_brain_region_or_network | False | — | exists |
| c5 | c5#suff:brain-behavior | named_brain_region_or_network | False | named_brain_region_or_network | exists |
| c5 | c5#suff:brain-behavior | behavior_or_behavioral_measure | False | named_brain_region_or_network | exists |
| c6 | c6#suff:brain-attitude | named_brain_region_or_network | False | named_brain_region_or_network | exists |
| c6 | c6#suff:brain-attitude | attitude_type_or_measure | False | named_brain_region_or_network | exists |
| c8 | c8#suff:trait-construct | individual_difference_trait_or_construct | True | — | open_list |
| c9 | c9#suff:trait-scale-pairing | individual_difference_trait_or_construct | True | individual_difference_trait_or_construct | for_each_discovered_instance |
| c10 | c10#suff:culture-existence | named_culture_or_population | False | — | exists |
| c11 | c11#suff:culture-operationalization-pairing | culture_or_population | True | — | for_each_discovered_instance |
| c11 | c11#suff:culture-operationalization-pairing | operationalization_or_measure | True | — | for_each_discovered_instance |
| c12 | c12#suff:intervention-effectiveness | intervention | True | — | exists |
| c12 | c12#suff:intervention-effectiveness | target_manifestation | True | — | exists |

Notable real shapes this inventory corroborates: `named_brain_region_or_network` is the SAME role
name reused across c1/c4/c5/c6, independently distinguished only by `child_id`
(`individual_difference_trait_or_construct` likewise across c8/c9) — exactly the audit's §3/§4
disambiguation claim, now proven against real data, not only the synthetic test fixture.
c5/c6/c9's roles that are ALSO listed in their own `parent_context_roles` are genuinely
independently reachable scopes (own-evidence-first, per `map_paired_requirement`'s existing
design) — never merely inert. c11/c12 each have TWO independent `model_nomination_only` roles on
one `multi_instance=True` requirement with no parent context — the exact shape that exercises the
per-fork call-count redundancy this phase fixes.

`v9 combined_hash` reconfirmed unchanged throughout: `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

## 6. Test / regression results

TDD throughout — every new behavior's test was written and watched fail for the right reason
before the corresponding implementation was written (`_candidate_rows_for_role`'s extraction was
verified as a pure, zero-behavior-change refactor against the full pre-existing
`NominateWithModelTests` suite before any threading began). Exact counts (collected, not
estimated): `test_sufficiency_model_scope.py` is **new**, 49 tests; `test_sufficiency_mapping.py`
grew from 73 to 92 (**+19**); `test_sufficiency_diagnostic.py` grew from 13 to 18 (**+5**) — **73
new tests total**, 0 pre-existing test removed or weakened.

- `test_sufficiency_model_scope.py` + `test_sufficiency_mapping.py` + `test_sufficiency_diagnostic.py`
  together: **159 passed** (49 + 92 + 18), 0 failed.
- Whole sufficiency family (`recovery_targets`, `direction_effectiveness`, `engine`, `leakage`,
  `authoring`, `freeze`, the Phase 2/5/9 replay harnesses, the model-nomination diagnostic, the real
  11-child replay, recovery-neighborhood-context): **245 passed**, 0 failed.
- Full `experiments/ask_cli_revised` tree: **2251 passed, 11 skipped, 2 failed**. The 2 failures
  are `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`
  and `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`
  — the **identical pre-existing pin-drift pair already disclosed by Phase 16/17/18's own
  regression runs**, confirmed unrelated to this work by direct inspection: `git diff --stat`
  shows zero changes to `hierarchy_contract.py`, `test_hierarchy_contract.py`, or
  `test_hierarchy_e2e.py`. Arithmetic cross-check: Phase 18's own baseline was 2178 passed; this
  phase adds exactly 73 new tests — 2178 + 73 = 2251, matching exactly.
- `ruff format --check` and `ruff check`, scoped to the 6 touched files: both clean.
- v9 `combined_hash`: reconfirmed unchanged (§5 above).

## 7. Newly discovered issues

One, already described in full above (§1/§3): the pre-existing per-fork nomination-call
redundancy, now fixed as a direct, required corollary of the scope design rather than filed as a
separate follow-up — it only ever manifests once a `nomination_context` is supplied, so it carried
zero live-model-call cost to discover or fix (every reproduction in this phase's test suite uses a
plain scripted fake, never a real client).

## 8. Is robust model scoping CLOSED?

**Yes, for Scope A** (robust scope/receipt infrastructure, production calls OFF) — the audit's own
recommended and authorized scope. `ModelNominationScope`, `request_fingerprint`,
authorization policies, nomination receipts, in-pass memoization, held-fixed replay, mechanical-
failure fallback, and the `RecoveryTarget → scope` projection are all built, tested, and proven
against both synthetic fixtures and the real v9 contract's exhaustive inventory. The one design
fork the audit flagged for sign-off (scope inside the wire protocol vs. outside it) was resolved
per the audit's own recommendation and the researcher's explicit confirmation (§A of the
implementation directive): the raw `model_client.nominate_sufficiency_role` protocol is completely
unchanged, and every one of the ~10 existing live/recorded/replay/fake client implementations
needed zero modification.

## 9. Recommended next phase

**Production initial model-assisted sufficiency mapping** — wiring a real `model_client` (and,
where desired, a `nomination_context` with an `ALL_ELIGIBLE` policy) into `e2e.py`'s own initial
mapping call site — is the natural next step, and no prerequisite surfaced during this
implementation that would block it. One concrete, cheap preparatory task worth doing first and
disclosed rather than silently deferred: deciding whether production's initial pass should always
construct a `nomination_context` (gaining the now-proven call-count memoization for free on any
multi-instance-forking child) or continue passing a bare `model_client` with no context at all
(simpler, but re-exposing the per-fork redundancy this phase fixed only for context-aware callers)
— a real, named, non-default choice, not a hidden assumption.

## 10. Lineage

See `CONTRIBUTION-LINEAGE.md`'s own Phase 19 entry, appended in the same commit as this document.
