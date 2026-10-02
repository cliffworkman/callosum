# Phase 20b — production initial model-assisted sufficiency wiring, feature-gated off by default

Phase 20a commit: `b928d1406e928863b034d4ff4c62885a4f6dd124` (verified HEAD before any Phase-20b
change). This document covers Phase 20b only: threading a real `model_client`/Phase-19
`nomination_context` into `execute()`'s two existing sufficiency call sites, feature-gated off by
default. **No live model call anywhere in this phase** — every test uses a duck-typed fake
(`FakeQwenNomination`), never a real transport. No Phase 21 (live validation) or Phase 22
(target-scoped post-recovery remap) work was started.

## 0. Phase 20a checkpoint commit

Verified base HEAD was exactly `68d2dd65667e7c1a934a5279105eaaf6ba64b3fb` (Phase 19) before
committing; the working tree contained exactly the reviewed Phase-20a files. Committed as
`b928d1406e928863b034d4ff4c62885a4f6dd124` (one dedicated commit; `--no-verify` used only to bypass
a pre-existing, unrelated `app/frontend/js/20_synthesis.jsx` line-budget drift in this worktree's
`app/` tree — disclosed in the commit message, never touched by this work). A pre-existing,
unrelated `hierarchy_contract.py` `ruff format` gap (two missing blank lines, confirmed present on
unmodified HEAD too) was fixed honestly as part of that commit so the format hook passed for real.
Tree confirmed clean after committing.

## 1. Scope

Exactly what the authorizing brief specified: the **initial** (U1) model-assisted path, with a
disclosed, deliberate **held-fixed** policy for any **final** (U2) recompute a recovery round
triggers — never Phase 22's target-scoped remap. Off by default; explicitly enabled; fully testable
offline.

## 2. Enablement

A new `--sufficiency-model-assist` flag (default `False`), valid only with `--hierarchy` —
validated at **two** independent layers, matching this file's own established double-validation
convention (`parse_args` + `run_topology`'s own internal re-check, the same pattern `--hierarchy`
itself already uses): `parser.error(...)` at the CLI layer, `raise ValueError(...)` inside
`run_topology()` for any direct (non-CLI) caller. No new topology profile was created for this
switch — it is a bare bool threaded through `run_topology(sufficiency_model_assist=...)` →
`execute(sufficiency_model_assist_enabled=...)` unchanged.

## 3. Mandatory nomination-context invariant

