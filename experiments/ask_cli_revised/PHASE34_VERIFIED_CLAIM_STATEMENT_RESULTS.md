# Phase 34 — Verified claims restored to the scientific answer

**Disposition: QUALIFIED OFFLINE. Not run live.** The reviewed answer now states the sealed, verified claim and
puts the source's own sentence directly beneath it. No model was called, no E2E run, the reporting review was
not touched, JUNO was not contacted. Two things you should know before anything else:

1. **About one claim in six is materially unfaithful to its quotation** (10 of 64). I did not treat that as
   grounds to stop, because the project's existing rephrasing screen rejects 8 of the 10 and none of the 10
   reaches the answer in the offline replay. The two it misses are named in section 5.
2. **My audit overstated one finding.** I wrote that the display step re-decides an attribution the
   sufficiency mapping had already made. That is true for only 9 of 49 values. The other 40 are named-value
   bindings the mapping never classified, so for them the display word list is the *only* attribution
   judgment and I left it in place. Repair 3 is therefore narrower than the audit implied.

## 1. Fidelity inspection of the 64 sealed claims

Read by me, claim against quotation, one pass. Not an adjudicated label set.

| Category | Count | Claims |
|---|---|---|
| Faithful | 48 | — |
| **Materially unfaithful** | **10** | below |
| Borderline wording | 2 | p45 ("The excerpt supports the claim that…"), p57 ("suggests" → "indicates") |
| Faithful text, but the prior-work attribution in the quotation is dropped | 4 | p33, p41, p48, p50 |

The ten:

| Problem | Claims | Example |
|---|---|---|
| Changed referent and dropped hedge | p12, p26 | Source: "We suggest that **dehumanization** is underpinned by…". Claim: "The **'anomalous-is-bad' stereotype** is underpinned by…" |
| Hedge dropped | p36, p38, p64 | Source: "These findings suggest that exposure-based storytelling can alter…". Claim: "Exposure-based storytelling can alter…" |
| Direction or recipient not in the source | p6, p25 | Source: "…affecting prosociality". Claim: "…as **reduced** prosociality **in** people with anomalous faces" |
| Causal wording added | p11 | "…manifests in attitudes by **leading to** the belief that…" |
| Forced into the question's frame | p40 | Asked about behavior: "manifests **in behavior** as negative attitudes" |
| Not a scientific claim | p29 | "The provided excerpt does not support a claim regarding…" (sealed, NLI 0.93) |

**Predictions.** Every prediction or hypothesis keeps its status in the claim (p42 "were predicted to elicit",
p47 "is hypothesized to", p59 "The hypothesis predicts"). Where a prediction was later presented as a
finding, that happened in synthesis, not in claim formation.

**Does the existing screen separate them?** I ran the project's rephrasing screen (`overview_guards.screen`)
on each claim against its own quotation: it rejects 8 of the 10 (misses p36 and p40), both borderline cases,
and 5 of the 48 faithful claims. That is the gate I used. No new check was written.

## 2. Implementation

All behavior changes apply on the fresh (reviewed) route only. The frozen Phase 28 reproduction is
byte-identical and nothing was re-frozen.

| File | Change |
|---|---|
| `layerc_presentation.py` | `_settle`: after the existing checks, apply the authority record and the claim. `ground_acronyms`. Clause sharing generalized (below). |
| `answer_plan/display_corrections.py` | `claim_statement_reasons` (calls the existing screen); citation-marker ending is not truncation |
| `parent_synthesis_v2.py` | Carries the statement, its evidence sentence and its qualifier |
| `answer_plan/render_v5.py` | Prints the source sentence under the statement; does not print the same content twice; optional acronym hook |
| `answer_plan/disclosure_v5.py` | One prefix function (same strings); accurate wording for the perceiver/perceived case |
| `layerc_pipeline.py` | Passes the acronym hook on the fresh route |
| `test_claim_statement.py` (new, 11 tests); `test_reviewed_ask_admission.py` (one assertion, section 6) | |

