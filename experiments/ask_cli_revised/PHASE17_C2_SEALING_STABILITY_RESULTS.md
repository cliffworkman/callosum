# Phase 17 — C2 re-sealing stability / locality: implementation (2026-10-01)

Implements the design accepted OTR: strict append-only C2 sealing. Once a proposition has been
sealed against the full obligation set, a later recovery round may never add, remove, or replace
its `responsive_obligation_ids` — recovery is evidence *addition*, never re-adjudication of
unchanged old evidence. A newly recovered proposition is still classified exactly once, against
the FULL obligation set (never narrowed to the triggering child, a RecoveryTarget's search owner,
or any descendant scope).

## Commits

- `stages.py` — `SealingPrefixDriftError`, `record_identity`, `verify_stable_prefix_and_new_pids`
  (new); `run_coverage_audit` gains `classify_pids` (optional, backward-compatible); `seal` gains
  `prior_sealed` (optional, backward-compatible) with the whole-ledger merge described below.
- `e2e.py` — the C1/C2 orchestration wiring (`coverage()` closure, the recovery branch, the final
  `seal()` call).
- `__main__.py` — `_new_unique_verified`'s identity tuple now delegates to `stages.record_identity`
  (one source of truth, per the accepted design's §D).
- `test_stages.py` — 18 new tests (`CoverageClassifyPidsTests`, `PrefixStabilityTests`,
  `RecordIdentityTests`, `AppendOnlySealTests`, `SameLedgerRerunDriftTests`); one existing test
  (`test_e2e_run.py::ModelCoverageTopologyTests::test_the_model_c_is_the_authority_and_the_
  manifest_names_it`) updated with documented rationale where the fix correctly overturns its
  pre-Phase-17 expectation (§2 below).
- `phase17_c2_sealing_stability_replay.py` (new) — the offline Phase-15 counterfactual replay
  against real recorded artifacts (§3).
- This results doc + `CONTRIBUTION-LINEAGE.md` entry.

Starting HEAD: `61f5d513f34a740eccbc4639a26ee7d0c9edd05a` ("Phase 16: parent-context multiplicity
and parent-instance eligibility") — verified exact match against the plan's own expected hash
before any work began. v9 `combined_hash` confirmed unchanged throughout:
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

## 1. The two-primitive design, as implemented

**`run_coverage_audit(..., classify_pids: set[str] | None = None)`** — `classify_pids=None` is
byte-identical to the original whole-ledger behavior (every pre-existing call site is untouched).
When given, the model-facing candidate proposition list (`props`) is filtered to exactly that
subset; `obligations`/`subquestions` stay the FULL set regardless, so a new proposition remains
fully classifiable against any obligation. Proposition ids are still minted from the full
`records` list (`_ledger` itself is untouched) — only which rows are shown to the model changes,
never how pids are numbered. An empty `classify_pids` (a round that added evidence that didn't
survive into `source_verified`, or a defensive no-op call) short-circuits to the same
`skipped_reason="empty_ledger"` shape the function already used for a genuinely empty ledger —
no model call, no new code path.

**`seal(..., prior_sealed: dict | None = None)`** — `prior_sealed=None` is byte-identical to the
original behavior. When given, every proposition already present in `prior_sealed` keeps its
`responsive_obligation_ids` **byte-for-byte**, guarded by `record_identity` (§4) at the merge
point so a positional pid can never silently land on a different physical record; only
propositions absent from `prior_sealed` (the new suffix `coverage` was actually asked to
classify) take their attachment from `coverage`'s own fresh result. `obligation_states` /
`coverage_assessed` / `coverage_outcome` / `coverage_authority` are then re-derived from that
SAME merged attachment map — see §2 for exactly how and why.

## 2. Whole-ledger coverage-summary merge semantics (the one implementation-time STOP condition)

Before writing the merge, every field `seal()` returns was audited for what it is supposed to
mean, per the accepted design's §B. The hazard named there is real: `coverage["obligations"]`
(the raw per-round classification result) is NOT the same thing as "the cumulative truth for
this item," and blindly trusting a new-only round's own output for that field would misreport
"new evidence added nothing to item X" as "item X lacks support" — a real regression, not a
hypothetical, found live via `test_e2e_run.py::ModelCoverageTopologyTests` (§5).

**Resolution found** (no new schema invented; a deterministic derivation from `prior_sealed` +
the new coverage result, exactly the escape hatch the accepted design offered):

- If `prior_sealed is None`: every field is taken from `coverage` exactly as before (zero
  behavior change for the initial-pass / no-recovery path).
- If `prior_sealed is not None` **and the new-only call succeeded** (`coverage["assessed"]`):
  `obligation_states` is **re-derived from the merged attachment map** — for each subquestion,
  `JUDGED_RESPONSIVE` iff *any* proposition (old, preserved, or new, freshly classified) names
  that obligation, ordered by global ledger position. This is the existing `_obligation_row`
  convention (state follows directly from whether `proposition_ids` is non-empty), applied to the
  union of old+new evidence instead of to one round's own output. `coverage_assessed=True`,
  `coverage_outcome=None`, `coverage_authority=coverage["authority"]` (the round that most
  recently, successfully established the now-current cumulative picture).
- If `prior_sealed is not None` **and the new-only call failed mechanically**
  (`not coverage["assessed"]`): `obligation_states` / `coverage_assessed` / `coverage_outcome` /
  `coverage_authority` are **all inherited unchanged from `prior_sealed`** — a failed attempt to
  add more evidence must never retroactively unassess what was already truthfully assessed (§H).

Because `states` (the one local variable feeding both the nested
`coverage.original_request.source_units` projection and `hierarchy_contract.rollup(contract,
states)`) is fixed at this single point, both downstream consumers inherit correctness for free —
no second special-case was needed at either site.

## 3. Phase-15 counterfactual replay — real recorded artifacts, not a live call

`phase17_c2_sealing_stability_replay.py` (run manually; gitignored `.local/` dependency, not
pytest-collected) reconstructs the real C1 sealed ledger purely/locally from the preserved
`q-aib-hierarchical-t5c-live-20260930` run's own `11_verified_ledger.json` (26 real
source-verified records) and `12_coverage_audit.initial.json` (phi4:14b's real C1 result over
them) — the exact artifact `phase15_c4_semantic_consumption_experiment.py` itself already treats
as "the original ledger." It then appends Phase 13's own real recovered proposition text ("a
cortical region in the right temporo-parietal junction (RTPJ)") as p27, classifies it alone
(`classify_pids={"p27"}`) against a c4-only answer, and seals with `prior_sealed=` the real C1
baseline.

**Result** (exact, from a live run of the script against the real artifacts):

```
p3_before:  ["c2"]   p3_after:  ["c2"]   preserved: true
p16_before: ["c5"]   p16_after: ["c5"]   preserved: true
p27_after:  ["c4"]   attached_to_c4_only: true
every_old_pid_byte_identical: true   (all 26, not just p3/p16)
```

**Scoping note, disclosed rather than overclaimed**: this proves the mechanism — append-only
sealing preserves a real recorded C1 result byte-for-byte while still correctly attaching new
evidence — using `12_coverage_audit.initial.json` as that real C1 input. It does not reproduce
`PHASE15_C4_SEMANTIC_CONSUMPTION_RESULTS.md`'s own narrated "p3 gained a c2 tag it didn't have /
p16 moved from c3 to c5-only" numbers bit-for-bit: that report's own comparison baseline was not
fully pinned down from available artifacts in the time budgeted for this phase (its script layers
a second, separate live re-seal on top of a similar starting point before narrating its own
before/after). `AppendOnlySealTests` in `test_stages.py` is the primary, CI-running proof of the
mechanism itself, using controlled fixtures; this script is the best-effort tie to the real
preserved corpus the plan's §I asked for.

## 4. Stable-record identity + where it is asserted

`stages.record_identity(record) -> (paper_id, evidence_anchor_chunk_id, proposition_text.
casefold())` — reused, not invented. This is the exact tuple `__main__._new_unique_verified`
already established and documented as "the smallest exact identity that distinguishes [two
records sharing a physical evidence anchor]" (confirmed live: two records CAN share a chunk; the
claim text is what tells them apart — `RecordIdentityTests` proves this directly). `__main__.py`'s
own dedup closure now delegates to this one copy instead of carrying a second, driftable tuple.

