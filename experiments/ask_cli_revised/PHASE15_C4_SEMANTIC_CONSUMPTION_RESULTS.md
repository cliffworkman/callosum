# Phase 15 — one live, target-scoped semantic-consumption experiment (2026-10-01)

Tests whether newly-recovered evidence (Phase 13's c4 recovery) can reach and be considered by
exactly the one model-assisted role it was recovered for, while every other model-assisted role
across the whole hierarchy is held fixed at its established Phase-5 value. Builds on Phase 14's
production-call-graph audit and target-scoped-remap design; implements Cliff's own required
refinement over that design (a CONTROL map vs an EXPERIMENTAL map, both over the exact same
post-recovery ledger, rather than deterministic-only vs with-model).

## Commits

- `d0efd072` — offline preflight harness (`phase15_c4_semantic_consumption_experiment.py`),
  stopped before the live call per the fired Section-C stop condition.
- (this results doc + a follow-up fix to the harness's own isolation-check exclusion set,
  found while writing up the live result — see §G)

Starting HEAD (pre-Phase-15): `dc5f968b17a7bda35038e49eeb63697053a90361`.
v9 `combined_hash` confirmed unchanged throughout:
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

## A. Diagnostic harness

`experiments/ask_cli_revised/phase15_c4_semantic_consumption_experiment.py`. Replicates
`sufficiency_diagnostic.compute_diagnostic_sufficiency_map`'s own per-child topological loop
verbatim (imports and calls `sm.map_any_requirement` / `sd._stamp_model_dependency_origins` /
`se.new_contract` unmodified) because that function's single, shared `model_client` parameter
cannot express "one child's one role live, every other child held fixed" — production code is
unmodified, this is a diagnostic-only composition of its existing primitives, same posture as
`sufficiency_phase5_replay.py` and `phase13_c4_recovery_experiment.py`.

Two client classes implement Section A's hybrid design:
- `HeldFixedClient` (per child): filters offered candidates down to exactly the proposition ids
  that child's role saw **before** recovery, then delegates to Phase 5's recorded+adjudicated
  client (`_RecordedV9NominationClient` + `_Phase5AdjudicationValidator`, reused unmodified).
  Verified this always finds a historical match (zero `RecordedNominationReplayError`s) for every
  non-target child.
- `LiveTargetClient` (TARGET_CHILD only): forwards the **full** current pool to a real `QwenTasks`
  instance, unfiltered. No prior-answer field exists on `nominate_sufficiency_role` to inject
  steering into — confirmed structurally true, not newly designed (Section G).

## B/C. Control-map preflight — a real, confirmed stop condition, and why it was overridden

Offline reconstruction of the exact Phase-13 post-recovery sealed ledger (from the already-
recorded W2/C2 raw outputs — zero live calls, zero guessing; verified byte-for-byte against
`phase13_result.json`'s own saved `mapped_after_c4`/`mapped_after_c6`) found that the mandatory
C2 re-sealing call (needed to seal the new evidence into one ledger) reassigned
`responsive_obligation_ids` for **unrelated** pre-existing propositions differently than the
original run did (confirmed by diffing the two real recorded raw coverage-audit outputs):
p3 gained a `c2` tag it didn't have; p16 moved from `c3` to `c5`-only. This genuinely changed
c2's own candidate pool for its `behavior_or_behavioral_measure` role (model-nomination-only).

"Held every prior model nomination fixed" was operationalized as: filter to the pre-recovery
pool per child before delegating to history (see §A). Verified this resolves **both** misses —
c4's own target role (expected) and c2's role (the unrelated drift) — to their exact historical
answers, with zero other child's requirement `state`/role bindings differing from the Phase-5
with-model baseline. The residual difference — c5/c6/c12's `direction`/`effectiveness` fields (a
separate, deterministic, `model_client`-independent pass that scans the whole, now-broadened
per-child pool and returns the first direction/outcome word it finds) — is **confirmed, real,
unrelated drift**, exactly the condition the brief's Section C names as a stop condition.

All 50 offline gates in `build_state()` passed, including an explicit assertion that this drift
is confined to `direction`/`effectiveness` only (never `state` or any role binding) for exactly
`{c5, c6, c12}`. This drift is structurally **identical** between the CONTROL and EXPERIMENTAL
maps (both built from the same `sealed`, and `compute_direction_and_effectiveness` never reads
`model_client`), so it cancels out of the actual CONTROL-vs-EXPERIMENTAL comparison — it would
only ever surface as a false "unrelated isolation failure" against the wrong baseline (Phase-5's
pre-recovery state, which Section L explicitly says not to use as the primary comparison).

**Per the brief's own literal instruction, the harness stopped here** (committed at `d0efd072`,
`run_live()` implemented but gated behind `--live --acknowledge-drift-finding`, not invoked) and
the finding was presented to Cliff via a direct question rather than decided unilaterally. Cliff
reviewed the finding and selected **"Proceed with the live call now"** — the stop condition fired
as designed, was reported, and Cliff's own explicit decision (not a default, not silence)
authorized overriding it.

