# Phase 10 — live v9 single-stage minimal-referent diagnostic (2026-10-01)

**One live replay, zero retries.** Every call mechanically clean except for 3 genuine grounding
rejections (a first — see below). This is the frozen experiment output. Nothing below was
repaired, reinterpreted, or rerun after manual adjudication, and no prompt was tuned after
observing the result, per the authorization's explicit constraint.

**Headline result: the reformulation is a MIXED, role-dependent result — not a clean win.** It
dramatically improved c8's extraction granularity (minimal referents instead of abstract-headed
phrases), but it did **not** fix the original c2 circular-assertion problem — the model simply
picked a *different* vague occurrence-assertion span from the same sentence — and it introduced
**new** false positives in c5, c10, and c12 that no prior phase (2, 5, or 7) ever produced. Of 18
distinct accepted nominations: **9 correct, 7 incorrect, 2 ambiguous** — a sharp regression in raw
precision from Phase 5's 8/9/0. Phase 9's provisional-stop-search policy would correctly flag
every one of this run's `filled` requirements as non-certified (see the recovery-safety audit) —
but the **parent_context transitive-provenance gap is real and confirmed**, just not triggered by
this run's specific data.

## Pre-run gate (all 7 checks passed before any live call)

| Check | Result |
|---|---|
| 1. HEAD is the expected Phase 9 HEAD (`917f746a`) | **PASS** |
| 2. v9 byte-identical, hash `9c72dc6a...05586` | **PASS** |
| 3. No v10 exists | **PASS** |
| 4. `confirm_specific_instances`/`specificity_prompt`/`specificity_schema`/`verify_specific_instances` absent from the active path | **PASS** (`hasattr` confirmed `False` for all four) |
| 5. Exactly one semantic model step | **PASS** (`_bind_role_candidates` calls only `nominate_with_model`) |
| 6. Recovery gating OFF | **PASS** (no "recovery" reference anywhere in the diagnostic module; no env var) |
| 7. Leakage tests green | **PASS** (16/16) |

Isolated Ollama endpoint confirmed reachable with `qwen3.5:9b` installed before the live call.

## Authorization artifact

`experiments/ask_cli_revised/sufficiency_model_nomination_authorization_v9_phase10.json` — new,
separate from every prior phase's authorization. Bound to: `question_sha256s=["6e037bab...
57030"]`, `frozen_contract_hash="9c72dc6a...05586"`, `model="qwen3.5:9b"`, `thinking=false`,
`mapping_mechanism="single_stage_minimal_referent_nomination"`,
`specificity_confirmation_gate_present=false`, `recovery_enabled=false`,
`authorized_executions=1`.

## Run artifacts + hashes

| Artifact | Path | sha256 |
|---|---|---|
| Run result | `.local/sufficiency-nomination-diagnostic-v9-phase10-20261001/result.json` | `4c353adcf37ebed4dfec3088aad5c7189b9ec55f366b80767eda2648b923047c` |
| Call trace | `.local/sufficiency-nomination-diagnostic-v9-phase10-20261001/qwen_calls.jsonl` | `b74d8464368273ce37e958adeb007402a1fd051cb552e44ea7f3b500bfeb413e` |

## Effective model configuration

Identical envelope to every prior phase (`topology.SUPERVISOR_BASE_OPTIONS`, endpoint
`http://127.0.0.1:11435`): `{"num_ctx": 12288, "temperature": 0, "seed": 42, "num_thread": 6,
"num_batch": 512}`, `keep_alive="30m"`, `wall_timeout=1200.0s`, `num_predict` overridden per-task
to **256** (`_NOMINATION_OUTPUT_TOKENS`, unchanged). No parameter was changed from the current
codebase's canonical configuration.

## Full manual adjudication

