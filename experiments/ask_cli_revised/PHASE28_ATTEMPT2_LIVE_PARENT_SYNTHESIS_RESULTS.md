# Phase 28, Attempt 2 — Live Parent Synthesis: Results (compact technical handback)

**Outcome: SUCCESS. The complete hierarchical pipeline ran end to end — W1 → C1 → U1 → P1 → W2 → C2 →
U2 → eleven S1 child syntheses → the deterministic parent claim ledger → exactly one S2 call — with zero
mechanical (NO-ANSWER) failures across all 15 Supervisor calls. This is the first time parent synthesis
has run live under T5C.**

This is **Attempt 2** of Phase 28. **Attempt 1** (`.local/e2e-runs/phase28-live-parent-synthesis-20261003T223145Z/`,
documented in `PHASE28_LIVE_PARENT_SYNTHESIS_RESULTS.md` / `_FORENSIC_REPORT.md`) consumed its own
separate authorization and **failed before any pipeline stage completed** — a harness/infrastructure
bug (the scratch runner's `endpoint_guard.isolated_only()` intercepting `sentence-transformers`' lazy
HuggingFace adapter-config probe). That outcome is not evidence for or against T5C, S1, recovery, U1/U2,
or parent synthesis, and it is not called a "preflight" — it is the authorized Attempt 1, preserved
exactly as it happened. This document covers Attempt 2 only.

## Starting state

| Field | Value |
|---|---|
| Branch | `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z` |
| Starting HEAD | `7203b1a1e6ae0caa76be484288bb24a58c298b32` (the Attempt-1 evidence commit) |
| Prior attempt | `phase28-live-parent-synthesis-20261003T223145Z`, outcome `FAILED_BEFORE_PIPELINE`, preserved untouched |
| New run id | `phase28-live-parent-synthesis-attempt2-20261004T014500Z` |
| New authorization | `phase28_live_parent_synthesis_forensic_run_attempt2_20261004`, gate-verified |
| Question hash | `6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030` (q_aib / `BENCHMARK_QUESTION`) |
| Profile | resolve key `T5C`, display name `T5*+C` |
| Frozen v9 combined hash | `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586` — verified before and after |
| Library copy | Sept-30 preserved copy, fingerprint `4f2e98a54c92790e791d841ef63e2fd60c4b411246f9c29590c19e56da892523` — **verified identical before and after this attempt too; `library_unchanged_after_run: true` in the run's own manifest** |

## The harness correction (proven, not assumed)

`HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` set at module import (exact form copied from
`offline_pytest.py:14-15`), `endpoint_guard.isolated_only()` kept around the live call (not dropped).
Pre-authorization, a standalone reproduction under the *stricter* `refuse_all()` guard — a bare
`ModelRuntimeRegistry().get_embedding_model(...).encode_texts([...])` call, no library, no JUNO —
passed cleanly. **The correction worked**: the run reached `05_candidate_papers.json` and every
subsequent stage with zero `EndpointRefused` errors anywhere in its 1657-second run.

## Effective configuration (identical to Attempt 1's design, unchanged per the no-tuning mandate)

```python
e2e.run_topology(
    "T5C", "aib",
    db_path=<Sept-30 copy>, library_frozen=<its fingerprint>,
    out_dir=<run/>, git_root=ROOT, scored=True, hierarchy=True,
    experiment_authorization=<new phase28_authorization.json>,
    hierarchy_loader=lambda q: hc.load_contract(q, pins=None),
    sufficiency_model_assist=True, sufficiency_recovery_gate=True, parent_synthesis=True,
)
```

## Timing

| Stage | Role | Model | Wall seconds |
|---|---|---|---|
| W1 | W | qwen3.5:9b | 313.1 |
| C1 | C | phi4:14b | 151.3 |
| U1 | — | qwen3.5:9b (model-assist) | 69.1 |
| P1 | P | gemma3:12b | 88.6 |
| W2 | W | qwen3.5:9b | 671.0 |
| C2 | C | phi4:14b | 154.5 |
| U2 | — | qwen3.5:9b (model-assist remap) | 68.7 |
| S1 × 11 children | S | qwen3.5:9b | 64.2 total (2.4–8.2 each) |
| S2 | S | qwen3.5:9b | 61.0 |
| **Total** | | | **1657.3** (manifest: 1650.9) |

