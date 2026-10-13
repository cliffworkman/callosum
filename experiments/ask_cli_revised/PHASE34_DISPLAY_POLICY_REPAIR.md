# Phase 34 — Minimal display-policy repair before the integrated E2E

**Disposition: QUALIFIED OFFLINE. Not run live.** Two corrections to how the existing display checks are applied.
On the October 12 evidence the central amygdala finding now renders under c1 and c4, the cross-cultural
"results suggest" sentence is no longer withheld as an aim, and every must-stay-restricted example stays
restricted. No model was called, no E2E was run, the reporting contract was not touched or signed, JUNO was
not contacted.

## 1. Exact changes

| File | Change |
|---|---|
| `answer_plan/display_corrections.py` (new, 64 lines) | The two corrections as pure text functions |
| `layerc_presentation.py` | `finalize_display(..., corrected=False)` applies them when set |
| `layerc_pipeline.py` | Sets `corrected` for a fresh invocation only |
| `test_display_policy_repair.py` (new) | 7 tests on sentences taken verbatim from the sealed evidence |

The checks in `answer_plan/classify.py` and `answer_plan/text.py` are byte-identical (they are hash-pinned).
Models, DeBERTa, retrieval, sufficiency v8, Layer C authority records, plan-v5 and the renderer are unchanged.

**Correction 1 — closure is judged on the text shown.** When Layer C has narrowed a quotation to a clause, the
original sentence's `referentially_closed` failure no longer vetoes the clause, if (a) the clause itself
passes the closure check and (b) the words removed contain no negation, hedge, causal cue, or condition /
contrast word (if, unless, only, except, when, whereas, although, but, compared, than, among, between …).
Every other restriction of the original sentence still applies. The attempt records
`referentially_closed_after_narrowing` with the removed words; the original quotation and citation are
unchanged in provenance.

**An extension I had to add, for your judgment.** The first form alone did not render the finding. Layer C
gives each role value its own display span: the "evidence" value had the narrowed clause, the "named region"
value had the whole sentence, and the relational claim needs both to accept the *same* sentence. So a value
whose own sentence fails only on closure may be shown with a clause Layer C already narrowed to for another
value of the same proposition, when that clause lies inside its sentence, contains its literal, and passes
the same checks. No source, proposition or value association is added. This is slightly more than "assess
the proposed display text"; without it the amygdala statement count stays at zero.

**Correction 2 — a qualified result is not an aim.** A passage classed `aim_or_hypothesis` is reclassified
when the study's own results are the subject of a reporting verb ("results / findings / data suggest,
indicate, show …") and the passage states no aim, test or prediction as an act and carries no author-
interpretation cue ("we suggest", "we propose"). In practice this stops the bare noun "hypothesis" from
turning a result into an aim. The sentence is displayed verbatim, so "suggest" stays in the text.

**Scope of effect.** The corrections apply on the fresh (reviewed) route. The recorded Profile B
reproduction over the preserved Phase 28 evidence keeps its original behavior, so its frozen baselines and
preregistered display fixture remain exact and were not re-frozen.

## 2. Real-evidence counterfactual (October 12 sealed claims)

| Required case | Before | After |
|---|---|---|
| Central amygdala quotation (paper 67, p2/p14) | restricted: `referentially_closed` | **displayed** as "the specific amygdala response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality toward people with facial anomalies." Removed: "Across these levels of organization," |
| "results suggest the anomalous-is-bad stereotype is culturally shared, providing evidence against a universal pathogen avoidance byproduct hypothesis." (paper 68) | restricted: `attribution_aim_or_hypothesis` | **displayable**, verbatim |
| Context-dependent: "These results suggest … culturally shaped …" (paper 68) | restricted | **still restricted**: `referentially_closed`, `passage_complete` |
| Hypothesis: "This hypothesis predicts that anomalous and attractive … faces will implicate the dACC." | restricted: aim/hypothesis | **still restricted** |
| Author interpretation: "We suggest that dehumanization is underpinned by … the left amygdala." | restricted: aim/hypothesis | **still restricted** |
| Prior work: "Recent work with functional magnetic resonance imaging has implicated …" | restricted: prior work | **still restricted** |
| Truncated: Hadza result | restricted: `passage_complete` | **still restricted** |

**Counts.**

| Measure | Before | After |
|---|---|---|
| Distinct sealed sentences passing every display check (of 39) | 16 | 17 |
| Layer C values with an accepted display (of 49, replayed mapping) | 10 | 18 |
| Rendered statements in the selected answer | 5 | 7 |
| Values or statements that lost display | — | 0 |

**Newly admitted, inspected.** The one new whole sentence is the "culturally shared" sentence. All eight
newly displayable values use the single amygdala clause (roles across c1, c4, c5, c6). The two new
rendered statements are that clause under c1 and c4. Nothing else was admitted.

**What did not change.** c10 (cross-cultural) still shows no statement in the replay, because the replayed
mapping never placed the "culturally shared" sentence there; the sentence is now displayable if live
nomination maps it. c5 and c6 gain displayable values but no new statement; their relation is still marked
unestablished. Thirteen of 31 nominations remain unreplayed, as before.

## 3. Qualification

- New tests: 7 passed.
- Frozen Profile B baseline, preregistered display fixture, import allowlists, isolation hashes: pass, unchanged.
- Full offline Ask suite: 5,409 passed, 2 failed. Both are the hierarchy pin-drift tests that fail on the baseline
  commit too and in every earlier suite log. One test needing a live socket was deselected, as in every earlier run.
- `ruff format` and `ruff check` clean on the four files.

## 4. Remaining scientific risks

1. **The amygdala clause loses a scope phrase.** "Across these levels of organization" says the correlation
   held across the levels the paper had just described. The displayed clause states the correlation without
   it. Nothing false is asserted, and the full quotation remains in provenance, but a reader of the answer
   alone does not see that scope. "The specific amygdala response" also leans slightly on preceding text.
2. **The material-word test is lexical.** It refuses narrowing when the removed words contain a listed cue.
   A condition expressed without one of those words would pass. On this evidence exactly one narrowing was
   admitted and I read it.
3. **"Results suggest X may cause Y" would now be classed as a study result.** It is shown verbatim with
   its hedge, so nothing is promoted in the text, but the plan's attribution label is `this_study_result`,
   not a separate "tentative" label. I did not add one, to avoid a new classifier.
4. **The extension in section 1** shares a narrowed clause between values of one proposition. It is bounded
   and recorded, but it is my reading of the instruction rather than its letter.
5. **Validated on one question's evidence.** The frozen Phase 28 set is deliberately unaffected, so it gives
   no second check of the new behavior.
6. Hadza stays blocked by truncation at the chunk boundary; prior-work amygdala evidence stays blocked. Both
   are as you specified.

## 5. Is the corrected integrated E2E ready?

The code is. The run is not started and still needs, from you:

1. Your review of `q_aib.reporting.json` and your own `q_aib.review.json`.
2. E2E and JUNO authorization, and the thermal choice: I will use automatic stop (CPU 88 °C, GPU 80 °C)
   unless you say alert-only.

Configuration unchanged: Qwen3.5-9B, Phi-4:14B, Gemma 3:12B, DeBERTa at 0.50, recovery reuse off.

Counterfactual script and records: `.local/phase34-regression-forensics-20261012/d2_before_after.py`,
`p1_reviewed_route_assist.BEFORE.json`, `p1_reviewed_route_assist.json`.