**Repair 1 — the claim is the statement.** For each source sentence Layer C already authorized for a value, the
sealed `proposition_text` becomes the statement when (a) it passes the existing rephrasing screen against
*that sentence* and (b) for a named value, it contains the value. The sentence remains the evidence: every
authorization, citation and relation check still reads the sentence, never the claim. When the claim is used,
the raw-sentence form checks (referential closure, truncation) are not applied to it. A claim that fails is not
used and the sentence is judged exactly as before. No second paraphrase, no model call.

**Repair 2 — attribution.** Where the scientific record classified the assertion, that record decides: prior
evidence is shown with the existing "The source reports prior evidence: "; an aim or hypothesis is not
shown; an interpretation gets one new qualifier. A named value with no record of its own uses the record for
the same requirement and proposition. Where no record exists, the lexical check still applies.

**Repair 3 — acronyms.** The renderer calls the Phase 30 Step 2 function unchanged.

**Repair 4 — disclosure.** When every display attempt for a value fails the stimulus-rating check, the line
now reads: "Evidence mapped to this part reports how the people being judged were rated, not characteristics
of the people judging, so it is not reported as an answer here. This does not show that the library holds no
relevant evidence."

**What this supersedes.** The October 13 narrowing repair is no longer what recovers the amygdala finding;
the claim does. It and "qualified result is not an aim" remain as the path for claims that fail the screen and
for values without an authority record. I did not remove them. The clause-sharing step I flagged last time is
now general: a relation is shown only when both of its values accept the same evidence sentence, so a value may
also take a clause Layer C narrowed to for its sibling.

## 3. The selected answer, before and after (same sealed evidence, same replayed mapping)

**Before (`377f9af2`), abridged to the statements:**

- c1, c4: "the specific amygdala response to facial anomalies correlated with … less prosociality toward people with facial anomalies."
- c3: two raw sentences (explicit vs implicit bias; Explicit Bias Questionnaire)
- c5: two raw sentences (share decisions; reaction times)
- c6: one raw sentence (Explicit Bias Questionnaire)
- c2, c8, c9, c10, c11, c12: no statement

**After (complete):**