## D. Candidate-visibility gate

c4's target-role candidate pool over the post-recovery ledger: 3 propositions — p11 and p2 (the
pre-existing amygdala-bearing passage, same physical anchor, paper 67/chunk 34974/span e7) and
**p27** (the Phase-13-recovered RTPJ/theory-of-mind passage, paper 74/chunk 35979/span e8). The
recovered evidence was confirmed visible to the target role before any live call.

## E. Exactly-one-live-call proof

A dry run (`_DryRunTargetClient`, never touches the network) through the exact same `build_map`
mechanism proved mechanically: exactly one call-site (`c4`'s own target role) would go live,
seeing the full 3-proposition pool; every other of the 14 model-nomination call-sites across the
hierarchy resolved from `HeldFixedClient`'s historical replay, zero live calls.

## F. Target identification

`"a specific NAMED brain area"` is c4's own category_description and remains verified globally
unique in frozen v9 (Phase 14's finding, re-confirmed). This harness's own mechanism does **not**
rely on that uniqueness, though — `build_map`'s per-child loop disambiguates by `child_id`
directly (constructing a different client per child), which is structurally more robust than
string-matching. Recorded for completeness per the brief; not what this harness depends on.

## G. Confirmation-bias gate

Captured input to the real call: `category_description="a specific NAMED brain area"`,
`candidates=[{"proposition_id":"p11",...}, {"proposition_id":"p2",...}, {"proposition_id":"p27",...}]`
(verbatim passage text per candidate, nothing else). `qwen.nomination_prompt`'s signature has no
parameter for a prior answer or expected value — the previous binding's own exact_text ("the
specific amygdala response") was never passed as steering. The old amygdala-bearing passage
legitimately remained in the candidate pool as source evidence (p11/p2), not as answer feedback.

## H/I. Authorization artifact + pin drift

`.local/e2e-runs/phase15-c4-semantic-consumption/phase15_authorization.json` — self-describing,
distinct `experiment_id` from Phase 13's, names the exact target/role/category, the reconstruction
method, and the disclosed drift finding. Pin drift: same disclosed `pins=None` condition Phase 13
found (`hierarchy_contract.py`'s own code hash drifted after an unrelated bug fix; hierarchy data
and the other two code inputs unchanged) — re-verified, not re-decided. Not re-frozen.

## J. Live execution record

- Endpoint: isolated (JUNO tunnel). Model: `qwen3.5:9b`, `think=False`,
  `topo.SUPERVISOR_BASE_OPTIONS` (unchanged canonical options).
- Readiness pre-check (`check_endpoint_reachable`, a plain GET, no generative call): reachable, ok.
- Wall time: 44.188s total (model load + one generation call); the raw nomination call itself:
  44.093s.
- Exactly one live call made, confirmed by `len(live_rows) == 1` assertion inside `run_live`.
- Raw model output (`qwen_calls.jsonl`, single row):
  ```json
  {"nominations":[
    {"proposition_id":"p27","exact_text":"a cortical region in the right temporo-parietal junction (RTPJ)"},
    {"proposition_id":"p11","exact_text":"the specific amygdala"},
    {"proposition_id":"p2","exact_text":"the specific amygdala"}
  ]}
  ```
- Grounded/accepted: all three raw nominations passed `canonical_text_contains` (each
  `exact_text` is a literal substring of its named proposition's own passage) — nothing rejected
  at that stage. `nominate_with_model`'s own anchor-based dedup then collapsed p11+p2 (same
  physical anchor, same normalized text) into one nomination (`proposition_id="p11"`,
  `supporting_proposition_ids=["p11","p2"]`); p27 stayed separate (a distinct anchor). Final
  accepted set: **2** grounded nominations — `{p27: RTPJ}` and `{p11 (⊇p2): amygdala}`.

## K. Result classification

**Outcome 4 — MULTIPLE BINDINGS.** The fresh nomination produced two independently-grounded
named-region candidates from two different anchors (the pre-existing amygdala passage and the
newly recovered RTPJ passage), which the existing, unmodified `_fork_instances_over_role`
mechanism forked into two instances for c4 — exactly the "already structurally supported, not a
special case" mechanism Phase 14 named without predicting it would fire. Neither "same binding"
(outcome 1) nor "decline" (outcome 5) occurred; this was not a close call between the two —
**both** survived independent grounding.

## L. Primary comparison — CONTROL vs EXPERIMENTAL

**c4** (`c4#suff:specific-region`):
| | CONTROL (held fixed) | EXPERIMENTAL (live) |
|---|---|---|
| instance count | 1 | 2 |
| region binding(s) | p11, "the specific amygdala response" | **fork 1:** p27, "a cortical region in the right temporo-parietal junction (RTPJ)" — **fork 2:** p11, "the specific amygdala" |
| candidate_source | model_mapping | model_mapping (both forks) |
| model | scripted-phase5-adjudication (replayed) | **qwen3.5:9b** (both forks) |
| region_bears_on_bias_evidence | p11 (deterministic, unchanged) | p11 (deterministic, unchanged) — paired with fork 2 only; fork 1 is `partially_filled`/`incomplete_instance` (RTPJ region ≠ p11 evidence, `same_proposition` fails) |
| requirement `state` | `filled` | `filled` (via fork 2 — the `exists` quantifier needs only one complete instance) |
| generated RecoveryTarget(s) | `c4::f47ec929d445f600` (`reason="partial"`, still appears in reporting since c4's own instance pool now has an incomplete fork alongside the complete one — not re-executed, no new search) | not separately recomputed in this run; `state=filled` either way, so the requirement-level completion conclusion is unchanged |

**c6** (`c6#suff:brain-attitude`, inherits c4's region via `parent_context`,
`_parent_context_binding_for_single_instance` — which reads only `parent_requirement["instances"][0]`):
| | CONTROL | EXPERIMENTAL |
|---|---|---|
| instance count | 2 (both pairing the amygdala) | 2 (both pairing **fork 1's region = RTPJ**, since that is c4's first instance now) |
| inherited region binding(s) | p11, "the specific amygdala response", `upstream_model_dependent=true` | p27, "a cortical region in the right temporo-parietal junction (RTPJ)", `upstream_model_dependent=true` |
| own `attitude_type_or_measure` bindings | p14 (⊇p17,p3,p7) and p26, both "Explicit Bias Questionnaire" | **identical** — p14 (⊇p17,p3,p7) and p26, both "Explicit Bias Questionnaire" (held fixed, c6's own role was never live) |
| `direction` | reported, negative, p17 | reported, negative, p17 — unchanged (c6's own evidence, unaffected) |
| requirement `state` | `filled` | `filled` |
| generated RecoveryTarget(s) | none for this requirement in either map (already `filled`) | same |

Zero new code was needed for c6's inheritance — exactly as Phase 14 predicted: the existing
single-instance parent-context fallback simply read whichever region c4's first instance now
carries.

**For every other child** (c1, c2, c3, c8, c9, c10, c11, c12): confirmed byte-identical between
CONTROL and EXPERIMENTAL by direct dict comparison (zero diffs). `c12`'s own `direction`/
`effectiveness` drift (§B/C) is present in **both** maps identically, so it produces no CONTROL-
vs-EXPERIMENTAL difference there either — consistent with the preflight's own prediction.

## G (harness bug found and fixed while writing this report)

`run_live`'s own first draft hard-coded the "expected to change" exclusion set as
`{TARGET_CHILD, "c6"}` when computing `unrelated_isolation_failures` — an incomplete assumption,
not a fact about the architecture. The live run's own saved result flagged `c5` as an "unrelated
isolation failure." Investigating (purely offline — no second live call; replayed the already-
recorded live nomination result through `build_map` again) found: **c5 shares c6's exact
relationship with c4** (`parent_context_roles=["named_brain_region_or_network"]`, `parent_of[c5]
== c4`) and is therefore **also expected to change** — its top-level requirement `state`/`reason`
stayed identical (`partially_filled`/`incomplete_instance` in both maps, since c5's *other*
required role, `behavior_or_behavioral_measure`, is independently missing in both — its own
evidence search and its historical recorded search both return empty), but its *inherited*
region binding's `exact_text`/`proposition_id`/`provenance` legitimately changed from the
amygdala to the RTPJ, mirroring c6's own change exactly. **This is not a new drift class and not
an isolation failure** — it is the same forked-parent-context-propagation mechanism already
documented for c6, extended correctly to every structural sibling, not just the one the brief
named by example. Fixed `run_live` to derive the exclusion set structurally
(`_target_and_descendants`, scanning `contract_by_child`/`parent_of` for every child declaring
`TARGET_ROLE` in its own `parent_context_roles` with `parent_of` pointing at `TARGET_CHILD`)
rather than hard-coding it. Re-verified offline (replaying the already-recorded live result, no
new live call) that with this fix, the true unrelated-isolation-failure set is **empty** — c1,
c2, c3, c8, c9, c10, c11, c12 are all exactly identical between CONTROL and EXPERIMENTAL, and only
`{c4, c5, c6}` differ, all three fully explained.

## M. Provenance / attempt semantics

The fresh c4 bindings carry `candidate_source="model_mapping"`, `model="qwen3.5:9b"` — both
forks. Per `compute_stop_search_certified`/`_instance_completion_is_model_dependent` (unchanged,
checks `candidate_source == "model_mapping"` unconditionally), both remain **provisional** for
stop-search purposes — never upgraded to deterministic merely because recovery preceded them.
Phase 13's own RecoveryTarget (`c4::0c3e1a392e7868e4`) has already consumed its one bounded
recovery attempt; no recovery was re-run here, and none is authorized by this result. A
reporting pass over the EXPERIMENTAL map would still surface `c4::f47ec929d445f600`-shaped
targets (c4's own incomplete fork) as still-provisional, not as authorization for another search.

## N. Two questions, assessed separately

1. **Semantic-consumption mechanism: YES.** The recovered evidence reached and was considered by
   exactly the intended model-assisted role (confirmed: offered pool included p27; the live call
   nominated from it), with every unrelated model mapping held fixed (confirmed: zero diffs for
   c1/c2/c3/c8/c9/c10/c11/c12, and c4's own two non-target items — `region_bears_on_bias_evidence`
   deterministic, c6's own `attitude_type_or_measure` held-fixed — unchanged). The architecture
   validated end to end on a real, non-trivial case (a genuine second-candidate discovery, not a
   trivial re-affirmation).
2. **Scientific effect: Outcome 4, multiple bindings.** Qwen did **not** simply re-affirm the
   amygdala when shown the broadened evidence — it recognized the RTPJ passage as an
   independently specific named brain area and surfaced it alongside the amygdala, rather than
   discarding either. Per Section N's own instruction, this is reported as a mechanical fact, not
   ranked good/bad: the mechanism's validity does not depend on which of the five outcomes fired.

## Regression / lineage

Existing sufficiency-family test suites run unaffected (zero production code touched by this
phase): `test_sufficiency_diagnostic.py`, `test_sufficiency_mapping.py`,
`test_sufficiency_recovery_targets.py`, `test_sufficiency_phase5_replay.py`,
`test_sufficiency_leakage.py` — **129 passed**. v9 `combined_hash` confirmed byte-identical
throughout: `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`. No recovery
search, no retrieval, no second live call, no contract or pin change.

## Recommendation for the next production-integration design phase

Phase 14 already established the larger boundary this experiment does not close: production
`e2e.py` performs **no** model-assisted sufficiency nomination at any point, initial pass or
post-recovery. This phase proved the target-scoped-remap mechanism is sound and produces a real,
non-trivial, honestly-classified outcome on genuine data. The next design phase should address,
in order: (1) the C2 re-sealing side effect found here (§B/C) — a re-sealing call's own
candidate-pool perturbation on **unrelated** children is a structural property of re-running
coverage audit over a growing ledger, not specific to this experiment, and will recur for any
future recovery; whether it needs bounding (e.g. scoping re-sealing to only the affected
obligation) is an open question for that phase, not decided here; (2) robust `(child_id,
requirement_id, role)`-based scoping for a real production target-scoped client (this harness's
own per-child-loop mechanism is one validated pattern, not the only one); (3) the production
lifecycle question Phase 14 already named (when/how an initial model-assisted pass would run,
how it is gated, cost/budget accounting). No model-assisted mapping is wired into production by
this phase.