No stage hit the 1200s wall-timeout; the longest (W2, the recovery retrieval round) ran at ~56% of budget.

## Call counts — from the independent `SupervisorCallRecorder`, not self-reported by the system under test

- **Total `stages.Supervisor.call` invocations: 15** — `coverage_audit` ×2 (C1, C2), `recovery_planning` ×1 (P1), `overview_synthesis` ×11 (S1, one per child), `parent_synthesis` ×1 (S2).
- **S2 calls: exactly 1.** The architectural invariant (`S2 attempts ≤ 1`) is non-vacuously satisfied this time — a real call was made, exactly once.
- Every one of the 15 calls: `response_outcome: "usable"`, `done_reason: "stop"`, `answer_is_none: false`. **Zero mechanical (NO-ANSWER) failures.** (The separately-reported `gate_no_answer: {calls: 110, no_answer: 0}` in the manifest covers the W-role's own internal packet-level gate decisions during retrieval growth — a different call path, `backends.NativeWorker`/`QwenTasks`, not wrapped by this recorder; see the forensic report's scope note.)
- The S2 call's raw prompt (9,959 chars) and schema were captured verbatim by the recorder and hash-match the production `parent_synthesis.realize()`'s own self-reported `prompt_sha256`/`schema_sha256` exactly (`66bc9e18f265...` / `65c376fc85d4...`) — an independent confirmation, not a trust-the-system-under-test assumption.

## U1 → U2 accounting

- **U1** (initial, pure model-assist nomination): 18 scopes reached, all status `fresh`.
- **U2** (final, targeted remap after recovery): 31 scopes reached — 16 `fresh`, 10 `held_fixed_no_valid_prior`, 5 `held_fixed_replay`.
- `recovery_targets_initial_count`: 20. `u2_fresh_request_key_count`: 16.

## Recovery accounting

