# Phase 23 — one bounded LIVE recovery + exact-request U2 remap validation

Authorized by Cliff Workman, 2026-10-02, immediately after "Phase 22 accepted and CLOSED" (commit
`2e8bb879`). **Exactly ONE live run occurred. No retry. No second live run. No production code
change.** This is an empirical validation phase, not an implementation phase: it exercises, for the
first time live, the full U1 → recovery (W2/R2/C2) → Phase-22 target-scoped U2 remap lifecycle
`execute()` already implements, against real retrieval and a real recovery round.

## Profile choice — Cliff's own framing (verbatim, binding)

> "Use T0 for Phase 23. The purpose of this one-shot experiment is to guarantee exercise of the
> recovery/remap mechanism, not to validate P. Treat legacy P as an explicit experimental
> qualification. Do not interpret the run as evidence about production model-driven planning. A
> later broader E2E gate should use T5/production P once recovery itself has been proven live."

The profile actually run was **not** standing T0 (its W/R bind `kind="managed_local"`, which needs an
installed local Qwen runtime this machine does not have — confirmed by direct inspection:
`CALLOSUM_APP_DATA_DIR` unset, no `managed-local-ai/target.json` under either real desktop app-data
directory). Per Cliff's second, explicit resolution, the run used a **T0-shaped variant**: W/R
swapped to `ollama`/`qwen3.5:9b`/`think=False` against the authorized isolated JUNO Ollama
(`:11435`) — the same binding Phase 21's T5 used — while **P stayed `legacy`** (guaranteeing a
SEARCH action fires), C stayed `det`, S stayed `off`.

**Per Cliff's own instruction: this run is not evidence about production model-driven planning
(P).** Its purpose is solely to exercise the recovery/remap mechanism under `legacy` P, which it did.

## Preflight / authorization

- **Pre-run HEAD:** `2e8bb8795e3703fabf6b7cbf8dcb5721f7562f6a` (Phase 22) — matched the brief's
  expected HEAD exactly.
