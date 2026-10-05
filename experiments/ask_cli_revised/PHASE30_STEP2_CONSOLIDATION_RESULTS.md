# Phase 30 Step 2 — consolidation, qualification recall, grounded context (offline)

**Scope.** Offline, deterministic, replay-only. No model call, no live run, no prompt change, no pin refresh, no frontend
change, no sufficiency-engine change, no repair of upstream U-stage bindings. Node 4 was not routed through p11 into 4A, the
amygdala gap was not recovered from external knowledge or a manual span repair, the Hadza/operationalization binding was not
repaired, and no trait/scale mapping was repaired. Step 2 completion does **not** authorize Steps 3–4; this report stops here.

**Starting commit:** `739eba84` (Phase 30 Step 1). Step-2 changes are uncommitted in the working tree at the time of
writing; the final commit state is recorded in §12.

## 1. Files changed

| File | Change |
|---|---|
| `answer_plan/step2.py` | **New.** Paper-level limitation discovery, promotion rule, grounded acronym expansion, disclosure consolidation, Layer-2/3 per-node records (`finalize`). |
| `answer_plan/source_metadata.py` | **New.** Citeproc-style labels from a read-only metadata extract; neutral fallback; `a`/`b` year suffixes for colliding labels; CLI to regenerate the extract. The Step-1 dead `.replace` is removed. |
| `answer_plan/plan.py` | `build_plan(labels=…)`; structured per-facet disclosure items; `_build_node` rebuilt; set-aside records; Step-1 qualification block and `_term_support`/`expansion_support` removed. Version `answer-plan-step2-v1`. |
| `answer_plan/render.py` | Citeproc labels in Layer 1 and Layer 2; Layer 2 sectioned; **new** `render_layer3`; 9 new invariant checks (45 total). |
| `answer_plan/text.py` | `definition_hits` (replaces Step-1 `expansion_support`); `has_statistics`. |
| `answer_plan/classify.py` | `Ctx.labels`; `paper_label` returns the narrative label, neutral `Source N` when absent. |
| `answer_plan/replay.py` | Loads `phase30_replay/source_metadata_extract.json`; writes `deterministic_layer3.md`; records `layer1_body_words`. |
| `phase30_replay/source_metadata_extract.json` | **New.** Read-only extract of citation fields (authors, year) for the 9 papers in the sealed ledger; library fingerprint `4f2e98a5…`. No titles, no text. |
| `phase30_replay/{answer_plan.json, answer_plan_audit.json, deterministic_layer1.md, deterministic_layer2.md}` | Regenerated. `deterministic_layer3.md` is new. `replay_decomposition_authorization.json` is unchanged. |
| `test_answer_plan.py` | Two Step-1 tests removed (they tested the removed qualification functions); one rewritten for `definition_hits`; one updated for structured items. 22 tests remain. |
| `test_answer_plan_step2.py` | **New.** 20 synthetic, question-agnostic tests (§4). |

## 2. Exact semantics

**A. Disclosure consolidation.** Within one node, facets whose state is `not_established` are worded in one sentence
(“The retrieved evidence does not establish any of the following: …”); facets whose state is `searched_empty` are worded in
one sentence likewise. A single facet keeps its own sentence. Relation-unwitnessed and role-missing lines are never merged,
because each is a separate obligation. Every facet's state and every raw disclosure item is kept in Layer 3 (`node.facets`,
`node.layer3.disclosure_items`), so no facet state is lost by wording.

**Generic explanations** (the fixed reason texts and the qualification pointer) appear **once per answer** in Layer 1, at
the first node that carries them. Later nodes still carry their own copy in Layer 2. Obligations (“This run did not assess …”)
stay per node, because they name a scope that differs by node. This is a deliberate reading: a reader is not told the same
generic reason repeatedly, and no node loses the reason in its own Layer 2.

**B. Qualification recall (paper level).** For each node, every sealed sentence from a paper that contributes displayed
evidence to that node is a candidate if it carries a generic limitation or scope cue (`LIMITATION_CUE`: limit\*, caveat\*,
cannot, may/might not, (not) generaliz\*, further/future research, future studies, preliminary, tentative\*, durabilit\*,
alternative explanation\*, interpret\*, proxy/proxies, directly test\*). Attachment **does not depend on shared words**. Excluded
and recorded in Layer 3: background (prior work, aim/hypothesis, literature, design rationale), a sentence already stated in
the answer, and a duplicate of a sentence already listed for the same item (overlapping sealed spans).
Each attached entry records why it was attached (same-paper evidence, the cue, and whether structural section metadata was
used; none was available).

