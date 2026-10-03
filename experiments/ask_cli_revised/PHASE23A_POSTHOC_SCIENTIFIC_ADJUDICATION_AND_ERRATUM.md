# Phase 23a — read-only post-hoc evidence erratum + scientific adjudication

Authorized by Cliff Workman, 2026-10-03, immediately after "Phase 23 infrastructure result
accepted." **This is not an implementation phase.** No production code change, no live model call,
no network retrieval, no rerun, no new recovery round, no prompt/contract change. Every number and
adjudication below is read directly from the single, already-frozen Phase-23 run artifacts.

- **Phase-23 run id (unchanged, re-cited):** `phase23-live-recovery-targeted-u2-remap-validation-20261003T020939Z`.
- **Source artifacts used:** `phase23_result.json`, `run/18_sufficiency_model_assist.json`,
  `run/11_verified_ledger.json`, `run/17_sufficiency_map.{initial,}.json`, plus the frozen v9
  sufficiency contract (`sufficiency_freeze.load_verified()`) for role `category_description`/
  `mapping_strategy`/`role_completion` lookups.
- **No-live/no-network/no-rerun confirmation:** every command run for this pass was a local,
  read-only `python -c`/script invocation against the files above; no `OllamaClient`, no
  `requests`/`httpx` call, no `execute()`/`resolve_nomination()` invocation anywhere in this pass.
  This document preserves the original Phase-23 result unmodified; this is an **additive** artifact.

## 1. Call-accounting erratum — verified mechanically, not assumed

Confirmed by direct re-read of `resolve_nomination`'s own docstring and code
(`sufficiency_model_scope.py:292-299`): **"when `scope` IS authorized for a fresh call but
`candidate_rows` is empty, `make_fresh_call` is never invoked at all."** `fresh_no_candidates` is
checked *before* `make_fresh_call`, mechanically, not inferred from an empty `candidates_offered`
after the fact. This means `fresh_no_candidates` keys are authorized, reached, and reconsidered —
but produce **zero** physical model inference calls, exactly as Phase 23a's brief predicted.