```
c1. how does the anomalous is bad bias manifest in brain
The specific amygdala response to facial anomalies correlates with stronger just-world beliefs, less dispositional empathic concern, and less prosociality toward people with facial anomalies. [1][8][21][25]
    Source [1][8][21][25]: "the specific amygdala response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality toward people with facial anomalies."
An evidence-supported value cannot be displayed with an authorized quotation here; this is a presentation limitation, not scientific absence.

c2. how does the anomalous is bad bias manifest in behavior
The available evidence does not establish an answer to this part.
A completed scoped search is not recorded for this unresolved obligation.

c3. how does the anomalous is bad bias manifest in attitudes
Participants expressed explicit biases against people with facial anomalies, but their implicit biases were slight and not significant. [20]
we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anoma- lies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire). [5][10][12][28][29]
An evidence-supported value cannot be displayed with an authorized quotation here; this is a presentation limitation, not scientific absence.

c4. Please return the specific brain areas in which the anomalous-is-bad bias manifests.
The specific amygdala response to facial anomalies correlates with stronger just-world beliefs, less dispositional empathic concern, and less prosociality toward people with facial anomalies. [2][3][4][24]
    Source [2][3][4][24]: "the specific amygdala response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality toward people with facial anomalies."
An evidence-supported value cannot be displayed with an authorized quotation here; this is a presentation limitation, not scientific absence.

c5. In the context of the anomalous is bad bias, please return whether and how specific brain areas relate to behaviors, which kinds of behaviors
In addition, when comparing share decisions between partners (good versus bad), participants made more share decisions overall when playing with the good partner than with the bad (t11 ¼ 3.26, P o 0.01) or neutral (t11 ¼ 2.0, P ¼ 0.07) partners. [7][27]
Participants were faster to share when playing with the good partner compared to the bad partner (t11 = -3.73, P < 0.005) and neutral partners (t11 = -1.89, P = 0.08). [13][16]
    Source [13][16]: "Finally, using reaction time data acquired during the experimental session, we observed that participants were faster to share when playing with the good partner compared to the bad (t11 ¼ –3.73, P o 0.005) and neutral partners (t11 ¼ –1.89, P ¼ 0.08)."
The available evidence does not establish the requested relationship; separately supported findings do not suffice.
A completed scoped search is not recorded for this unresolved obligation.

c6. In the context of the anomalous is bad bias, please return whether and how specific brain areas relate to attitudes, and which kinds of attitudes.
The study found evidence for the 'anomalous-is-bad' stereotype in explicit negative attitudes about people with facial anomalies, observed both as individual character inferences and as group-level scores on the Explicit Bias Questionnaire. [6][9][11][14][15][18][19][22][26][30]
    Source [6][9][11][14][15][18][19][22][26][30]: "Nevertheless, we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anoma- lies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire)."
The available evidence does not establish the requested relationship; separately supported findings do not suffice.
A completed scoped search is not recorded for this unresolved obligation.
An evidence-supported value cannot be displayed with an authorized quotation here; this is a presentation limitation, not scientific absence.

c8. what kind of specific personality traits relate to the anomalous is bad bias's manifestation?
Evidence mapped to this part reports how the people being judged were rated, not characteristics of the people judging, so it is not reported as an answer here. This does not show that the library holds no relevant evidence.
An evidence-supported value cannot be displayed with an authorized quotation here; this is a presentation limitation, not scientific absence.
Some relevant evidence does not meet this requirement's support rules and is not used as support.

c9. which scales measure the specific personality traits that relate to the anomalous is bad bias's manifestation?
The available evidence does not establish the requested relationship; separately supported findings do not suffice.
A completed scoped search is not recorded for this unresolved obligation.

c10. is there any cross-cultural evidence for the anomalous is bad bias?
From a source passage cut off in extraction: Hadza individuals who regularly interact with outside cultural groups are more likely to perceive other Hadza with facial scarring as less moral. [17][23]
    Source [17][23]: "However, Hadza who regularly interact with outside cultural groups were more likely to think Hadza with facial scarring were less moral and were better"
The evidence answers only part of this question.
A completed scoped search is not recorded for this unresolved obligation.

c11. in which cultures is there evidence for the anomalous is bad bias, and how was the anomalous is bad bias measured in each?
The available evidence does not establish the requested relationship; separately supported findings do not suffice.
A completed scoped search is not recorded for this unresolved obligation.

c12. are there effective interventions aimed at reducing the anomalous is bad bias?
The available evidence does not establish the requested relationship; separately supported findings do not suffice.
A completed scoped search is not recorded for this unresolved obligation.
```

| Measure | Before | After |
|---|---|---|
| Rendered statements | 7 | 8 |
| Question parts with a statement | 5 of 11 | 6 of 11 |
| Statements given as a verified claim with its source sentence beneath | 0 | 5 |
| Established values still not displayable | 31 | 27 |
| Cited sources | 28 | 30 |
| Materially unfaithful claims in the answer | 0 | 0 |
| Misleading "presentation limitation" lines | 1 (c8) | 0 |

**Scope exclusions.** Of the 21 propositions Layer C offered for display, 10 supplied the statement, 8 were
not used because the claim did not name the authorized value, and 3 were rejected by the rephrasing screen
(p5, p10, p45). All 11 fell back to the source sentence under the old rules.

## 4. The traced cases