**Promotion to Layer 1** happens only if the entry is closed and complete on its own (no closure failure, terminal
punctuation) **and** either shares two or more content words with a displayed finding of its own paper, or refers back to
“these/this/the present findings/results/effects”. Otherwise it stays in Layer 2 with its reason. The Layer-1 pointer
(“The paper adds a qualification to this result; it is listed in the supporting evidence.”) appears when a node has attached,
non-promoted limitations, once per answer.

**C. Grounded acronym expansion.** An acronym gains `Long Form (ACRONYM)` on its **first Layer-1 use** only when exactly one
explicit definitional construction (`Long Form (ACR)` or `ACR (Long Form)`) occurs in the **same paper's** sealed text, and the
definition is not already in that sentence. Later uses stay bare. An acronym with no definition, with two different definitions,
or with a definition only in another paper's text is not expanded, and the reason is recorded in Layer 2 and Layer 3. The
expansion is a recorded edit (`acronym_expansion_introduced`) reversed by the verbatim check.

**D. Source labels.** Layer 1 source entries use the list form from library metadata (`Workman et al., 2021, page 10.`).
Self-reference substitution (“This research …”) uses the narrative form (`Workman et al. (2021) …`). A paper with no usable
metadata gets `Source N`. Colliding labels receive `a`/`b` suffixes in ascending paper-id order. The model never authors
source identity.

**E. Layer 2 / Layer 3 separation.** Layer 2 (per item): supporting passages (verbatim, with statistics flag), qualifications
and limitations (with why-attached and promotion outcome), definitions (with applied/not-applied reason), attributed/adjacent/
set-aside evidence (with fixed human reasons), and not-assessed scope. Layer 3 (`deterministic_layer3.md`): plan and input
hashes, grounded/introduced acronyms, every facet's state and roles, every limitation decision, every definition decision,
raw disclosure items with reason codes, claim roles, and the engine-vs-AnswerPlan disagreements. Layer-1 fixed text is checked
against a Layer-3 vocabulary and must contain none of it (`layer1_fixed_text_has_no_layer3_vocabulary`).

## 3. Layer-1 before and after

Measured with the same counter (`render.layer1_body_words`: body above the source list, without markers):

| Measure | Step 1 (`739eba84`) | Step 2 |
|---|---:|---:|
| Layer-1 body words | 1,020 | **900** (−120, −11.8%) |
| `Earlier work reports this` | 5 | 1 |
| `A passage gives only a general summary` | 4 | 1 |
| `The paper adds a qualification` (pointer) | 1 | 1 |
| `does not establish` | 12 | 12 |
| `This run did not assess` | 6 | 6 |
| `Paper N` source labels | 7 | 0 |

The Step-1 report recorded 1,007 words with a different counter; the table uses one counter for both sides. The
`does not establish` count did not move: on this replay each unmet node already had one unmet facet, so there was little to
merge. The reduction came from the once-per-answer generic lines and from the labels, not from merging unmet facets.
Node states are unchanged (partial 3, not established 6).

Promoted to Layer 1 (verbatim; the Layer-1 text shows the same sentence after the recorded acronym edit where one applies):

- “Another, not mutually exclusive, possibility is that the control intervention generalized more strongly across groups th…” (paper 248, span `e13`). Basis: closed and complete on its own; shares 3 content words with a displayed finding of its paper.
- “Because we did not measure par- ticipants’ behavior, we cannot determine whether the observed changes in implicit bias t…” (paper 248, span `e4`). Basis: closed and complete on its own; shares 4 content words with a displayed finding of its paper.
- “Accordingly, the present findings should be interpreted specifically as changes in automatic evaluative associations mea…” (paper 248, span `e7`). Basis: closed and complete on its own; refers back to the paper's own findings.
- “We therefore cannot determine whether the observed reductions in implicit bias are driven primarily by moral-exemplar co…” (paper 248, span `e24`). Basis: closed and complete on its own; shares 3 content words with a displayed finding of its paper.


### After (Layer 1, `deterministic_layer1.md`)

#### Answer (offline deterministic replay, Step 2)

_No model wrote this text. Every sentence is a verbatim source sentence or a fixed disclosure._

**1. How does the anomalous-is-bad bias manifest in / relate to measures of brain structure and function across regions and networks?**

*Not established in the retrieved evidence.*