14 total calls (all `nominate_sufficiency_role` — no second stage). **Mechanically**: 0 provider
failures, `done_reason="stop"` on every call (no truncation), `thinking_chars=0` throughout
(thinking OFF confirmed). **43 raw nominations, 6 of 14 declines** (down from Phase 5's 9 of 14 —
the model became *less* willing to decline, not more). **3 grounding rejections** — the first of
any phase in this entire arc (all three are the identical text "empathy and disgust sen sitivity"
from propositions p18/p6/p25; the real source PDF text contains a non-standard whitespace
character the model's copy didn't exactly reproduce — a benign PDF-extraction artifact, not a
model hallucination, and the grounding gate correctly caught it before it could become an accepted
binding regardless of the separate semantic question below).

### Per-call raw nominations and category text

| # | Category | Raw nominations | Note |
|---|---|---|---|
| 0 | neural_measure_or_modality (c1) | decline | matches every prior phase |
| 1 | brain_region_or_network (c1) | "the specific amygdala response to facial anomalies" ×2 (p2,p11) | |
| 2 | named_culture_or_population (c10) | "culturally shared" ×2 (p21,p22) | **new** — declined in every prior phase |
| 3 | named_intervention, unit A (c12) | decline | matches |
| 4 | target_manifestation, unit A (c12) | "people with anomalous faces" ×5 | **new** — declined in every prior phase |
| 5 | named_intervention, unit B (c12) | decline | matches |
| 6 | target_manifestation, unit B (c12) | decline | matches |
| 7 | behavior_or_behavioral_measure (c2) | 8 items across 3 distinct texts | see below |
| 8 | named_brain_region_or_network (c4) | "the specific amygdala response to facial anomalies" ×2 | |
| 9 | individual_difference_trait_or_construct (c8) | 8 items, 5 distinct texts (truncated at `maxItems=8`) | see below |
| 10 | brain_region_or_network (c5) | decline | matches |
| 11 | behavior_or_behavioral_measure (c5) | 8 items across 3 distinct texts | **new** — declined in every prior phase |
| 12 | brain_region_or_network, 2nd search (c6) | decline | matches |
| 13 | attitude_type_or_measure (c6) | 8 items, 2 accepted + 3 grounding-rejected | see below |

### Distinct accepted (post-grounding, post-anchor-dedup) nominations — manual adjudication

