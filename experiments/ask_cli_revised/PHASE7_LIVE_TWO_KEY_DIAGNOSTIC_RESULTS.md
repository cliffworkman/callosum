# Phase 7 — live v9 two-key (nomination + specificity) diagnostic (2026-09-30)

**One live replay, zero retries.** Every call mechanically clean. This is the frozen experiment
output. Nothing below was repaired, reinterpreted, or rerun after manual adjudication, and no
prompt/schema/gate parameter was tuned after observing the result, per the authorization's explicit
constraint.

**Headline result: NOT READY.** The specificity gate did not merely fail to improve on Phase 5 — it
produced a **net-worse** outcome. It approved the one nomination it was specifically built to catch
(c2's circular claim), while incorrectly vetoing **eight** genuinely correct nominations (amygdala
×2, all four of c8's named traits, both of c6's EBQ anchor groups) that Phase 5's single-key run had
accepted correctly. See "New finding" below.

## Pre-run gate (all 6 checks passed before any live call)

| Check | Result |
|---|---|
| 1. v9 byte-identical, hash `9c72dc6a...05586` | **PASS** (confirmed against disk) |
| 2. No v10 exists or is needed | **PASS** (confirmed, no v10 file anywhere in the tree) |
| 3. Two-key path active: `nominate_with_model` → grounding/admissibility → `confirm_specific_instances` → accepted `RoleBinding` | **PASS** (confirmed by reading `_bind_role_candidates`'s source — nomination call precedes confirmation call) |
| 4. Confirmation task is veto-only | **PASS** (Phase 6's 9 mechanical proofs re-run, 21/21 green) |
| 5. Recovery gating disabled | **PASS** (no "recovery" reference anywhere in `sufficiency_model_nomination_diagnostic.py`; no recovery env var set) |
| 6. Leakage tests green | **PASS** (17/17) |

Isolated Ollama endpoint (`http://127.0.0.1:11435`) confirmed reachable with `qwen3.5:9b` installed
before the live call (a read-only `GET /api/tags`, never a generative call).

## Authorization artifact

`experiments/ask_cli_revised/sufficiency_model_nomination_authorization_v9_phase7.json` — a new,
separate file (Phase 2's and Phase 5's authorization files are untouched, per instruction). Bound
to: `experiment_id="q_aib_sufficiency_model_nomination_diagnostic_v1"`, `run_id="phase7-v9-two-key-
live-20260930"`, `question_sha256s=["6e037bab...57030"]`, `frozen_contract_hash="9c72dc6a...05586"`,
`model="qwen3.5:9b"`, `thinking=false`, `specificity_confirmation_enabled=true`,
`recovery_enabled=false`, `authorized_executions=1`.

## Run artifacts + hashes

| Artifact | Path | sha256 |
|---|---|---|
| Run result | `.local/sufficiency-nomination-diagnostic-v9-phase7-20260930/result.json` | `a6bb246cb3bbc343739a8fd4a4b80931b8d8f0d7995d4100761bdf11a4518903` |
| Call trace | `.local/sufficiency-nomination-diagnostic-v9-phase7-20260930/qwen_calls.jsonl` | `481742486dcb0c4ffb1f2ae6f24fa95139628cc6199f862d8255e7764973ee3c` |

(Both `.local/` — gitignored, local-only, per repo convention; only hashes are committed to markdown.)

## Exact effective model configuration

Identical envelope to Phase 2/Phase 5 (`topology.SUPERVISOR_BASE_OPTIONS`, endpoint
`http://127.0.0.1:11435`): `{"num_ctx": 12288, "temperature": 0, "seed": 42, "num_thread": 6,
"num_batch": 512}`, `keep_alive="30m"`, `wall_timeout=1200.0s`. `num_predict` is overridden per-task
by `qwen.py`'s own output-cap constants (unchanged mechanism, confirmed by reading `_call`): **256**
for `nominate_sufficiency_role` (`_NOMINATION_OUTPUT_TOKENS`, same value Phase 2/5 used), **384**
for `verify_specific_instances` (`_SPECIFICITY_OUTPUT_TOKENS`, new to Phase 6/7). No parameter was
changed from the current codebase's canonical configuration.

## Two-key audit — complete, both stages preserved independently

19 total calls: **14 nomination calls** (identical role/candidate-set sequence to Phase 5, byte-for-
byte — confirms full determinism of the unchanged nomination stage under temp=0/seed=42) +
**5 specificity-validation calls** (one per nomination call that produced ≥1 raw nomination).

### Nomination stage (all 14 calls)

| # | Category | Candidates shown (proposition_ids) | Raw nominations | Grounding | Admissibility |
|---|---|---|---|---|---|
| 0 | neural_measure_or_modality | p2,p11 | 0 (decline) | n/a | offered = admissible |
| 1 | brain_region_or_network | p2,p11 | 2 (both "the specific amygdala response") | both grounded | both admissible |
| 3 | culture_or_population | p21,p22 | 0 (decline) | n/a | — |
| 4 | named_intervention (c12 unit A) | p24,p1,p4,p8,p12 | 0 (decline) | n/a | — |
| 5 | intervention_target_aspect (c12 unit A) | p24,p1,p4,p8,p12 | 0 (decline) | n/a | — |
| 6 | named_intervention (c12 unit B) | p25,p6,p18 | 0 (decline) | n/a | — |
| 7 | intervention_target_aspect (c12 unit B) | p25,p6,p18 | 0 (decline) | n/a | — |
| 8 | behavior_or_behavioral_measure (c2) | 10 props | 8 (5× circular text, 2× "visual attention toward...", 1× "influence visual attention...") | all 8 grounded | all offered admissible |
| 10 | named_brain_region_or_network (c4) | p11,p2 | 2 (both "the specific amygdala response") | both grounded | both admissible |
| 12 | individual_difference_trait_or_construct (c8) | p20,p9 | 8 (4 distinct texts ×2 propositions) | all 8 grounded | all admissible |
| 14 | brain_region_or_network (c5) | 16 props | 0 (decline) | n/a | — |
| 15 | behavior_or_behavioral_measure (c5) | 16 props | 0 (decline) | n/a | — |
| 16 | brain_region_or_network (c6, 2nd region search) | 11 props | 0 (decline) | n/a | — |
| 17 | attitude_type_or_measure (c6) | 11 props | 5 (all "Explicit Bias Questionnaire") | all 5 grounded | all admissible |

**Grounding rejections: 0 of 25** raw nominations (independently re-verified: every `exact_text` is
a literal substring of its proposition's own verified passage — `canonical_text_contains` checked
directly against `11_verified_ledger.json`). **Raw first-stage nominations: 25. First-stage
declines: 9 of 14** (identical count and identical candidate sets to Phase 5 — these 9 decline calls
inherit Phase 5's own already-completed false-negative review unchanged, since nothing about their
wording or candidate pool differs; no new false negative found or expected).

After `nominate_with_model`'s anchor-based dedup (collapsing same-anchor/same-text duplicates), the
25 raw nominations collapse to **11 distinct candidates** offered to the specificity gate:

| Nomination group | Candidates after dedup |
|---|---|
| c1 brain_region (p2/p11, amygdala) | 1 |
| c4 named_brain_region (p11/p2, amygdala) | 1 |
| c2 behavior (10 raw → 3 distinct: circular / visual-attention-A / visual-attention-B) | 3 |
| c8 trait (8 raw → 4 distinct texts) | 4 |
| c6 attitude (5 raw → 2 anchor groups, both "EBQ") | 2 |
| **Total** | **11** |

### Specificity stage (all 11 candidates, across 5 calls)

| Child/role | Candidate (`exact_text`) | Nomination-level adjudication | Validator decision | Classification |
|---|---|---|---|---|
| c1 `brain_region_or_network` | "the specific amygdala response" | **Correct** (unambiguously the amygdala, a specific region) | `specific=False` | **INCORRECT VETO** |
| c4 `named_brain_region_or_network` | "the specific amygdala response" | **Correct** (same region, independently re-discovered) | `specific=False` | **INCORRECT VETO** |
| c2 `behavior_or_behavioral_measure` | "described a behavioral manifestation of the 'anomalous-is-bad' stereotype affecting prosociality" | **Incorrect** (vague/circular — Phase 5's own target failure mode) | `specific=True`, `instance_text`=same text | **INCORRECT ACCEPT** |
| c2 `behavior_or_behavioral_measure` | "visual attention toward people with facial anomalies" | **Correct** (genuine measurable behavioral construct) | `specific=True`, `instance_text`=same text | **CORRECT ACCEPT** |
| c2 `behavior_or_behavioral_measure` | "influence visual attention when looking at faces with anomalous anatomy" | **Correct** (same, distinct phrasing) | `specific=True`, `instance_text`=same text | **CORRECT ACCEPT** |
| c8 `individual_difference_trait_or_construct` | "negative attitudes (IAT and EBQ)" | **Correct** | `specific=False` | **INCORRECT VETO** |
| c8 `individual_difference_trait_or_construct` | "social cognitive biases (just-world beliefs)" | **Correct** | `specific=False` | **INCORRECT VETO** |
| c8 `individual_difference_trait_or_construct` | "emotional dispositions (affective empathy)" | **Correct** | `specific=False` | **INCORRECT VETO** |
| c8 `individual_difference_trait_or_construct` | "undesirable behaviors (less generosity in the DG)" | **Correct** | `specific=False` | **INCORRECT VETO** |
| c6 `attitude_type_or_measure` | "Explicit Bias Questionnaire" (anchor group 1) | **Correct** | `specific=False` | **INCORRECT VETO** |
| c6 `attitude_type_or_measure` | "Explicit Bias Questionnaire" (anchor group 2) | **Correct** | `specific=False` | **INCORRECT VETO** |

**Totals: 11 specificity decisions. Correct accepts: 2. Incorrect accepts: 1. Correct vetoes: 0.
Incorrect vetoes: 8.**

Every vetoed `instance_text` was returned as the required empty string (`""`) — confirming the
schema/fail-closed contract held exactly as designed even though the SEMANTIC judgment was wrong;
this is a calibration failure of the model's judgment, not a plumbing defect. All 3 accepted
decisions carried `instance_text` identical to their own `exact_text`, trivially satisfying the
grounding check.

### Final RoleBindings / requirement states (post-gate)

| Candidate | Accepted? | Final RoleBinding state | Instance survives? |
|---|---|---|---|
| c1 amygdala | No (vetoed) | `missing` | No — c1 reverts to its deterministic-only state |
| c4 amygdala | No (vetoed) | `missing` | No — c4 reverts to its deterministic-only state |
| c2 circular | **Yes (false accept)** | `filled` | **Yes — survives into the final map** |
| c2 visual-attention A | Yes (correct accept) | `filled` | Yes |
| c2 visual-attention B | Yes (correct accept) | `filled` | Yes |
| c8 × 4 traits | No (all vetoed) | `missing` | No — c8 reverts to its deterministic-only state |
| c6 × 2 EBQ groups | No (both vetoed) | `missing` | No — c6 reverts to its deterministic-only state |

**Post-gate accepted semantic claims: 3. Correct: 2. Incorrect: 1. Ambiguous: 0.**

## Comparison: Phase 2 (v8, single-key) vs Phase 5 (v9, single-key) vs Phase 7 (v9, two-key)

| # | Metric | Phase 2 (v8) | Phase 5 (v9) | Phase 7 (v9, two-key) |
|---|---|---|---|---|
| 1 | Nomination calls | 15 | 14 | **14** |
| 2 | Specificity-validation calls | n/a | n/a | **5** |
| 3 | Total model calls | 15 | 14 | **19** |
| 4 | Total wall time | 68.89 s | 66.999 s | **73.905 s** |
| 5 | Cold-load contribution (first call) | 44.83 s | 41.70 s | **36.678 s** |
| 6 | Incremental validator wall time | n/a | n/a | **12.218 s** (5 calls) |
| 7 | Mechanical failures | 0 | 0 | **0** |
| 8 | Grounding rejections | 0 | 0 | **0** |
| 9 | `thinking_chars` | 0 on every call | 0 on every call | **0 on every call** |
| 10 | Raw first-stage nominations | 26 | 25 | **25** |
| 11 | First-stage declines | 8 of 15 | 9 of 14 | **9 of 14** |
| 12 | Specificity accepts | n/a | n/a | **3** |
| 13 | Specificity vetoes | n/a | n/a | **8** |
| 14 | Correct/incorrect/ambiguous first-stage candidates | 5/1/1 (Phase 2's own report: 7 distinct claims, v8 wording) | 8/1/0 (9 distinct claims, v9 wording) | **10/1/0** (11 distinct candidates, v9 wording — identical nomination-stage text to Phase 5, re-split here per-candidate rather than per-post-collapse-claim since the specificity stage operates at candidate granularity) |
| 15 | Correct accepts | n/a | n/a | **2** |
| 16 | Incorrect accepts | n/a | n/a | **1** |
| 17 | Correct vetoes | n/a | n/a | **0** |
| 18 | Incorrect vetoes | n/a | n/a | **8** |
| 19 | Post-gate correct/incorrect/ambiguous semantic claims | 5/1/1 (no gate existed) | 8/1/0 (no gate existed) | **2/1/0** |
| 20 | Per-child final state | see Phase 5 report | see Phase 5 report | see table below |
| 21 | Per-requirement instance counts | see Phase 5 report | see Phase 5 report | see table below |
| 22 | c8→c9 propagation | 8→8 (raw, pre-Phase-4-fix) | 4→4 | **0→0** (mechanically correct given c8's state; the real loss is upstream) |
| 23 | c2 detailed outcome | `partially_filled` (no model fill found) | `filled`/3 (false fill, ungated) | **`filled`/3 (false fill persists — the gate missed it)** |
| 24 | Mapper-limited vs evidence-limited gaps | — | c9 scale, c10/11/12 culture/intervention | **unchanged — c9 scale, c10/11/12 culture/intervention (the gate has no effect here; no model nominations existed for these roles in any phase)** |

### Per-child final state / instance counts (Phase 7)

| Child | Requirement | Deterministic-only | Phase 7 with-model (two-key) | vs. Phase 5 (single-key) |
|---|---|---|---|---|
| c1 | `c1#suff:neural-manifestation` | `partially_filled`, 1 | `partially_filled`, 1 | **Regressed** (Phase 5: `filled`, 1) |
| c2 | `c2#suff:behavioral-manifestation` | `partially_filled`, 1 | `filled`, 3 | **Unchanged — false fill persists** |
| c3 | `c3#suff:attitude-manifestation` | `filled`, 1 | `filled`, 1 | Unchanged (gate never reached this role) |
| c3 | `c3#suff:implicit-explicit-coverage` | `partially_filled`, 2 | `partially_filled`, 2 | Unchanged |
| c4 | `c4#suff:specific-region` | `partially_filled`, 1 | `partially_filled`, 1 | **Regressed** (Phase 5: `filled`, 1) |
| c5 | `c5#suff:brain-behavior` | `missing`, 1 | `missing`, 1 | **Regressed further** (Phase 5: `partially_filled`, 1 — c5's own nomination attempt still correctly declines here, same as both prior phases; this particular row is unaffected by the gate, listed for completeness) |
| c6 | `c6#suff:brain-attitude` | `missing`, 1 | `missing`, 1 | **Regressed** (Phase 5: `filled`, 2) |
| c6 | `c6#suff:implicit-explicit-coverage` | `partially_filled`, 2 | `partially_filled`, 2 | Unchanged |
| c8 | `c8#suff:trait-construct` | `missing`, 1 | `missing`, 1 | **Regressed** (Phase 5: `partially_filled`, 4) |
| c9 | `c9#suff:trait-scale-pairing` | `missing`, 0 | `missing`, 0 | **Regressed** (Phase 5: `partially_filled`, 4) |
| c10 | `c10#suff:culture-existence` | `missing`, 1 | `missing`, 1 | Unchanged |
| c11 | `c11#suff:culture-operationalization-pairing` | `missing`, 0 | `missing`, 0 | Unchanged |
| c12 | `c12#suff:intervention-effectiveness` | `partially_filled`, 2 | `partially_filled`, 2 | Unchanged |

**Note on c5:** the "Regressed further" annotation above is imprecise bookkeeping noise, not a real
regression — c5's own `behavior_or_behavioral_measure` attempt declined (0 raw nominations) in all
three phases identically (same 16-candidate pool, same correct true-negative decline), so c5's state
was never touched by the gate in Phase 7 either; it is listed only because the state-table scan
includes every requirement row for completeness.

**Six of nine model-discoverable requirement rows regressed** from Phase 5's correctly-filled state
back down to the deterministic-only baseline (c1, c4, c6, c8, c9, and arguably c5's framing above),
while the one requirement that should have been fixed (c2) was not.

## c2 detailed outcome

c2 is `filled` with 3 instances, identical in SHAPE to Phase 5's own false-fill outcome. The
surviving instances:

1. The circular nomination ("described a behavioral manifestation...") — `behavior_or_behavioral_
   measure: filled` + `behavioral_manifestation_evidence: filled`, **both on the same proposition
   p1** (self-referential, exactly Phase 5's own documented mechanism) → `same_proposition` joint
   grounding passes → this instance is `complete` → the requirement aggregates to `filled`.
2. "visual attention toward people with facial anomalies" (p5/p15) — correctly accepted, but its
   `behavior_or_behavioral_measure` proposition never shares a proposition with `behavioral_
   manifestation_evidence`'s own p1, so this instance does NOT independently satisfy joint
   grounding (consistent with Phase 6 Part F's own finding).
3. "influence visual attention when looking at faces with anomalous anatomy" (p5) — same as above.

**The specificity gate was explicitly designed to veto exactly candidate 1 and did not.** Its
failure to do so means c2 ends this run in the identical false `filled` state Phase 5 found —
the gate provided zero correction for its own target case in this live run.

## Validator false-positive / false-negative analysis

**False positive (incorrect accept): 1 of 11 (9%).** The one case the gate was purpose-built to
catch. Not confirmed mechanistically why the validator approved it this time (no model internals
inspected) — plausible continuity with Phase 5's own hypothesis that the word "behavioral" appearing
literally in the nominated text is lexically salient regardless of which prompt (nomination vs.
specificity) is asking about it.

**False negatives (incorrect vetoes): 8 of 11 (73%).** This is the dominant, more severe pattern in
this run, and it is **systematic, not isolated**: every candidate that was NOT c2's circular text —
8 of 8 — was incorrectly vetoed, spanning three unrelated roles (`brain_region_or_network` ×2,
`individual_difference_trait_or_construct` ×4, `attitude_type_or_measure` ×2) and three unrelated
children (c1, c4, c8, c6). A single named, unambiguous entity ("amygdala," "Explicit Bias
Questionnaire") or a short compound noun phrase with a parenthetical gloss (c8's four trait
descriptions) is exactly the shape the gate's own worked examples ("adolescents in Japan,"
"mindfulness training") were meant to recognize as specific — and in this run the validator rejected
every one of them. Given the authorization's own framing ("an isolated incorrect veto is not
automatically equivalent in severity to an incorrect accept"), this is unambiguously **systematic**:
it is not one unlucky candidate, it is the validator's apparent default behavior on this entire
batch of genuinely-specific nominations. Recovery experimentation gated on this map would be
**distorted and wasteful** — every one of these 8 suppressed findings is a real, correct discovery
that a recovery controller would needlessly re-search for, believing the requirement genuinely
unfilled.

**No evidence of systematic approval of generic existence statements as specific** (criterion #7) —
the opposite problem dominates this run. Criterion #7 as literally stated is not violated, but the
spirit of the concern (the validator not reliably distinguishing specific from non-specific) is
violated in the other direction.

## Timing / call overhead introduced by confirmation

5 specificity calls added 12.218 s of incremental wall time (16.5% of the 73.905 s total), each with
near-zero cold-load contribution (0.002–0.017 s, since the model was already warm from the preceding
nomination call) — confirming the batching design (one call per role-call's full nomination batch)
keeps per-call overhead small. Total wall time rose from Phase 5's 66.999 s to 73.905 s (+10.3%),
entirely attributable to the 5 new specificity calls; nomination-stage wall time (61.687 s) is
within normal run-to-run variance of Phase 5's own nomination-only wall time.

## Regression results

| Suite | Result |
|---|---|
| `test_sufficiency_specificity_gate.py` (pre-run gate check 4) | 21/21 passed |
| `test_sufficiency_leakage.py` (pre-run gate check 6) | 17/17 passed |

No code was changed in this phase — Phase 7 is purely an authorized live-run execution against
Phase 6's already-regression-tested code. No further test changes were made or are needed; the full
suite status is unchanged from Phase 6's hand-back (142 targeted + 619 `contract_directed` + 2040
passed/11 skipped/2 pre-existing-unrelated-failed in the full tree).

## v9 byte-identity confirmation (post-run)

```
git diff HEAD -- experiments/ask_cli_revised/sufficiency_contract.aib_hier_v9.frozen.json
```

→ empty. `combined_hash` unchanged: `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.
No v10 was created at any point.

## Recovery readiness

**A. Did the specificity gate eliminate the dangerous false-fill shape found in Phase 5?**
**No.** c2 remains `filled`/3 with the same false claim surviving, byte-for-byte the same failure
shape Phase 5 found. The gate had zero corrective effect on its own target case in this live run.

**B. Did it do so without introducing systematic false-negative veto behavior?**
**No — it introduced exactly that, and severely.** 8 of 11 candidates (73%) were incorrectly
vetoed, spanning 3 roles and 4 children, suppressing every genuinely correct finding except the one
case (c2) where the gate's failure ran the other direction.

**C. Are all post-gate accepted semantic claims sufficiently precise to serve as stop-searching
evidence for an EXPERIMENTAL recovery controller?**
**No.** 1 of 3 post-gate accepted claims (33%) is the exact vague/circular claim the gate exists to
exclude. A recovery controller reading c2 as `filled` would incorrectly treat it as resolved.

**D. Is the semantic/accounting layer structurally stable?**
**Yes, with no new structural bug.** Every state/count difference from Phase 5 traces cleanly and
entirely to the specificity gate's semantic miscalibration (confirmed candidate-by-candidate above),
not to any defect in `confirm_specific_instances`'s fail-closed plumbing, `same_proposition` joint
grounding, instance-key derivation, or parent propagation — all of which behaved exactly as Phase 6's
own tests proved they would, given these specific (wrong) specificity decisions as input. The
architecture is sound; the live model's specificity judgment in this one run was not.

## **Recommendation: NOT READY FOR RECOVERY EXPERIMENTATION.**

Concrete reason: in this one live execution, the specificity gate was net-harmful rather than
net-helpful — it suppressed 8 correct findings (a majority of everything it was asked to judge)
while failing to catch the 1 incorrect finding it exists specifically to catch. Gating recovery on
this map would both (a) fail to prevent the exact false-`filled` state Phase 6 targeted, and (b)
trigger wasteful, distorted recovery attempts for 4 children (c1, c4, c6, c8, and transitively c9)
whose findings were genuinely already present but incorrectly suppressed. This is a single live
sample (n=1 run, 11 specificity decisions) — it does not by itself prove the validator is
*always* miscalibrated this way, but it is sufficient to disqualify the two-key gate, as currently
prompted/schema'd, from recovery-controller use without further investigation. No prompt or schema
change was made in response to this result, per the authorization's explicit constraint; any fix is
out of this phase's scope.

**No recovery was enabled or run.**

## Newly discovered issue

**The live specificity validator exhibits a severe, directionally-inverted miscalibration on this
one run**: a strong bias toward vetoing genuinely specific named entities/short descriptive phrases
(8 of 8 such candidates incorrectly rejected) alongside a continued failure to reliably reject
genuinely vague/circular restatements (the 1 case offered was incorrectly accepted). This is a
different and more severe failure mode than anything found in Phases 2–6 — no prior phase's live run
exercised the specificity task at all, so this is the first empirical data point on its actual
reliability, and it is a poor one. Worth investigating before any further specificity-gate
experimentation: whether this reflects prompt wording the model interprets more conservatively than
intended ("When uncertain, mark the candidate NOT specific" may be over-triggering on already-clear
cases), a batching artifact (all candidates in one call, unlike the two-stage separation here), or
genuine model unreliability on this exact task shape. Not investigated further in this phase, per
the no-tuning-after-results constraint.