It is asserted at **two** points, both BEFORE any model call is possible:

1. `verify_stable_prefix_and_new_pids(prior_sealed, records)` — called by `e2e.py` immediately
   before constructing `classify_pids`, i.e. before `coverage("C2", ...)` is ever invoked. Proves
   every old pid in the current ledger still names the same physical record as it did in
   `prior_sealed`, and that the ledger did not shrink. Raises `SealingPrefixDriftError` closed,
   before any call, if either check fails — `PrefixStabilityTests` proves this structurally (the
   function never references a `Supervisor` at all, so there is nothing for it to call).
2. `seal()` itself re-checks the same identity at its own merge point, independently of whether
   the caller already checked — belt-and-suspenders, not redundant busywork: `seal()` is a public
   function other callers could in principle invoke directly with a stale `prior_sealed`.

## 5. Exact C1/C2 orchestration (`e2e.py`)

```
coverage_initial = coverage("C1")                       # unchanged: classify_pids=None
pre_recovery_records = list(sink.all_records)           # cheap snapshot, no seal() call yet
...
if planned_search:
    before = len(stages.source_verified(sink.all_records))
    _recover_round(...)                                  # may append new records
    if len(stages.source_verified(sink.all_records)) > before:
        responsiveness("R2")
        sealed_initial = stages.seal(contract, subquestions, pre_recovery_records,
                                      sink.evidence_packets, coverage_initial)
        new_pids = stages.verify_stable_prefix_and_new_pids(sealed_initial, sink.all_records)
        coverage_final = coverage("C2", classify_pids=new_pids)
    else:
        skip("C2", "no_new_source_verified_evidence")    # unchanged
...
sealed = stages.seal(contract, subquestions, sink.all_records, sink.evidence_packets,
                      coverage_final, prior_sealed=sealed_initial)   # None when no recovery ran
```