| # | Child | Role | Final `exact_text` | Adjudication | Rationale |
|---|---|---|---|---|---|
| 1 | c1 | `brain_region_or_network` | "the specific amygdala response to facial anomalies" | **Correct** (non-minimal) | Names the amygdala; a reader can answer "which region?" — but the instruction to extract the SHORTEST span was not followed (the span grew relative to Phase 5/7's own "the specific amygdala response") |
| 2 | c4 | `named_brain_region_or_network` | same text, independently re-discovered | **Correct** (non-minimal) | Same |
| 3 | c2 | `behavior_or_behavioral_measure` | "detected explicit biases against people with facial anomalies" (p1) | **Incorrect** | A research-finding/occurrence assertion ("biases were detected"), not a named behavior/task/measure — the exact targeted failure mode, recurring with different wording |
| 4 | c2 | `behavior_or_behavioral_measure` | "visual attention toward people with facial anomalies" (p15) | **Correct** | Genuine, specific behavioral measure; unchanged across every phase |
| 5 | c2 | `behavior_or_behavioral_measure` | "reduce bias toward people with anomalous faces" (p6) | **Incorrect** | Drawn from hypothetical/speculative language ("might... improve... and reduce..."), not a described behavior |
| 6 | c5 | `behavior_or_behavioral_measure` | "detected explicit biases against people with facial anomalies" (p12) | **Incorrect** | Same error as #3, independently recurring |
| 7 | c5 | `behavior_or_behavioral_measure` | "scores on the Explicit Bias Questionnaire" (p14) | **Incorrect** | Direct violation of the role's own explicit exclusion ("not a self-report attitude, belief, or prejudice questionnaire") — EBQ *is* a self-report prejudice questionnaire |
| 8 | c5 | `behavior_or_behavioral_measure` | same text (p26) | **Incorrect** | Same violation |
| 9 | c5 | `behavior_or_behavioral_measure` | "visual attention toward people with facial anomalies" (p15) | **Correct** | Same genuine finding, now also surfacing in c5's broader candidate pool |
| 10 | c6 | `attitude_type_or_measure` | "Explicit Bias Questionnaire" (anchor group 1) | **Correct** | Unchanged across every phase |
| 11 | c6 | `attitude_type_or_measure` | "Explicit Bias Questionnaire" (anchor group 2) | **Correct** | Unchanged |
| 12 | c8 | `individual_difference_trait_or_construct` | "IAT" | **Ambiguous** | The passage parenthetically lists IAT as the *instrument measuring* "negative attitudes" (the actual construct) — extracting the instrument's name alone for a "trait or construct" role is a defensible-but-debatable category read |
| 13 | c8 | `individual_difference_trait_or_construct` | "EBQ" | **Ambiguous** | Same reasoning |
| 14 | c8 | `individual_difference_trait_or_construct` | "just-world beliefs" | **Correct** | Genuine construct name, properly minimal |
| 15 | c8 | `individual_difference_trait_or_construct` | "affective empathy" | **Correct** | Genuine construct name, properly minimal |
| 16 | c8 | `individual_difference_trait_or_construct` | "less generosity in the DG" | **Correct** | Same adjudication precedent as every prior phase |
| 17 | c10 | `named_culture_or_population` | "culturally shared" | **Incorrect** | Does not name any population at all — the source sentence argues the stereotype is cross-cultural ("evidence *against* a universal... hypothesis" notwithstanding, "culturally shared" is a predicate about the stereotype's distribution, not a named group) |
| 18 | c12 | `target_manifestation` | "people with anomalous faces" | **Incorrect** | Names *who the bias targets*, not *which aspect of the bias* the (never-identified) intervention addresses — a category confusion |

**Totals: 18 distinct accepted nominations. 9 correct, 7 incorrect, 2 ambiguous.**

**Grounding-rejected, never reaching an accepted binding:** "empathy and disgust sen sitivity" ×3
(c6's `attitude_type_or_measure`, propositions p18/p6/p25) — worth noting on its semantic merits
too, independent of why it was rejected: the passage frames this as an *individual-difference
trait* ("knowledge about individual differences in empathy and disgust sensitivity"), not an
*attitude*, so it would likely have been adjudicated **Incorrect** even had grounding let it
through — a second, independent reason it shouldn't have counted.

### Declines reviewed for false negatives

All 6 decline calls (c1's modality attempt, c12's intervention ×2 units, c12 unit B's target
attempt, c5's region attempt, c6's second region search) have **identical candidate pools and
category wording** to calls Phase 2/5/7 already manually reviewed and confirmed as genuine true
negatives. **No new false negative found.**

### Did Qwen extract smaller referent spans where appropriate? (a primary Phase 10 question)

**Role-dependent — not a uniform yes.** For `individual_difference_trait_or_construct` (c8), **yes,
dramatically**: the abstract-headed phrases Phase 7's live validator incorrectly vetoed ("negative
attitudes (IAT and EBQ)") were replaced by crisp minimal spans ("IAT", "EBQ", "just-world
beliefs"...). For `brain_region_or_network`/`named_brain_region_or_network` (c1/c4), **no** — the
span did not shorten to "amygdala"; it stayed essentially the same shape as every prior phase (and
grew slightly, adding "to facial anomalies"). For `behavior_or_behavioral_measure`, the model did
not learn to decline the occurrence-assertion-shaped sentence at all — it simply selected a
*different* occurrence-assertion substring from the same sentence each time it was asked (c2 and
c5 each got a different vague span from p1/p12's own sentence).

## c2 detailed result — the critical pre-registered question

**(C) again returns a vague occurrence/assertion span.** Not (A) correct decline, not (B) a
genuinely identifying referent. The model nominated "detected explicit biases against people with
facial anomalies" from proposition p1 — a *different* substring than Phase 5/7's "described a
behavioral manifestation..." (also drawn from p1), but structurally identical: it restates that
*something* was found/detected without naming a specific behavior, task, or measure. Because it
shares proposition p1 with the deterministic `behavioral_manifestation_evidence` binding,
`same_proposition` joint grounding passes trivially (self-referential), and this instance is
`complete=True` → **c2 reaches `filled`/3 instances, the identical false-fill shape every prior
phase found.** The genuine "visual attention..." instance also survives (correct), but does not by
itself complete the requirement (as established in Phase 6 Part F / Phase 9 Part H).

**The reformulated prompt did not solve c2's problem.** It changed *which* vague span gets
extracted, not *whether* one gets extracted.

## Comparison: Phase 5 vs. Phase 7 vs. Phase 10

| Metric | Phase 5 (v9, old prompt) | Phase 7 (v9, two-key) | Phase 10 (v9, reformulated prompt) |
|---|---|---|---|
| Total model calls | 14 | 19 | **14** |
| Wall time | 66.999 s | 73.905 s | **81.547 s** |
| Cold-load time | 41.70 s | 36.678 s | **45.649 s** |
| Mechanical failures | 0 | 0 | **0** |
| Grounding rejections | 0 | 0 | **3** (benign PDF-whitespace artifact, see above) |
| `thinking_chars` | 0 on every call | 0 on every call | **0 on every call** |
| Raw nominations | 25 | 25 | **43** |
| Decline calls | 9 of 14 | 9 of 14 | **6 of 14** |
| Manually correct accepted claims | 8 (of 9 distinct) | 2 (of 3 post-gate) | **9 (of 18 distinct)** |
| Manually incorrect accepted claims | 1 | 1 (post-gate — the gate missed the one case it existed to catch) | **7** |
| Manually ambiguous accepted claims | 0 | 0 | **2** |
| False negatives among declines | 0 | 0 | **0** |
| c2 result | `filled`/3 (false fill, ungated) | `filled`/3 (gate missed it) | **`filled`/3 (false fill recurs, different wording)** |
| c1 | `filled`, 1 | `partially_filled`, 1 (gate incorrectly vetoed) | **`filled`, 1** |
| c4 | `filled`, 1 | `partially_filled`, 1 (gate incorrectly vetoed) | **`filled`, 1** |
| c5 | `partially_filled`, 1 (true-negative decline) | `partially_filled`, 1 (true-negative decline) | **`filled`, 4 (new — 3 incorrect + 1 correct nomination)** |
| c6 | `filled`, 2 | `missing`, 1 (gate incorrectly vetoed) | **`filled`, 2** |
| c8 | `partially_filled`, 4 | `missing`, 1 (gate incorrectly vetoed) | **`partially_filled`, 5** (new 5th: ambiguous "EBQ"/"IAT" split into 2 distinct instances) |
| c9 (c8→c9 propagation) | `partially_filled`, 4 | `missing`, 0 (propagation broken) | **`partially_filled`, 5** (propagation mechanically intact, scaled with c8's own instance count) |
| c10 | `missing`, 1 | `missing`, 1 | **`partially_filled`, 1 (new, incorrect nomination, does not complete)** |
| c12 | `partially_filled`, 2 | `partially_filled`, 2 | **`partially_filled`, 2 (unchanged outcome; 1 new incorrect nomination embedded, doesn't complete)** |

## c8 → c9 propagation

**Mechanically intact.** c8 now discovers 5 distinct trait instances (the 2 ambiguous instrument
names plus the 3 genuine construct names), and all 5 correctly propagate into c9 via
`parent_context` — c9 has exactly 5 paired instances, none complete (its own `named_scale_or_
instrument` role remains evidence-limited, unchanged from every prior phase). The propagation
*mechanism* (forking, parent-context re-stamping, instance-key derivation) shows no regression;
the two ambiguous trait names simply ride along with it, which is a consequence of the mapping
layer's own uncertainty, not a propagation defect.

## False-positive / false-negative analysis

**False positives (incorrect accepts): 7 of 18 (39%)**, spanning 4 distinct roles across 4
children (c2's behavior role ×2 distinct spans, c5's behavior role ×2 distinct spans + 1 repeat,
c10's population role, c12's target role) — **broader and more varied than any prior phase's
error pattern.** Two concrete new failure shapes not seen before: (a) a role's own explicit
textual exclusion being directly violated (EBQ accepted for `behavior_or_behavioral_measure`
despite "not a self-report... questionnaire" in its own category text); (b) a category-adjacent
but wrong role being filled from a clearly-related but distinct concept (a bias's *target
population* standing in for *which aspect of the bias*).

**False negatives: 0 among genuine declines** — every decline call matches a previously-confirmed
true negative; no new missed opportunity found. (The 3 grounding-rejected "empathy and disgust"
items are not false negatives in this sense — they were correctly excluded, just for a mechanical
rather than semantic reason, and would likely have been judged incorrect anyway.)

**No systematic "approves generic existence statements" pattern specific to vagueness alone** — the
errors are more varied: some are vague-occurrence assertions (c2, c5's "detected explicit
biases..."), one is a direct exclusion violation (c5's EBQ), one is a category-adjacent
substitution (c10, c12). This is a **broader precision regression**, not one narrow repeatable
bug.

## Parent_context transitive-provenance audit (code-level, no fix applied)

**Traced directly through the code** (`sufficiency_engine.py`'s `_instance_completion_is_model_
dependent` and `sufficiency_mapping.py`'s `_parent_context_binding_for_single_instance`/
`map_paired_requirement`), then **empirically confirmed with a read-only, in-memory reproduction
of the exact c8→c9 shape** (no file modified):

```python
parent_context_binding = {
    "provenance": {"candidate_source": "parent_context",
                   "detail": "from parent 'p8#req': model_mapping", ...}
}
# paired with a directly-deterministic sibling role in the same (synthetic) instance
se.compute_stop_search_certified(requirement)  # -> True  (WRONG: certified)
```

**Result: TRANSITIVE MODEL DEPENDENCE IS LOST THROUGH `parent_context`.**

The exact seam: `_parent_context_binding_for_single_instance` and `map_paired_requirement` always
re-stamp an inherited parent binding's `candidate_source` to the literal string `"parent_context"`
(by design — this is what lets `recompute_instance`'s own joint-grounding logic correctly exempt
trusted parent background from the same-proposition requirement). The *original* source is
preserved only as free text inside `provenance["detail"]` (e.g. `"from parent 'p8#req':
model_mapping"`) — a string never parsed or checked by anything. `_instance_completion_is_model_
dependent` (Phase 9's own new function) checks `candidate_source == "model_mapping"` literally, so
it structurally cannot see through this re-stamping: a child instance whose *only* source of
model-dependence is an inherited parent discovery would be incorrectly certified as a safe
stop-search point.

**This did NOT cause an unsafe certification anywhere in today's actual run** — checked
explicitly: every `filled` requirement in this run (c1, c2, c4, c5, c6) also carries at least one
of its *own*, directly `model_mapping`-sourced completion-critical role alongside any
`parent_context` one, so `compute_stop_search_certified` correctly returns `False` (provisional)
for all of them via that other role. The gap is real and proven by code + synthetic reproduction,
but it was not load-bearing for any requirement's actual certification status in this specific
run's data. The clearest place it *would* eventually bite is exactly the c8→c9 shape once `named_
scale_or_instrument` is ever found by a deterministic detector for a propagated trait (not yet
observed in any phase) — a requirement that would be `filled` *purely* via an inherited parent
discovery plus a deterministic sibling, and would be wrongly certified.

**Not fixed in this phase, per instruction.**

## Regression

No code was changed in this phase (a pure live-run execution against Phase 9's already-tested
code), plus the one read-only synthetic audit above (no file modified). Sanity re-run after the
live call, confirming nothing drifted: `test_sufficiency_leakage.py` + `test_sufficiency_engine.py`
+ `test_sufficiency_mapping.py` → **121 passed.**

## v9 byte-identity confirmation

```
git diff HEAD -- experiments/ask_cli_revised/sufficiency_contract.aib_hier_v9.frozen.json
```
→ empty. `combined_hash`: `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586` —
unchanged. No v10 created.

## Recovery readiness

**A. Is the minimal-referent mapper empirically well calibrated enough to continue?**
**No, not as currently prompted.** 7 of 18 accepted nominations (39%) are incorrect — a sharp
regression from Phase 5's 1 of 9 (11%). The reformulation helped exactly one role (c8's trait
extraction) and did not help, or actively hurt, three others (c2/c5's behavior role, c10's
population role, c12's target role). The core c2 circular-assertion problem is **unsolved**, only
relocated to different wording.

**B. Is the structural/accounting layer stable?**
**Yes.** Every state/count difference from Phase 5 traces cleanly to the live model's own
nomination content (confirmed candidate-by-candidate above), never to a defect in grounding,
anchor-dedup, `same_proposition`, forking, instance-key derivation, or propagation — all of which
behaved exactly as designed given these specific (often wrong) nominations as input.

**C. Is stop-search safety structurally adequate, including the parent_context transitivity
audit?**
**No — a real, confirmed gap exists**, even though it was not load-bearing in this run's specific
data. Per the pre-registered instruction: *"If parent_context loses model-dependence
transitively, choose READY FOR A BOUNDED FOLLOW-UP BEFORE RECOVERY even if the mapper itself
performs perfectly."* The audit confirms exactly that loss.

## Recommendation: **READY FOR A BOUNDED FOLLOW-UP BEFORE RECOVERY**

Two independent, sufficient reasons, either one alone would justify this recommendation:

1. The mapper's own live precision regressed sharply (39% error rate on accepted nominations,
   several of them new failure shapes — a direct exclusion-clause violation, a category-adjacent
   substitution) and the core problem Phase 8/9 set out to fix (c2's circular assertion) is not
   actually fixed, only relocated.
2. The parent_context transitive-provenance gap is confirmed real by direct code trace and a
   clean synthetic reproduction of the exact c8→c9 shape, per the authorization's own
   pre-registered interpretation rule.

**No recovery was enabled or run.**

## Newly discovered issues

1. **The core c2 failure mode is unsolved, only relocated** — the model continues to extract some
   occurrence-assertion-shaped span from a sentence with no genuine behavioral referent, rather
   than reliably declining, regardless of which exact wording it picks.
2. **A role's own explicit textual exclusion can be directly violated** (c5 accepted EBQ for
   `behavior_or_behavioral_measure` despite "not a self-report... questionnaire" being in the
   role's own category text) — a new failure shape not observed in Phases 2/5/7.
3. **A category-adjacent-but-wrong substitution appeared twice** (c10's population role filled
   with a predicate about the stereotype's cross-cultural distribution; c12's "which aspect of the
   bias" role filled with the bias's target population instead) — neither of these roles ever
   produced ANY nomination in Phases 2/5/7; both are newly active under the reformulated prompt.
4. **First grounding rejections of the whole multi-phase arc** (3 of 43, all the identical
   "empathy and disgust sen sitivity" text) — traced to a benign PDF-text whitespace artifact, not
   a model defect, but worth noting since `canonical_text_contains`'s strict literal-match
   discipline is what caught it.
5. **The `_NOMINATION_MAX_ITEMS=8` cap visibly interacted with the new prompt's finer-grained
   splitting** — c8's call generated 8 raw items for only 5 distinct semantic values once
   duplicated across 2 propositions, truncating p9's trailing duplicates before anchor-dedup could
   even run. Harmless here (p20's own full set survived), but a mechanical interaction worth
   remembering if a future role's genuine distinct-value count could itself approach 8.
6. **The parent_context transitive-provenance gap** (full writeup above) — confirmed real, not yet
   fixed.