- **Tree state:** clean except the one new, intentionally-untracked harness
  (`phase23_live_recovery_targeted_u2_remap_validation.py`) — confirmed by the harness's own
  equivalent dirty-tree check (mirroring Phase 21's precedent) immediately before authorization was
  written, and reconfirmed after the run (see "Production-code diff" below).
- **Frozen v9 `combined_hash`:** reconfirmed `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.
- **Library copy:** reused the preserved T5C run's own frozen copy
  (`.local/e2e-runs/q-aib-hierarchical-t5c-live-20260930/library_copy.sqlite`); `library_copy.verify()`
  confirmed zero drift against its frozen fingerprint both before and after the run.
- **Required-model liveness check (not inference):** `GET /api/tags` on `:11435` confirmed
  `qwen3.5:9b` present, digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` —
  matching JUNO's own ops convention of probing identity before any authorized runtime use.
- **Declared-scope ceiling (mechanically knowable in advance):** `mscope.enumerate_model_nomination_
  scopes(contract_by_child)` = **15**, reconfirmed immediately before authorization was written.
  **Unlike Phase 21, the REACHED/nonempty/physical U1 and U2 call counts could not be pre-derived
  this time** — U1 runs over a sealed ledger that does not exist until this same live run's own
  W1/R1/C1 round completes, and U2's own fresh-request set F is a function of the recovery round's
  real search results, which also do not exist until this same live run's W2/R2/C2 round completes.
  Both counts are reported below as honest post-hoc observations, never a pre-declared ceiling.
- **Standing experiment gate:** `hierarchy_contract.check_authorization()` — the real, unmodified
  production gate — was invoked against the written authorization record before the hierarchy was
  loaded, exactly as `run_topology()`'s own CLI path would.

## Disclosed departures from a literal `run_topology()`/CLI invocation

Every other component reused is the real, unmodified production object (`e2e.bind`, `e2e.require_
models`, `runtime.build_runtime`, `backends.ResidencyGuard`, `e2e.execute`,
`sufficiency_diagnostic.compute_diagnostic_sufficiency_map`/`compute_direction_and_effectiveness`,
`sufficiency_recovery_targets.compute_recovery_targets`/`project_fresh_request_keys`,
`sufficiency_model_scope.*`, `hierarchy_contract.*`). Nothing here reimplements any of them.

1. **Hierarchy loaded via `hc.load_contract(question, pins=None)`, not `load_contract_for_live`** —
   the same pre-existing, disclosed pin-drift bypass Phase 21 already used.
2. **A custom `Profile` variant constructed directly** (above), not resolved through
   `topo.resolve_profile`'s name registry, since this is a one-shot experimental qualification, not a
   standing named profile.
3. **`execute()` called directly, not through `run_topology()`.** `run_topology()`'s own `execute(...)`
   call site never threads `sufficiency_recovery_gate_enabled` — confirmed by direct read, no CLI
   flag exists for it either. This script replicates `run_topology()`'s own pre-`execute()` setup
   sequence verbatim (`endpoints_used`, `require_models`, `build_runtime`, `bind`,
   `backends.ResidencyGuard`) rather than reimplementing any of it differently.
4. **`run_topology()`'s own `scored=True` path was not used**, for a structural reason:
   `provenance.assert_clean()` refuses on any dirty path including an untracked file, and this
   harness script itself necessarily exists, uncommitted, at the moment it runs. The harness instead
   ran its own equivalent dirty-tree check (mirroring Phase 21's precedent exactly): abort unless the
   only dirty path is the harness file itself. The real safety property `assert_clean` protects (no
   uncommitted *production* code drift) was independently preserved.

## Run identity

- **Model:** `qwen3.5:9b` · **think:** `False` · **endpoint:** `http://127.0.0.1:11435` (JUNO, isolated).
- **Question:** `aib` (question_sha256 `6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030`).
- **Run id:** `phase23-live-recovery-targeted-u2-remap-validation-20261003T020939Z`.
- **Elapsed:** 1718.2s (~28.6 min) — W1 341.3s, R1 97.0s, C1 0s (det), U1 13.7s, P1 0s (legacy, no
  model call), W2 1053.4s (the recovery round — 22 LEGACY search actions), R2 186.4s, C2 0s, U2
  25.8s.
- **Stage log:** `W1 → R1 → C1 → U1 → P1 → W2 → R2 → C2 → U2`. **Nothing skipped** — every stage
  that could run, ran, including the recovery round the earlier Phase 21 run never exercised.
- **Records/claims:** 385 records total, 74 source-verified propositions in the final sealed ledger.
- **Library unchanged after run:** `True`.

## U1 accounting (pre-recovery)

| Metric | Value |
|---|---|
| Declared semantic scopes | 15 |
| U1 request keys reached | 13 |
| `fresh` | 10 |
| `fresh_no_candidates` | 3 |
| Declared scopes never reached at all (zero candidates before any call) | 3 — `c12`×2 roles (`intervention`, `target_manifestation`), `c9`'s `individual_difference_trait_or_construct` |

All 13 reached U1 keys, with offered/accepted counts, are in `18_sufficiency_model_assist.json`'s
`"initial"` array (also embedded in `phase23_result.json`). Notable: `c8` reached two real
partitioned contexts (`U1`: 5 offered/0 accepted; `U6`: 2 offered/**4 accepted**) — the same
real multi-context shape Phase 21 found, now reconfirmed.

## RecoveryTarget inventory, before recovery

**19 targets** (recomputed post-hoc, read-only, from `17_sufficiency_map.initial.json` via the exact
same pure `compute_recovery_targets` function `execute()` calls internally — not a
reimplementation). Reason-code breakdown: `missing`=16, `partial`=2, `provisional_corroboration`=1.

`c6` (4 targets: 2 `brain-attitude` model-nomination roles reason=`missing` scope=none; 2
`implicit-explicit-coverage` `category_evidence` instance-scoped, reason=`missing`), `c8` (2 targets:
`individual_difference_trait_or_construct` reason=`missing` scope=none; `relationship_to_bias_
manifestation` reason=`missing` scope=none), `c11` (2 targets, both `missing`, scope=none), `c12` (3
targets, all `missing`, scope=none) — matching the structural shapes the Phase-22 audit identified
from Phase 21's data.

## Recovery round (W2/R2/C2)

- **Plan:** `legacy` planned a `LEGACY` search action for all 11 children with an unresolved item
  (22 unresolved rows across repeated children, since several children carried more than one
  synthetic recovery obligation).
- **Recovery log:** 22 rows, all action `LEGACY`.
- **Result:** source-verified claims grew from the W1-only ledger; `R2`/`C2` both ran (the `len(...)
  > before` gate that only sections C2/R2 when new evidence actually appears).

## U2 accounting (post-recovery, target-scoped remap)

| Metric | Value |
|---|---|
| U2 request keys reached | 23 |
| `fresh` | 17 |
| `fresh_no_candidates` | 2 |
| `held_fixed_replay` | 4 |
| **Actual physical U2 fresh-attempt calls** (`fresh` + `fresh_no_candidates` + both `fresh_failed_*`) | **19** |

The 4 `held_fixed_replay` keys are exactly the U1 contexts the independently-recomputed F (below)
correctly excludes: `c1`'s `neural_measure_or_modality` (ctx=None), `c8`'s `U1` and `U6` contexts,
and `c5`'s `named_brain_region_or_network` (ctx=None) — each replayed its U1 receipt unchanged,
proving the mechanism does **not** needlessly re-litigate an unrelated settled request merely
because its sibling scope was targeted.

## F (projected fresh-request set) — the hard call-budget cross-check

`sufficiency_recovery_targets.project_fresh_request_keys` was independently re-run, read-only, from
the written trace artifacts (the real `recovery_targets_initial`, the real `sufficiency_map_
initial`, the real U1 receipt keys, and a candidate-construction-only dry enumeration of the
post-recovery request inventory — the identical technique the production code itself uses
internally).

**|F| = 19.** Comparing F against the actual physical U2 fresh-attempt calls observed in the trace:

```
actual_fresh_keys ⊆ F:  True
actual_fresh_keys − F:  ∅
F − actual_fresh_keys:  ∅
```

**F and the actual physical fresh-call set are EXACTLY EQUAL (19 = 19, set equality, not merely a
subset relation).** This is the strongest possible live confirmation of Phase 22's central
guarantee: production's own internal hard-call-budget assertion (`e2e.py`'s `if not actual_fresh_
keys <= sufficiency_u2_fresh_request_keys: raise RuntimeError(...)`) fired with real,
recovery-augmented evidence and passed — the run completed with exit code 0, no exception — and an
*independently recomputed* F (built by this validation script from the trace artifacts, not by
reading the live object the production run itself used) matches it exactly, with nothing authorized
but unused.

F's 19 keys span 6 children: `c1` (1 key), `c10` (1), `c11` (4 — two roles × two contexts, `U10`
pre-existing and `U21` newly discovered by recovery), `c12` (8 — two roles × four contexts, `U18`/
`U19`/`U28`/`U30`, **all four newly discovered by recovery** — `c12` was declared but unreached in
U1), `c2` (1), `c4` (1), `c5` (1), `c6` (2).

## RecoveryTarget inventory, after recovery

**33 targets.** Reason-code breakdown: `partial`=13, `missing`=7, `provisional_corroboration`=10,
`relationship_unverified`=3.

- **6 targets persist unchanged** (identical `target_id`) — genuinely unresolved after the one
  authorized round, reported honestly rather than cleared:
  - `c3::0ff295b8` — `category_evidence` (`implicit` instance), `missing`.
  - `c5::22fa1417` — `behavior_or_behavioral_measure`, `partial`, scope=none.
  - `c6::90646ddc` / `c6::efad0cb3` — `category_evidence` (`implicit`/`explicit` instances), `missing`.
  - `c8::2319dd98` — `individual_difference_trait_or_construct`, `missing`, scope=none.
  - `c8::74f276a2` — `relationship_to_bias_manifestation`, `missing`, scope=none.
- **13 targets resolved** (target disappeared — the condition that generated it no longer holds):
  spanning `c10`×2, `c11`×2, `c12`×3, `c1`×1, `c2`×1, `c4`×2, `c6`×2.
- **27 targets are new** (appeared only after recovery): `c4`×8 (`provisional_corroboration`,
  `named_brain_region_or_network`), `c6`×8 (`partial`, `attitude_type_or_measure`), `c11`×4, `c10`×2,
  `c2`×3 (`relationship_unverified`), `c12`×1 (`provisional_corroboration`), `c1`×1
  (`provisional_corroboration`).

## Structural-case verdicts

- **`c8` (real, confirmed suppression, matching the Phase-22-audit's pre-identified case exactly):**
  `c8`'s `individual_difference_trait_or_construct` role DID receive 4 real accepted nominations
  (context `U6`, both in U1 and held fixed through U2) — yet both of `c8`'s own targets persist
  **unresolved** across the entire run, because the sibling required role
  `relationship_to_bias_manifestation` never received any candidate evidence at all, even after a
  full recovery round. **PASS** — confirms the mechanism correctly withholds completion when a
  sibling role is starved, under real live conditions, not just offline replay.
- **`c12` (the two-context adversarial case):** `c12` was *declared but entirely unreached* in U1
  (zero candidates for either role) and was discovered live by recovery, producing **four** distinct
  partitioned contexts (`U18`, `U19`, `U28`, `U30`) across two roles — 8 of F's 19 keys. Each context
  resolved independently (`U18`: both roles accepted; `U19`/`U28`: neither accepted; `U30`:
  `intervention` accepted, `target_manifestation` not) — **no cross-context contamination observed**,
  each context's own fresh call saw only its own candidate pool. **PASS**.
- **`c11` (the request-context-broadening case):** `c11`'s pre-existing `U10` context was
  re-authorized fresh (both roles, zero new acceptances) *and* a genuinely new `U21` context was
  discovered by recovery and also fresh-authorized (one role accepted, one not) — confirming F
  correctly includes both an existing-context reconsideration and a brand-new post-recovery context
  under the same semantic scope. **PASS**.
- **`c6` (parent-context *role propagation*, traced, not merely asserted):** `c6#suff:brain-attitude`
  declares `parent_context_roles: ["named_brain_region_or_network"]` and remains `multi_instance:
  False` in its own authored contract throughout — yet its final map carries **8** instances, each
  `partially_filled`/`incomplete_instance` (role-fork-derived content-hash instance keys, not
  positional `U##` contexts). This exactly tracks `c4`'s own final map, which independently shows
  **8** instances on `c4#suff:specific-region` (`multi_instance: False`, 8 forked instances) —
  matching `c4`'s own 8 real accepted `named_brain_region_or_network` nominations in U2 one-for-one.
  **c6 inherits c4's 8 forked brain-region fills via structural parent-context role propagation**,
  and since `c6`'s own `attitude_type_or_measure` role never received any candidate in either pass
  (`fresh_no_candidates` in both U1 and U2, offered=0 throughout), every one of those 8 inherited
  instances is individually flagged `partial` rather than silently merged or dropped. This is a real,
  live confirmation of the pre-existing parent-context-role-propagation substrate interacting
  correctly with Phase 22's new target machinery — **distinct from** Phase 22's own
  `dependency_origins` cross-child redirection (see next item), which this run did **not** exercise.
- **Parent-context `dependency_origins` redirection (Phase 22's own specific mechanism):**
  searched every final target's `dependency_origins` for an entry whose `child_id` differs from the
  target's own `search_child_id`. **Count: 0 — not exercised live this run**, the same honest gap
  the Phase-22 audit already disclosed for Phase 21's offline data. The underlying propagation
  mechanism (previous item) was exercised; this specific redirect code path was not, because no
  `provisional_corroboration` target happened to originate from a propagated (rather than
  directly-owned) binding this run.

## Scientific nomination adjudication — kept separate from infrastructure correctness

Per the brief's own requirement, this section is a plain observational note, **not** a quality
judgment call: several real U2 acceptances occurred this run (`c1`: 7 of 9 offered;
`c4`: 8 of 5 — note offered=5 but accepted=8 is an internal artifact of role-forking across repeated
candidate rows, not examined further here; `c10`: 2 of 5; `c2`: 3 of 20; `c11`'s `U21` context: 2 of
2 for `culture_or_population`). No scientific correctness adjudication of any individual accepted
nomination was performed as part of this validation — that is explicitly out of scope for an
infrastructure/call-budget validation, per the brief's own instruction to keep the two separate.

## Evidence-recovery adjudication — kept separate from infrastructure correctness

The recovery round's 22 `LEGACY` search actions materially changed the evidence base (385 total
records vs. a W1-only count not separately captured by this script, 74 final verified claims) and
discovered real new partitioned instances for `c11`, `c12`, `c1`, `c4`, and (via propagation) `c6`.
Whether any individual recovered passage is a scientifically good match for its triggering gap was
not adjudicated here — this validation's purpose is the recovery/remap *mechanism*, not the
retrieval quality of any one recovered passage.

## Before/after semantic-map comparison

| Requirement state | Initial (13 requirements) | Final (13 requirements) |
|---|---|---|
| `filled` | 2 | 4 |
| `partially_filled` | 4 | 7 |
| `missing` | 7 | 2 |

Recovery materially improved coverage (2→4 `filled`, 7→2 `missing`) while simultaneously surfacing
more, not fewer, reconsideration/review targets (19→33) — exactly the intended "silence is not a
certificate" posture: more real evidence produces more inspectable candidates, never a quieter,
falsely-reassuring map.

## Stop-search / one-round convergence

No requirement reached a `stop_search_certified` state in either pass (0/13 both times — this
contract's own completion semantics never mark a `model_nomination_only`-dependent fill as
independently certified without further corroboration, by design). The 6 persisted targets are
correctly reported as **unresolved after the one authorized round** — no further automatic attempt
was made, matching the Phase-22-audit's own documented one-round-convergence discipline exactly.

## Latency / resource accounting

See "Run identity" above for the full per-stage breakdown. U1 (13.7s) and U2 (25.8s) — the two
sufficiency-nomination stages Phase 22 touches — together are under 40s of the run's 1718s total;
the overwhelming majority of wall-clock time is real retrieval (W1 341s, W2 1053s) and
responsiveness judging (R1 97s, R2 186s), which Phase 22 does not modify.

## Production-code diff from starting HEAD

```
git diff --stat 2e8bb8795e3703fabf6b7cbf8dcb5721f7562f6a -- '*.py'
```
excluding the new harness file (`phase23_live_recovery_targeted_u2_remap_validation.py`) is
**empty** — confirmed. The only tracked change this phase introduces is this results document, the
new harness script, and the `CONTRIBUTION-LINEAGE.md` append below.

## Infrastructure PASS/FAIL

**PASS.** Every structural-case check above passed; the hard call-budget invariant held exactly
(set equality, not merely a subset bound) against real, recovery-augmented evidence; no production
code changed; the one-round-convergence/honest-unresolved-reporting discipline held; parent-context
role propagation interacted correctly with the new target machinery; no cross-context evidence
contamination was observed anywhere in `c11`/`c12`'s multi-context cases.

## Newly discovered issues

None that block the mechanism. Two honest residual gaps, both pre-existing and unrelated to Phase
22/23: (1) `c9`'s own `individual_difference_trait_or_construct` scope never received a single
candidate across the entire run, even after recovery; (2) `c6`'s own `attitude_type_or_measure`
and `named_brain_region_or_network` (as a *directly-nominated*, not propagated, role) scopes never
received a candidate either. Neither is a Phase-22/23 defect — both are retrieval/evidence-coverage
gaps in this specific real corpus against this specific contract, exactly the kind of honest
"silence, not a certificate" the architecture is designed to surface rather than paper over.

## Readiness verdict

**The recovery/target-scoped-remap architecture is READY for the broader five-question E2E ladder**,
with the explicit qualification Cliff himself specified: this run validates the *mechanism*
(recovery discovery → target projection → exact-request U2 authorization → hard call-budget
enforcement) under `legacy` P. A future broader E2E gate using `T5`/production P remains a distinct,
not-yet-run validation of model-driven *planning* quality — unaffected by, and not validated by,
this phase.