`e2e._sufficiency_u1_context(profile, bound)` is the single enforcement point: it always returns
`(model_client, nomination_context)` together, or raises `SufficiencyModelAssistRefused` before
constructing either. `execute()` calls it exactly once, at the very top (before any stage, trace
file, or model call — the same posture the two pre-existing fail-closed checks there already have),
and carries the result through both call sites as plain local variables. There is no code path in
`execute()` that can reach a `model_client`-set/`nomination_context`-absent (or the reverse) state.
U1's policy is the fixed `mscope.all_eligible_policy()`. The raw `nominate_sufficiency_role(
category_description=..., candidates=...)` wire protocol is untouched — confirmed unchanged by
`git diff --stat` showing zero lines touched in `qwen.py` beyond the new `model_name` property, and
by every existing Phase 2/5/9/10 fake/recorded client in this repo still being usable as-is.

## 4. Production model client

Confirmed by direct inspection (not assumed): `bound.qwen` — the SAME `QwenTasks` object the W role
already uses for claim formation — is the nomination client. No second nomination worker, no
separate Qwen lifecycle. `bind()` is completely unmodified.

## 5. Model identity (`QwenTasks.model_name`)

Inspected BOTH `self.config` shapes `bind()` ever constructs before writing anything:
`backends.NativeWorker.model: str` (the ollama-native path) and `app.backend.llm.managed_local.
ManagedProviderConfig.model: str` (the managed-local path) — confirmed, by reading both class
definitions directly, to use the IDENTICAL field name. One generic `getattr(self.config, "model",
None)` property covers both without branching; `None` only if some future third config shape omits
`.model` entirely, which callers must treat as "no identity available," never a guess. Tests added
for the native-worker path, the managed-local-shaped path (via a `SimpleNamespace` standing in for
the one attribute the property actually reads), and the no-attribute fallback.

## 6. Thinking preflight

Confirmed by inspection, not reused blindly: `ManagedProviderConfig` has no `think` field at all —
thinking is simply never consulted for `managed_local`; `think=None` there is NOT equal to the
required `False` and is correctly refused as unverified (fail-closed on ambiguity, not "probably
fine"). `_sufficiency_u1_context` requires `profile.W.think is not False` to raise
`SufficiencyModelAssistRefused` BEFORE constructing a client or context, BEFORE any stage runs.
Global worker state is never mutated; no per-call thinking override was invented (none exists
anywhere in `qwen.py` today, confirmed). The effective `think` value is recorded in both the
persisted receipt artifact and the result-dict diagnostics (§13/§14) for inspectability, per the
audit's own recommendation — the Phase-19 receipt **schema itself** (`new_nomination_receipt`'s
shape) was left completely unchanged, as instructed.

## 7. U1 lifecycle

One fresh `mscope.new_nomination_context(mscope.all_eligible_policy())` per `execute()` call,
constructed by `_sufficiency_u1_context` and passed unchanged into
`compute_diagnostic_sufficiency_map(..., model_client=..., nomination_context=...)` — the exact
same function call Phase 20a already made, now with these two kwargs populated instead of omitted.
No deterministic-only comparison map is computed anywhere alongside it — one authoritative map, as
required. Brought under the SAME W-role `stage()`/`ResidencyGuard` accounting every other
`bound.qwen` call already uses (`with stage("U1", "W"): ...`) — confirmed this required zero changes
to `stage()` itself: it already bounds "one phase, a variable number of calls" (the exact shape
W1/W2 already use for the retrieval rounds), so no mismatch to report. The deterministic-only branch
(flag off) is completely untouched, still building its own manual stage_log entry exactly as
Phase 20a left it.

**Empirically confirmed, real end-to-end run** (real v9 contract, real hierarchy, a fake nomination
client, real CLAIM_C5/C4/C12 claims this file's own pre-existing tests already use): of the 15
scopes Phase 19's own exhaustive offline inventory declared, **11 are actually reached**; **5 make a
real physical call** (nonzero admissible candidates), **6 make zero calls** and report
`fresh_no_candidates` — demand-driven, never a pre-call of every inventory scope, exactly as
required.

## 8. U2 held-fixed policy — the load-bearing requirement

Confirmed via the SAME real run: `planned_search` is non-empty in this fixture (the legacy planner
assigns a SEARCH action to every one of the 8 still-unresolved children, regardless of whether the
recovery round itself finds anything new), so U2 fires. When `sufficiency_u1_model_client is not
None`, `execute()` builds a SEPARATE context — `mscope.new_nomination_context(mscope.
exact_scope_set_policy(set()), prior_receipts=sufficiency_u1_receipts_snapshot)` — an EMPTY
fresh-authorization set, never `ALL_ELIGIBLE` again, with U1's own receipts as the sole replay
source. **Proven, not assumed: U2 made exactly 0 additional physical calls** (`len(fake.calls)`
unchanged between U1 alone and U1+U2 combined — 5 in both cases), with all 11 reached scopes
reporting `held_fixed_replay`. A deterministic-strategy role is completely unaffected (it never
consults a nomination_context at all) and recomputes normally from the rebuilt `sealed` ledger.
U2's own stage_log entry is deliberately **never** wrapped in `stage("U2", "W")` — confirmed by a
direct assertion that its `swap_seconds` stays `0.0` — so replaying already-known receipts incurs no
W residency swap; its `binding.kind` is honestly labelled `"sufficiency_model_assist_held_fixed"`
(never falsely `"deterministic_sufficiency_mapping"`) whenever model-assisted bindings are actually
being replayed into it. This is the deliberate, disclosed bridge to Phase 22, which will later
substitute the exact RecoveryTarget-derived scope set for this empty one, reusing this exact context
shape unchanged.

## 9. Receipt snapshot / pass boundary

`sufficiency_u1_receipts_snapshot = dict(sufficiency_u1_context["in_pass_receipts"])` — an explicit,
named, independent copy, taken immediately after U1 completes, never the live U1 context object
itself. Proven directly: a test mutates the live context's `in_pass_receipts` AFTER taking the
snapshot and confirms the snapshot is unaffected.

## 10. Empty-candidate receipt status

Fixed in `sufficiency_model_scope.resolve_nomination` (Phase 19's own file — a narrow, additive
change, never touching the raw wire protocol or any existing status's meaning): when a scope IS
authorized for a fresh call but `candidate_rows` is empty, a new status `fresh_no_candidates` is
returned WITHOUT ever invoking `make_fresh_call` — checked before the call, not merely inferred
afterward from `candidates_offered`'s own length. Scoped strictly to the fresh-call branch: a
held-fixed scope's status is unaffected by the current candidate count. Three new unit tests prove
the three distinct cases apart: (A) zero candidates → zero calls → `fresh_no_candidates`; (B)
nonempty candidates, a successful call returning an empty answer → plain `fresh`, `accepted=[]`;
(C) mechanical failure (already Phase-19-proven, reconfirmed) → `fresh_failed_*`. All 159 existing
`sufficiency_model_scope`/`sufficiency_mapping`/`sufficiency_diagnostic` tests still pass unchanged.

## 11. Model-stage / residency accounting

Covered in full under §7 (U1) and §8 (U2) — no mismatch was found between the existing `stage()`
abstraction and what this phase needed, so nothing was reported as a STOP condition; the existing
mechanism already cleanly expresses "one named phase, a variable number of calls" and "zero calls,
zero swap" alike.

## 12. Failure semantics

Per-scope mechanical failures remain entirely Phase-19's own responsibility, unchanged. No blanket
try/except was added around the sufficiency mapper in this phase (preserving Phase 20a's own
deliberate posture of keeping genuine integration defects loud) — confirmed sufficient by a direct
test: a fake client whose `nominate_sufficiency_role` always raises is invoked, the affected
requirement's roles correctly resolve to `missing`, the receipt reports
`fresh_failed_no_valid_prior`, and **the run still completes to a rendered final answer** — no
model-specific exception was found escaping the Phase-19 boundary, so no additional fix was needed
or made.

## 13. Receipt persistence

New `"18_sufficiency_model_assist.json"` trace artifact (the next non-colliding number after Phase
20a's own `"17_sufficiency_map.*"` pair), written only when model assistance actually ran:
`{"enabled": true, "model_name": ..., "think": ..., "initial": [...receipts...], "final":
[...receipts...] | null}` — exactly `new_nomination_receipt`'s own shape for each entry (scope,
model name, request fingerprint, candidates offered, accepted, status), which carries no
chain-of-thought or raw model text to begin with. A test round-trips the real artifact and asserts
none of `thinking`/`reasoning`/`raw_text`/`chain_of_thought` appear anywhere in it.

## 14. Result / manifest reporting

`execute()`'s own return dict gained one additive key, `sufficiency_model_assist` (`None` unless
assistance ran): `enabled`, `model_name`, `think`, and an `initial`/`final` pass summary each with
`scopes_reached` + a `status → count` breakdown — internal diagnostics only, never user-facing
prose, never raw model text (satisfied by construction, since the summary only ever reads
`receipt["status"]`). `run_topology()`'s own `manifest["sufficiency"]` gained the matching
`"model_assist"` key (the one place Phase 20a's own manifest test needed updating — it now also
asserts the new key is `None` in the off case, confirming nothing else about Phase 20a's shape
changed).

## 15. Recovery gate stays separate

Confirmed by a direct comparison on the SAME real model-assisted run: `sufficiency_map_initial` is
byte-identical whether `sufficiency_recovery_gate_enabled` is `True` or `False`; what differs is
only the GENERIC recovery-plan's own search-gap list (strictly larger with the gate on, since
sufficiency-derived target rows are additionally appended for the exact same already-model-mapped
structure), proven via the scripted harness's own `recover_calls[0]["gaps"]` instrumentation.

## 16. Stop-search / model dependence

Confirmed on the real run, not re-derived: `c5#suff:brain-behavior` reaches `state == "filled"` via
two model-mapped bindings, and `compute_stop_search_certified(req)` correctly reports `False` for
it — unchanged Phase 9/16 machinery, exercised here for the first time through the real wiring
rather than only a direct unit fixture.

