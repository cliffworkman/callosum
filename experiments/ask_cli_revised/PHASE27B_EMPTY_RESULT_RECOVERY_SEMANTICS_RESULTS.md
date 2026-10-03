# Phase 27b -- empty-result semantics in RecoveryTarget generation (audit and stop; offline only)

> **Status update (read first).** Section 0 below is the original audit and its STOP, preserved unchanged. Cliff and ChatGPT then reviewed that STOP and authorized Option A (section 13) under an explicit, widened implementation scope. The implementation, its evidence, and the final status are in **Part II** at the end of this document. Part II supersedes the "Phase 28 BLOCKED" status in section 0, and nothing else in section 0 is altered.

## 0. Outcome (original audit, preserved)

**No code change was made.** The audit did not support the narrow fix the brief expected. Applying the
expected rule (suppress every RecoveryTarget for an allowed-empty requirement whose bindings are all missing) would
remove the sufficiency-generated search obligations for `c4` from the initial recovery round. The frozen Phase-23
record shows those obligations driving a targeted search that verified new evidence. The brief's own STOP
conditions apply: the correct behavior needs terminal-after-search state, and the gap authority cannot observe that
state without a change to `e2e.py`, which the brief lists as out of scope.

- **Phase 27b: NOT CLOSED.** Architectural question handed back (section 13).
- **Phase 28 live parent synthesis: BLOCKED.**
- **Commit: none.** The brief makes the commit conditional on the audit supporting the narrow fix. It did not.
  This document and the lineage entry are uncommitted working-tree changes.

## 1. Starting state

| Item | Value |
|---|---|
| Starting HEAD (full) | `280eb3ca9ca4266fa7d6ef44b6c04378f34e336a` |
| Tree at start | clean (`git status --short` empty) |
| Phase 27a commit | present (`280eb3ca`) |
| Frozen v9 `combined_hash` | `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`, read from `sufficiency_contract.aib_hier_v9.frozen.json` `combined_hash`; matches the brief |
| Frozen Phase-23 artifacts | present under `.local/e2e-runs/phase23-live-recovery-targeted-u2-remap-validation-20261003T020939Z/` (gitignored, read only) |
| Implementation commit | none |
| Final HEAD | `280eb3ca9ca4266fa7d6ef44b6c04378f34e336a` (unchanged) |

## 2. Field-semantics audit: `empty_result_semantically_allowed`

Every occurrence, traced by grep over the worktree:

| Location | Role |
|---|---|
| `sufficiency_authoring.py:303` | `_build_c4` is the only author that sets it, to `True`. All other requirements default to `False`. |
| `sufficiency_engine.py:224` | `new_requirement(..., empty_result_semantically_allowed: bool = False)` |
| `sufficiency_engine.py:260` | persisted onto the requirement dict as `bool(...)` |
| `sufficiency_contract.aib_hier_v8/v9.frozen.json` | persisted; v9 sets `true` on exactly one requirement (section 3) |
| `test_sufficiency_authoring.py:140` | asserts the c4 value is `True` |
| `sufficiency_recovery_targets.py` | **no reference** |
| `sufficiency_engine.py` state, aggregation, `compute_stop_search_certified`, `compute_recovery_needed` | **no reference** |
| `sufficiency_mapping.py`, `sufficiency_diagnostic.py`, `sufficiency_model_scope.py` | **no reference** |
| `parent_synthesis_ledger.py:482` | a docstring note recording the gap; no read |
| `PHASE26_...`, `PHASE27_...`, `PHASE27A_...`, `CONTRIBUTION-LINEAGE.md` | record it as authored and unconsumed |

**Intended semantics (repository evidence, not the field name).** The authored source is the closure record for c4,
not the sufficiency code:

- `.local/decompose-runs/aib-dev/closure_v8/CLOSURE_APPROVALS.json` (CD-4): the qualification
  `c4#constraint:empty-result-allowed` = "a downstream answer that finds no supported area must be able to say so."
- `CLOSURE_DECISIONS.md` item 2: "E2E must carry those constraints into c4's evidence step and must **not treat an
  empty result as a failure**."
- `CLOSURE_REVIEW.md` item 3: "an empty result is a valid answer."

Reading the field against this evidence:

- **A.** The field means: *a zero-findings answer for this requirement is a legitimate terminal outcome.* It is not an
  instruction to skip searching. The request is "what does the evidence establish," so the search must still happen.
- **B.** The only v9 requirement that sets it is `c4#suff:specific-region`.
- **C.** It is conditional on the requirement being genuinely empty. It is not a generic ignore switch, and it is
  question-agnostic in form (no quantifier is named).
