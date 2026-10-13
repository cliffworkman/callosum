# Phase 34 — Pre-E2E diagnostic: why established amygdala evidence is not displayed

**Disposition: INTENDED CONTRACT, NOT A DEFECT. No code changed. Stopped for your decision.** The integrated
route establishes the amygdala finding and then declines to display it because of a deterministic
presentation rule, `referentially_closed`, that has been in the answer plan since Phase 30 and was known
then to suppress this exact sentence. The incomplete replay does not explain it. On the October 12 evidence
no amygdala sentence can be displayed by the integrated route, whatever the mapping does.

No model was called, no E2E was run, the reporting contract was not signed, JUNO was not contacted.

## 1. One finding traced

| Step | Record |
|---|---|
| Source | Paper 67, "Morality is in the eye of the beholder: the neurocognitive basis of the 'anomalous-is-bad' stereotype" (2021), chunk 34974, span e7, p. 1 |
| Quotation (verified exact) | "Across these levels of organization, the specific amygdala response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality toward people with facial anomalies." |
| Verified claims | p2 (child c1) and p14 (child c4); DeBERTa support 0.99 |
| v8 sufficiency mapping | c4 `specific-region`: **filled**. Role `named_brain_region_or_network` = "the specific amygdala response"; role `region_bears_on_bias_evidence` filled from the same passage |
| Layer C value coverage | `scientific_goal_state: established`; 2 authorized display sources (p2, p14); 2 citation sources |
| Display finalization | `display_state: restricted`; 2 attempts, 0 accepted |
| Reason on both attempts | `referentially_closed` |
| Plan-v5 facet | `map_requirement_state: filled`, `scientific_goal_state: established`, `reported_value_refs: []` |
| Rendered line | "An evidence-supported value cannot be displayed with an authorized quotation here; this is a presentation limitation, not scientific absence." |

So the quotation was available, authorized and cited. It was rejected at one place:
`layerc_presentation.finalize_display` → `answer_plan.classify.evaluate_sentence` →
`answer_plan.text.closure_failures`.

**The exact condition.** Two patterns in `answer_plan/text.py` match the sentence:

- `scope_phrase_refers_outside`: a sentence opening with *Across / Within / Among / In / For / Throughout*
  followed by *these / this / those*.
- `anaphor_in_sentence`: "this" or "these" followed by one of *research, study, work, paper, findings,
  levels, results, effect(s)* anywhere in the sentence.

Layer C does narrow the display span to the clause after the comma, and the narrowed clause passes those two
patterns. The finalizer then re-applies the checks to the original sentence and combines them
("can only remove permission"), so the restriction stands. That step is deliberate and commented as such.
Removing the opening phrase would not help in any case: a sentence beginning "The specific …" matches a
third pattern, `pronoun_or_anaphor_opener`.

**This was known.** `PHASE30_DETERMINISTIC_ANSWERPLAN_RESULTS.md` records the same sentence as "suppressed:
referentially_closed" and explains: it opens with "Across these levels of organization," the retrieved text
does not identify those levels, and "Step 1 does not repair the anaphor, because the brief forbids editing
meaning. Node 4 is therefore not established."

**c1 fails the same way** (same passage, same reason), so I did not trace it separately.

**The other amygdala sentences are blocked by different rules of the same check set:**

| Sentence | Rule | Why |
|---|---|---|
| "Laypersons with high levels of implicit bias … demonstrated increased amygdala reactivity.6" (paper 61) | `attribution_prior_work` | It reports another study's result; only the citing study's own results are displayed |
| "… particularly the amygdala" (paper 61 discussion) | `passage_complete`, `attribution_prior_work` | Truncated passage, prior work |
| "We suggest that dehumanization is underpinned by … all factors associated with the functioning of the left amygdala." (paper 67) | `attribution_aim_or_hypothesis` | "We suggest" is classed as an aim or hypothesis |

## 2. Replay artifact or genuine behavior

Genuine. The decision is made on a value that *was* established and *did* have authorized sources; the
missing 13 nominations and the missing recovery state do not enter it. The check reads only the sentence
text and its passage.

To size the effect without the mapping at all, I applied the same display checks to every distinct sentence
in the 64 sealed claims:

| | Sentences |
|---|---|
| Distinct sealed sentences | 39 |
| Pass every display check | 16 |
| Blocked by at least one | 23 |
| … `attribution_unknown` | 8 |
| … `passage_complete` (truncated) | 7 |
| … `referentially_closed` | 5 |
| … `attribution_prior_work` | 5 |
| … `attribution_aim_or_hypothesis` | 5 |

By finding:

| Finding | Can the integrated route display it? |
|---|---|
| Amygdala (all four sentences) | **No** |
| Hadza result | **No** — cut mid-sentence, fails `passage_complete` |
| "Culturally shared" / "culturally shaped" | **No** — "results suggest" is classed as aim or hypothesis |
| NAME intervention reduced implicit bias | Yes, if the mapping fills the role |
| Explicit Bias Questionnaire sentence | Yes (it is displayed in the preview) |
| Share decisions and reaction times | Yes (displayed in the preview) |
| dACC "may track beauty" | Yes, if mapped |

**What remains uncertain,** and cannot be settled without the model: which of the 16 displayable sentences
the mapping will actually place, since 13 of 31 nominations had no replay. That affects the intervention and
behavior parts. It does not affect the brain or cross-cultural parts.

## 3. Repair