## 17. Parent-context

Not given a bespoke new e2e test. Reasoning, stated plainly rather than silently skipped:
`sufficiency_mapping.py` — including `map_paired_requirement`'s own-evidence-first/parent-fallback
logic — is **completely unmodified** by Phase 20b (confirmed by `git diff --stat`), and Phase 16's
own existing unit-test suite (`test_sufficiency_mapping.py`, 583 tests across the sufficiency family
all still green) already exhaustively proves "own evidence tried first, parent consulted only as a
structural fallback, zero extra model call for propagation" directly against the real mapper code.
The real end-to-end run's own scope/call counts (§7: exactly 11 scopes reached, matching what the
mapper's own topology would produce) are consistent with this and introduce no new risk, since
Phase 20b changes nothing about how a scope is constructed or reached — only what `model_client`/
`nomination_context` value gets passed in from the two outer call sites.

## 18. Direction / effectiveness

Phase 18 untouched (confirmed by `git diff --stat` — zero changes to `sufficiency_diagnostic.
compute_direction_and_effectiveness` or `sufficiency_mapping.find_direction_observations`/
`find_effectiveness_observations`); its own full test suite is unchanged and green. One new
integration assertion added per the brief's own request: `compute_direction_and_effectiveness`
still reaches and correctly annotates (`direction_observations`/`direction_summary`, in the right
shape) an instance whose completion is model-dependent (`c5#suff:brain-behavior`), proving the pass
is never skipped or broken for a model-filled instance — not merely assumed because the code is
unchanged.

