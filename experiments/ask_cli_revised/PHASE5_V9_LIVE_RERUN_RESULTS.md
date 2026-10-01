# Phase 5 — v9 live model-assisted nomination rerun (2026-09-30)

**Experiment:** `q_aib_sufficiency_model_nomination_diagnostic_v1` (same mechanism, v9 contract)
**Model:** `qwen3.5:9b` · **Thinking:** OFF (confirmed: `thinking_chars=0` on every call)
**Recovery:** OFF throughout · **Authorized by:** Cliff, `2026-09-30T20:17:31-04:00`
**One live replay, zero retries** — every call mechanically clean.

This is the frozen experiment output. Nothing below was repaired, reinterpreted, or rerun after
manual adjudication.

## Mechanical review gate (run before any live call)

| Check | Result |
|---|---|
| 1. v8 byte-identical, hash `9de276b1...3094ac` | **PASS** |
| 2. v9 byte-identical, hash `9c72dc6a...05586` | **PASS** |
| 3. v8→v9 diff limited to the 3 reported `category_description` changes | **PASS** (6 leaf diffs = exactly 3 descriptions + their 3 consequent per-child hashes; all 8 other children byte-identical) |
| 4. Those 3 descriptions contain only generic semantic distinctions, no benchmark content | **PASS** (`provenance_tokens=[]`, `mentions_networks=False`, zero hidden-benchmark-term hits on both description strings) |

All 4 passed — proceeded per instruction.

## Artifacts

| Artifact | Path | sha256 / hash |
|---|---|---|
| v9 review (Cliff's approval) | `sufficiency_contract.aib_hier_v9.review.json` | n/a (approval record) |
| v9 authorization (this experiment) | `sufficiency_model_nomination_authorization_v9.json` | `frozen_contract_hash: 9c72dc6a...05586` |
| Run result | `.local/sufficiency-nomination-diagnostic-v9-20260930/result.json` | `466672a5c0c0ab21b1ea51d425b05372d0de3b1e672da879ce97dd40cfee704b` |
| Call trace | `.local/sufficiency-nomination-diagnostic-v9-20260930/qwen_calls.jsonl` | `60b073def84c437d01cebfdb9b853a6eb0ad5ed56ddf78c073316ab39d774827` |

Phase 2's own `sufficiency_model_nomination_authorization.json` (v8-bound, already consumed) is
untouched — this is a **separate** authorization file, not a reuse.

## Exact effective model options

Identical envelope to Phase 2 (`topology.SUPERVISOR_BASE_OPTIONS`, endpoint `http://127.0.0.1:11435`):
`{"num_ctx": 12288, "num_predict": 256, "temperature": 0, "seed": 42, "num_thread": 6,
"num_batch": 512}`, `keep_alive="30m"`, `wall_timeout=1200.0s`.

## Comparison vs. Phase 2 (items 1–10)

| # | Metric | Phase 2 (v8) | Phase 5 (v9) |
|---|---|---|---|
| 1 | Total calls | 15 | **14** |
| 2 | Wall time | 68.89 s | 66.999 s |
| 3 | Cold-load time (first call) | 44.83 s | 41.70 s |
| 4 | Mechanical failures | 0 | **0** |
| 5 | Grounding rejections | 0 | **0** |
| 6 | `thinking_chars` | 0 on every call | **0 on every call** (thinking OFF confirmed) |
| 7 | Raw nominations | 26 | 25 |
| 9 | Zero-nomination (decline) calls | 8 of 15 | **9 of 14** |
| — | Mechanically clean | yes | yes |

**Why one fewer call (14 vs 15):** c1's `neural_measure_or_modality` now correctly declines (0
candidates) under v9's tightened wording, so it never forks — eliminating the duplicate
re-query of `brain_region_or_network` that forking had caused in Phase 2 (a structural
side-effect of the fix, not a new behavior change).

## Manual adjudication — every accepted semantic claim (item 7–8)

**11 raw accepted bindings**, collapsing to **9 distinct semantic claims** (c2's two "visual
attention" phrasings are the same underlying finding at one anchor, kept as separate machine
output per the no-cross-value-collapsing rule; reported as one claim here for adjudication):

