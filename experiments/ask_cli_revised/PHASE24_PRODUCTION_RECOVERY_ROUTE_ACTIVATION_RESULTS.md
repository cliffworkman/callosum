# Phase 24 — production-route activation of sufficiency recovery

Authorized by Cliff Workman, 2026-10-03, immediately after "Phase 23a accepted and CLOSED." This
is an integration phase, not a semantic redesign: it closes the one remaining reachability gap
Phase 23 exposed — `run_topology()` never threaded `sufficiency_recovery_gate_enabled` into
`execute()`, and no CLI/config surface activated it through the normal production-shaped entry
path. **No live model call, no network retrieval, no q_aib rerun, no c12 tuning, no parent
synthesis, no multi-round recovery.** Every proof below is offline, against fake/scripted
backends.

## Authoritative state

- **Starting HEAD:** `18e0b066937bde5435dc03c8222b2ee71350976c` (Phase 23a) — matched.
- **Phase 24 implementation/evidence commit / final HEAD:** `4d54e795830a42db9cb8f193a850cfac877bafa3`
  (self-referential by construction — this is the one commit this document itself ships in).
- **Frozen v9 `combined_hash`:** reconfirmed unchanged:
  `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.
- **Files changed:** `experiments/ask_cli_revised/e2e.py` (+54 lines), `test_hierarchy_e2e.py`
  (+332 lines, 8 new tests + one pre-existing test's manifest-shape assertion extended). **Zero**
  changes to `sufficiency_mapping.py`, `sufficiency_diagnostic.py`, `sufficiency_model_scope.py`,
  `sufficiency_recovery_targets.py`, `sufficiency_engine.py`, `qwen.py`, or `hierarchy_contract.py`
  — confirmed by `git diff --stat` against each, all empty.
- **Phase 23/23a artifacts:** untouched (not read, not modified, not re-run).

## 3. Entry-path audit (performed before any edit)

- **A. `--sufficiency-model-assist` parsing/threading:** `parse_args()` (a `store_true` flag,
  validated to require `--hierarchy`), threaded through `main()`'s `run_topology(...,
  sufficiency_model_assist=args.sufficiency_model_assist, ...)` call.
- **B. Hierarchy activation validation:** twice, redundantly but harmlessly — once in `parse_args`
  (`--hierarchy` combo checks) and `main()` itself (`load_contract_for_live` +
  `check_authorization`, both discarded — used only for early, side-effect-free failure before any
  sampler/output directory is touched), and again for real inside `run_topology()` itself (its own
  `hierarchy_loader`/`authorization_checker`, independently overridable — the seam every
  `*RefusalTests`/`*WiringTests` class in this file already uses).
- **C. `sufficiency_recovery_gate_enabled` default:** **no CLI surface existed at all** —
  `execute()`'s own default (`False`) was the only place it was ever set; `run_topology()`'s
  `execute(...)` call site never passed it, confirmed by direct read before any edit. This is the
  exact gap Phase 24 closes.
- **D. Every direct `execute()`/`run_topology()` call site:** enumerated by repo-wide grep —
  `hierarchy_test_support.py`'s `HierHarness.run()` (already accepts
  `sufficiency_recovery_gate_enabled` as a pass-through kwarg, Phase 20a-vintage, unaffected),
  `test_e2e_run.py`, `test_hierarchy_e2e.py` (several integration classes, including Phase 22's own
  `TargetedPostRecoveryRemapIntegrationTests` — the fixture this phase's own equivalence tests
  reuse), `test_hierarchy_checks.py`, `test_overview_e2e.py`, `overview_test_support.py`,
  `phase13_c4_recovery_experiment.py`, and the three preserved live-validation harnesses (Phase
  21/23). None of these needed a change — the new `run_topology()` parameter is additive with a
  `False` default, so every existing caller that never passes it observes byte-identical behavior
  (confirmed: the full suite's pre-existing pass count grew by exactly 8, the number of new tests
  added, with zero other deltas).
- **E. Alternate production-shaped entry points:** `main()`/`run_topology()` is the only one — no
  other script calls `run_topology()` outside the test suite and the three preserved Phase 21/23
  one-shot validation harnesses (which intentionally bypass `run_topology()` for their own
  disclosed reasons, unaffected by this phase).

## 4-5-6. The new surface, its validation rule, and the model-assist/recovery relationship

- **CLI/config switch:** `--sufficiency-recovery` (a `store_true` flag, mirroring
  `--sufficiency-model-assist`'s own shape exactly).
- **Default:** **off.** Absent, `run_topology()`'s new `sufficiency_recovery_gate: bool = False`
  parameter keeps `execute()`'s own existing default — byte-identical to every pre-Phase-24 call.
- **Validation:** `--sufficiency-recovery` without `--hierarchy` is refused at **both** layers,
  matching the existing `--sufficiency-model-assist` precedent exactly: `parser.error(...)` in
  `parse_args()`, and a `raise ValueError(...)` inside `run_topology()` itself (since it is a real,
  directly-callable unit independent of the CLI parser — the same rationale the pre-existing
  model-assist check documents, now proven by a dedicated test that calls `run_topology()` with no
  parser involved at all).
- **Does recovery require model assistance?** **Audited from code, not assumed — no.**
  `execute()`'s own recovery-gate block (`if sufficiency_recovery_gate_enabled and
  sufficiency_map_initial is not None:`) depends only on a sufficiency map existing at all, and
  `sufficiency_map_initial` is computed whenever `sufficiency_contract is not None` —
  **unconditionally**, via the deterministic-only path when `sufficiency_u1_model_client is None`.
  The U2 remap block's own guard is identical in kind. **Deterministic-only sufficiency recovery is
  a valid, already-supported mode, confirmed live (offline) in
  `test_recovery_without_model_assist_is_a_valid_supported_mode`**: with model assistance OFF and
  recovery ON, a real, nonempty `RecoveryTarget` inventory is computed and injected as search gaps,
  through both the direct-`execute()` path and the full `run_topology()` route, with no
  model-nomination concept anywhere in the loop (`sufficiency_model_assist` stays `None`, `F`'s own
  count is honestly `0`). `--sufficiency-recovery` and `--sufficiency-model-assist` are **not**
  required to pair, and neither flag implies the other.

## 4-state matrix (all four proven offline)

| Model-assist | Recovery | Proven by |
|---|---|---|
| OFF | OFF | Every pre-existing test in this file that never passes either flag (unchanged; zero new behavior). |
| ON | OFF | `test_model_assist_on_recovery_off_leaves_the_initial_map_reachable_but_injects_nothing` (through `run_topology()`) and the pre-existing direct-`execute()` test `test_model_assist_on_with_recovery_gate_off_still_maps_but_injects_no_recovery_targets`. |
| OFF | ON | `test_recovery_without_model_assist_is_a_valid_supported_mode` (both paths). |
| ON | ON | `test_recovery_flag_reaches_execute_exactly_once_and_the_route_is_semantically_equivalent` (both paths; the central equivalence proof). |

## 7. Profile independence

**No profile-specific branch exists anywhere in the new threading** — confirmed two ways: (1) every
equivalence test above runs under `self.assist_profile` (a `think=False` variant of `T0`, legacy
P), and (2) `test_no_profile_specific_branch_exists_for_the_new_flag` repeats the direct-`execute()`
proof under a **second**, structurally different profile variant (`T0`'s own W/R, but with P
swapped to an `ollama`-kind binding from `T1` rather than `legacy`) — the gate fires an identical
real `RecoveryTarget` inventory and fills `c5` identically, with zero code path distinguishing
which P-kind or profile name is active. The new `run_topology()` parameter is a bare boolean
threaded to `execute()`; nothing in its implementation inspects `profile.name` or any profile field
at all.

## 8. Direct-`execute()` vs. integrated-route equivalence (offline, required proof)

**Fixture:** Phase 22's own real, already-proven-nontrivial scripted scenario
(`TargetedPostRecoveryRemapIntegrationTests`'s claim/recovery set — `c5`'s brain-behavior
requirement starts under-evidenced, a real recovery round broadens it, a real targeted U2 remap
fills it — plus `_DeclineUnderTwoCandidatesClient`, the same decline-under-2/accept-at-2-or-more
fake nomination client). Reused verbatim, never reinvented, per the brief's own instruction.

**Method:** `_direct_execute()` mirrors `TargetedPostRecoveryRemapIntegrationTests._run()` exactly
(construct `bound` via the real `bind()`, substitute only `bound.qwen` with the fake client, call
`execute()` directly). `_via_run_topology()` drives the **real** `run_topology()` — real git-state/
library/contract pluggable hooks (the same seam `RunTopologySufficiencyWiringTests` already
established), a spy wrapping the real `execute()` to capture its exact kwargs and return value, and
one additional narrow substitution `direct_execute()` doesn't need: `e2e._sufficiency_u1_context`
is patched to return the same fake client directly, because `run_topology()` constructs `bound`
itself via its own real `bind()` (T0's W/R are `managed_local`, so `bound.qwen` would otherwise be
a real `QwenTasks` wrapping a fixture-only `rt.qwen_config` string with no real model identity to
resolve) — this substitutes **one seam**, never `execute()`'s own control flow, `bind()`'s
construction, or `require_models()`'s check.

**Result:** `self.assertEqual(self._without_timing(direct), self._without_timing(captured_result))`
passes exactly — every field `execute()` returns (`stage_log` stage names/bindings, `skipped`,
`recovery_plan`, `recovery_log`, `coverage_initial`/`coverage_final`, `sealed`/`sealed_hash`,
`sufficiency_map_initial`/`_final`, `sufficiency_recovery_targets`/`_initial` (both pre- and
post-recovery RecoveryTarget inventories), `sufficiency_model_assist` (the full U1/U2 receipt
detail — fresh/fresh_no_candidates/held_fixed statuses included), `sufficiency_u2_fresh_request_
key_count`, `records_total`, `supervisor_records`) is **identical** between the two call shapes,
modulo only the two real-wall-clock fields (`wall_seconds`/`swap_seconds`) every invocation of
anything necessarily differs on. **Current direct `execute()` == the integrated `run_topology()`
route**, on this fixture, exactly as Phase 20a's own equivalence-proof pattern established for
`sufficiency_contract`/`sufficiency_parent_of` threading.

The flag itself was independently confirmed to reach `execute()`: `captured_kwargs["sufficiency_
recovery_gate_enabled"] is True` (and `is False` in the gate-off variant) — asserted on the spy's
own captured call, not inferred from the result alone.

## 9. Gate-off equivalence (required proof)

`test_gate_absent_through_run_topology_matches_gate_off_direct_exactly`: with the new flag absent,
`run_topology()`'s route produces a result **identical** (same `_without_timing` comparison) to
calling `execute()` directly with `sufficiency_recovery_gate_enabled=False` — no target-driven
recovery round beyond what the generic (non-sufficiency) gap pass would have planned anyway, `F`'s
own count `0`, the `RecoveryTarget` inventory empty (`sufficiency_recovery_targets_initial`
falsy), and the manifest's own `recovery_gate_requested`/`recovery_gate_enabled` both `False`.
**Phase 24 causes zero behavior change when its own flag is not passed.**

## 10. Gate-on offline recovery proof (required proof, not merely a boolean arrival)

The SAME fixture as §8 proves this is not merely "the boolean arrived": `direct`/`captured_result`
both show `stage_log` containing `W2`/`R2`/`C2` (the recovery round genuinely ran),
`sufficiency_recovery_targets_initial` nonempty (real `RecoveryTarget`s existed before recovery),
`sufficiency_model_assist.final.by_status` containing a real `fresh` entry (a genuine new U2
physical call occurred) alongside `held_fixed_replay` entries (not everything was reconsidered),
and `sufficiency_map_final["c5"]`'s own requirement reaching `state == "filled"` with both roles
filled — the full U1 → recovery → F → targeted U2 lifecycle fired for real, through the production-
shaped route, not a synthetic toy mapper.

## 11. Normal `run_topology()` now owns the configuration

Confirmed by construction: the new flag's parsing (`parse_args`), validation (both layers),
threading (`run_topology()`'s own `execute(...)` call site), and diagnostics (the manifest's
`sufficiency` block) are all native to the production path. The Phase-23 direct-`execute()` harness
is no longer the only way to exercise `sufficiency_recovery_gate_enabled=True` — it remains, as
historical experiment evidence, unmodified.

## 12. Manifest/trace diagnostics (minimal, additive)

Added to `manifest["sufficiency"]` (never duplicating the detailed Phase-22 trace artifacts, which
remain the sole source of full per-scope receipt detail):

| Key | Meaning |
|---|---|
| `recovery_gate_requested` | the raw flag value this call received |
| `recovery_gate_enabled` | whether the gate was actually live (requires a sufficiency map to exist at all) |
| `recovery_targets_initial_count` | `len(sufficiency_recovery_targets_initial)` |
| `recovery_round_executed` | whether a `W2` stage ran at all (a search was planned and executed, regardless of whether it added new evidence) |
| `u2_fresh_request_key_count` | `|F|` — the fresh-**authorized** request-key count (see §13) |

Two small, additive keys were also added to `execute()`'s own return dict to make this possible
without re-deriving anything: `sufficiency_recovery_targets_initial` (the BEFORE-recovery
inventory `execute()` already computed internally for gap injection — Phase 23 had to recompute
this post-hoc, read-only; now exposed directly) and `sufficiency_u2_fresh_request_key_count` (a
bare count of the already-computed `sufficiency_u2_fresh_request_keys` local — never the raw key
set itself, which stays exclusively in the trace artifact).

## 13. F vs. physical-call terminology (Phase 23a's correction carried forward)

`manifest["sufficiency"]["u2_fresh_request_key_count"]` is explicitly, and by test
(`test_recovery_flag_reaches_execute_exactly_once_and_the_route_is_semantically_equivalent`),
**not** the physical-call count — the test asserts it `!=` the real `by_status["fresh"]` count on
this fixture's own data (`|F|` includes both the genuine physical `fresh` call and any
`fresh_no_candidates` members). No test or doc added in this phase reintroduces the Phase-23
wording error.