- **D.** It must affect *when a deficit becomes a gap*, not whether evidence is sought. The sufficiency layer currently
  has no notion of "searched, found nothing," so the field cannot be applied at the generator without either
  suppressing the search (wrong) or adding that notion (architectural). See section 6.

## 3. The real v9 requirement carrying the flag

| Field | Value |
|---|---|
| child | `c4` |
| requirement id | `c4#suff:specific-region` |
| kind | `atomic` |
| instance quantifier | `exists` |
| multi_instance | `False` |
| required roles | `named_brain_region_or_network` (`model_nomination_only`, category "a specific NAMED brain area"); `region_bears_on_bias_evidence` (`achieved_outcome_predicate`, category "evidence that the named region bears on the bias") |
| alternative groups | none |
| parent_context_roles | none |
| source wording | "Please return the specific brain areas in which the anomalous-is-bad bias manifests." |
| authored rationale | the closure qualifications above (CD-4). The contract's own `_authored` field is absent on this requirement. |

No other requirement in the v9 frozen contract (13 requirements across 11 children) sets the flag.

## 4. Exact bug path (reproduced)

The bug is real, but the brief's expected fix is wrong for this requirement. The reproduction, using the unchanged
code (read-only scratch probe, no socket):

| Fixture | Recovery targets emitted | Reasons |
|---|---|---|
| flag `False`, one instance, both bindings missing | 2 | `missing` (single_role, scope none) |
| flag `True`, one instance, both bindings missing | 2 | `missing` (identical to flag `False`) |
| flag `True`, zero instances | 2 | `missing` (via first-instance path) |

The flag has no effect on target generation.

**Parent propagation, reproduced.** The same flag=`True`, all-missing fixture passed to
`parent_synthesis_ledger.build_gap_report(targets, sufficiency_map_final=...)` yields **2 parent gaps**, each carrying
`requirement_id = c4#suff:specific-region`, reason `missing`, target roles, and category descriptions. So a zero-findings
c4 outcome is currently presented as two unresolved gaps. That is the user-visible symptom the brief describes.

## 5. The frozen Phase-23 evidence: why the expected fix is wrong here

Read-only probe over `phase23_result.json`. The probe calls `srt.compute_recovery_targets` on the recorded maps with
`parent_of={}`, and separately simulates a blanket rule (drop every target whose requirement is allowed-empty and has
only missing bindings). Nothing was executed and no model was called.

| Map | Recorded targets | Recomputed with unchanged code | Same ids? | Targets a blanket rule would drop |
|---|---|---|---|---|
| `sufficiency_map_initial` | 19 | 19 | yes | **2** (both c4) |
| `sufficiency_map_final` | 33 | 33 | yes | 0 |

The two dropped initial targets are:

- `c4::ed1c091df96fa134` (`missing`, single_role, `named_brain_region_or_network`)
- `c4::16fda026555aa730` (`missing`, single_role, `region_bears_on_bias_evidence`)

Both are the initial sufficiency obligations for c4. In the recorded run's `recovery_log`:

- the structured `named_brain_region_or_network` target: `recovery_added_evidence`, `new_verified: 2`, query
  "specific named brain areas where anomalous-is-bad bias manifests";
- the structured `region_bears_on_bias_evidence` target: `recovery_no_new_evidence`, `new_verified: 0`, query
  "specific brain areas where anomalous-is-bad bias manifests".

The run ends with c4 filled 8/8. Its final targets are 8 instance-scoped `provisional_corroboration` rows, none of them
empty-result gaps. This matches the Phase-27 finding: the frozen final state is unaffected by a blanket rule, because c4
never ended on the empty path.

**Limit of this evidence.** The recovery log also contains a generic (non-sufficiency) gap row for c4 with its own
search (`new_verified: 2`), so the artifact does not establish how many of the 8 fills depend on the structured targets.
The honest claim is narrower: a blanket rule removes two sufficiency-generated search obligations that the frozen run
recorded as running. It does not, by itself, prove c4 would have ended empty. I did not measure a counterfactual, and
I am not asserting one.

**Why this still rules out the blanket rule.** The field says an empty result is acceptable once it is *established*
(a search ran and found nothing). A rule that suppresses the initial obligation prevents the search from ever running,
so "nothing found" is never established. It converts "not yet searched" into "acceptable," which is the opposite of the
authored meaning.

## 6. Why no narrow fix is available inside the authorized surface

The terminal-after-search distinction needs a fact the final gap computation can see. Checked:

- `sufficiency_recovery_targets.compute_recovery_targets` already accepts `search_status_by_requirement`, and the engine
  defines `scoped_search_completed_no_additional_support` and `recovery_budget_exhausted` in `new_search_status`.
- **Nothing sets those flags.** Grep finds them only in `sufficiency_engine.py` and the tests. `e2e.py` never builds a
  per-requirement status map.
- `e2e.py:595` calls `compute_recovery_targets(sufficiency_map_initial, parent_of)` with **no** status, to drive the
  search round.
- `e2e.py:800` calls `compute_recovery_targets(sufficiency_map_final, parent_of)` with **no** status. This call is the
  gap authority that `build_gap_report` projects.
- The `e2e.py` comment at the round-level budget says persisting attempts across calls "is left unbuilt here."

So at the moment the gap is computed, the generator receives the same map shape for "never searched" and "searched,
found nothing." The map cannot distinguish them. A correct fix therefore needs:

1. a persisted per-requirement "scoped search completed, no support" fact, written by the search round;
2. that fact threaded into the final `compute_recovery_targets` call;
3. suppression limited to the zero-evidence deficit once that fact is set.

Items 1 and 2 require changes to `e2e.py`, which the brief lists as zero-change, and they add a new cross-call semantic
link. Per the brief, that is a STOP, not a widening of scope.

## 7. Requirement-state disposition

Unchanged in every option considered. `state` stays `missing` / `reason` stays `not_found`. No "empty_allowed" state, no
synthetic instance, no fake evidence. `compute_stop_search_certified` returns `True` for any non-`filled` requirement, so
it already reports "nothing further to certify" for an empty c4. It needs no change for this purpose. (Its behavior for
an empty requirement is correct; the problem is the recovery-target gate, not stop-search.)

## 8. Target reasons: what a correct fix would suppress and preserve

For the record, the rule the brief asked me to verify, with this audit's answer:

| Reason | Under a correct fix (after search completed, nothing found) | Evidence in code |
|---|---|---|
| `missing` (zero evidence, allowed-empty) | suppress | `_incomplete_instance_targets` / `_first_instance_targets` |
| `partial` (any filled role) | **preserve** | any filled binding = evidence; `_incomplete_instance_targets` |
| `relationship_unverified` | **preserve** | requires two filled own-evidence roles; `_relationship_unverified_roles` |
| `provisional_corroboration` | **preserve** | requires a complete, model-dependent instance = evidence |
| `open_list_breadth` | preserve when evidence exists | requires complete instances |
| `cardinality_deficit` | suppress only for zero evidence; preserve once any qualifying finding exists | `_cardinality_deficit_targets` |
| ambiguous / conflicting evidence | **preserve** | binding `state == "ambiguous"` is never "missing" |

None of this is implemented. The table records the rule a correct fix must honor.

## 9. Zero-instance and quantifier behavior

- Zero-instance allowed-empty requirement: currently emits a first-instance `missing` target (section 4). A correct fix
  must suppress it only after a completed search, and must keep the current first-instance target for
  `empty_result_semantically_allowed=False`.
- Quantifiers: the flag is question-agnostic. A correct fix would apply the same terminal-after-search rule to
  `exists`, `all_requested_categories`, `for_each_discovered_instance`, `at_least_n`, and `open_list`, with no
  quantifier-specific exception. Only `exists` is exercised by v9 data.

## 10. Stop-search disposition

`compute_stop_search_certified` (`sufficiency_engine.py:779`) and its only caller in `compute_recovery_needed`
(`:809`) were audited. The only other caller is `parent_synthesis_ledger.py:150`, which is a requirement-scoped
passthrough. Behavior for an allowed-empty `missing` requirement is already correct (`True`). **No change required.**
Modifying it would broaden this phase beyond the RecoveryTarget scope, which the brief forbids.

## 11. F / recovery effect and parent-gap propagation

- **F projection:** `project_fresh_request_keys` (`sufficiency_recovery_targets.py:657`) derives requests only from
  targets. A requirement that emits no target therefore authorizes no U2 request and creates no dependency origin. This
  follows from the existing target-driven design and was not separately measured.
- **Parent gap report:** `build_gap_report` projects every target it is given, unchanged (`parent_synthesis_ledger.py:474`).
  Suppressing a target at the source would therefore remove the gap with no parent code change, which is the brief's
  expected propagation. In the current code, the gap appears because the target exists (section 4).
- **Caveat for Phase 28:** removing the false gap is not the same as the answer *saying* that nothing was found. The
  contract wants the answer to be able to say so. If a suppressed outcome has no positive statement in the parent
  output, a reader sees silence for c4, not "searched; none established." The Principles gate treats silence as not a
  certificate. This must be resolved in the terminal-state design, not by the absence of a gap.