| Child | Role | Proposition(s) | Exact text | Adjudication | Note |
|---|---|---|---|---|---|
| c1 | `brain_region_or_network` | p11 (supp: p11,p2) | "the specific amygdala response" | **Correct** | Unchanged from Phase 2's own adjudication; amygdala is unambiguously a specific region |
| c4 | `named_brain_region_or_network` | p11 (supp: p11,p2) | "the specific amygdala response" | **Correct** | Same region, independently re-discovered |
| c2 | `behavior_or_behavioral_measure` | p1 (supp: p1,p4,p8,p12,p24) | "described a behavioral manifestation of the 'anomalous-is-bad' stereotype affecting prosociality" | **Incorrect** | Vague/circular — does not name a specific behavior or task; it is itself a claim that *a* behavioral manifestation occurred, which is `behavioral_manifestation_evidence`'s own job on the SAME requirement. Its acceptance causes c2 to complete via a self-referential match (both roles bound to the identical sentence, p1). **See "New finding" below.** |
| c2 | `behavior_or_behavioral_measure` | p15/p5 (supp: p15,p5 / p5) | "visual attention toward people with facial anomalies" / "influence visual attention when looking at faces with anomalous anatomy" | **Correct** | Visual-attention tracking is a genuine, measurable behavioral construct; the two exact-text spans are the same underlying finding, kept separate per the "distinct values within one anchor stay distinct" rule |
| c6 | `attitude_type_or_measure` | p14 (supp: p14,p17,p3,p7) / p26 | "Explicit Bias Questionnaire" (×2 anchor groups) | **Correct** (×2) | Unchanged wording, unchanged correct fit — EBQ genuinely is an attitude measure |
| c8 | `individual_difference_trait_or_construct` | p20/p9, ×4 | 4 named constructs (IAT/EBQ, just-world beliefs, affective empathy, DG generosity) | **Correct** (×4) | Unchanged wording; clean literal extraction, identical to Phase 2's own adjudication |

**Totals: 9 distinct claims — 8 correct, 1 incorrect, 0 ambiguous.**

**Declines reviewed for false negatives (item 10):** 9 of 14 calls declined. 7 are unchanged from
Phase 2 (identical wording, identical candidates: c10 culture/population, both c12
intervention/target roles ×2 units, c5's own region search, c6's own region search) — already
manually reviewed in Phase 2 and confirmed genuine true negatives (no false negatives found
then, and nothing about those candidate sets changed). **2 are new** under v9's tightened
wording:
- c1's own `neural_measure_or_modality` attempt (p2/p11, "the specific amygdala response") —
  correctly declines; no imaging modality (fMRI, structural MRI, etc.) is named anywhere in that
  sentence. **True negative, not a false negative.**
- c5's own `behavior_or_behavioral_measure` attempt (16 candidates) — correctly declines EBQ.
  Checked whether a genuine behavioral measure exists elsewhere in c5's own candidate pool (the
  "less generosity in the DG" passage, p9/p20) — it is **not** among c5's 16 offered candidates
  (same as Phase 2; retrieval/evidence scope unchanged). **True negative** — honestly
  evidence-limited, not a missed opportunity.

**No false negatives found among any decline.**

## New finding: a different nomination error, in a different child

**c2 flipped `partially_filled` → `filled`** via the "described a behavioral manifestation..."
nomination above. Inspected directly: `behavior_or_behavioral_measure` (model-sourced) and
`behavioral_manifestation_evidence` (deterministic) both resolve to the **identical proposition
p1** — the SAME sentence satisfies both roles, because that one sentence both asserts "a
behavioral manifestation occurred" (which the deterministic `achieved_outcome_predicate`
detector correctly reads as manifestation evidence) and happens to contain the word
"behavioral" (which the model latched onto as if it named the behavior itself). The
Phase-4-fixed `same_proposition` check correctly judges this as "same proposition" (because it
genuinely is), but the underlying nomination doesn't do what the role intends: it doesn't name a
specific behavior/task, it just restates that one occurred — functionally duplicating the
`behavioral_manifestation_evidence` role rather than independently identifying `behavior_or_
behavioral_measure`.

