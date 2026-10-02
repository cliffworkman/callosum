# Phase 20a — deterministic sufficiency mapping reachable through run_topology()/main()

Starting HEAD: `68d2dd65667e7c1a934a5279105eaaf6ba64b3fb` (the Phase 19 implementation commit) —
verified exactly, clean tree, before any change. This document covers Phase 20a only: making the
already-built deterministic sufficiency-mapping block inside `execute()` reachable from a real
`run_topology()`/`main()` invocation. **No model_client, no nomination_context, no live model
call, no retrieval experiment, no contract/pin change, no v10, no Phase-19 redesign.**

## 1. The headline discovery that authorized this phase

The Phase 20 audit (Plan Mode, read-only; `~/.claude/plans/pasted-content-id-d898-new-architectura-
serialized-coral.md`, outside this repo) traced `execute()`'s two sufficiency call sites (both
already accepting `sufficiency_contract=`/`sufficiency_parent_of=`/`model_client=`/
`nomination_context=` since an earlier phase, threaded all the way to the Phase-19 model-nomination
checkpoint) and found that `run_topology()` — the function `main()` actually calls for a real
`python -m experiments.ask_cli_revised --hierarchy ...` run — never supplied the first two at all.
A repo-wide search for the literal `sufficiency_contract=` call-site pattern returned zero matches
in any `.py` file, production or test, before this phase. **Even Phase 1–18's deterministic-only
sufficiency map had never run inside a real `execute()`/`run_topology()` invocation, live or in
CI.** This phase closes exactly that integration gap, deterministic-only, per Cliff's explicit
20a/20b split decision.

## 2. Mandatory read-only preflight — where the contract and parent map come from