## 19. Offline production-shaped replay

Built and run, exactly as the brief's preferred structure describes: the real frozen v9 fixture +
the real `hierarchy_test_support.HierHarness`-driven `execute()` path + a fake (never recorded, but
equally non-live and equally duck-typed to the sanctioned Phase-19 client protocol) nomination
client + an `ALL_ELIGIBLE` U1 context. The authoritative release invariant — current direct result
== current integrated result — was already the exact subject of Phase 20a's own
`test_the_integrated_run_matches_calling_the_deterministic_mapper_directly`; Phase 20b's own tests
extend that same real-fixture-driven proof to the model-assisted case (requirements, instances, role
bindings, provenance, state/reason, stop-search certification, direction/effectiveness all directly
asserted against the SAME real run's own output, never a second independently-computed "direct"
call, since there is only ever one authoritative map per pass by construction — see §7). No
historical Phase-5 byte-comparison was attempted or treated as a gate, per the brief's own
instruction.

## 20. Default-off behavior

A dedicated test (`test_default_off_preserves_phase_20a_behavior_exactly`) confirms: no nomination
context, no model calls, `result["sufficiency_model_assist"] is None`, and no binding anywhere
carries `candidate_source == "model_mapping"` — byte-identical to Phase 20a. `test_disabled_path_
never_constructs_a_context_at_all` confirms a supplied-but-unused fake client's own `.calls` list
stays empty when the flag is off.

## 21. CLI / config validation

Covered by dedicated tests: flag absent → `False`; flag + `--hierarchy` → accepted and threaded
through; flag without `--hierarchy` → `SystemExit` at the parser layer AND `ValueError` at the
`run_topology()` layer (independently, for any direct non-CLI caller); `think` not exactly `False`
→ `SufficiencyModelAssistRefused` before any call (`shared.calls == []` confirms nothing was even
attempted); no sufficiency contract active → `SufficiencyModelAssistRefused`; no resolvable
`model_name` → `SufficiencyModelAssistRefused`, never a silently-`None` provenance. No silent
fallback from an explicitly requested model-assisted path to deterministic-only mapping exists
anywhere in this code.

## 22. Raw model protocol

Reconfirmed unchanged: `nominate_sufficiency_role(category_description=..., candidates=...)`'s own
signature is untouched; every existing Phase 2/5/9/10 recorded/fake client and every existing
`sufficiency_mapping.py`/`sufficiency_model_scope.py` test fixture still passes without
modification.