The retrieved evidence does not establish a specific neural finding about the bias. A passage gives only a general summary, without a specific measure or result, so it is listed in the supporting evidence instead. Earlier work reports this, and the retrieved text does not present it as this study's result, so it is listed in the supporting evidence.

**2. How does it manifest in / relate to measures of behavior?**

*Not established in the retrieved evidence.*

The retrieved evidence does not establish a specific behavioral finding about the bias. This run did not assess the choice of behavioral measures.

**3. How does it manifest in / relate to implicit and explicit attitudes?**

*Answered in part.*

Participants expressed explicit biases against people with facial anomalies, but their implicit biases were slight and not significant.[1] The retrieved evidence does not establish a specific attitude finding about the bias. The paper adds a qualification to this result; it is listed in the supporting evidence. This run did not assess the choice of implicit and explicit attitude measures.

**4. Which specific brain areas or networks are implicated?**

*Not established in the retrieved evidence.*

The retrieved evidence does not establish a specific named brain area or network, and how it bears on the bias. A passage that bears on this question depends on context that is not in the retrieved text, so it is not stated as an answer.

&emsp;&emsp;**4A. How do specific brain areas/networks relate to behavioral measures, including direction where established?**

&emsp;&emsp;*Not established in the retrieved evidence.*

&emsp;&emsp;The retrieved evidence does not establish how the brain area or network named for this question and the behavioral measure relate. Related evidence on a different construct is listed in the supporting evidence and does not answer this question. This run did not assess the choice of behavioral measures. This run did not assess the documented nature or direction of a relationship, where supported.

&emsp;&emsp;**4B. How do specific brain areas/networks relate to implicit and explicit attitude measures, including direction where established?**

&emsp;&emsp;*Answered in part.*

&emsp;&emsp;Nevertheless, we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anomalies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire).[2] The retrieved evidence does not establish implicit attitude findings. The retrieved evidence does not establish how the brain area or network named for this question and the attitude measure relate. This run did not assess the choice of implicit and explicit attitude measures. This run did not assess the documented nature or direction of a relationship, where supported.

**5. Which specific personality / individual-difference traits relate to its manifestation, and which scales measured them?**

*Not established in the retrieved evidence.*

The retrieved evidence does not establish a specific personality or individual-difference trait related to the bias. The retrieved evidence does not establish how the personality or individual-difference trait and the scale or instrument relate. A rating of stimuli is not stated as a characteristic of people. The authors present this as a suggestion or a study aim, so it is not stated as a result.

**6. Is there cross-cultural evidence bearing on generalizability? Which cultures/populations, and how was the bias measured/operationalized?**

*Not established in the retrieved evidence.*

The retrieved evidence does not establish a named culture or population with evidence on the bias. The retrieved evidence does not establish how the culture or population and how the bias was measured relate. A passage that may bear on this question ends before its finding is complete, so it is not stated.

**7. Are there effective interventions aimed at reducing manifestations of the bias?**

*Answered in part.*

We also observed that the anomalous faces variant of the Normalizing Anomalies with Mobile Exposure (NAME) intervention produced a clear reduction in implicit bias against people with anomalous faces, whereas bias toward people of color in that condition remained essentially unchanged.[3] Taken together, our data are consistent with the possibility that repeated, targeted exposure to individuals with facial differences, embedded in positive narratives and opportu-nities for perspective taking, can help reduce negative implicit biases associated with limited contact, while also leaving room for more general repetition-based mechanisms to contribute.[4] Another, not mutually exclusive, possibility is that the control intervention generalized more strongly across groups than the anomalous faces intervention.[5] Because we did not measure participants’ behavior, we cannot determine whether the observed changes in implicit bias translated into more prosocial actions toward people with facial anomalies.[6] Accordingly, the present findings should be interpreted specifically as changes in automatic evaluative associations measured within the Implicit Association Test (IAT) paradigm, not as evidence that the intervention necessarily altered long-term personal beliefs or downstream discriminatory behaviors.[7] We therefore cannot determine whether the observed reductions in implicit bias are driven primarily by moral-exemplar content, by associating people with facial anomalies with socially valued occu-pations, or by increased individuating information and familiarity.[8] The retrieved evidence does not establish how the intervention, which aspect of the bias the intervention targets and the observed effect relate.

#### Sources