This is a **plausible side effect of the tightened wording's own vocabulary**: v9's description
repeats "behavior"/"behavioral" multiple times ("an observed behavior, behavioral choice or
action, or a task or measure of behavior"), and a sentence that literally contains the word
"behavioral" (even used in a vague, meta sense) may be more lexically salient to the model under
this wording than under v8's shorter "a named behavior or behavioral measure." **Not confirmed
mechanistically** (no model internals were inspected) — offered as the most plausible
explanation, not a proven cause.

## Per-child state comparison (item 11–13)

| Child | Deterministic-only | Phase 2 (v8) | Phase 5 (v9) | Instance count (v9) |
|---|---|---|---|---|
| c1 | `partially_filled` | `filled` | `filled` | 1 (was 4 in P2's raw count) |
| c2 | `partially_filled` | `partially_filled` | **`filled`** | 3 |
| c3 (×2) | `filled` / `partially_filled` | unchanged | unchanged | 1 / 2 |
| c4 | `partially_filled` | `filled` | `filled` | 1 (was 2) |
| c5 | `missing` | `filled` | **`partially_filled`** | 1 |
| c6 | `missing` | `filled` | `filled` | 2 (was 5) |
| c6 (coverage) | `partially_filled` | unchanged | unchanged | 2 |
| c8 | `missing` | `partially_filled` | `partially_filled` | 4 (was 8) |
| c9 | `missing` | `partially_filled` | `partially_filled` | 4 (was 8) |
| c10, c11, c12 | unchanged | unchanged | unchanged | unchanged |

**c8→c9 propagation (item 13): confirmed still 4→4.** c8/c9's own roles were never touched by
Finding C — this pairing is unaffected by anything in this rerun; the count stayed exactly where
Phase 4's accounting fix left it.

## Did the two Phase 2 category-boundary errors disappear, persist, or change form? (item 14)

- **Error 1 (`neural_measure_or_modality` accepting a neural finding):** **Disappeared.**
  c1's own modality attempt now correctly returns zero candidates; c1 remains `filled` via
  `brain_region_or_network` alone (its genuine alt-group partner), exactly as the alt-group
  design intends.
- **Error 2 (`behavior_or_behavioral_measure` accepting EBQ as behavior):** **Disappeared** for
  c5 specifically — c5's own attempt now correctly declines EBQ, and c5 honestly reverts from a
  falsely-`filled` state to the accurate `partially_filled`. **A related but distinct new
  acceptance appeared in c2** (a different child, same role name) — see "New finding" above. This
  is not the SAME error recurring; it is a different nomination, in a different evidence pool,
  with a different (also imperfect) character.

## Item 15 — any new semantic error: yes, documented above (c2's circular nomination).
## Item 16 — over-conservative nomination from the tighter wording: no evidence found. If
anything, c2 shows a mild OVER-inclusive tendency in one spot, the opposite direction.
## Item 17 — remaining mapper-limited vs. evidence-limited gaps:
all unchanged from Phase 2/4: c9's `named_scale_or_instrument` (evidence-limited — no scale named
in c9's own scope for any of the 4 traits), c10/c11/c12 (evidence-limited — genuinely no specific
culture/intervention named in their own candidate pools, confirmed again this run).

## Readiness decision

**A. Is model-assisted sufficiency mapping now sufficiently accurate to serve as an input to an
experimental recovery controller?** **No, not yet.** 8 of 9 distinct claims are correct, and both
originally-targeted errors are gone — but the new c2 finding is a concrete, concerning failure
mode specifically FOR recovery purposes: a vague, self-referential nomination can still flip a
requirement to `filled`/"stop searching" without genuinely adding new information. A recovery
controller gated on this map would incorrectly treat c2 as resolved.

**B. Is the sufficiency map reasonably calibrated rather than systematically over/under-flagging?**
**Mostly yes, with one real exception.** Not systematic (8/9 claims correct, 9 clean declines, 0
false negatives) — but the exception is directly relevant to calibration: it is a `filled` state
built on weak grounding, which is exactly the failure shape calibration concerns are about.

**C. Any remaining structural/accounting bugs that should block recovery experimentation?**
**No.** Every count/state difference from Phase 2 traces cleanly to either the Phase 3/4
accounting fixes (instance-count reductions, zero state surprises) or v9's own semantic changes
(c1, c5 fixed as intended; c2's new finding). Parts A/B/Phase-4's fixes hold completely under this
second live run.

**Recommendation: NOT READY FOR A SEPARATELY AUTHORIZED SUFFICIENCY-DIRECTED RECOVERY
EXPERIMENT.**

Concrete blocking failure mode: the `behavior_or_behavioral_measure` role (and plausibly other
roles sharing its "name the X, as opposed to just asserting X happened" shape) can still be
satisfied by a nomination that merely restates an already-established manifestation fact rather
than independently naming the specific behavior/measure — producing a `filled` state that would
incorrectly suppress recovery for a genuinely still-incomplete finding. This was not present
(went undetected, since Phase 2's c2 never found anything) before this rerun, and needs its own
targeted investigation — not a repeat of this same tightening approach — before recovery gating
should be trusted.

No recovery experiment run. Recovery remains OFF.

## Newly discovered issue

Documented above: c2's circular/self-referential nomination. No other new issue found.
