# Phase 34 — DeBERTa integration and fresh full q_aib run

**Disposition: FRESH E2E COMPLETED ON THE SECOND ATTEMPT. The answer is honest and well cited but
scientifically thin: it omits the central brain finding and the central cross-cultural finding, both of
which the run retrieved and verified.** Nothing shown is fabricated, and every displayed sentence traces
to an exact verified passage. Three displayed sentences misrepresent their source by omission or
substitution. DeBERTa scored every pair and made no difference that this run can show.

Attempt 1 was stopped by the host safety monitor after eight minutes and produced no answer. Attempt 2,
authorized separately by Cliff after he added cooling, ran to completion with the same configuration.

## 1. What was built (commit `555a1d31`)

**DeBERTa verifier, opt-in (`--nli-verifier deberta`).** Every Ask NLI call shares one scorer
(`rt.verifier.support_scorer`): source verification calls it through the verifier, and the child-synthesis
and parent-synthesis screens receive the same callable. `nli_verifier.py` replaces that one scorer.

| Setting | Value |
|---|---|
| Checkpoint | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` @ `6f5cf0a2b59cabb106aca4c287eed12e357e90eb` |
| Label order | entailment / neutral / contradiction, checked at load; a mismatch refuses to load |
| Direction | premise = source passage, hypothesis = claim (shared code, unchanged) |
| Entailment threshold | 0.50 at the source verifier and at both synthesis screens |
| Unchanged gates | similarity 0.70, exact quote 1.0, contradiction 0.55 and above support |
| Precision / device | FP32; auto device with CPU fallback (CPU on the laptop that ran the pipeline) |

The synthesis screens read their threshold from the shared default (0.55), so a model swap alone would
have left them on MiniLM's value; `overview_guards.nli_screen_config` sets it for the run. The default
verifier is still MiniLM and the application's summarize path is untouched.

**Hierarchical narrative answer, opt-in (`--parent-narrative`).** The presentation contract was not
implemented: the parent answer was a claim-by-claim list and no combined document existed.
`hierarchical_answer.py` adds stage S3 — one call to the unchanged overview stage over the passages cited
by displayed child statements — and a deterministic renderer for `19_hierarchical_answer.md`. A parent
statement that fails screening is withheld; no claim list is substituted.

**Before the run.** Offline, through the integrated runtime, the scorer reproduced the frozen bakeoff on
all 99 pairs (largest difference 1.2e-06). The Ask suite, offline with the `contract_directed` subfolder
excluded and one network-dependent test deselected, gave 4,754 passed and 2 failed; both failures are
hierarchy pin drift and both reproduce on the unmodified baseline `a6cfeec6`. The line-budget hook was
skipped for that commit, with Cliff's authorization, because it fails on a file the commit does not touch.

## 2. Configuration and provenance (both attempts)

| | |
|---|---|
| Call | `run_topology("T5C", "aib", hierarchy, model-assist, recovery, parent synthesis, parent narrative, nli_verifier="deberta")` |
| Generators | qwen3.5:9b (thinking off), phi4:14b, gemma3:12b on JUNO's isolated Ollama 0.34.3, CUDA |
| NLI | DeBERTa on the laptop CPU |
| Library | fresh working copy per attempt of the preserved Sept-30 copy (266 papers); sha256 `4f2e98a5…2523` before and after; preserved copy unchanged |
| Contract | `pins=None` (same disclosed departure as Phase 28); v9 sufficiency hash `9c72dc6a…5586` |
| Attempt 1 | run id `phase34-deberta-fresh-e2e-20261012`, HEAD `555a1d31`, stopped at 483 s |
| Attempt 2 | run id `phase34-deberta-fresh-e2e-attempt2-20261012`, HEAD `887b41ba` (attempt-1 report only; code identical), 2,065 s |

Nothing from any earlier run was read. Attempt 2 did not read attempt 1.

## 3. Attempt 1: stopped by the host monitor

A monitor on JUNO, independent of the laptop, sampled every two seconds with limits fixed beforehand (CPU
warn 85 / abort 88 °C, GPU 75 / 80 °C, memory, kernel errors, 90 minutes). The first pass's generation
finished (213 usable Qwen calls, CPU up to 86 °C). The first coverage audit then loaded phi4:14b, which
does not fit the 8 GB card: 18 of its 41 layers ran on six CPU threads, the CPU went from about 54 °C to
88 °C in two minutes, and the monitor stopped Ollama at 19:53:19. No reset, no kernel error. No evidence
had been written to disk, because the pipeline writes first-pass evidence only when the pass seals.

## 4. Attempt 2: completed

Cliff added ice packs by the fan and asked for a rerun. Preflight was healthy (CPU 42 °C, GPU 36 °C,
11.7 GB available, kernel log clean). The same monitor ran with the same limits. At 20:24:57, on Cliff's
instruction during the run, the two temperature limits were changed from automatic stop to alert only;
the memory, kernel-error and runtime stops stayed automatic. That change was never exercised: the highest
CPU reading in the whole run was 87 °C (20:10:21, during the phi4 audit, before the change), and no reading
after the change exceeded 78 °C.

| Stage | Model | Seconds | CPU peak | GPU peak |
|---|---|---|---|---|
| W1 initial retrieval, selection, claims, verification | qwen3.5:9b | 374 | 74 °C | 56 °C |
| C1 coverage audit, U1 mapping, P1 recovery plan | phi4, qwen, gemma | 277 | 87 °C | 57 °C |
| W2 recovery retrieval | qwen3.5:9b | 1,010 | 84 °C | 58 °C |
| C2, U2, 11 child syntheses, S2, S3 | phi4, qwen | 328 | 78 °C | 60 °C |

Available memory fell to 3.7 GB during W2 (the generator process held 9.1 GB) and levelled off; swap peaked
at 2.1 GB. No kernel error, no throttle event, no reset; the host was returned to its idle state and the
tunnel closed.

**All stages ran fresh:** 684 model calls checked, 16 supervisor calls (2 coverage audits, 1 recovery plan,
12 overview syntheses, 1 parent claim realization), zero no-answer failures. 296 claims were formed and
verified; 64 were sealed as source-verified evidence. The run's own technical validity is `true`. One
mechanical check is false (`hierarchy_carriage`: recovery-query prompts lack an item line); the same check
is false in the Phase 28 run, so it is not new.

## 5. DeBERTa in the run

| | |
|---|---|
| Receipt | revision `6f5cf0a2`, labels entailment/neutral/contradiction, float32, CPU, no device fallback |
| Use | 132 calls, **352 pairs scored, 0 embedding fallbacks** |
| Source verification | 296 claims: 88 verified, 136 weak, 68 unverified, 4 contradicted |
| Effect of the 0.50 threshold | **none**: no claim had support between 0.50 and 0.55 |
| Lost to the similarity gate | 92 claims had an exact quote and support ≥ 0.50 but similarity below 0.70 |
| Rejected on support | 44 claims had an exact quote and similarity ≥ 0.70 but support below 0.50 |
| Contradiction | one claim, formed four times in recovery, contradicted at 0.99 |

DeBERTa was genuinely the verifier at all three sites. Whether it admitted better evidence than MiniLM
would have is not something one run can show: the code has moved since Phase 28 and the generators are not
deterministic. The loss this run makes visible is again the similarity gate, not the NLI model.

## 6. The complete user-facing answer

Exactly as rendered in `19_hierarchical_answer.md`.

---

### Answer

> how does the anomalous is bad bias manifest in brain, behavior, and attitudes? please return specific brain areas and whether and how they relate to behaviors, which kinds of behaviors, and whether they relate to attitudes, and which kinds of attitudes\. what kind of specific personality traits relate to its manifestation? and using which scales? is there any cross\-cultural evidence for the bias? which cultures and how was this measures? and are there effective interventions aimed at reducing it?

#### Overview

Participants expressed explicit biases against people with facial anomalies, but their implicit biases were slight and not significant\. [1] Results suggest that the anomalous\-is\-bad stereotype is culturally shared\. [2] The anomalous faces variant of the NAME intervention produced a clear reduction in implicit bias against people with anomalous faces, based on the idea that repeated exposure and narratives can shift automatic evaluations\. [3][4] Exposure\-based storytelling can alter automatic evaluations of individuals with facial anomalies and may offer a promising, scalable approach to reducing stigma associated with visible differences\. [5]

_2 further proposed statement(s) were withheld by screening and are not shown; this synthesis may omit findings the passages support._

_2 cited passage(s) did not fit the overview's evidence limit and were not offered to it._

**What remains unresolved.**

No synthesis statement passed screening for: "how does the anomalous is bad bias manifest in brain"; "Please return the specific brain areas in which the anomalous\-is\-bad bias manifests\."; "which scales measure the specific personality traits that relate to the anomalous is bad bias's manifestation?".
46 evidence requirement(s) remain open across 10 subquestion(s); they are listed under each subquestion below.

#### 1. how does the anomalous is bad bias manifest in brain

_No overview statement passed screening (2 proposed statement(s) were withheld; see the detailed inspection). The passages are listed below._

Not established for this subquestion:

- a specific named brain area: one usable finding; corroboration still open.

_Evidence and screening detail: `14_final_answer.c1.md`, `14b_detailed_inspection.c1.md`._

#### 2. how does the anomalous is bad bias manifest in behavior

Behavioral manifestations include diminished prosociality and elevated antisociality in behavioral economic games compared with typical faces\. [6][7]

_1 further proposed statement(s) were withheld by screening and are not shown; this synthesis may omit findings the passages support._

Not established for this subquestion:

- an observed behavioral finding bearing on the bias: not established in the retrieved evidence.
- an observed behavior, behavioral choice or action, or a task or measure of behavior \(not a self\-report attitude, belief, or prejudice questionnaire\): not established in the retrieved evidence.

_Evidence and screening detail: `14_final_answer.c2.md`, `14b_detailed_inspection.c2.md`._

#### 3. how does the anomalous is bad bias manifest in attitudes

The 'anomalous\-is\-bad' stereotype is expressed in negative attitudes about people with facial anomalies, manifesting as explicit biases against individuals and group\-level scores\. [8][9] Evidence supporting this hypothesis includes harsher character judgments made before versus after surgical correction and robust implicit biases against facial anomalies\. [10]

_1 further proposed statement(s) were withheld by screening and are not shown; this synthesis may omit findings the passages support._

_Evidence and screening detail: `14_final_answer.c3.md`, `14b_detailed_inspection.c3.md`._

#### 4. Please return the specific brain areas in which the anomalous\-is\-bad bias manifests\.

_No overview statement passed screening (1 proposed statement(s) were withheld; see the detailed inspection). The passages are listed below._

Not established for this subquestion:

- a specific NAMED brain area: one usable finding; corroboration still open.

_Evidence and screening detail: `14_final_answer.c4.md`, `14b_detailed_inspection.c4.md`._

#### 5. In the context of the anomalous is bad bias, please return whether and how specific brain areas relate to behaviors, which kinds of behaviors

Participants expressed explicit biases against people with facial anomalies, rating them as less attractive, less content, and more anxious than typical faces\. [1][8][11]

_1 further proposed statement(s) were withheld by screening and are not shown; this synthesis may omit findings the passages support._

Not established for this subquestion:

- an observed behavior, behavioral choice or action, or a task or measure of behavior \(not a self\-report attitude, belief, or prejudice questionnaire\): one usable finding; corroboration still open.

_Evidence and screening detail: `14_final_answer.c5.md`, `14b_detailed_inspection.c5.md`._

#### 6. In the context of the anomalous is bad bias, please return whether and how specific brain areas relate to attitudes, and which kinds of attitudes\.

The 'anomalous\-is\-bad' stereotype is expressed in explicit negative attitudes about people with facial anomalies, observed both as individual character inferences and as group\-level scores\. [8][9] Knowledge about individual differences in empathy and disgust sensitivity might improve decision\-making and reduce bias toward people with anomalous faces\. [12]

_1 further proposed statement(s) were withheld by screening and are not shown; this synthesis may omit findings the passages support._

Not established for this subquestion:

- a named attitude type or measure: one usable finding; corroboration still open.
- attitude category \(implicit/explicit\) evidence: not established in the retrieved evidence.

_Evidence and screening detail: `14_final_answer.c6.md`, `14b_detailed_inspection.c6.md`._

#### 7. what kind of specific personality traits relate to the anomalous is bad bias's manifestation?

This bias may be underpinned by a suite of negative attitudes, social cognitive biases characterized by just\-world beliefs, emotional dispositions involving affective empathy, and undesirable behaviors such as less generosity\. [13] Lesser proportionality is associated with impressions of anger, dominance, and threateningness\. [14]

_1 further proposed statement(s) were withheld by screening and are not shown; this synthesis may omit findings the passages support._

Not established for this subquestion:

- a named individual\-difference trait or construct; evidence relating the trait/construct to the bias's manifestation: findings exist; the breadth of the list remains open.

_Evidence and screening detail: `14_final_answer.c8.md`, `14b_detailed_inspection.c8.md`._

#### 8. which scales measure the specific personality traits that relate to the anomalous is bad bias's manifestation?

_No overview statement passed screening (1 proposed statement(s) were withheld; see the detailed inspection). The passages are listed below._

Not established for this subquestion:

- a named scale or instrument: only partly established.

_Evidence and screening detail: `14_final_answer.c9.md`, `14b_detailed_inspection.c9.md`._

#### 9. is there any cross\-cultural evidence for the anomalous is bad bias?

Results suggest that the anomalous\-is\-bad stereotype is culturally shared, providing evidence against a universal pathogen avoidance byproduct hypothesis\. [2]

Not established for this subquestion:

- evidence bearing on the bias/generalizability in that population: only partly established.

_Evidence and screening detail: `14_final_answer.c10.md`, `14b_detailed_inspection.c10.md`._

#### 10. in which cultures is there evidence for the anomalous is bad bias, and how was the anomalous is bad bias measured in each?

Results suggest that the anomalous\-is\-bad stereotype is culturally shared\. [2]

Not established for this subquestion:

- a named culture or population: not established in the retrieved evidence.
- how the bias was measured/operationalized there: not established in the retrieved evidence.

_Evidence and screening detail: `14_final_answer.c11.md`, `14b_detailed_inspection.c11.md`._

#### 11. are there effective interventions aimed at reducing the anomalous is bad bias?

The 'Normalizing Anomalies with Mobile Exposure' \(NAME\) intervention, which utilizes repeated exposure and narratives to shift automatic evaluations, produced a clear reduction in implicit bias against people with anomalous faces\. [3][4] These findings suggest that exposure\-based storytelling can alter automatic evaluations of individuals with facial anomalies and may offer a promising, scalable approach to reducing stigma associated with visible differences\. [5] Having knowledge about individual differences in empathy and disgust sensitivity might improve decision\-making and reduce bias toward people with anomalous faces\. [12]

Not established for this subquestion:

- a definitive, non\-speculative reported outcome: not established in the retrieved evidence.
- a named intervention: not established in the retrieved evidence.
- which aspect of the bias the intervention targets: not established in the retrieved evidence.

_Evidence and screening detail: `14_final_answer.c12.md`, `14b_detailed_inspection.c12.md`._

#### Sources

[1] Morality is in the eye of the beholder: the neurocognitive basis of the “anomalous‐is‐bad” stereotype \(2021\) (paper 67), p. 10
[2] Evidence against the “anomalous\-is\-bad” stereotype in Hadza hunter gatherers \(2022\) (paper 68), p. 3
[3] Changing the narrative: stories reduce biases against anomalous faces \(2026\) (paper 248), p. 13
[4] Changing the narrative: stories reduce biases against anomalous faces \(2026\) (paper 248), p. 1
[5] Changing the narrative: stories reduce biases against anomalous faces \(2026\) (paper 248), p. 1
[6] Morality is in the eye of the beholder: the neurocognitive basis of the “anomalous‐is‐bad” stereotype \(2021\) (paper 67), p. 2
[7] Morality is in the eye of the beholder: the neurocognitive basis of the “anomalous‐is‐bad” stereotype \(2021\) (paper 67), p. 2
[8] Morality is in the eye of the beholder: the neurocognitive basis of the “anomalous‐is‐bad” stereotype \(2021\) (paper 67), p. 10
[9] Morality is in the eye of the beholder: the neurocognitive basis of the “anomalous‐is‐bad” stereotype \(2021\) (paper 67), p. 2
[10] Morality is in the eye of the beholder: the neurocognitive basis of the “anomalous‐is‐bad” stereotype \(2021\) (paper 67), p. 2
[11] Morality is in the eye of the beholder: the neurocognitive basis of the “anomalous‐is‐bad” stereotype \(2021\) (paper 67), p. 10
[12] Reader in face\-reading: viewer’s empathy and sensitivity to disgust impacts the first impressions of anomalous faces \(2025\) (paper 107), p. 11
[13] Morality is in the eye of the beholder: the neurocognitive basis of the “anomalous‐is‐bad” stereotype \(2021\) (paper 67), p. 13
[14] Associations of Facial Proportionality, Attractiveness, and Character Traits \(2022\) (paper 60), p. 1

#### Inspecting this answer

- Exact quotations and verification scores for every source above: `19b_hierarchical_answer_evidence.md`.
- The overview's own record, withheld statements and screening reasons: `19a_parent_overview.json`, `19c_parent_overview_inspection.md`.
- The deterministic parent claim ledger and the full list of open requirements: `15_parent_answer.md`.

_This answer reports the evidence retrieved and verified in this run. It makes no statement about what the library or the literature holds, and completeness is not certified. Screening can withhold a statement but cannot prove one correct; every statement cites the passages it restates._

---

The exact quotation and verification scores behind each numbered source are in
`19b_hierarchical_answer_evidence.md`. The eleven standalone child answers (`14_final_answer.cN.md`), the
parent overview's standalone form (`19e_parent_overview_standalone.md`) and the deterministic parent claim
ledger (`15_parent_answer.md`, 17 claims, 10 phrased by the model and 7 by deterministic fallback, 46 open
requirements) are in the run folder.

## 7. Child syntheses, one by one

"Shown" is statements displayed out of statements proposed. Assessment is against the cited passage.

| # | Subquestion | Shown | Assessment |
|---|---|---|---|
| 1 | manifest in brain | 0 of 2 | **Null, not justified by the evidence.** The run verified the amygdala finding; both proposed statements were withheld by a lexical screen (see F1). |
| 2 | manifest in behavior | 1 of 2 | **Unsupported as stated.** A prediction and a general remark about dehumanization are presented as observed behavior (F3). |
| 3 | manifest in attitudes | 2 of 3 | **Addressed and faithful.** Explicit negative attitudes, individual and group level. The second sentence's "this hypothesis" has no referent in the answer. |
| 4 | specific brain areas | 0 of 1 | **Null, not justified.** A correct near-verbatim amygdala statement was withheld (F1). |
| 5 | brain areas ↔ behaviors | 1 of 2 | **Not responsive.** Faithful to its sources, but it reports explicit ratings; it names no brain area and no behavior. |
| 6 | brain areas ↔ attitudes | 2 of 3 | **Not responsive.** Faithful sentences about attitudes and about empathy knowledge; no brain area, no relationship. |
| 7 | personality traits | 2 of 3 | **Partly addressed, with two faults.** Referent substitution and a dropped brain link (F4); perceived traits of faces offered as perceiver traits (F5). |
| 8 | scales | 0 of 1 | **Null, not justified.** A faithful statement naming the Explicit Bias Questionnaire was withheld for paraphrase vocabulary. |
| 9 | cross-cultural evidence | 1 of 1 | **Faithful sentence, misleading answer.** It keeps the full passage, but without the Hadza result a reader will take "culturally shared" to mean shared across cultures (F2). |
| 10 | which cultures, how measured | 1 of 1 | **Not responsive.** Repeats the same sentence truncated; names no culture, though the run verified a Hadza finding (F2). |
| 11 | interventions | 3 of 3 | **Addressed and mostly faithful.** Names the NAME intervention and its effect on implicit bias, keeps "may" and "suggest". It drops "further research is needed to test durability and generalizability". |

Seven of eleven children show at least one statement; three of those seven answer something other than
what was asked.

## 8. Parent overview

**Narrative quality.** Four sentences, each a close restatement of one or two passages, placed side by
side. It reads as a short list, not a synthesis: it draws no relationship between findings, makes no
distinction between studies, and says nothing about brain, behavior or traits. The unresolved section is
honest and specific. Two proposed sentences were withheld for paraphrase vocabulary, though both were
faithful.

**Scientific fidelity.** Sentences 1, 3 and 4 are faithful. Sentence 2 is the truncated "culturally
shared" claim (F2). Sentence 3 joins two passages with "based on the idea that", which is accurate. Sentence
1 (implicit bias "slight and not significant") sits unreconciled with child 3's "robust implicit biases";
both are in the source, one as the study's own result and one as prior work, and the answer does not say so.

**Did the 12-passage, 6-statement limit matter?** Slightly. Two cited passages were not offered, including
the only one that names the dorsal anterior cingulate. The larger limit is the evidence rule I chose: the
overview may draw only on passages cited by *displayed* child statements. Because the brain children showed
nothing, the amygdala evidence never reached the overview at all. The deterministic claim ledger, built
from the sufficiency map instead, does contain it.

## 9. Observed failures, traced to their earliest stage

**F1. The amygdala finding is missing from the answer.** *Earliest stage: child synthesis screening.*
The run verified "the specific amygdala response to facial anomalies correlated with stronger just-world
beliefs … less dispositional empathic concern, and less prosociality" and "laypersons with high levels of
implicit bias … demonstrated increased amygdala reactivity". Child 4's proposed sentence was a
near-verbatim join of those two passages with NLI support 0.97, and was withheld for `negation_dropped`
because the second passage goes on to a clause the sentence did not use. Child 1's was withheld because the
model wrote "reduced" where the passage says "less" (NLI support 0.995). These are false rejections by the
lexical screens, not by DeBERTa. The claim ledger carries the finding; the reader-facing answer does not.

**F2. The cross-cultural answer points the wrong way.** *Earliest stage: evidence extraction.* The paper
is "Evidence against the 'anomalous-is-bad' stereotype in Hadza hunter gatherers". Its passage "Hadza who
regularly interact with outside cultural groups were more likely to think Hadza with facial scarring were
less moral and were better" was verified, but it is cut mid-sentence at a chunk boundary and so was
ineligible for synthesis as a truncated passage. What remained was "results suggest the anomalous-is-bad
stereotype is culturally shared, providing evidence against a universal pathogen avoidance byproduct
hypothesis" — and the same paper's abstract, also verified, says "culturally **shaped**". The parent
overview and child 10 then drop the qualifying clause. A reader is told the stereotype is "culturally
shared" and is not told that the Hadza evidence is evidence against universality.

**F3. A prediction presented as a result.** *Earliest stage: evidence admission; compounded at child
synthesis.* "Compared with typical faces, facial anomalies were predicted to elicit more antisociality and
less prosociality in behavioral economic games" was admitted as evidence with no qualification flag. Child
2 states it as a manifestation. NLI support for the passage-claim pair was 0.99: entailment does not
distinguish a predicted outcome from an observed one when the claim copies the passage.

**F4. Referent substitution and a dropped link.** *Earliest stage: claim formation.* The source says
"dehumanization is underpinned by a suite of negative attitudes … all factors associated with the
functioning of the left amygdala". The claim, and then child 7, say "this bias may be underpinned by …"
and omit the left amygdala. This pair's support was 0.552, the lowest of any source used.

**F5. Wrong construct for "personality traits".** *Earliest stage: coverage and responsiveness mapping.*
"Lesser proportionality is associated with impressions of anger, dominance, and threateningness" describes
how faces are perceived, in a study of facial proportionality. The subquestion asks which traits of people
relate to showing the bias.

**F6. The answer and its own gap list disagree.** *Earliest stage: sufficiency mapping.* Child 11 names
the NAME intervention and reports its outcome, while its gap list says a named intervention and a definitive
outcome are "not established in the retrieved evidence". Child 10's list says no culture is named while the
claim ledger holds "Hadza". The gap lists come from the sufficiency map, the syntheses from the passages,
and the two are not reconciled.

**F7. Three child syntheses answer a different question** (5, 6 and 10). *Earliest stage: child
synthesis.* Each is faithful to its passages and none addresses the relationship or the list it was asked for.

**What went right.** The one contradicted claim (contradiction 0.99) was excluded. Hedges were kept in the
intervention and empathy sentences. Every withheld statement is recorded with its reason. No sentence in
the answer lacks an exact verified source, and no citation points at a passage that does not contain what
is attributed to it.

## 10. Overall assessment

- **Useful today?** As a cited index into the library, partly: it finds the right papers (the neurocognitive
  study, the Hadza study, the NAME intervention) and its attitude and intervention sections are sound. As an
  answer to the question, no. It names no brain area, gives a misleading impression on cross-cultural
  evidence, and presents a prediction as a behavioral finding.
- **The pattern of failure is conservative but not harmless.** Most losses are omissions: correct
  statements withheld, a key passage cut at a chunk boundary. But omission produced a misleading sentence in
  F2, and F3 and F4 are real errors that passed every check.
- **DeBERTa is not the limiting factor in either direction.** It scored everything, rejected the one clear
  contradiction, and its 0.50 threshold changed nothing. It also passed F3 and F4, which are failures of
  what is compared, not of the comparison.
- **The narrative parent overview is not yet a synthesis.** With this evidence rule and these screens it
  produces a short list of safe restatements.

## 11. Limitations that bear on a release decision

1. One question, one run, one library. Generators are not deterministic.
2. The scientific assessment here is mine, read against the cited passages; it is not independent review.
3. The lexical screens rejected at least four faithful statements in this run (F1 twice, child 8, child 9's
   second sentence, and two parent sentences). Their false-rejection rate has not been measured.
4. Passages cut at chunk boundaries are excluded from synthesis even when verified (F2).
5. The parent overview's evidence rule excludes everything belonging to a child that showed nothing (F1).
6. The similarity gate again discarded 92 claims with exact quotes and adequate NLI support.
7. JUNO ran the generator set at up to 87 °C with added cooling; without it the run does not complete under
   an 88 °C limit. First-pass evidence is not durable until the pass seals.
8. The DeBERTa verifier and the hierarchical answer are opt-in in the experimental route only.

Nothing was tuned, rerun or adjusted after seeing these results.

## 12. Artifacts

- Attempt 2: `.local/e2e-runs/phase34-deberta-fresh-e2e-attempt2-20261012/` — driver, authorization, console
  log, `run/` (73 files), `juno/` (1,076 monitor samples, both monitor scripts, logs, host state), and
  `run_and_records.zip` (sha256 `8e579b19…9e81`).
- Attempt 1: `.local/e2e-runs/phase34-deberta-fresh-e2e-20261012/` — preserved unchanged.
- Preparation: `.local/phase34-deberta-e2e-20261012/` — predeclaration, offline parity check, suite logs.
- On JUNO: two small monitor folders under `/media/brain/JUNO/callosum-ask-exp/`.
- Working library copies: `C:/Users/cliff/callosum-data/ask-deberta-e2e-20261012/` and
  `…-attempt2-20261012/` (665 MB each).