## 12. Real frozen replay counts

- Phase-23 `recovery_targets_initial`: 19 recorded, 19 recomputed, ids identical (`parent_of={}`).
- Phase-23 `recovery_targets_final`: 33 recorded, 33 recomputed, ids identical.
- Frozen Phase-23 parent claims / gaps: `test_parent_synthesis_replay.py` asserts `len(claims) == 24` (line 127) and
  `len(gaps) == 33` (line 128), and `test_the_gap_report_is_the_full_33_entries` (line 168). That file passed in the
  section-14 run against the frozen state. No code changed, so the 24 / 33 baseline is unchanged.

## 13. Architectural question (hand-back)

**Question:** how should an allowed-empty requirement reach a "searched; nothing established" terminal state, when the
gap authority is computed without search history?

Options:

- **A (recommended).** Persist a per-requirement "scoped search completed, no supporting evidence" fact from the
  recovery round. Thread it into the final `compute_recovery_targets` call. Suppress only the zero-evidence `missing`
  deficit when that fact is set, and only for `empty_result_semantically_allowed=True`. Preserve partial, relational,
  ambiguous, corroboration, breadth, and cardinality obligations. Pair the suppression with a positive
  "searched; none established" statement in the parent output, so the outcome is not silence. Requires an explicit
  authorization to change `e2e.py` (the search round and the final call) and, for the parent statement, the parent
  rendering layer.
- **B (not recommended).** Adopt the brief's expected rule as written. Suppresses the initial search obligation. The
  search never runs, so the field's own condition ("established") is never met. Rejected.
- **C.** Keep the gap, but render it as "searched; nothing established" rather than "unresolved." Changes parent rendering
  without fixing the gap authority. Partial.
- **D.** Do nothing. Phase 28 can run, but a zero-findings c4 outcome will appear as two unresolved gaps. Known false
  output.

## 14. Focused tests and regression

**Focused offline suites (executed, socket-guarded):** `test_sufficiency_recovery_targets.py`,
`test_parent_synthesis.py`, `test_parent_synthesis_wiring.py`, `test_parent_synthesis_per_item.py`,
`test_parent_synthesis_replay.py`, `test_parent_synthesis_ledger.py`, `test_parent_synthesis_render.py`,
`test_parent_synthesis_audit.py`, `test_sufficiency_freeze.py`, `test_sufficiency_authoring.py`.

**Result: 242 passed, 0 failed, 0 skipped** (57.6 s). The artifact-backed replay tests ran against the frozen Phase-23
state; none were skipped.

**Full regression:** not run. The brief's full-regression requirement applies to a code change. No code changed, so the
focused run is the relevant check. The Phase-27a record lists known baseline failures in the full suite (pin drift, a
loopback-Ollama guard). They are environment-dependent and were not re-run, since running the full suite would touch the
shared Ollama and JUNO services unless carefully guarded.

No new tests were added. A characterization test that encodes the current behavior (flag has no effect) would lock in
the bug, so it was not written. Tests for the correct rule belong with the option the user selects.

## 15. Frozen v9 hash