Resolved by source inspection before writing any code (per the authorizing brief's section B):

- **Frozen contract.** `sufficiency_freeze.py` already owned a writer (`write_frozen`/
  `FROZEN_PATH`) for the frozen, UNREVIEWED_CANDIDATE sufficiency-contract artifact, but no reader.
  The repo already carries a committed, human-reviewed sign-off
  (`sufficiency_contract.aib_hier_v9.review.json`, `reviewed_by: "Cliff"`, `reviewed_at:
  2026-09-30T20:17:31-04:00`, naming `combined_hash` `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`
  exactly). No runtime re-authoring was needed or used.
- **`parent_of`.** The loaded hierarchy contract's own `hierarchy.children[*].parent` field is
  already the sole source of truth `assert_executable` itself cross-checks (`hierarchy_contract.py`)
  — the identical field `sufficiency_diagnostic.compute_diagnostic_sufficiency_map`'s own docstring
  already documents as the required source. No second, independently-maintained topology map
  existed or was invented.

Neither case required a new semantic decision about contract identity or parentage — both sources
already existed and structurally agreed (the same 11 child ids: `c1, c2, c3, c4, c5, c6, c8, c9,
c10, c11, c12`), so implementation proceeded OTR per the brief's own instruction.

## 3. Implementation — files changed

| file | change |
|---|---|
| `hierarchy_contract.py` | **new** `parent_of(contract) -> dict[str, str]` — a thin, generic projection of `_hierarchy(contract)["children"]`'s own `parent` field. Reuses the existing version/shape guard; raises `HierarchyRejected` identically to `assert_executable` for a non-hierarchy contract. Zero other changes. |
| `sufficiency_freeze.py` | **new** `REVIEW_PATH` sibling constant, `SufficiencyContractRejected` exception (same base class/shape as `hierarchy_contract.HierarchyRejected`), and `load_verified(*, frozen_path=None, review_path=None) -> dict | None` — the reader half of this module's existing writer-only convention. Verifies each child's `frozen_view` against its own recorded per-child hash, the file's own `combined_hash`, and a review record naming that exact hash with non-empty `reviewed_by`/`reviewed_at`. Returns `None` (never raises) only when the frozen file itself doesn't exist. |
| `e2e.py` | **new** module-level `_default_sufficiency_loader(contract) -> tuple[dict \| None, dict \| None]` composing the two functions above. `run_topology()` gained one new injectable `sufficiency_loader=_default_sufficiency_loader` parameter (the same DI convention its six other `*_loader`/`verify_*`/`*_factory` parameters already use), invoked only `if hierarchy:` immediately after `contract` is built, and threaded straight into the unmodified `execute(...)` call as `sufficiency_contract=`/`sufficiency_parent_of=`. One small manifest addition: `manifest["sufficiency"] = {"contract_supplied": ..., "mapped_children": sorted(result["sufficiency_map_initial"] or {})}` inside the existing `if hierarchy:` manifest block — a thin presence/coverage summary; the full map is already the pre-existing `"17_sufficiency_map.initial.json"`/`"17_sufficiency_map.json"` trace artifacts `execute()` itself writes (discovered already built, unmodified by this phase — see §4). |
| `hierarchy_test_support.py` | `HierHarness.run()` gained three optional, `None`/`False`-defaulted keyword parameters (`sufficiency_contract`, `sufficiency_parent_of`, `sufficiency_recovery_gate_enabled`), forwarded to the unmodified `e2e.execute(...)` call — every existing caller that omits them observes byte-identical behavior. |
| `test_hierarchy_contract.py`, `test_sufficiency_freeze.py`, `test_hierarchy_e2e.py` | new tests (§6). |

**No other file was touched.** `sufficiency_mapping.py`, `sufficiency_diagnostic.py`,
`sufficiency_model_scope.py`, `sufficiency_recovery_targets.py`, `sufficiency_engine.py`, and
`qwen.py` are byte-identical to HEAD (confirmed by `git diff --stat`).

## 4. A discovery that narrowed this phase's own scope

While tracing `execute()`'s full body (brief section L asked what to persist), its return-dict
construction and trace-writing were already found complete: `execute()` already writes
`"17_sufficiency_map.initial.json"`/`"17_sufficiency_map.json"` and already returns
`sufficiency_map_initial`/`sufficiency_map_final`/`sufficiency_recovery_targets` in its result dict
— all gated on `is not None`, inert when no contract is supplied. This predates Phase 20a; it was
simply never reachable. **No artifact-persistence code was added in this phase** beyond the one
thin manifest summary in §3 — exactly the brief's own instruction to prefer existing conventions
and defer anything beyond that as unrelated scope.

## 5. Exact call graph after this change

```
main() --hierarchy
 -> run_topology(..., hierarchy=True, sufficiency_loader=_default_sufficiency_loader)
     hier_contract = (hierarchy_loader or hierarchy_contract.load_contract_for_live)(question)
     check_authorization(...)
     contract = hier_contract
     sufficiency_contract, sufficiency_parent_of = sufficiency_loader(contract)
         -> sufficiency_freeze.load_verified()                      # None, or {child_id: SufficiencyContract}
         -> hierarchy_contract.parent_of(contract)                  # {child_id: parent_child_id}  (only if the above was not None)
     -> execute(..., sufficiency_contract=sufficiency_contract, sufficiency_parent_of=sufficiency_parent_of)
         # UNCHANGED from HEAD below this line:
         early_sealed = stages.seal(...)
         sufficiency_map_initial = sufficiency_diagnostic.compute_diagnostic_sufficiency_map(
             early_sealed, sufficiency_contract, sufficiency_parent_of or {}
         )  # model_client and nomination_context both omitted -> both None, exactly
         sufficiency_diagnostic.compute_direction_and_effectiveness(early_sealed, sufficiency_map_initial)
         ... (recovery round, unchanged) ...
         sufficiency_map_final = <recomputed from `sealed` iff planned_search, else == sufficiency_map_initial>
         recovery_targets_final = sufficiency_recovery_targets.compute_recovery_targets(...)
         trace.write_json("17_sufficiency_map.initial.json", ...)   # pre-existing, now actually fires
         trace.write_json("17_sufficiency_map.json", ...)           # pre-existing, now actually fires
         return {..., "sufficiency_map_initial": ..., "sufficiency_map_final": ..., "sufficiency_recovery_targets": ...}
     manifest["sufficiency"] = {"contract_supplied": ..., "mapped_children": [...]}   # new, thin
```

## 6. Proof `model_client=None`/`nomination_context=None` exactly

`run_topology()`'s own `execute(...)` call passes neither kwarg — Python binds `execute()`'s own
defaults (`model_client=None, nomination_context=None`) for both, identical to passing them
explicitly. `test_model_client_and_nomination_context_are_never_passed_by_run_topology` asserts
`"model_client" not in captured and "nomination_context" not in captured` against a spy wrapping
the real `execute()`. `test_execute_reaches_sufficiency_mapping_with_zero_model_assistance`
additionally walks every binding in a real integrated result and asserts
`provenance.candidate_source != "model_mapping"` anywhere — a behavioral proof, not just a
call-signature one.

## 7. Current-direct vs. integrated deterministic comparison (section H's authoritative invariant)

`SufficiencyIntegrationTests.test_the_integrated_run_matches_calling_the_deterministic_mapper_
directly` runs the real, committed v9 contract through the real hierarchical `execute()`
orchestration (via `HierHarness`, real claims `CLAIM_C5`/`CLAIM_C4`/`CLAIM_C12` already established
by this file's own pre-existing `HierarchyExecuteTests`), then independently calls
`compute_diagnostic_sufficiency_map` + `compute_direction_and_effectiveness` directly on the exact
resulting `sealed` ledger, and asserts full equality against `sufficiency_map_final`. **Passes.**
Per the brief's own section H/O instruction, this is the release gate; no comparison against
historical Phase 2/5/9/10 artifacts (a different, no-longer-current mapper state) was attempted or
treated as authoritative.

## 8. Recovery-gate behavior

`sufficiency_recovery_gate_enabled` was left at its existing `False` default in `run_topology()`'s
own `execute(...)` call — mapping reachability and recovery-gating are proven as two genuinely
separate capabilities: `test_the_recovery_gate_never_changes_the_mapping_result` asserts
`sufficiency_map_initial` is byte-identical whether the gate is on or off, and
`test_recovery_targets_are_reachable_under_their_own_existing_gate` exercises the gate explicitly
(never implied merely because mapping ran) and cross-checks its output against calling
`compute_recovery_targets` directly.

## 9. Initial/final map behavior

Unchanged from HEAD, confirmed by the equivalence test in §7: initial map from `early_sealed`;
final map recomputed from `sealed` only when recovery's own `planned_search` is non-empty, else
inherited unchanged — Phase 17/18 semantics, untouched by this phase.

## 10. Artifacts written

`"17_sufficiency_map.initial.json"`/`"17_sufficiency_map.json"` (pre-existing in `execute()`,
simply now reachable) plus one new `manifest["sufficiency"]` presence/coverage summary (§3/§4).
No nomination-receipt artifact — there are no nominations in this phase.

## 11. Regression results

- Targeted (`test_hierarchy_contract.py` + `test_sufficiency_freeze.py` + `test_hierarchy_e2e.py`):
  **102 passed**, 2 failed — both pre-existing, independently reconfirmed present on unmodified
  base HEAD *before this phase touched anything* (reverted all four changed files to `git show
  HEAD:...`, re-ran the exact two tests, same failure, same message: `pin drift: code input
  hierarchy_contract.py changed since the pins were generated` and `rc=3 != 0`; both are the
  identical pair Phase 16/17/18/19 already documented as a disclosed, unrelated pin-drift issue).
- Full `experiments/ask_cli_revised` tree: **2273 passed, 11 skipped, 2 failed** (the same two).
  Arithmetic cross-check: Phase 19's own baseline was 2251 passed; this phase adds exactly 22 new
  tests (2 `parent_of` + 8 `load_verified` + 6 `SufficiencyIntegrationTests` + 6
  `RunTopologySufficiencyWiringTests`, each count collected via `pytest --collect-only`, not
  estimated) — 2251 + 22 = 2273, matching exactly.
- `ruff format --diff` / `ruff check`, scoped to the 7 touched files: both clean (one pre-existing,
  unrelated formatting gap at `hierarchy_contract.py`'s unchanged line ~970 confirmed present on
  base HEAD too — left untouched per rule #7, no drive-by fix).
- v9 `combined_hash` reconfirmed unchanged (every `load_verified()` call recomputes and checks it
  live against the frozen file's own content, never trusting a cached value):
  `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

## 12. New tests added (22)

- `test_hierarchy_contract.py::RealHierarchyTests` (+2): `parent_of` reads exactly each child's own
  `parent` field; rejects a non-hierarchy contract identically to `assert_executable`.
- `test_sufficiency_freeze.py::LoadVerifiedTests` (+8, new class): the real committed v9 pair
  verifies and returns every child in the exact `frozen_view` shape `compute_diagnostic_
  sufficiency_map` expects; a missing frozen file is a benign `None`; a tampered per-child hash, a
  tampered `combined_hash`, a missing review file, a review naming a different `combined_hash` or
  `question_key`, and each missing required review field are all rejected with a problem string
  naming what failed.
- `test_hierarchy_e2e.py::SufficiencyIntegrationTests` (+6, new class): the real frozen contract and
  real hierarchy agree on every child; `execute()` reaches sufficiency mapping with zero model
  assistance (behavioral, not just signature); the integrated run equals the direct deterministic
  call (§7); recovery targets are reachable under their own gate; the gate never changes the
  mapping result; omitting `sufficiency_contract` reproduces exact pre-Phase-20a (`None`) behavior.
- `test_hierarchy_e2e.py::RunTopologySufficiencyWiringTests` (+6, new class): `run_topology()`
  itself sources the real frozen contract and real parent map; `model_client`/`nomination_context`
  are never passed; a non-hierarchical run never sources anything; an injected `sufficiency_loader`
  is honored and receives the loaded contract; the manifest records the thin presence summary; an
  unverifiable (tampered/unreviewed) frozen artifact fails the run loudly before `execute()` is ever
  reached, never silently treated as absent.

## 13. Newly discovered issues

One, already described in full in §4: `execute()`'s own sufficiency-persistence (trace artifacts +
return-dict keys) was already fully built in an earlier phase and simply unreachable — not a defect
in this phase's own scope, and it needed zero new code once reachability was fixed. No other new
issue was found; the two failing tests are the pre-existing pin-drift pair (§11), confirmed
unrelated by direct reversion-and-rerun against unmodified HEAD, not merely asserted.

## 14. Is deterministic production-shaped sufficiency integration CLOSED?

**Yes, for Phase 20a's own scope** (brief section A): a real `--hierarchy` invocation now sources
and threads the frozen, human-reviewed v9 sufficiency contract and the real hierarchy's own parent
map into `execute()`'s pre-existing deterministic mapping block, proven equal to calling that block
directly on the same sealed ledger, with recovery-gating kept a genuinely separate, still-off-by-
default capability, and zero model-client/nomination-context involvement anywhere. Every item the
authorizing brief explicitly deferred (the broad sufficiency try/except, `stage()`/residency
accounting, `QwenTasks.model_name`, the model-assist CLI flag, nomination receipts) was left
untouched, confirmed by `git diff --stat` showing no changes to `sufficiency_mapping.py`,
`sufficiency_model_scope.py`, or `qwen.py`.

## 15. Is Phase 20b ready?

**Recommend yes** — the production initial model-assisted sufficiency wiring (feature off by
default) the original Phase 20 audit designed can now build on a seam that has, for the first time,
actually been exercised end-to-end through the real `run_topology()`/`execute()` path, with a
current-code equivalence proof already established as the release-gate pattern to extend. No new
prerequisite surfaced during this phase that would block it. **Not started; no live call made.**