- **P1** (gemma3:12b): recommended `DEEPEN` for all 11 children — a real, substantive model decision (not a default), with an explicit rationale ("All requested items currently have available recovery actions... I will choose the DEEPEN action for each item").
- **W2/C2**: 20 recovery-target searches executed, each reusing the same 25-paper candidate pool (no new papers nominated — `new_papers_nominated: []` throughout) but searching it with new, targeted queries. **14 of 20 targets added new verified evidence** (`recovery_added_evidence`, `new_verified` ranging 1–5); **6 found nothing new** (`recovery_no_new_evidence`, `new_verified: 0`). Zero targets failed mechanically.
- **Scoped-search terminality** (Phase 27b's own invariant): all 11 requirements with a structured search show `completed: true`; **zero** show `terminal: true` (none were genuinely-empty terminal searches) — consistent with the recovery round actually finding something for most targets. `resolved_empty_outcome_count: 0`.

## S1 — all 11 children, actual outcome

| Child | Overview state | Units sent | Proposals | Displayed |
|---|---|---|---|---|
| c1 | ok (partial) | 5 | 2 | 1 |
| c2 | ok (partial) | 10 | 3 | 2 |
| c3 | ok (partial) | 8 | 3 | 2 |
| c4 | ok (partial) | 2 | 2 | 1 |
| c5 | **no_grounded_sentences** | 9 | 2 | 0 |
| c6 | ok (partial) | 7 | 3 | 2 |
| c8 | ok (partial) | 4 | 3 | 2 |
| c9 | **no_grounded_sentences** | 1 | 1 | 0 |
| c10 | ok | 1 | 1 | 1 |
| c11 | ok | 1 | 1 | 1 |
| c12 | ok (partial) | 6 | 3 | 2 |

c5 and c9 are genuine, honest zero-statement outcomes (the model's proposed sentences for those two were withheld by screening; the passages are still listed in their reports) — not a mechanical failure. Full text for every child is in the forensic report.

## Parent claim ledger / gap / resolved-empty counts

- **21 ParentClaims** constructed deterministically from the final sufficiency map (4 claim kinds: `relational` ×6, `direction_or_effectiveness` ×1, `role_value` ×7, `category_list` ×7).
- **39 gaps** in the final gap report (role-level and corroboration-level granularity — finer than the 20 initial recovery targets; see the forensic report's note on why these counts aren't directly comparable).
- **0 resolved-empty outcomes.**

## S2 — grounded/fallback counts (the headline result)

- **7 of 21 claims grounded** (S2's phrasing passed every screen: claim-value, evidence-passage, heterogeneity, and batched NLI).
- **14 of 21 fell back** to the deterministic literal rendering: **11 withheld** (10 by NLI low-support, 1 by a lexical hedge-drop) and **3 invalid_item** (structural, e.g. a bare one-word "statement" for a `category_list` value).
- **Realization state: `mixed_model_and_fallback`.** Per-claim fallback worked exactly as designed — one rejected item never touched a sibling claim.

## Mechanical checks

All green except one: **`hierarchy_carriage: false`** — 13 of 626 checked calls (all `recovery_query`
worker-task calls, scoped to children c4/c5/c6/c11/c12 during W2) were missing the child's exact
"item line" the carriage invariant expects every call touching a child to carry verbatim. This is a
**genuine, newly-surfaced, bounded finding** — not a blocking issue (`technical_validity.valid: true`,
`issues: []`; this specific check is reported, not gating) and not something this phase patches, per
the no-code-change mandate. See the forensic report for detail and a recommendation.

## Known-tracer comparison (Phase 23A, consulted only after this run's artifacts were sealed)

- **c8 tracer RECURS, confirmed.** Phase 23A flagged `"undesirable behaviors (less generosity in the DG)"` as a category-boundary error (a behavior mislabeled as a trait/construct) in c8's accepted values. **The identical value is present in this run's c8 claim ledger too** (`category_list::f1f51b4ba55bad3c`). It was independently withheld by S2's screen for an unrelated reason (`hedge_dropped`) and so still appears in the final answer via the deterministic fallback, verbatim. **Earliest-error classification: `SEMANTIC_MAPPING_ERROR`, introduced at U1/U2 model-assisted nomination, faithfully propagated by the ledger, S2, and the fallback alike** — S2 neither introduced nor could have fixed it; it has no mandate to re-judge upstream semantic assignments.
- **c12's specific Phase 23A contamination does not recur** (no COVID-19-misinformation-paper value appears in this run's c12 claims) — but this is a **different run under a different profile and recovery path** (T5C/model-assisted vs. Phase 23's legacy-P/T0-variant), so absence here is not evidence the underlying retrieval-quality issue was fixed; it may simply reflect different search queries surfacing different candidates. c12's `target_manifestation` role, which Phase 23A found a *wrong* value accepted for, instead shows as an honest open gap (`missing`/`partial`) throughout this run's ledger — a more conservative outcome, not a resolution.

## Did Attempt 2 fulfill Phase 28's intended empirical purpose?

**Yes.** This is the first live, authorized observation of T5C's complete pipeline including parent
synthesis, with an independent (not self-reported) S2 witness confirming exactly one call, and a full
stage-by-stage trail from W1 through the rendered parent answer. See the forensic report for the
complete biography, the full sentence-level provenance table, and the earliest-error analysis.

## Recommended next step

The Attempt-1 infrastructure finding (harness network-guard scoping vs. `sentence-transformers`'
unconditional HF probe) is resolved and documented; no further action needed there. The one new,
bounded `hierarchy_carriage` finding (recovery_query prompts occasionally missing the item line) is
worth a future, separately-scoped investigation of `hierarchy_contract.carriage_violations`'s
`recovery_query` branch — not urgent (it didn't affect this run's mechanical validity), not done here
(no code changes this phase). The c8 category-boundary tracer recurrence is a real, confirmed upstream
semantic-mapping finding that predates this phase and remains open, exactly as Phase 23A left it.