`sealed_initial` (the pure, local, zero-model-call C1 seal) is computed **lazily**, only inside
the branch that confirmed new evidence actually exists — every run that never reaches recovery,
or whose recovery adds nothing, pays zero added cost and takes the exact pre-Phase-17 code path
(`prior_sealed=None` at the final `seal()` call, matching `coverage_final is coverage_initial`).
`det_coverage` (the non-model coverage mechanism) needed no change at all: it reads each record's
own `obligation_ids`, and R already skips already-mapped records, so its attachment is
append-only-stable for free, upstream of this phase entirely (documented in-line in `e2e.py`).

## 6. Failure semantics

A mechanically failed new-only C2 call (`not coverage["assessed"]`) leaves the cumulative sealed
ledger **exactly** as `prior_sealed` was: every old attachment untouched, `obligation_states` /
`coverage_assessed` / `coverage_outcome` inherited unchanged (§2). The new propositions remain in
`verified_propositions` (inspectable) with `responsive_obligation_ids=[]` — the same shape an
honestly-judged "no responsive claim" already takes, distinguished only by the top-level
`coverage_assessed` flag, exactly mirroring the pre-existing convention rather than inventing a
new per-proposition status. `AppendOnlySealTests::test_a_mechanically_failed_new_only_call_
leaves_the_prior_cumulative_state_untouched` proves this directly.

## 7. Independent same-ledger drift regression (a new finding from this audit)

Beyond the Phase-13/15 c4 case, this audit's own planning pass independently diffed a second,
unrelated preserved run (`q-aib-hierarchical-t5c-live-20260930`'s own internal C1→C2 transition,
for a `c9` recovery gap) and found the SAME class of defect, both gain and **loss**: p1 (c1→c2),
p3 (c2→c3), p16 (c5→c3+c5 — note: a *different* pair of values than the Phase-15 c4 case; these
are two separate recorded instances, not the same numbers), p22/p23 (c11→**[]**, lost entirely),
p26 (**[]**→c9, gained from nothing). `SameLedgerRerunDriftTests` bakes this class of finding in
as a permanent, hardcoded-literal regression fixture (the Phase-16 lineage precedent: real
recorded disagreement, not a live `.local/` dependency) — proving both that the pre-Phase-17
whole-reseal path genuinely can drift on an UNCHANGED ledger (no new evidence required at all),
and that the real `e2e.py` gate (`coverage_final = coverage_initial` whenever nothing new was
added) already makes that specific shape of drift structurally impossible once this phase's
locality fix is in place.

## 8. Multi-round synthetic result

`AppendOnlySealTests::test_two_recovery_rounds_never_reclassify_a_round_one_sealed_proposition`
chains `seal(prior_sealed=...)` across two synthetic rounds (round 0: p1; round 1 adds p2,
classified once; round 2 adds p3, classified once) and confirms p1's attachment is untouched by
either later round, p2's attachment (set in round 1) is untouched by round 2, and p3 is freshly
classified in round 2 only. No multi-round production orchestration was implemented — this is
exactly the semantic/generalization proof the accepted design asked for, confirming the
`prior_sealed` chain (round N's input is round N-1's own output) generalizes with **no new
schema**: the provenance of "which pids are old" is the chained `prior_sealed` reference itself,
re-derivable each time from the existing `before`/`after` counts.