| Case | Outcome |
|---|---|
| **Amygdala** | Stated as the verified claim, full source sentence beneath, under c1 and c4. No narrowing is involved in the wording. |
| **Hadza** | Now shown under c10, labelled "From a source passage cut off in extraction:", with the cut-off quotation visible. The claim asserts only the part present ("less moral"). c10 moves from no statement to "The evidence answers only part of this question." |
| **NAME** | Not placed in the replay (c12's requirement is unfilled without the unreplayable nominations), so it does not appear above. Run on the sealed claims directly, the wired expansion gives: "The anomalous faces variant of the Normalizing Anomalies with Mobile Exposure (NAME) intervention produced a clear reduction in implicit bias…", expands once, and leaves a claim that already defines NAME alone. |
| **EBQ / IAT** | Expanded from each paper's own definition when a statement uses the acronym. PT, FT, AD and others with no sealed definition are left as they are. |
| **Prior work** | The record now governs: the "increased amygdala reactivity" value is accepted with "The source reports prior evidence:". It is **still not rendered**, because the two values of that relation accept different evidence sentences (section 5). The other prior-work values have no record and stay withheld. |
| **Prediction** | "were predicted to elicit…" and "This hypothesis predicts…" are not shown as findings. |
| **Perceiver vs perceived** | c8 now says the evidence concerns the people being judged. The mapping still marks those values established; that error is disclosed, not fixed. |
| **Fabricated causal claim** (existing safety control) | The claim "…cause an increased amygdala response" is rejected by the screen; only the source's own sentence appears. |

## 5. Remaining limitations

1. **Two unfaithful claims pass the screen.** p36 turns "our data are consistent with the possibility that
   … can help reduce" into "can help reduce", and p40 files an attitude under behavior. Neither is displayed
   in the replay. If live mapping places p36, it will appear with the full hedged sentence directly beneath
   it. I added no rule for them.
2. **Attribution is only as good as the record's coverage.** 40 of 49 values have no scientific attribution
   record. For those the word list still decides: 6 are withheld as prior work, 5 as aim or hypothesis,
   including "We suggest that dehumanization…" and "Recent studies have … implicated … the amygdala". Lifting
   that would need the classifier applied where the mapping never applied it, which is new scientific work.
3. **Prior-work evidence is qualified but not yet visible.** The sentence splitter does not break at a
   citation superscript ("anomalies.6 Laypersons…"), so one value's evidence is a three-sentence run and the
   other's is the single sentence; the relation needs them equal. The splitter is in a hash-pinned file.
4. **Sub-question placement is unchanged.** c5 and c6 still show share-decision and questionnaire findings
   that do not relate a brain area to anything, under a line saying the relationship is not established.
   That is the mapping's doing and it reads poorly.
5. **The same statement appears under c1 and c4.** Both questions own it. I did not suppress repeats across
   question parts.
6. **Truncation is disclosed, not repaired.** The Hadza sentence is still cut at "and were better".
7. **Acronym long forms keep the source's capitalization**, e.g. "via The Implicit Association Test (IAT)".
   That is the existing function's output.
8. **The perceiver/perceived mapping error and context-free verification** are untouched, as instructed.
9. **One question, one library, a partial replay.** Thirteen of 31 nominations could not be replayed, so
   c2, c9, c11 and c12 are not informative here.

## 6. Tests

- New: `test_claim_statement.py`, 11 passed.
- Frozen Profile B baseline, preregistered display fixture, import allowlists, isolation hashes: pass, unchanged.
- Full offline Ask suite: **5,420 passed, 2 failed.** Both failures are the hierarchy pin-drift tests that fail
  on the baseline too. One test needing a live socket was deselected, as before.
- **One existing safety test was edited.** `test_an_admitted_causal_overstatement_cannot_put_its_wording_into_the_selected_answer`
  asserted that the answer is identical whether the claim is faithful or fabricated. Under this assignment a
  faithful claim is supposed to appear, so that equality cannot hold. The test now asserts that the faithful
  claim and the source sentence both appear, and that the fabricated claim, and the word "cause", do not. Its
  safety assertions are otherwise unchanged.

## 7. E2E readiness

The code is ready for the separately authorized three-model run with plan-v5 as the selected answer. Still
needed from you: your own review file for the reporting contract; E2E and JUNO authorization; and the thermal
choice (I will use automatic stop unless told otherwise). Configuration is unchanged: Qwen3.5-9B, Phi-4:14B,
Gemma 3:12B, DeBERTa at 0.50, sufficiency v8, recovery reuse off.

Working files: `.local/phase34-claim-statement-20261013/` (`probe.py`, `BASE.*`, `NEW.*`).