[1] Workman et al., 2021, page 10.
[2] Workman et al., 2021, page 10.
[3] Bilici et al., 2026, page 13.
[4] Bilici et al., 2026, page 13.
[5] Bilici et al., 2026, qualifying passage.
[6] Bilici et al., 2026, qualifying passage.
[7] Bilici et al., 2026, qualifying passage.
[8] Bilici et al., 2026, qualifying passage.


<details>
<summary>Before (Step 1, committed at 739eba84)</summary>

#### Answer (offline deterministic replay, Step 1)

_No model wrote this text. Every sentence is a verbatim source sentence or a fixed disclosure._

**1. How does the anomalous-is-bad bias manifest in / relate to measures of brain structure and function across regions and networks?**

*Not established in the retrieved evidence.*

The retrieved evidence does not establish a specific neural finding about the bias. A passage gives only a general summary, without a specific measure or result, so it is listed in the supporting evidence instead. Earlier work reports this, and the retrieved text does not present it as this study's result, so it is listed in the supporting evidence.

**2. How does it manifest in / relate to measures of behavior?**

*Not established in the retrieved evidence.*

The retrieved evidence does not establish a specific behavioral finding about the bias. A passage gives only a general summary, without a specific measure or result, so it is listed in the supporting evidence instead. Earlier work reports this, and the retrieved text does not present it as this study's result, so it is listed in the supporting evidence. This run did not assess the choice of behavioral measures.

**3. How does it manifest in / relate to implicit and explicit attitudes?**

*Answered in part.*

Participants expressed explicit biases against people with facial anomalies, but their implicit biases were slight and not significant.[1] The retrieved evidence does not establish a specific attitude finding about the bias. A passage gives only a general summary, without a specific measure or result, so it is listed in the supporting evidence instead. Earlier work reports this, and the retrieved text does not present it as this study's result, so it is listed in the supporting evidence. This run did not assess the choice of implicit and explicit attitude measures.

**4. Which specific brain areas or networks are implicated?**

*Not established in the retrieved evidence.*

The retrieved evidence does not establish a specific named brain area or network, and how it bears on the bias. A passage that bears on this question depends on context that is not in the retrieved text, so it is not stated as an answer. Earlier work reports this, and the retrieved text does not present it as this study's result, so it is listed in the supporting evidence.

&emsp;&emsp;**4A. How do specific brain areas/networks relate to behavioral measures, including direction where established?**

&emsp;&emsp;*Not established in the retrieved evidence.*

&emsp;&emsp;The retrieved evidence does not establish how the brain area or network named for this question and the behavioral measure relate. Related evidence on a different construct is listed in the supporting evidence and does not answer this question. This run did not assess the choice of behavioral measures. This run did not assess the documented nature or direction of a relationship, where supported.

&emsp;&emsp;**4B. How do specific brain areas/networks relate to implicit and explicit attitude measures, including direction where established?**

&emsp;&emsp;*Answered in part.*

&emsp;&emsp;Nevertheless, we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anomalies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire).[2] The retrieved evidence does not establish how the brain area or network named for this question and the attitude measure relate. The retrieved evidence does not establish implicit attitude findings. This run did not assess the choice of implicit and explicit attitude measures. This run did not assess the documented nature or direction of a relationship, where supported.

**5. Which specific personality / individual-difference traits relate to its manifestation, and which scales measured them?**

*Not established in the retrieved evidence.*

The retrieved evidence does not establish a specific personality or individual-difference trait related to the bias. A rating of stimuli is not stated as a characteristic of people. The authors present this as a suggestion or a study aim, so it is not stated as a result. The retrieved evidence does not establish how the personality or individual-difference trait and the scale or instrument relate.

**6. Is there cross-cultural evidence bearing on generalizability? Which cultures/populations, and how was the bias measured/operationalized?**

*Not established in the retrieved evidence.*

The retrieved evidence does not establish a named culture or population with evidence on the bias. A passage that may bear on this question ends before its finding is complete, so it is not stated. The retrieved evidence does not establish how the culture or population and how the bias was measured relate.

**7. Are there effective interventions aimed at reducing manifestations of the bias?**

*Answered in part.*