## 14. c12 — explicitly out of scope, not touched

No recovery query, retrieval ranking, role prompt, contract wording, or candidate guard was
modified anywhere in this phase (confirmed by the module-level diff: only `e2e.py`'s own
CLI/orchestration surface and the test file changed). Phase 23a's two `c12` scientific findings
(the wrong-half `target_manifestation` nomination; the likely off-topic `U30` recovery evidence)
remain an explicitly **deferred** evaluation/tuning question for before any broader scored E2E gate
— not addressed, not silently dropped.

## 15. Pin-drift disposition

**Audited, not incidentally fixed.** The real (non-test) CLI path — `main()`'s own call to
`hierarchy_contract.load_contract_for_live(hier_question)`, which runs before `run_topology()` is
even reached — **still fails** on the same pre-existing pin-drift rejection every phase since
before Phase 19b has documented (`hierarchy_contract.py` changed since the pins were last
generated). This is **unrelated to and unworsened by** Phase 24: the identical failure already
blocked a plain `--hierarchy` run, `--sufficiency-model-assist`, and would equally block
`--sufficiency-recovery`, with or without this phase's changes. No pins were re-frozen, no
production pin-checking logic was touched or bypassed, and no `pins=None` default was introduced
into any production code path. All of this phase's own tests use the already-established
`hc.load_contract(BENCHMARK_QUESTION, pins=None)` test fixture (via an injected `hierarchy_loader`,
the same seam every prior `*WiringTests`/`*IntegrationTests` class in this file already uses) —
**exactly the brief's own sanctioned approach**, never a change to what the real CLI does.