`combined_hash` in `sufficiency_contract.aib_hier_v9.frozen.json`: `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.
Unchanged. No frozen contract, pin, or `hierarchy_contract.py` file was modified.

## 16. Files touched

- Added: this document.
- Modified: `CONTRIBUTION-LINEAGE.md` (Phase 27b entry appended; prior entries unchanged).
- Not modified: every code file, every frozen contract, every pin, `e2e.py`, `parent_synthesis*.py`, `topology.py`,
  Overview modules, `qwen.py`, retrieval and prompts.
- Scratch probes live in the session scratchpad, outside the repository.

## 17. Newly discovered issues

1. **The search-status machinery is defined and never used.** `new_search_status` and the two flags that would encode
   "search completed, nothing found" are read by the engine, but no production caller sets them. The recovery budget is
   per-call, as the `e2e.py` comment says. This is the same gap as section 6, seen from the engine side.
2. **The brief's expected rule would remove a live search obligation.** Recorded in section 5. The brief's own wording
   ("absence of findings does NOT itself create a recovery obligation") is correct only after a search has completed.
   This is a refinement of the brief, not a disagreement with its intent.
3. **Silence risk in the parent output.** A correct gap removal still needs a positive "searched; none established"
   statement, or the outcome reads as silence (section 11).

## 18. Phase status

- **Phase 27b:** NOT CLOSED. Awaiting the architectural decision in section 13.
- **Phase 28 live parent synthesis:** BLOCKED. Readiness question answered in section 19.

## 19. Phase-28 readiness gate

*Could a Phase-28 live run now legitimately return zero findings for the real allowed-empty requirement without the parent
answer falsely listing that outcome as an unresolved gap?*

**NO.** Evidence: with the unchanged code, a zero-findings c4 (flag `True`, all bindings missing) yields two
`missing` RecoveryTargets, and `build_gap_report` projects them as two parent gaps (section 4). The only available
suppression at the generator removes the initial search obligation, which the frozen run shows is part of how c4 gets
evidence (section 5), so it cannot be applied without first adding terminal-after-search state (section 6). That state
requires an `e2e.py` change, which is out of scope here.


---

# Part II -- authorized implementation (Option A)

## 20. Authorization and starting state

- **Authorization.** Cliff and ChatGPT accepted the section-0 STOP as correct and authorized Option A, with an explicit,
  widened surface: `e2e.py` (persistence and threading of search status), `sufficiency_recovery_targets.py` (only the
  narrow generic correction below), a separate resolved-empty projector in `parent_synthesis_ledger.py`, deterministic
  display in `parent_synthesis_render.py`, orthogonal record threading and audit, and tests. No live model, no network,
  no frozen-contract, pin, scientific-mapping, retrieval, prompt, or Overview change.
- **Starting HEAD.** `280eb3ca9ca4266fa7d6ef44b6c04378f34e336a`. The starting tree held exactly the two audit files
  (`PHASE27B_..._RESULTS.md` new, `CONTRIBUTION-LINEAGE.md` modified), verified before any edit.
- **Frozen v9 `combined_hash`.** `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`, read from the frozen
  file before and after the implementation (unchanged).

## 21. Search-status architecture (audited, then used)

The audit before editing confirmed the existing machinery, as described in section 6:

- `compute_recovery_targets(..., search_status_by_requirement=...)` already accepted a status map.
- `se.new_search_status` already defined `scoped_search_completed_no_additional_support` and
  `recovery_budget_exhausted`. `se.compute_recovery_needed` reads both as "budget spent" for every requirement state.
- No production caller set either flag. The round's log is produced by `__main__._recover`, which does not record a
  budget. Nothing in the implementation renames or reinterprets those fields.

**Persistence design.** The search status is built in three steps, each inspectable:

1. `srt.structured_search_outcomes(initial_inventory, recovery_log)`, after W2. For each initial structured target, it
   reads only log rows whose `gap._recovery_target_id` names that target. Output:
   `{requirement_id: {"completed": bool, "target_states": {target_id: {"state", "reason_code"}}}}`.
2. `srt.terminal_search_status(final_map, round_outcomes)`, after U2 and before the final target computation:
   `{requirement_id: {"completed", "terminal", "target_states"}}`. `terminal` is true only when the search completed AND
   the final map is zero-evidence terminal for the requirement.
3. `srt.engine_search_status(...)` converts to the engine's own `se.new_search_status` shape. Only `terminal` drives the
   scoped flag. The same converted map is passed to the final `compute_recovery_targets` call.

Written to `13c_scoped_search.json` (`{"round": ..., "final": ...}`), returned as `scoped_search_round` and
`scoped_search_final`, and recorded in the parent construction record as `scoped_search_status`. Counts only go to the
manifest (`scoped_search`, and `resolved_empty_outcome_count` in `parent_synthesis`).

**Canonicalization.** `target_states` contain only a state and a deterministic reason code, keyed by target id. Wall-clock
time, `new_verified` counts, and recovery query text are excluded from every semantic structure. Hashes use sorted-key
JSON, so dict insertion order cannot change them.

## 22. "Scoped search completed" -- the exact rule

Per initial structured target (the target inventory the round searched):

| Observed | State | Why |
|---|---|---|
| exactly one log row names the target, reason `recovery_added_evidence` or `recovery_no_new_evidence` | `completed` | the search ran to its end |
| exactly one row, reason `plan_no_search` | `not_completed` | the planner chose no search |
| exactly one row, reason `recovery_query_no_answer` | `not_completed` | mechanical NO ANSWER; no search state |
| no row names the target | `not_attempted` | unresolved subquestion, no planned action, round never ran, or an exception dropped the round |
| more than one row names it | `not_completed` (`ambiguous_log_rows`) | never guess |

Per requirement: `completed` only when it owns at least one initial target AND every such target is `completed`
(conservative aggregation). A generic child gap, which carries no `_recovery_target_id`, is ignored, so it cannot prove
structured completion.

**Failure and budget.** A failed search, a skipped target, a budget-blocked target, and an exception that drops the round
all leave the target `not_attempted` or `not_completed`, so none becomes terminal. `recovery_budget_exhausted` keeps its
existing meaning (stop searching this requirement) and is never mapped to completion. Section 33 records a latent
over-reach in that existing meaning.

## 23. Final target-suppression rule

A requirement's targets are suppressed in the FINAL inventory only when the requirement is zero-evidence terminal:
`empty_result_semantically_allowed` is true, every binding in every instance is `missing`, the requirement state is
`missing`, AND its scoped search completed (`terminal`). For such a requirement, every remaining target is a
zero-evidence deficit, so suppressing the requirement is exactly suppressing those deficits.

- Partial, relationship-unverified, ambiguous/conflicting, corroboration, open-list breadth with findings, and cardinality
  with findings are not zero-evidence. They are never suppressed. This is enforced twice: `terminal` requires a genuinely
  empty map, and `_gate_status` strips a stray flag from any requirement that is not zero-evidence terminal before the
  engine reads it. The engine would otherwise read that flag as budget-spent for every state.
- The INITIAL inventory is computed with no status, so the search obligation is never suppressed before the search.

## 24. Requirement-state disposition

No change. A terminal allowed-empty requirement keeps `state == "missing"` and `reason == "not_found"` (or its existing
equivalent). No new state, no fake instance, no fake binding, no pseudo-filled marker. The status channel alone carries
terminality. `se.compute_stop_search_certified` is unchanged and still returns true for any non-filled requirement.

## 25. `ResolvedEmptyOutcome` schema, wording, and S2 isolation

**Schema** (a list field `resolved_empty_outcomes` in the construction record, sorted by `(child_id, requirement_id)`):

    {"child_id": "c4", "requirement_id": "c4#suff:specific-region",
     "category_descriptions": ["a specific NAMED brain area", "evidence that the named region bears on the bias"],
     "outcome": "searched_no_support_established"}

Derived by `psl.build_resolved_empty_outcomes(final_map, status)`, which re-checks the map (`srt.is_zero_evidence_terminal`)
and requires `completed` AND `terminal` in the status. It never reads model prose, never reads target absence alone, and
never creates a ParentClaim or an UnresolvedGap. It appears in neither `claim_ledger` nor `gap_report`.

**Deterministic wording.** Rendered as a section only when at least one outcome exists, titled
`## Searched, no supported result established`, placed before `## Unresolved parts`:

    - The scoped search completed without establishing a supported result for a specific NAMED brain area; evidence that the named region bears on the bias.