Re-deriving the full status table directly from `18_sufficiency_model_assist.json`'s raw receipts
(not from the Phase-23 report's own prose):

| | U1 | U2 |
|---|---|---|
| `fresh` (physical model call made) | 10 | **17** |
| `fresh_no_candidates` (authorized, reached, zero candidates, **no call**) | 3 | **2** |
| `fresh_failed_fallback_to_prior` | 0 | 0 |
| `fresh_failed_no_valid_prior` | 0 | 0 |
| `held_fixed_replay` | 0 | 4 |
| `held_fixed_no_valid_prior` | 0 | 0 |
| `memoized_in_pass` | 0 | 0 |
| **Total fresh-status keys (authorized + reached)** | 13 | **19** |
| **Actual physical model inference calls** | 10 | **17** |

Sanity-checked mechanically: every `fresh_no_candidates` receipt has `len(candidates_offered) == 0`;
every `fresh` receipt has `len(candidates_offered) > 0`. No exception anywhere. **Zero
`fresh_failed_*` statuses occurred in either pass** — every attempted physical call succeeded
mechanically (no transport/parse failure this run).

### Corrected claim

The Phase-23 report's "19 actual physical U2 fresh-attempt calls" is **wrong terminology**. The
correct statements are:

- **|F| = 19** (the independently-recomputed projected fresh-request set, unchanged from Phase 23).
- **Fresh-status keys exercised (authorized + reconsidered) = 19** — exactly `|F|`, confirming the
  **stronger locality result still holds**: zero fresh-authorized keys outside F, zero F members
  omitted from the fresh-status set.
- **`fresh_no_candidates` = 2** (authorized, reconsidered, zero candidates, no inference call).
- **Actual physical model inference calls (`qwen3.5:9b` invocations) = 17.**

The corrected infrastructure claim is: **the actual fresh-authorized/reconsidered key set exactly
equals F** (set equality, 19 = 19) — **not** "the physical model call set equals F." Of F's 19
members, 17 triggered a real inference call and 2 were authorized-but-starved (reached the fresh
path, found nothing to offer the model, and correctly recorded that as a distinct, inspectable
outcome rather than silently skipping it).

No raw historical trace data was altered. `18_sufficiency_model_assist.json`'s own `fresh_request_
count` field (in `stage_log.json`'s `U2` entry, value 19) already counted **F/fresh-status slots**,
not physical calls — its existing meaning is documented here, not renamed.

## 2. Infrastructure verdict — unchanged

The terminology correction does not touch the underlying guarantee. Fresh-status key set (19) ==
F (19) exactly; physical calls occurred only for the 17 callable (nonempty) members of F. **Phase
23's infrastructure PASS verdict is unchanged.** 19 authorized keys producing 17 actual inference
calls is expected, correct behavior (`fresh_no_candidates` is a first-class, designed-for outcome,
not a shortfall).

## 3. Scientific nomination adjudication

**Scope and denominator.** The brief asks for every grounded/accepted U2 nomination from the frozen
run. Two overlapping sets exist in the final U2 pass's own accepted content:

- **25 raw accepted items** from the **17 physical** (newly-made) U2 calls — the new information
  this run's own fresh reconsideration produced.
- **5 additional accepted items** carried forward via `held_fixed_replay` (unchanged from U1, but
  still part of the final U2-pass semantic map: `c8`'s `U6` context, 4 items; `c5`'s
  `named_brain_region_or_network`, 1 item).

All **30** are adjudicated below for completeness, labelled by source. **Denominator note (brief
§6):** every one of the 30 rows is a distinct `(requirement, role, request_context, proposition_id,
exact_text)` tuple — **no row is a literal repeat of another row.** Apparent repetition (the same
`proposition_id` appearing under several rows) is **cross-requirement reuse of shared evidence**,
never the same decision counted twice — detailed in §3b.

### 3a. Adjudication table

| # | Source | child/req/role/ctx | proposition_id | exact_text | Verdict | Reason |
|---|---|---|---|---|---|---|
| 1 | physical | c1 / neural-manifestation / brain_region_or_network | p11 | "the specific amygdala" | **Correct** | Verbatim-grounded, cleanly names the amygdala. |
| 2 | physical | c1 / same / same | p26 | "bilateral fusiform" | **Correct** | Verbatim in p26's own quote. |
| 3 | physical | c1 / same / same | p26 | "bilateral amyg- dala" | **Correct** | Verbatim (matches the source's own PDF-hyphenated rendering). |
| 4 | physical | c1 / same / same | p26 | "right hippocampus" | **Correct** | Verbatim. |
| 5 | physical | c1 / same / same | p26 | "right latOFC" | **Correct** | Verbatim; a specific named region (lateral OFC). |
| 6 | physical | c1 / same / same | p26 | "right VS" | **Correct** | Verbatim (ventral striatum). |
| 7 | physical | c1 / same / same | p26 | "right superior occipital cortex" | **Correct** | Verbatim. |
| 8 | physical | c4 / specific-region / named_brain_region_or_network | p26 | "bilateral fusiform" | **Correct** | Same passage, same verdict as #2. |
| 9 | physical | c4 / same / same | p26 | "bilateral amyg- dala" | **Correct** | — |
| 10 | physical | c4 / same / same | p26 | "right hippocampus" | **Correct** | — |
| 11 | physical | c4 / same / same | p26 | "right latOFC" | **Correct** | — |
| 12 | physical | c4 / same / same | p26 | "right VS" | **Correct** | — |
| 13 | physical | c4 / same / same | p26 | "right superior occipital cortex" | **Correct** | — |
| 14 | physical | c4 / same / same | p26 | "left IFG" | **Correct** | Verbatim; c4's own call extracted 2 regions c1's call did not. |
| 15 | physical | c4 / same / same | p26 | "bilat- eral IPS" | **Correct** | Verbatim. |
| 16 | physical | c10 / culture-existence / named_culture_or_population | p36 | "Hadza" | **Correct** | Verbatim-named population, directly on-topic. |
| 17 | physical | c10 / same / same | p69 | "Hadza" | **Correct** | Same population, near-duplicate source text (see §3b). |
| 18 | physical | c11 (ctx U21) / culture_or_population | p36 | "Hadza" | **Correct** | Independently correct re-identification for a different requirement. |
| 19 | physical | c11 (ctx U21) / same | p69 | "Hadza" | **Correct** | — |
| 20 | physical | c12 (ctx U18) / intervention | p33 | "the anomalous faces variant of the NAME intervention" | **Correct** | Verbatim-named intervention, directly on-topic for the anomalous-is-bad hierarchy. |
| 21 | physical | c12 (ctx U18) / target_manifestation | p33 | "bias toward people of color" | **Incorrect** | The source sentence names TWO bias types in contrast: the intervention *reduced* "bias against people with anomalous faces" and left "bias toward people of color" **unchanged**. The nominated value is the bias the intervention did **not** affect — the wrong half of the contrast. |
| 22 | physical | c12 (ctx U30) / intervention | p45 | "scalable real-world inoculation interventions" | **Incorrect** | Not a *named* intervention (generic plural noun phrase); the proposition's own canonical text names the actual intervention as "the adaptation of the Bad News game." Compounded by a likely off-topic source (see §4, p45). |
| 23 | physical | c2 / behavioral-manifestation / behavior_or_behavioral_measure | p47 | "decisions that were incongruent with behavioral bias (share with bad partner and keep with good partner versus the alternative choices)" | **Correct** | A genuine behavioral-choice task, verbatim-grounded, matches the (non-self-report) category exactly. |
| 24 | physical | c2 / same / same | p58 | "participants made more share decisions overall when playing with the good partner than with the bad" | **Correct** | A behavioral outcome measure. |
| 25 | physical | c2 / same / same | p59 | "participants were faster to share when playing with the good partner compared to the bad" | **Correct** | A behavioral (reaction-time) measure. |
| 26 | held-fixed | c8 / trait-construct / individual_difference_trait_or_construct (U6) | p20 | "negative attitudes (IAT and EBQ)" | **Correct** | A named trait/construct with its measurement instruments. |
| 27 | held-fixed | c8 / same | p20 | "social cognitive biases (just-world beliefs)" | **Correct** | "Just-world beliefs" is a well-established individual-difference construct. |
| 28 | held-fixed | c8 / same | p20 | "emotional dispositions (affective empathy)" | **Correct** | A recognized trait construct. |
| 29 | held-fixed | c8 / same | p20 | "undesirable behaviors (less generosity in the DG)" | **Incorrect** | Category-boundary violation: the source's own four-item list explicitly separates three trait/construct items from a fourth, *behavioral* item ("undesirable behaviors"). The role requires "a named individual-difference **trait or construct**," not a behavior — this item belongs under a behavior-category role (c2/c5), not c8. |
| 30 | held-fixed | c5 / brain-behavior / named_brain_region_or_network | p11 | "the specific amygdala response to facial anomalies" | **Ambiguous** | Correctly identifies the amygdala, but the extracted span bundles in outcome language ("response to facial anomalies") beyond a clean "named brain area" — imprecise rather than wrong. |

### 3b. Verdict tallies

| | Correct | Incorrect | Ambiguous | Total |
|---|---|---|---|---|
| 25 new physical-call items | 23 | 2 | 0 | 25 |
| 5 held-fixed-but-present items | 3 | 1 | 1 | 5 |
| **All 30** | **26** | **3** | **1** | **30** |

**Duplicate/fork representation (brief §6), resolved explicitly:** 9 unique `proposition_id`s
underlie the 25 physical-call items (10 across all 30, adding `p20`). `p26` feeds 14 of the 30 rows
(6 under `c1`, 8 under `c4`) — **not** 14 independent facts counted once each nor a forking
artifact: it is **one** verified passage naming up to 9 distinct brain regions, independently
re-extracted by **two different requirements** (`c1`, `c4`) asking closely related but distinct
questions. `p36`/`p69` each feed 2 rows (`c10` and `c11`) — the same real-world fact ("Hadza"),
independently and correctly recognized by two different requirements. `p33` feeds 2 rows under two
different **roles** of the same requirement (`intervention`, `target_manifestation`) — two different
semantic extractions from one shared sentence, not a repeat. **No row represents the identical
`(requirement, role, proposition_id, exact_text)` decision as another row** — the scientific-quality
denominator above (30, or 25 restricted to new calls) is not inflated by representation multiplicity.

## 4. Recovery-evidence adjudication

Cross-referencing each accepted-nomination's source `proposition_id` against its own
`provenance.origin` field in `11_verified_ledger.json` separates **pre-existing** evidence
(`origin: "initial"`, already present before recovery ran) from **genuinely new** recovery-discovered
evidence (`origin: "recovery"`).

| proposition_id | origin | recovered via (`request.source_unit_id`) | adjudication (relative to its own triggering target) | rationale |
|---|---|---|---|---|
| `p11` | **initial** | — (pre-existing, not recovered) | n/a | Already in the W1-only ledger; recovery contributed nothing new here. |
| `p20` | **initial** | — | n/a | Same. |
| `p26` | recovery | `c4` | **Directly addresses** | c4's own missing `named_brain_region_or_network` target; the recovered passage is exactly on-topic. |
| `p36` | recovery | `c10` | **Directly addresses** | c10's own missing `named_culture_or_population`/`bias_evidence_in_population` targets. |
| `p69` | recovery | **`c6`** | **Unrelated / retrieval miss (for c6's own triggering gap)** | c6's own recovery search (for brain-attitude/implicit-explicit evidence) instead surfaced a culture/population passage with no bearing on c6's actual roles. Safely contained — nothing was asserted for c6 from it — but serendipitously reused by `c10`/`c11`, whose requirements it does genuinely satisfy. |
| `p33` | recovery | `c12` | **Directly addresses** | On-topic, high-quality: names a real intervention and its measured effect on the hierarchy's own target bias. |
| `p45` | recovery | `c12` | **Unrelated / retrieval miss** | Describes a COVID-19 misinformation-inoculation study (the "Bad News" game) — a different phenomenon from the "anomalous is bad" facial bias this entire contract is about. A likely keyword-level ("inoculation intervention") retrieval false-positive. |
| `p47` | recovery | `c2` | **Directly addresses** | A genuine behavioral-choice task, on-topic for c2. |
| `p58` | recovery | `c5` | **Directly addresses `c2`'s category; structurally excluded from `c5`'s own relational requirement** | `c5#suff:brain-behavior` is `kind: relational` with `relationship_verifiers: ["same_proposition"]` — a candidate must jointly name a brain region AND a behavior in the *same* proposition. `p58` is behavior-only, so it is correctly excluded from `c5`'s own candidate pool (never reaches the model for `c5`), while it correctly *does* satisfy `c2`'s simpler, non-relational behavior-only requirement. Not a retrieval miss — a correct cross-requirement repurposing. |
| `p59` | recovery | `c5` | Same as `p58` | — |

**8 of 10 propositions feeding the 30 adjudicated nominations are genuinely new, recovery-discovered
evidence; 2 (`p11`, `p20`) were already present before recovery ran** and merely got re-offered
(and, for `p11`, re-nominated with a cleaner span) in the wider post-recovery candidate pool.

## 5. Target → recovered evidence → U2 pathway

| Pathway | Case |
|---|---|
| **A — useful recovery + useful nomination → semantic improvement** | `c4` (p26, all 8 correct); `c10`/`c11` culture half (p36/p69, both correct); `c2` (p47/p58/p59, all correct). |
| **B — useful recovery + bad/ambiguous nomination → evidence success, interpretation problem** | `c12`'s U18 context: p33 is excellent, on-topic evidence; the `intervention` extraction from it is correct, but the `target_manifestation` extraction from the *same* sentence picked the wrong half of a two-part contrast. |
| **C — weak recovery + model rejection/non-acceptance → retrieval miss safely contained** | `p69` relative to `c6`'s own triggering gap (no false assertion resulted); `c11`'s `operationalization_or_measure` role (offered candidates at both `U10` and `U21`, zero accepted at either — no incorrect value was forced). |
| **D — weak recovery + model acceptance → concerning semantic failure** | `c12`'s U30 context: p45 is off-topic (different bias phenomenon entirely), and the model nonetheless accepted a generic, non-"named" `intervention` value from it. The single most concerning finding in this adjudication. |
| **E — useful deterministic/structural evidence → improvement without a fresh model nomination** | `c6`'s 8 new `partially_filled` instances — pure `parent_context_roles` propagation of `c4`'s already-verified brain-region fills; no new nomination call for c6 itself. |
| **F — recovery created a new instance/context but remained incomplete** | `c11`'s `U21` context (culture filled, measure still empty); `c10`'s two new post-recovery instances (population named, `bias_evidence_in_population` still only "partial" — plausibly the `hedged` disqualifying guard correctly declining the passage's own "were more likely to" phrasing, though the guard's exact logic was not independently re-derived here). |

## 6. Structural vs. scientifically-supported coverage

Structural facts (unchanged from Phase 23): `filled` 2→4, `partially_filled` 4→7, `missing` 7→2.
Identifying the exact 5 requirement-level state transitions (direct per-requirement diff, not
inferred): **`c4` and `c12`: missing→filled; `c10`, `c11`, `c6`: missing→partially_filled.**

| Requirement | Transition | Caused by | Scientifically supported? |
|---|---|---|---|
| `c4` | missing → **filled** | Fresh U2 nomination, 8/8 correct (pathway A) | **Yes — fully supported.** |
| `c12` | missing → **filled** | Fresh U2 nomination at `U18`: 1 correct (`intervention`) + 1 incorrect (`target_manifestation`) (pathway B) | **Questionable.** The structural "filled" state rests on one of its two role values being wrong. |
| `c10` | missing → partially_filled | Fresh nomination (culture, correct) + an unresolved deterministic role (pathway F) | **Partially supported** — the filled half is correct; the still-missing half may be a correctly conservative guard, not a clear defect. |
| `c11` | missing → partially_filled | Fresh nomination (culture, correct) + an honestly empty measure role (pathway F) | **Supported** — an honest partial reflecting a genuine evidentiary gap, not an error. |
| `c6` | missing → partially_filled | Pure structural propagation (pathway E), zero fresh nomination of c6's own roles | **Supported** — nothing fabricated; correctly shares already-verified content while leaving c6's own unaddressed role honestly unfilled. |

**STRUCTURAL COVERAGE:** 5 transitions, missing 7→2.
**SCIENTIFICALLY SUPPORTED IMPROVEMENT:** 4 of 5 transitions (`c4`, `c10`, `c11`, `c6`) rest on
correct or honestly-partial grounds.
**QUESTIONABLE IMPROVEMENT:** 1 of 5 (`c12`) — reported `filled`, but one of its two defining role
values is a confirmed incorrect nomination (#21 above). This is not collapsed into a single score;
it is named explicitly as the one transition warranting a closer look before treating "`c12`
filled" as a clean win.

## 7. Persisted targets (6) — why each remains unresolved

| Target | Classification |
|---|---|
| `c3::0ff295b8` (`category_evidence`, "implicit" instance) | Retrieval found nothing relevant even after recovery. |
| `c6::90646ddc` / `c6::efad0cb3` (`category_evidence`, "implicit"/"explicit" instances) | Same — no candidate evidence found for either instance across the whole run. |
| `c5::22fa1417` (`behavior_or_behavioral_measure`, partial) | Evidence existed and was recovered (`p58`/`p59`), but `c5`'s own `same_proposition` relational guard correctly excluded it (behavior-only evidence cannot satisfy a joint brain+behavior requirement) — "evidence existed but the role mapper correctly declined it," not a retrieval failure. |
| `c8::2319dd98` (`individual_difference_trait_or_construct`, missing-scope) / `c8::74f276a2` (`relationship_to_bias_manifestation`, missing) | Sibling role remained starved: the trait role has 4 real accepted values (`U6`), but `relationship_to_bias_manifestation` never received a single candidate, even after recovery, so the requirement never reaches `complete`. |

## 8. New targets (27) — high-level character

Dominated by **legitimate newly exposed obligations from richer evidence**, not fragmentation for
its own sake: `c4`'s 8 new `provisional_corroboration` targets and `c6`'s 8 new `partial` targets
together account for 16 of the 27, but both trace back to just **two** underlying real
discoveries (`p26`'s 8 regions; their structural propagation into `c6`) — the per-instance tracking
is the architecture's intended "no silent merging" behavior, correctly giving each distinct named
region its own reviewable instance rather than collapsing them. `c11`'s 4 new targets and `c10`'s 2
new targets reflect the same pattern at smaller scale. `c2`'s 3 new `relationship_unverified`
targets are a genuinely new obligation class, created because `c2` now has multiple accepted
behavioral instances whose joint grounding with the bias's own manifestation has not yet been
separately verified — a real, newly-exposed scrutiny need, not noise. **No suspicious target
explosion was found**; the raw count (27) somewhat overstates the number of independently-discovered
facts (closer to 6-8 genuinely new findings, forked into per-instance targets), but every fork
traces to real, distinct evidence content, not duplication.

## 9. c8 / c11 / c12 scientific read

- **c8:** The trait role (`individual_difference_trait_or_construct`) is genuinely filled — 3 of its
  4 accepted values are scientifically correct named constructs; the 4th (#29) is a category-
  boundary error (a behavior mislabeled as a trait). The sibling `relationship_to_bias_manifestation`
  role remains entirely starved. **Was withholding completion scientifically appropriate?** Yes —
  even setting the one mislabeled item aside, naming traits is not the same as establishing their
  *relationship* to the bias's manifestation, which this evidence set never supplies. The
  architecture's refusal to call `c8` complete is correct, not overly conservative.
- **c11:** Recovery materially improved the *culture* half (Hadza correctly identified in two
  independent contexts) but contributed nothing to the *operationalization/measure* half across
  either context. **Did recovered evidence meaningfully improve coverage?** Partially — one half of
  a paired requirement, not the whole pairing. The honest `partially_filled` state is the correct
  characterization; treating this as a win on "culture or operationalization pairing" as a whole
  would overclaim.
- **c12:** Recovery created four genuinely distinct contexts. One (`U18`) corresponds to real,
  coherent intervention/effectiveness evidence (confirmed correct `intervention` and recovered,
  on-topic text) undermined by one mis-extracted role value; two (`U19`, `U28`) accepted nothing
  either way (safely inert); one (`U30`) is a mechanically valid partition built on topically
  off-target evidence that nonetheless produced an accepted (and incorrect) value. **Verdict:** the
  four contexts are mechanically valid partitions, but only one (`U18`) corresponds to evidence that
  is both on-topic and substantially correct — `U30` is the adjudication's clearest concern.

## 10. One-round recovery — scientific usefulness

Recovery materially advanced coverage with mostly-correct evidence (pathways A/E dominate: `c4`
fully correct, `c2` fully correct, `c10`/`c11`'s culture half correct, `c6`'s propagation clean).
Against that, two concrete failure modes surfaced in this single round: **(1)** a correct-intervention/
wrong-target-manifestation pairing (`c12`/U18, pathway B) and **(2)** a topically off-target recovered
passage that the model nonetheless accepted a (weak) value from (`c12`/U30, pathway D). Both are
concentrated in `c12` specifically — the requirement discovered entirely by recovery this run, with
no U1 baseline to anchor it. **Verdict: one recovery round is scientifically useful on the evidence
examined here (the architecture surfaces, rather than hides, both its successes and its two real
failure cases) — but `c12`'s "filled" state should not be read as a clean certification without the
caveat recorded in §6.**

## 11. Newly discovered issues

1. **`c12`'s U18 `target_manifestation` nomination is a confirmed scientific error** (picks the
   unchanged half of a stated contrast). Not a Phase-22/23 infrastructure defect — a model-nomination
   quality issue, now on record.
2. **`c12`'s U30 context rests on likely off-topic recovered evidence** (a COVID-19
   misinformation-inoculation paper, not an anomalous-is-bad-bias intervention study) that the model
   nonetheless partially accepted from. Worth a closer look at the recovery query/retrieval ranking
   for `c12` specifically before relying on this contract/evidence combination for a scored benchmark
   run.
3. No issue found requires a runtime, prompt, or contract change — per the brief's own instruction,
   none is proposed here.

## 12. Phase 24 readiness

**Phase-23's infrastructure PASS stands, unchanged, with corrected terminology.** This adjudication
adds a scientific-quality caveat on exactly one transition (`c12` filled) and one concerning pathway
(`c12`/U30) — both isolated to the newly-discovered `c12` requirement, not to the recovery/remap
mechanism itself, which performed exactly as designed (correct locality, correct held-fixed
replay, correct honest-unresolved reporting, correct structural propagation). **Phase 24 production-
route activation readiness: READY for the mechanism**, with the explicit recommendation that any
broader E2E gate (per Cliff's own Phase-23 framing, under T5/production P) include a closer look at
`c12`'s own recovery-query construction, since this is the one requirement this adjudication found a
real, concrete semantic weakness in.