## 16. Test inventory (all offline; `pytest experiments/ask_cli_revised -q`: 2351 passed, 11
skipped, 2 failed — the same 2 pre-existing pin-drift failures every phase this session has
reconfirmed; **+8** relative to Phase 23a's own 2343-passed baseline, exactly the 8 new tests)

1. `--sufficiency-recovery` absent → off: `test_cli_accepts_the_flag_with_hierarchy_default_off_when_absent`.
2. Present + hierarchy active → on: same test, positive branch; threading proven by
   `test_recovery_flag_reaches_execute_exactly_once_and_the_route_is_semantically_equivalent`.
3. Present without hierarchy → clear error: `test_cli_rejects_the_flag_without_hierarchy` (CLI layer) and
   `test_recovery_flag_without_hierarchy_is_refused_by_run_topology_itself` (`run_topology()` itself, independent of the parser).
4. Model-assist flag behavior unchanged: confirmed by the unmodified pre-existing model-assist test suite remaining green (minus the one manifest-shape test deliberately extended, never weakened).
5. Model-assist ON + recovery OFF: `test_model_assist_on_recovery_off_leaves_the_initial_map_reachable_but_injects_nothing`.
6. Recovery ON + model-assist OFF — explicitly proven supported: `test_recovery_without_model_assist_is_a_valid_supported_mode`.
7. Both ON: `test_recovery_flag_reaches_execute_exactly_once_and_the_route_is_semantically_equivalent`.
8. Normal profile resolution works: every test above resolves `"T0"` through the (patched-for-the-variant) real `topo.resolve_profile` seam, never a bespoke lookup.
9. No T0/T5-specific branch: `test_no_profile_specific_branch_exists_for_the_new_flag` (a second, `ollama`-P profile variant).
10. Flag reaches `execute()` exactly once: asserted directly on the spy's captured kwargs in every `_via_run_topology` test.
11. Gate-on causes actual offline recovery: §10 above.
12. Gate-off causes no recovery: §9 above.
13. Target-scoped U2 still exact: the full-result equality in §8 includes `sufficiency_recovery_targets`/`_initial` and every U2 receipt.
14. No fresh U2 key outside F: inherited unchanged from `execute()`'s own hard call-budget assertion (untouched code; would raise `RuntimeError` on violation, and did not).
15. `fresh_no_candidates` not counted as physical inference: §13 above.
16. Direct `execute()` == integrated route: §8.
17. Manifest diagnostics correct: asserted field-by-field against the direct result in the main equivalence test.
18. Phase-20/21 model-assist integration tests green: confirmed (full suite).
19. Phase-22 recovery tests green: confirmed, including `TargetedPostRecoveryRemapIntegrationTests` itself, unmodified.
20. Frozen v9 unchanged: reconfirmed above.

## Newly discovered issues

None blocking. One pre-existing, unrelated, already-documented condition reconfirmed: the real
(non-test) hierarchy-pin-drift rejection, disposed of per §15.

## Phase 24 status

**CLOSED.** The recovery/remap mechanism (Phase 22, live-validated Phase 23/23a) is now reachable
through the normal production-shaped `main()`/`run_topology()` entry path, independently of
model-assist, independently of profile, with zero semantic changes to any sufficiency module and
zero regressions.

## Readiness for the next architectural rung

Parent synthesis is **not** addressed by this phase (explicitly out of scope) and its readiness is
not assessed here. What Phase 24 does establish: the activation seam a future broader E2E gate (or
a parent-synthesis rung sitting above per-child recovery) would need is no longer missing —
`sufficiency_recovery_gate` is a first-class, independently-testable `run_topology()` parameter
today, not a harness-only bypass.