## 9. Tests / regression

- `test_stages.py`: 39/39 passed (21 pre-existing, unchanged + 18 new).
- `test_e2e_run.py` + `test_e2e_checks.py` + `test_flat_path_golden.py` + `test_hierarchy_e2e.py`
  + `test_hierarchy_child_overview.py` + `test_sufficiency_recovery_targets.py` +
  `test_sufficiency_diagnostic.py` + `test_sufficiency_freeze.py` + `test_sufficiency_leakage.py`:
  205/206 passed (the one failure, `MainOrderingTests::test_preflight_only_...`, confirmed
  pre-existing and unrelated by direct comparison against unmodified HEAD — §10).
- Full `experiments/ask_cli_revised/` tree: **2145 passed, 11 skipped, 2 failed** (both
  pre-existing — `MainOrderingTests::test_preflight_only_...` and
  `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_
  preserved_artifacts`, a stale local pin-vs-code-hash artifact unrelated to any file this phase
  touched — both reproduced identically against unmodified HEAD, confirmed by direct `git stash`
  comparison, not assumed). 2127→2145 passed is exactly +18, matching the new tests added; no
  prior test's pass/fail status changed except the one documented, deliberate update (§10).
- `phase17_c2_sealing_stability_replay.py`: run manually against the real `.local/` artifacts,
  result in §3.
- `ruff check` clean on every new/touched line; `ruff format` applied only to the two wholly-new
  files (`test_stages.py`'s new tests, the replay script) — pre-existing unformatted spots in
  `stages.py`/`__main__.py` outside this phase's own diff were left untouched (rule: minimal
  diff, no drive-by reformatting).
- v9 `combined_hash` confirmed unchanged: `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

## 10. One existing test deliberately updated, with rationale (not silently)

`test_e2e_run.py::ModelCoverageTopologyTests::test_the_model_c_is_the_authority_and_the_manifest_
names_it` asserted `result["coverage_final"]["obligations"]`'s `s3-o1` row named `p1` (old
evidence). Under Phase 17, `coverage_final` is now the C2 round's own new-pids-only result — p1
is OLD, byte-for-byte preserved from C1, correctly never re-asked of C2 — so the fixture's canned
answer (which always names "p1", unconditionally) is now outside C2's own narrower schema and
fails closed as `not_assessed` for that round, exactly as a real schema-constrained model would
never have produced that answer in the first place. Verified live (not assumed) that this
fixture's class of test passes cleanly on unmodified HEAD, confirming the change in behavior is
this phase's, not a second unrelated bug. The assertion now targets `sealed["obligation_states"]`
— the canonical, cumulative per-item truth — where it correctly shows `p1`/`judged_responsive`,
preserved exactly as C1 established it.

## 11. Any newly discovered issue

Two, both disclosed above rather than silently absorbed: (1) the independent same-ledger drift
instance in a second, unrelated preserved run (§7) — new evidence this audit surfaced, not
previously documented; (2) the exact Section-B hazard the accepted design anticipated did occur
live, in `ModelCoverageTopologyTests` (§10) — found by running the real test suite, not by
inspection, and resolved per the design's own escape hatch rather than by inventing new schema.

## 12. Is C2 sealing stability/locality CLOSED?

**Yes**, for the scope this phase was authorized to close: proposition-level `responsive_
obligation_ids` stability across a recovery round, and the whole-ledger coverage-summary fields
that are derived from it. The design, code, real-artifact replay, and regression all converge on
the same answer, and the one implementation-time STOP condition the accepted design anticipated
was resolved deterministically rather than by inventing new semantics.

**Not closed, and explicitly deferred** (per the accepted design's own instruction not to expand
scope): the separate `units_by_child`/`build_units` first-match-by-pool-order sensitivity —
`direction`/`effectiveness` can still drift when a genuinely NEW proposition shares a dedup unit
with an OLD one, because that mechanism operates on freshly-rebuilt derived units, not on
proposition-level sealing. This was traced, not fixed, in the prior (plan-mode) pass; nothing in
this implementation touches it.

## 13. Recommended next phase

**Direction/effectiveness determinism** — unless implementation evidence surfaced here reveals a
blocker that must precede it. None did: the mechanism (§12, `units_by_child`'s global-order
pooling + `map_direction`/`map_effectiveness`'s first-match convention) is independently
understood and scoped; nothing about implementing Phase 17 changed that assessment.