**None made.** This is the intended contract of the answer plan, not a wiring error: the rule is explicit,
documented, tested, and was applied to this sentence on purpose. Changing it is a scientific-policy
decision, which this assignment reserves to you.

The specific restrictions, for that decision:

1. **`referentially_closed`.** Blocks any sentence that opens with a scope phrase or contains "these
   levels / this study / these results" and similar. Purpose: do not present a sentence whose meaning
   depends on text the reader cannot see. Cost here: the run's central brain finding, whose claim is
   intelligible without the phrase.
2. **Re-applying the original sentence's checks after Layer C narrows the display span.** This is what
   defeats the narrowing for this sentence.
3. **`attribution_prior_work`.** Blocks a paper's report of earlier findings. Cost here: the second amygdala
   finding.
4. **`attribution_aim_or_hypothesis` triggered by "suggest".** Cost here: the cross-cultural conclusion and
   the left-amygdala sentence.
5. **`passage_complete`.** Blocks truncated passages. Cost here: the Hadza result. The underlying fault is
   the chunk boundary, not this rule.

All five were built and qualified against the preserved Phase 28 evidence and synthetic cases. None has
been observed improving a live answer.

## 4. The q_aib reporting contract

File: `.local/e2e-runs/phase34-integrated-reviewed-e2e/inputs/q_aib.reporting.json`. Not signed; no review
record was created.

| Node | Parent | Owns | Text (identical to the approved child wording) |
|---|---|---|---|
| c1 | — | c1 | how does the anomalous is bad bias manifest in brain |
| c2 | — | c2 | how does the anomalous is bad bias manifest in behavior |
| c3 | — | c3 | how does the anomalous is bad bias manifest in attitudes |
| c4 | — | c4 | Please return the specific brain areas in which the anomalous-is-bad bias manifests. |
| c5 | c4 | c5 | In the context of the anomalous is bad bias, please return whether and how specific brain areas relate to behaviors, which kinds of behaviors |
| c6 | c4 | c6 | In the context of the anomalous is bad bias, please return whether and how specific brain areas relate to attitudes, and which kinds of attitudes. |
| c8 | — | c8 | what kind of specific personality traits relate to the anomalous is bad bias's manifestation? |
| c9 | c8 | c9 | which scales measure the specific personality traits that relate to the anomalous is bad bias's manifestation? |
| c10 | — | c10 | is there any cross-cultural evidence for the anomalous is bad bias? |
| c11 | c10 | c11 | in which cultures is there evidence for the anomalous is bad bias, and how was the anomalous is bad bias measured in each? |
| c12 | — | c12 | are there effective interventions aimed at reducing the anomalous is bad bias? |

`scientific_only_child_ids: []`, `requested_construct_terms: []`.

**Checked mechanically against the approved hierarchy:**

- Eleven nodes for eleven approved children, in the hierarchy's own order. None missing, none added.
- Every node's text equals the approved child wording, and its hash equals the hierarchy's recorded
  `wording_sha256`.
- Every parent equals the hierarchy's parent.
- Each node owns exactly its own child; no child is hidden as scientific-only.

**Assessment.** It introduces no requirement, suppresses no approved question and changes no child's
wording. It is a one-to-one projection of the hierarchy.

**Points for your independent review:**

1. **There is no c7.** The hierarchy folds c7 into c8 (`c8.folded = ["c7"]`). The reporting contract
   inherits that; it does not create it.
2. **Three children carry non-final statuses in the hierarchy itself:** c9 and c11 are
   `pending_researcher_confirmation`, c4 is `researcher_supplied`. They ran in both earlier E2Es. Signing
   the review does not resolve those statuses.
3. **`requested_construct_terms` is empty.** The plan uses these terms in one display check. Empty means
   that check adds no restriction. Adding terms would add one.
4. **The original question does not appear as a node.** Plan-v5 renders the eleven parts and no parent
   node, so the selected answer has no overview of its own. That is how the plan is built, not a choice made
   in this file.

## 5. Blockers to an informative three-model E2E

1. **A decision on the display rules above.** Without one, the run will very likely report "cannot be
   displayed" for both brain parts and "not established" or a limitation for both cross-cultural parts.
   That would confirm this diagnostic at the cost of a full run. With the rules left as they are, the
   informative parts of the run are narrower: whether live nomination under v8 fills the intervention,
   behavior and trait parts, and how the child syntheses compare with the plan-v5 answer on the same evidence.
2. **Your review of the reporting contract.** The route will not start without `q_aib.review.json`.
3. **JUNO thermal protection: a choice to make, not a current state.** Nothing of mine is running there; both
   monitor units from October 12 were stopped. Two scripts exist: `watch.sh`, which stops Ollama
   automatically at CPU 88 °C or GPU 80 °C, and `watch_alert_only.sh`, which was swapped in during attempt 2
   on your instruction. With automatic stop, attempt 1 was stopped at 88 °C; with ice packs attempt 2 peaked
   at 87 °C. I will start the next run with **automatic stop** unless you tell me otherwise, and I will not
   start it alert-only without your saying so.

Configuration is unchanged and as planned: Qwen3.5-9B, Phi-4:14B, Gemma 3:12B, DeBERTa at 0.50, recovery
reuse off.

Diagnostic script: `.local/phase34-regression-forensics-20261012/d1_display_rules.py`; decision records are
in `p1_reviewed_route_assist.json` (`value_coverage` → `attempts`).