We also observed that the anomalous faces variant of the NAME intervention produced a clear reduction in implicit bias against people with anomalous faces, whereas bias toward people of color in that condition remained essentially unchanged.[3] Taken together, our data are consistent with the possibility that repeated, targeted exposure to individuals with facial differences, embedded in positive narratives and opportu-nities for perspective taking, can help reduce negative implicit biases associated with limited contact, while also leaving room for more general repetition-based mechanisms to contribute.[4] Another, not mutually exclusive, possibility is that the control intervention generalized more strongly across groups than the anomalous faces intervention.[5] Because we did not measure participants’ behavior, we cannot determine whether the observed changes in implicit bias translated into more prosocial actions toward people with facial anomalies.[6] We therefore cannot determine whether the observed reductions in implicit bias are driven primarily by moral-exemplar content, by associating people with facial anomalies with socially valued occu-pations, or by increased individuating information and familiarity.[7] The retrieved evidence does not establish how the intervention, which aspect of the bias the intervention targets and the observed effect relate. A passage gives only a general summary, without a specific measure or result, so it is listed in the supporting evidence instead. Earlier work reports this, and the retrieved text does not present it as this study's result, so it is listed in the supporting evidence. The paper adds a qualification to this result; it is listed in the supporting evidence.

#### Sources

[1] Paper 67, page 10.
[2] Paper 67, page 10.
[3] Paper 248, page 13.
[4] Paper 248, page 13.
[5] Paper 248, qualifying passage.
[6] Paper 248, qualifying passage.
[7] Paper 248, qualifying passage.


</details>

## 4. Tests and verification

- **Synthetic (question-agnostic), `test_answer_plan_step2.py` (20):** consolidation of same-state facets; single facet
  unchanged; generic explanation once per answer with Layer-3 copy kept; same-paper limitation attached without shared words;
  other-paper limitation never attached; background limitation recorded and excluded; standalone interpretive limitation promoted
  with a passing verbatim check; truncated limitation attached but not promoted; “these findings” promotion only when closed;
  first-use expansion from a same-paper definition only once; unsupported acronym never expanded; other-paper-only definition
  reported, not applied; unexpanded parenthetical acronym fails the grounding check; citeproc label forms and neutral fallback;
  colliding-label suffixes; Layer-1 source list uses labels; Layer-1 fixed text free of Layer-3 vocabulary; Layer-2 explains each
  limitation; Layer-3 records the plan hash and every claim role; plan hash stable with labels; body word counter.
- **Step-1 tests, `test_answer_plan.py` (22)** and **preserved-artifact regression, `test_answer_plan_replay.py` (10):** pass.
  Total targeted run: **52 passed**.
- **Replay** (`python -m experiments.ask_cli_revised.answer_plan.replay`): plan hash `d965a6144377de37f2c688df3cd59a7f8c2354c54c3103b1dfbe61f2207d6c0c` identical on two
  independent builds; ParentClaim ledger rebuilds identically (21 ids); **45 invariant checks, 0 failed**; no model call.
- **Lint/format:** `ruff format --check` and `ruff check` clean on all nine touched Python files (scoped to those files).
- **Broader offline suite** (`offline_pytest experiments/ask_cli_revised`, run before the final two Phase-30 edits):
  **2,614 passed, 3 failed, 11 skipped, 2 deselected.** The three failures are
  `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`,
  `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`, and
  `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`.
  **Comparison with Step 1.** The Step-1 report (`739eba84`, line 177) recorded the same suite command with
  **2596 passed, 11 skipped, 2 deselected, 3 failed**, and named the same three tests. It attributes (a) to a connection attempt
  to a local model endpoint, refused in that environment, and (b) and (c) to `pin drift: code input hierarchy_contract.py changed
  since the pins were generated`. Step 2's run adds 18 passing tests (20 new Step-2 tests, minus the two Step-1 qualification
  tests removed) and has the same three failures. Those three failures therefore predate Step 2, as Step 1 reported.
  This step did not re-verify Step 1's causes. In particular, the dirty-tree test's refusal reason was not isolated here.
  Step 2 did not modify `hierarchy_contract.py` (byte-identical to HEAD). None of the three modules imports `answer_plan`
  (verified by grep). Only the three Phase-30 test modules import it, and those were re-run after the final edits.

## 5. Qualification attachment results (replay)

- Candidate sentences across the corpus: **158**. Per-node decisions (a sentence can be a candidate for more than one node):
  attachable **32**; excluded as a duplicate of a sentence already listed for the same item (overlapping sealed spans) **64**;
  excluded as already stated in the answer **12**; background — literature **10**, design rationale **8**, aim/hypothesis **1**,
  prior work **1**.
- Attached to Layer 2 per node: 3 → 5; 4B → 5; 7 → 22. Nodes 1, 2, 4, 4A, 5, 6 have no attached limitations: attachment is defined only
  for paper-contributed displayed evidence, and those nodes have none. Node 7's 22 come from paper 248.