Asserted by test not to contain "no such", "does not exist", "proves", "evidence of absence", or "literature shows there is no".

**Proof that S2 cannot alter it.**

- `parent_synthesis.realize` and `parent_synthesis.build_prompt` take no outcome or scoped-search argument. A test asserts
  this against the real signatures.
- The outcome is written by `render_answer` through its own keyword argument. `realize` never sees it.
- In the zero-findings execute run, the claim ledger is empty, so S2 is never called. The structural proof is therefore
  what covers S2. A claim-bearing S2 prompt capture with a terminal outcome present is not included; section 33 lists it
  as a residual.

## 26. Parent answer and record (what changed, what did not)

- `construction_record` always carries `resolved_empty_outcomes` (default `[]`) and `scoped_search_status` (default `{}`).
  `declined_record` carries the same empty values. `claim_ledger` and `gap_report` are byte-identical with and without
  outcomes (test). `parent_synthesis_hash` changes for every record, because the record has two more keys. That is the
  expected effect of the brief's item 19. The `ParentClaim` values and the `sufficiency_map_final_hash` are unchanged
  (covered by the claim-ledger and map-hash tests).
- `render_answer` adds its section only when outcomes exist, so an answer with no outcomes is byte-identical to before
  (test).
- Audit: two new checks. `resolved_empty_outcomes_match_rederivation` re-derives the outcomes from the final map and the
  recorded status. `scoped_search_terminal_flags_justified_by_map` confirms every `terminal` flag is consistent with the
  final map (a requirement absent from the map can never be terminal). A malformed record fails cleanly, without raising
  (test).

## 27. Zero-findings offline E2E (the main proof)

`test_empty_result_execute.py` runs the REAL `e2e.execute()` over the REAL v9 frozen contract, through `HierHarness`.
The real `__main__._recover` runs its own control flow (plan action, query, reason codes, skips). Only the three search
primitives are scripted to find nothing: `retrieval.within_paper_retrieve`, `discovery.nominate_papers`, and
`_process_hits`. No model call, no network. The chain it observes:

1. Initial inventory: 2 `missing` targets for `c4#suff:specific-region`, both single-role, scope none.
2. W2 runs, and each c4 target's log row is `recovery_no_new_evidence` (the scripted search verified nothing).
3. Round outcome: c4 `completed`, both targets `completed`.
4. Final status: c4 `terminal` (genuinely empty in the final map, allowed, completed).
5. Final inventory: 0 c4 targets. Gap report: 0 c4 gaps.
6. `resolved_empty_outcomes`: one c4 outcome with the categories above.
7. Parent answer: the section and the wording above are present. The parent audit passes (`ok`).
8. `13c_scoped_search.json` contains the c4 status, and it matches the record's `scoped_search_status`.

## 28. Counterfactual and failure cases

| Case | Round | Final target(s) | Gap report | Resolved outcome | Test |
|---|---|---|---|---|---|
| zero findings, flag True (main) | completed | 0 c4 | 0 c4 | 1 | `test_a_completed_zero_support_search_closes_only_the_zero_evidence_deficit` |
| zero findings, flag **False** (same search, in-memory flag change) | completed | 2 c4 | 2 c4 | 0 | `test_the_counterfactual_flag_false_runs_the_same_search_and_keeps_the_unresolved_gap` |
| flag True, c4 subquestion refuses its query (NO ANSWER) | not_completed (`recovery_query_no_answer`) | 2 c4 | 2 c4 | 0 | `test_a_refused_query_is_never_an_empty_result` |
| initial inventory, flag True vs False | identical | identical | n/a | n/a | `test_the_initial_search_obligation_is_present_and_identical...` |
| partial evidence (one role filled), flag True | n/a | kept | kept | 0 | sufficiency-layer test |
| relationship-unverified, flag True | n/a | kept (`relationship_unverified`) | kept | 0 | sufficiency-layer test |
| ambiguous/conflicting, flag True | n/a | kept | kept | 0 | sufficiency-layer test |
| zero instances, flag True | first-instance target exists before the search | suppressed only after a completed search | n/a | 1 after completion | sufficiency-layer matrix |
| zero instances, flag False | n/a | kept | n/a | 0 | sufficiency-layer matrix |

The flag-False counterfactual runs the same initial search, and the search still completes. The difference appears only at
the gap authority, which is the point of Option A: search terminality and permission to accept emptiness are separate axes.

**Coverage boundary.** The execute-level tests drive the real recovery control flow with the real reason-code vocabulary,
but only for the c4 shape in the real v9 contract. Partial, relationship-unverified, ambiguous, and zero-instance cases are
proven at the sufficiency layer with the real engine constructors and `recompute_requirement`. They are not run end-to-end
through `execute()`, because no offline fixture produces a deterministic partial fill for a model-nominated role without a
model.

## 29. Quantifier, F/U2, and stop-search dispositions

- **Quantifiers.** Zero-evidence shapes for `exists`, `exists` with zero instances, `at_least_n`, `open_list` with zero
  instances, `all_requested_categories` with zero instances, and `for_each_discovered_instance` with zero instances all
  behave identically under the rule (matrix test). Partial evidence is never suppressed on `exists` or `at_least_n`.
  No quantifier-specific exception exists.
- **F / U2.** `project_fresh_request_keys` derives requests from targets. The FINAL inventory no longer contains the
  suppressed c4 targets, so the final projection holds no request for them. However, the U2 remap block in `e2e.py` is
  driven by the INITIAL inventory (`recovery_targets_initial`, unchanged by this phase). In a model-assist run, c4's fresh
  model-nomination request is therefore still authorized exactly as before. This phase did not change U2. Section 33
  records the residual.
- **Stop-search.** `compute_stop_search_certified` is unchanged. It already returns true for any non-filled requirement.
  The only path that changed is the new flag gating in `compute_recovery_targets`, which affects only zero-evidence
  terminal requirements.

## 30. Frozen Phase-23 replay (read-only, no execute, no model)

`test_parent_empty_outcome.py::FrozenPhase23ReplayTests` (artifact-backed):

| Count | Before (Phase 27a) | After (Phase 27b) |
|---|---|---|
| initial RecoveryTargets (recomputed, no status) | 19 (c4 ids `c4::16fda026555aa730`, `c4::ed1c091df96fa134` present) | **19** (same ids) |
| final RecoveryTargets (recomputed with the derived status) | 33 | **33** (equal to the recorded inventory after JSON normalization) |
| parent ParentClaims | 24 | **24** |
| parent gaps | 33 | **33** |
| resolved-empty outcomes | (none existed) | **0** |