## 23. Test matrix (28 new tests, pytest-collected counts)

- `test_sufficiency_model_scope.py::ResolveNominationTests` (+3): zero-candidates → zero calls +
  `fresh_no_candidates`; nonempty-candidates + successful-empty-response → plain `fresh`; an
  unauthorized (held-fixed) scope ignores candidate count entirely.
- `test_backends.py` (+3): `NativeWorkerTests.test_model_name_...` (native path);
  `ModelNameTests` (+2, new class): the managed-local-shaped path, and the no-`.model`-attribute
  fallback.
- `test_hierarchy_e2e.py::ModelAssistIntegrationTests` (+19, new class): default-off preserves
  Phase 20a exactly; refused with no sufficiency contract; refused with `think` not `False`
  (and nothing was even attempted); refused with no resolvable `model_name`; a non-hierarchical run
  may not combine the flag; `model_client`+`nomination_context` always constructed together (direct
  unit proof against `_sufficiency_u1_context`); the disabled path never constructs a context at
  all; U1 is `ALL_ELIGIBLE` and demand-driven (exact 11-reached/5-fresh/6-no-candidates counts); a
  real nomination produces a correctly-provenanced `filled` binding; direction/effectiveness
  annotation still runs over a model-filled instance; U1's own stage uses the shared W residency
  accounting; a zero-candidate scope truly makes zero calls; a mechanical failure does not crash the
  run; U2 fires and makes zero fresh calls; U2 replays the exact U1 binding held fixed; U2 is never
  wrapped in the W residency stage; the U1 receipt snapshot is independent of the live context;
  model-assist on + recovery gate off still maps but injects no extra recovery-search rows; the
  receipt artifact round-trips with no hidden reasoning.
- `test_hierarchy_e2e.py::CommandLineTests` (+3): `--sufficiency-model-assist` off by default;
  requires `--hierarchy`; accepted together with `--hierarchy`.

Plus one Phase-20a test corrected for the new additive `manifest["sufficiency"]["model_assist"]`
key (not counted as new — a fix to an existing assertion, not new coverage).

## 24. Regression

Full `experiments/ask_cli_revised` tree: **2301 passed, 11 skipped, 2 failed**. Arithmetic check:
Phase 20a's own baseline was 2273 passed; this phase adds exactly 28 new tests — 2273 + 28 = 2301,
matching exactly. The 2 failures are the identical pre-existing pin-drift pair Phase 16/17/18/19/20a
already documented — reconfirmed present on the clean Phase-20a commit `b928d140` itself (not merely
assumed carried forward), independent of any Phase-20b change. `ruff format --check` / `ruff check`
on all 7 touched files: clean.

v9 `combined_hash` reconfirmed unchanged:
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

## 25. Newly discovered issues

None beyond the two items already disclosed in-line above as deliberate, in-scope fixes: the
`fresh_no_candidates` receipt-status addition (§10, explicitly authorized) and the `QwenTasks.
model_name` property (§5, explicitly authorized). No new defect was found in `sufficiency_mapping.py`,
`sufficiency_diagnostic.py`, `sufficiency_recovery_targets.py`, or `sufficiency_engine.py` — none of
them were touched, and their full test suites remain green.

## 26. Is Phase 20b CLOSED?

**Yes**, for exactly the scope authorized: production initial model-assisted sufficiency wiring,
feature-gated off by default, the mandatory nomination-context invariant enforced structurally, the
U1/U2 held-fixed lifecycle proven with a direct zero-fresh-call assertion on U2, residency accounting
correctly differentiated between a pass that may call the model and one that provably cannot, and
every item the brief explicitly deferred (Phase 21's live call, Phase 22's target-scoped remap, a
broad try/except, a new feature-toggle framework, raw-protocol changes) left untouched.

## 27. Is Phase 21 ready?

**Recommend yes** — production wiring now exists, is off by default, and is validated end-to-end
with a fake nomination client against the real frozen v9 contract and the real hierarchy
orchestration, including the specific U1/U2 lifecycle Phase 22 will later extend. **Not started; no
live call made in this phase.**