- Promoted to Layer 1: **4** (node 7). No other node promoted anything.
- Structural section metadata: **not present** in the sealed spans (the span schema has no section field). Every attachment is
  therefore lexical and says so. The structural branch is wired to an optional `section_family` key and is inert on this replay.

## 6. Grounded context results (replay)

- `IAT` → “Implicit Association Test”, introduced at first use in node 7, supporting span `e25` (paper 248).
- `NAME` → “Normalizing Anomalies with Mobile Exposure”, introduced at first use in node 7, supporting span `e3` (paper 248).
- `EBQ`: defined only in paper 248's sealed text; the Layer-1 statements that name the questionnaire are from another paper and
  write it out in full, so no `EBQ` appears in Layer 1 and the rule was not exercised on it. `DG`: no explicit definition in the
  sealed text; never expanded and never printed. Both are listed in Layer 2/3 where they occur.
- Every parenthetical acronym in Layer 1 is grounded (`parenthetical_acronyms_are_grounded` passes).

## 7. Layer 2 and Layer 3 organization

Layer 2 per item has five sections (supporting passages, qualifications and limitations, definitions, attributed/adjacent/
set-aside, not assessed). Layer 2 is where all 158 candidates' fates are visible for the items they touch. Layer 3 holds the
mechanical audit, including every ParentClaim id and reason code, which Layer 1 and Layer 2 do not show.

## 8. Disagreements with Step 1 (stated, not hidden)

1. **Generic reasons once per answer** (Step 1 repeated them per node). A reader gets each generic reason once; Layer 2 keeps
   the per-item copy. A judgment call; it can be reversed.
2. **Promotion now happens** (Step 1 promoted nothing). Only four sentences, all in node 7, all verbatim.
3. **Consolidation barely moved `does not establish`** (12 → 12). The redundancy the brief named was in generic lines and
   labels, not in unmet-facet statements. This is reported as found.
4. **Labels replace `Paper N` everywhere** in Layer 1 and Layer 2.
5. **Step-1 `expansion_support` and `_qualification_candidates` are removed**; the three tests that used them were rewritten or
   removed. No behavior of the Step-1 answerability states changed.

## 9. Remaining upstream blockers (not repaired in Step 2)

- **Node 4 / amygdala:** still unreachable; node 4 stays not established. Not routed into 4A (replay rule).
- **Node 5 (trait/scale, c8+c9):** still no answer; the one stimulus-rating sentence is refused, as in Step 1.
- **Node 6 (culture/operationalization, c10+c11):** still no answer.
- **Four engine-complete relations not witnessed by one passage** (c5 ×2, c6 ×2): unchanged; disclosed in Layer 3.
- **Source-text defects, displayed verbatim:** a replacement character in place of an apostrophe (`participants�`) and
  line-break hyphens that the sealed corpus does not confirm (`par- ticipants`, `opportu-nities`) come from the upstream text
  extraction. They are not corrected here.
- **Lexical cue over-attachment:** `interpret*` attaches some literature descriptions to Layer 2 (e.g., “Although UG rejections
  are often interpreted as …”). Layer 1 is protected by the promotion rule; Layer 2 is not.
- **No structural section metadata** in the sealed spans, so all attachment is lexical.

## 10. Residual readability

Layer 1 still reads as an audit for nodes 1, 2, 4, 5 and 6: each is a line of unmet-facet statements plus generic explanation
and obligation lines. That is an accurate description of an answer the retrieved evidence does not contain. It is a finding
about the upstream answer, not something Step 2 can improve without inventing content.

## 11. Readiness verdict

- **Step 2 offline items A–H: implemented and verified on the preserved Phase-28 Attempt-2 replay.** Replay deterministic,
  45/45 invariant checks pass, 52 targeted tests pass, lint clean. The broader offline suite has the same three failures
  the Step-1 report recorded (§4); none of those modules imports `answer_plan`. Step 1 attributed them to an endpoint
  connection and to pin drift. This step did not re-verify those causes.
- **Ready for review.** Not ready for any live run: Layer 1 still lacks answers for six of nine nodes, and the upstream
  binder blockers in §9 are untouched by design.
- **Steps 3–4 are not authorized.** Stopping here as instructed. No upstream binder repair has begun.

## 12. Commit state

This report is part of the Step-2 commit. Its hash is reported in the final message (`git log -1`) rather than written
here, to avoid a self-referential hash (the Step-1 lesson).