The round reads c4 as `completed` (one named-role target `recovery_added_evidence`, one bears-evidence target
`recovery_no_new_evidence`). The final map is not empty for c4 (8 of 8 filled), so `terminal` is false, and the final
inventory is unchanged. Section 0's claim that the frozen final state is unaffected now has an explicit mechanism behind it.

## 31. Focused tests

| File | Tests | Result |
|---|---|---|
| `test_sufficiency_empty_result_terminal.py` (new, pure) | 33 | pass |
| `test_empty_result_execute.py` (new, real `execute()`) | 7 | pass |
| `test_parent_empty_outcome.py` (new: projector, render, record, audit, frozen replay) | 23 | pass |
| Existing Phase-26/27/27a ledger, render, audit, wiring, per-item, replay, recovery-targets, freeze, authoring | 242 | pass (run after the wiring, before the new tests) |

Focused total for the new and touched areas: 63 new tests, all passing; the 242 existing tests passed after the wiring.

## 32. Full regression

Full run of `experiments/ask_cli_revised` under the socket-refusing launcher, serial, excluding `test_live_command.py`: **2564 passed, 11 skipped, 3 failed** (447 s). The three failures are the documented baseline, not new: `RunTopologyGuardTests` (loopback-Ollama `ConnectError`, environment-dependent) and `RealPinsTests` / `MainOrderingTests` (pin drift: `hierarchy_contract.py` changed since pins were generated). This change did not touch `hierarchy_contract.py` or any pin. **Count caveat:** Phase 27a recorded 2497 passed; 2497 + 63 new = 2560, so 4 tests are unaccounted for. I did not re-establish the Phase-27a baseline on this machine, so the 4 are not explained here.

## 33. Newly discovered issues

1. **Latent over-reach of `recovery_budget_exhausted`.** `se.compute_recovery_needed` treats it as budget-spent for every
   requirement state, so setting it on a requirement suppresses partial, relational, and ambiguous targets as well. No
   production code sets it, so this is latent. This phase preserves the existing meaning, as the brief requires, and only
   the scoped flag is gated (section 23). A future caller that sets the budget flag would silence real obligations. That
   should be fixed in the engine in its own phase.
2. **Silent log gaps in `_recover`.** A gap whose subquestion does not resolve, or whose plan has no action, writes no log
   row. The status derivation correctly records such a target as `not_attempted`, but the log itself does not say why. The
   log could record these explicitly. This phase did not change `_recover`.
3. **U2 is driven by the initial inventory.** In a model-assist run, c4's fresh nomination request is authorized from the
   initial target even when a later completed empty search closes the final gap (section 29). This is the existing,
   intended Phase-22 design. Whether a completed empty search should also withdraw that request is an open design question.
4. **Every manifest and every parent record changed shape.** The manifest gains `scoped_search`, and the parent record
   gains two keys, so `parent_synthesis_hash` changes for every run. The semantic counts are unchanged. Anything that pins the
   old hash will see the change; none is known in this repository.
5. **Zero-claim S2 proof is structural.** The zero-findings run has no claims, so the S2 non-influence proof rests on the
   structural signature check and on the absence of a call, not on a claim-bearing prompt capture. A claim-bearing capture
   would strengthen it.

## 34. Phase-28 forensic trail (answer biography)

For one completed-empty run, the trail reads:

- W1, R1, C1, U1: c4 has 2 missing RecoveryTargets (`13_gap_recovery.json`, `17_sufficiency_map.initial.json`).
- P1: the plan selects a search action for c4's gap rows (legacy in the test harness; model-planned in production).
- W2: each c4 target's structured search runs (`13_gap_recovery.json` row, `_recovery_target_id`, `reason_code`).
- R2, C2, U2: no new evidence changes c4, so the final map keeps c4 empty.
- `13c_scoped_search.json`: c4 `completed`, `terminal`.
- Final inventory: no c4 target. Gap report: no c4 gap.
- `15a`: `resolved_empty_outcomes` holds the c4 outcome. `15_parent_answer.md` has the searched-no-support section.

No model call is needed for this trail. A live Phase-28 run produces the same trail, plus whatever S2 emits for the claims
that exist.

## 35. Hand-back

**Phase 27b: implemented and tested; CLOSED** against the 14 success criteria, all met by the tests above, except criterion 14 (no new regressions), which holds on the documented baseline with the count caveat in section 32. **Phase 28: READY** for question (a) and question (b) above, with two qualifications. The live run itself has not been performed, and the U2 residual in section 33 still applies in model-assist runs. Not pushed; one commit, local branch only.
