# Phase 34 / I4-2b1 — Ownership uncertainty audit

**Recommendation B: fix attribution first. Do not weaken the conservative support-policy default.**
All six supports excluded by the original I4-2b0 projection have recoverable ownership failures in the
three audited contexts. After independently justified relation corrections, **zero of the six
exclusions remain**. I4-2b is **NOT READY for implementation** until a separately authorized upstream
attribution correction is specified, implemented, and validated.

**Date:** 2026-10-08. **Audit:** Cody/Codex. **Scope and acceptance:** Cliff Workman.
This is a planning/read-only audit materialized as documentation. No classifier rule or production
behavior has been changed.

## 1. Scope, provenance, and method

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
Starting HEAD: `d2f3e1619a820b27479e7e00abb1e1e002fd1882`; clean before the authorized documentation writes.
The only tracked changes are this report, [I4-2b0](PHASE34_I4_2B0_SUPPORT_POLICY_GUARD_AUDIT.md), and
the two [lineage](CONTRIBUTION-LINEAGE.md) appends.

The question is whether the six excluded supports are genuinely ownership-unresolved or reflect
upstream rule/input/context defects. The only target contexts are p2/p11, p40, and p41 assertion 2.
Existing source packets and neighboring context were inspected; no new retrieval was performed.
There was no external search, model call, scientific-content inference, or live E2E.

Preserved run, relative to the canonical worktree:
`.local/e2e-runs/phase28-live-parent-synthesis-attempt2-20261004T014500Z/run`.
Evidence includes `08_evidence_packets.jsonl`, sealed `11_verified_ledger.json`, provenance context
IDs, and existing source/chunk metadata. Additional corroboration comes from direct read-only SQL over
the frozen `.local/e2e-runs/q-aib-hierarchical-t5c-live-20260930/library_copy.sqlite`, not the current
mutable library or a search service.

| Integrity check | Result |
|---|---|
| Frozen library SHA-256 | `4f2e98a54c92790e791d841ef63e2fd60c4b411246f9c29590c19e56da892523`, matches recorded fingerprint |
| Frozen library size | 665096192 bytes |
| Sealed ledger SHA-256 | `a70409e8f5a0937f414c73c4796b293c6c1a9ef3b31c7fc83bbfa61794c6bd5d` |
| Initial map SHA-256 | `46a213044bc6211702fa89710268e1bfb6c4fc348259727a46cb238ef5bbc14e` |
| Final map SHA-256 | `28478500e485137cd6930b8010d274bb1da3afd48e7f4a6208dd183610d9ca0b` |
| Accepted v5 combined replay SHA-256 | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |

The existing classifier was run unchanged on each sealed quote and its full preserved source chunk.
All three target assertions remain unresolved in both forms. This demonstrates that merely widening
input text is not a complete implementation of any proposed repair.

Classification terms in this report:

- `classifier_rule_gap`: the necessary ownership cues are already in the actual classifier text, but
  its intentionally bounded rules do not connect them.
- `classifier_input_gap`: replayable ownership context exists in the preserved run but is not supplied
  as a verified, bounded signal at the classifier boundary.
- `sealing_context_gap`: required context was not preserved sufficiently for this audit to reconstruct
  ownership; no audited case requires this classification.
- `genuinely_unresolved`: complete available local evidence still does not justify ownership; no audited
  case requires this classification.

These categories distinguish the first failing boundary from additional work a future repair will need.
In particular, p2/p11 also needs context-resolution logic; it is not fixed by supplying an arbitrary
owner hint or the whole paragraph.

## 2. Findings and exact correction ledger

All spans below are half-open character offsets in the **unchanged sealed quote**. Two child views
of one source assertion are two candidate supports, not two independent scientific findings.

| Context / role use | Sealed anchor and assertion span | Original relation | Counterfactual relation | Failure classification |
|---|---|---|---|---|
| p2/p11, c1 neural manifestation | p2, [37,264) | unresolved | current_document | classifier_input_gap |
| p11/p2, c4 specific region | p11, [37,264) | unresolved | current_document | classifier_input_gap |
| p40, c4 specific region | p40, [147,273) | unresolved | attributed_external | classifier_rule_gap |
| p41 assertion 2, c8 anger | p41, [208,372) | unresolved | current_document | classifier_rule_gap |
| p41 assertion 2, c8 dominance | p41, [208,372) | unresolved | current_document | classifier_rule_gap |
| p41 assertion 2, c8 threateningness | p41, [208,372) | unresolved | current_document | classifier_rule_gap |

No changes to exact_text, spans, supporting proposition identities/order, aggregation, assertion_kind,
authority_veto, caption status, or attachment status are justified by this audit. The projection changes
only the listed original relation values and separately records gate evaluation. Original display
support_label values are deliberately left intact for the relation-only experiment; labels are never
read as semantic input. A future authorized metadata producer should derive consistent display labels
from its versioned outputs.

### 2.1 p2/p11: omitted ownership-bearing antecedent context

The sealed quote starts “Across these levels of organization”. Its isolated assertion has an unowned
grammatical subject and no explicit owner or citation. The existing classifier correctly fails closed
on that input. The previously frozen `pp_p11` test describes this as “LOCKED NON-RECOVERY” absent
replayable ownership; the audit does not rewrite that historical test.

Both propositions point to source chunk **34974**, paper/attachment **67**, page 1. Their recorded
`context_read` is [34974], with no grown chunks. This exact source paragraph was available in the run.
It starts with the research question and hypothesis, then says “We examined responses…” across three
levels, gives the corresponding parallel observations, and explicitly refers back to “these levels”
in the target sentence. “We replicated previously reported…” describes a current replication act; it
does not transfer the authors' neighboring current observations to a prior owner.

The local enumerated antecedent and first-person study act support current-document ownership without
requiring knowledge about the scientific claims. The target has no conflicting owner or citation.
The frozen paper abstract independently reproduces this paragraph under an Abstract title, corroborating
its textual identity; **abstract status alone is not an ownership rule**.

Primary classification: **classifier_input_gap**. The sealed quote omits its owner-bearing antecedent,
but the run retained it, and the provenance identifies it. There is no irrecoverable sealing-context gap.
The current mapping call supplies the quote to `locate_containing_assertion` without verified structural
ownership context. The existing `owner_signal` interface accepts a caller-verified owner but does not
itself establish the needed proof.

Proposed correction: current_document for the same assertion in both c1 and c4. Do not change the
assertion boundaries or include the contextual paragraph as new support text. A future resolver must
supply a bounded, replayable ownership proof; blanket paragraph/document inheritance is not authorized.

### 2.2 p40: adjacent prior-work continuation with the same citation

The sealed quote already contains three assertions. The first, “Recent work…has implicated…”, is
parsed as prior_work. The target second assertion has a participant subject and is unresolved under the
current subject-local rules. Both end in citation **6**, which the current parser recognizes at
[145,146) and [272,273). The third assertion explicitly discusses previous studies; later preserved
text says “This study aimed…” and “We hypothesized…”, providing an identifiable local transition to
the citing study's own work.

The target's exact span is [147,273), including its citation marker. All this needed text is in the
actual classifier input, so the primary failure is **classifier_rule_gap**, not missing quote context.
The missing connection is bounded prior attribution across adjacent sentences with a matching citation.

The frozen reference-list text in chunk **33606**, paper/attachment 61, page 5, identifies reference 6:

> 6. Workman CI, Humphries S, Hartung F, et al. Morality is in the eye of the be- holder: the neurocognitive basis of the “anomalous-is-bad” stereotype. Ann N Y Acad Sci. 2021;1494:3–17.

The citing paper is *Visual Attention, Bias, and Social Dispositions Toward People With Facial Anomalies*
(2023); reference 6 is a separate 2021 paper. The frozen library contains no `reference_instances`
rows for citing paper 61, so this is an inspection of preserved reference-list text, not a claim of a
working structured citation resolver. Bibliographic identity corroborates the ownership reading; no
claim was adjudicated against the cited paper's scientific findings.

Proposed correction: **attributed_external**, never current_document. The corrected support remains
legitimate under the general empirical default but would fail an explicitly current-document-only
policy. A citation by itself is not enough to infer external ownership, and the proposed rule must not
override an explicit current owner.

### 2.3 p41 assertion 2: Results label scope stops at the coordinated clause

The actual sealed quote begins “Results:” and is one sentence with a `while` coordination. The first
assertion at [43,200) resolves to current_document through the structural Results resolver. The second,
at [208,372), has its own unowned subject. `_all_assertions` restricts label scope to the first clause;
the second record carries neither effective label scope nor a Results label for the resolver.

Preserved source chunk **43437**, paper/attachment **60**, page 1, contains Background, Objective,
Methods, Results, and Conclusions run-in labels. Both coordinated clauses occur under Results, before
the next label. The frozen paper abstract's JATS Results section independently contains both clauses.
The claim is based on these structural and grammatical facts, not on intuition that reported numbers
“look like” original results.

Primary classification: **classifier_rule_gap**. The label and coordinated target are already inside
the sealed input. Passing the entire chunk also remains unresolved because the current classifier does
not track mid-input section state. Neither result licenses a general Results-section inheritance rule.

[The I4-1b report](PHASE34_I4_1B_STRUCTURAL_CONTEXT_RESULTS.md), §6, intentionally excludes contrast-linked
clauses with their own subject from label scope. The frozen `pp_p41_a2` test explicitly expects unknown,
and `pp_p41_whole` preserves separate records. This is a new bounded semantic proposal, not discovery
that the old implementation violated its tests. A future repair must supersede expectations explicitly,
preserve distinct assertions, and retain exact historical v5 behavior.

Proposed correction: current_document for assertion 2, applied independently to its three role-instance
uses. Assertion 1's two uses remain current_document; no candidate or instance is merged.

## 3. Full preserved evidence and context inventory

The following material is transcribed from preserved artifacts rather than reconstructed from the
scientific propositions. Quote-relative assertion offsets above must not be confused with attachment
character offsets in the chunk metadata.

### Sealed propositions and quotes

#### p2

```json
{
  "proposition_id": "p2",
  "subquestion_id": "c1",
  "obligation_ids": [],
  "mapping_state": "pending",
  "paper_id": 67,
  "retrieval_anchor_chunk_id": 34974,
  "evidence_anchor_chunk_id": 34974,
  "evidence_span_id": "e7",
  "proposition_text": "The specific amygdala response to facial anomalies correlates with stronger just-world beliefs, less dispositional empathic concern, and less prosociality toward people with facial anomalies.",
  "quote": "Across these levels of organization, the specific amygdala response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality toward people with facial anomalies.",
  "provenance": {
    "nomination_reason": [
      "paper_kNN",
      "axis:Facial Perception and Stigma",
      "axis:Social Perception Accuracy",
      "axis:Moral Judgment"
    ],
    "retrieval_score": 0.5994964241981506,
    "context_read": [
      34974
    ],
    "grown": [],
    "origin": "initial",
    "request": {
      "source_unit_id": "c1",
      "question_hash": "6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030"
    }
  },
  "verification": {
    "status": "verified",
    "retrieval": 0.7817927598953247,
    "quote": 1.0,
    "support": 0.9868131875991821,
    "contradiction": 0.007261707913130522,
    "page_start": 1,
    "page_end": 1,
    "coordinate_precision": "exact"
  },
  "responsive_obligation_ids": [
    "c1"
  ]
}
```

#### p11

```json
{
  "proposition_id": "p11",
  "subquestion_id": "c4",
  "obligation_ids": [],
  "mapping_state": "pending",
  "paper_id": 67,
  "retrieval_anchor_chunk_id": 34974,
  "evidence_anchor_chunk_id": 34974,
  "evidence_span_id": "e7",
  "proposition_text": "The specific amygdala response to facial anomalies correlates with less prosociality toward people with facial anomalies.",
  "quote": "Across these levels of organization, the specific amygdala response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality toward people with facial anomalies.",
  "provenance": {
    "nomination_reason": [
      "paper_kNN",
      "axis:Facial Perception and Stigma",
      "axis:Moral Judgment",
      "axis:Social Perception Accuracy"
    ],
    "retrieval_score": 0.6024568974971771,
    "context_read": [
      34974
    ],
    "grown": [],
    "origin": "initial",
    "request": {
      "source_unit_id": "c4",
      "question_hash": "6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030"
    }
  },
  "verification": {
    "status": "verified",
    "retrieval": 0.7562252581119537,
    "quote": 1.0,
    "support": 0.9803760051727295,
    "contradiction": 0.004652951844036579,
    "page_start": 1,
    "page_end": 1,
    "coordinate_precision": "exact"
  },
  "responsive_obligation_ids": [
    "c4"
  ]
}
```

#### p40

```json
{
  "proposition_id": "p40",
  "subquestion_id": "c4",
  "obligation_ids": [],
  "mapping_state": "pending",
  "paper_id": 61,
  "retrieval_anchor_chunk_id": 33550,
  "evidence_anchor_chunk_id": 33550,
  "evidence_span_id": "e10",
  "proposition_text": "Laypersons with high levels of implicit bias toward those with facial anomalies demonstrated increased amygdala reactivity.",
  "quote": "Recent work with functional magnetic resonance imaging has implicated certain neuroanatomic structures when viewing others with facial anomalies.6 Laypersons with high levels of implicit bias toward those with facial anomalies demonstrated increased amygdala reactiv- ity.6 Although previous studies have used eye-tracking to characterize visual attention toward patients with craniofacial anomalies, visual at- tention has not been analyzed alongside assessments of biases and other social dispositions.",
  "provenance": {
    "nomination_reason": [
      "paper_kNN",
      "axis:Facial Perception and Stigma",
      "axis:Social Perception Accuracy"
    ],
    "retrieval_score": 0.5776622593402863,
    "context_read": [
      33547,
      33548,
      33549,
      33550,
      33551,
      33552,
      33553
    ],
    "grown": [
      33547,
      33548,
      33549,
      33551,
      33552,
      33553
    ],
    "origin": "recovery",
    "request": {
      "source_unit_id": "c4",
      "question_hash": "6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030"
    }
  },
  "verification": {
    "status": "verified",
    "retrieval": 0.7356989681720734,
    "quote": 1.0,
    "support": 0.9459494948387146,
    "contradiction": 0.010412482544779778,
    "page_start": 1,
    "page_end": 1,
    "coordinate_precision": "exact"
  },
  "responsive_obligation_ids": [
    "c1",
    "c4"
  ]
}
```

#### p41

```json
{
  "proposition_id": "p41",
  "subquestion_id": "c8",
  "obligation_ids": [],
  "mapping_state": "pending",
  "paper_id": 60,
  "retrieval_anchor_chunk_id": 43434,
  "evidence_anchor_chunk_id": 43437,
  "evidence_span_id": "e20",
  "proposition_text": "Lesser facial proportionality is associated with impressions of anger, dominance, and threateningness.",
  "quote": "Results: Across the ratings for all faces, Spearman correlations revealed greater proportionality was associated with attrac- tiveness (ρ = 0.292, P < 0.001) and trustworthiness (ρ = 0.193, P < 0.001), while lesser proportionality was associated with impressions of anger (ρ = 0.132, P = 0.001), dominance (ρ = 0.259, P < 0.001), and threateningness (ρ = 0.234, P < 0.001).",
  "provenance": {
    "nomination_reason": [
      "paper_kNN",
      "axis:Facial Perception and Stigma",
      "axis:Social Perception Accuracy"
    ],
    "retrieval_score": 0.6970942616462708,
    "context_read": [
      43431,
      43432,
      43433,
      43434,
      43435,
      43436,
      43437
    ],
    "grown": [
      43431,
      43432,
      43433,
      43435,
      43436,
      43437
    ],
    "origin": "recovery",
    "request": {
      "source_unit_id": "c8",
      "question_hash": "6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030"
    }
  },
  "verification": {
    "status": "verified",
    "retrieval": 0.7118909060955048,
    "quote": 1.0,
    "support": 0.8677695989608765,
    "contradiction": 0.1073475256562233,
    "page_start": 1,
    "page_end": 1,
    "coordinate_precision": "exact"
  },
  "responsive_obligation_ids": [
    "c8"
  ]
}
```


### Source chunks that contain the audited assertions

#### Chunk 34974

```json
{
  "chunk_id": 34974,
  "section": null,
  "chunk_type": "body_prose",
  "evidence_role": "scientific",
  "attachment_id": 67,
  "char_start": 920,
  "char_end": 2340,
  "page_start": 1,
  "page_end": 1,
  "extraction_tool": "pymupdf",
  "extraction_version": "1.27.2.3",
  "source_attachment_checksum": "e69488571a95103bc028347349faafb2fa03a4722c303c3f4973d7bdaeed6283",
  "chunk_structure": {
    "chunk_id": 34974,
    "chunk_type": "body_prose",
    "evidence_role": "scientific",
    "reason_codes_json": "[\"shape.clear_prose\"]",
    "confidence": 0.7,
    "derivation_version": "chunk-structure-v1",
    "raw_sha": "8c1518e74a71dae10538a595a81f74b12ed3cb6a903c67f6b2f74a8a10e5ebdf",
    "chunk_version": "pymupdf-block-v2:pymupdf-1.27.2.3:e69488571a95103b",
    "reference_region": null,
    "reference_region_source": null,
    "repeated_boilerplate": 0
  }
}
```

> Are people with flawed faces regarded as having flawed moral characters? An “anomalous-is-bad” stereotype is hypothesized to facilitate negative biases against people with facial anomalies (e.g., scars), but whether and how these biases affect behavior and brain functioning remain open questions. We examined responses to anomalous faces in the brain (using a visual oddball paradigm), behavior (in economic games), and attitudes. At the level of the brain, the amygdala demonstrated a specific neural response to anomalous faces—sensitive to disgust and a lack of beauty but independent of responses to salience or arousal. At the level of behavior, people with anomalous faces were subjected to less prosociality from participants highest in socioeconomic status. At the level of attitudes, we replicated previously reported negative character evaluations made about individuals with facial anomalies, and further identified explicit biases directed against them as a group. Across these levels of organization, the specific amygdala response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality toward people with facial anomalies. Characterizing the “anomalous-is-bad” stereotype at multiple levels of organization can reveal underappreciated psychological bur- dens shouldered by people who look different.

#### Chunk 33550

```json
{
  "chunk_id": 33550,
  "section": null,
  "chunk_type": "body_prose",
  "evidence_role": "scientific",
  "attachment_id": 61,
  "char_start": 2360,
  "char_end": 3440,
  "page_start": 1,
  "page_end": 1,
  "extraction_tool": "pymupdf",
  "extraction_version": "1.27.2.3",
  "source_attachment_checksum": "7ce46401efa4f89ab4b44a479208625adba3c26ad3a34d2463e0ee0ae2bb41d9",
  "chunk_structure": {
    "chunk_id": 33550,
    "chunk_type": "body_prose",
    "evidence_role": "scientific",
    "reason_codes_json": "[\"shape.clear_prose\"]",
    "confidence": 0.7,
    "derivation_version": "chunk-structure-v1",
    "raw_sha": "8cb65cd38ee45fbf90145ba0be8f329354ef9d5eeadd8a1ea015008f771e348f",
    "chunk_version": "pymupdf-block-v2:pymupdf-1.27.2.3:7ce46401efa4f89a",
    "reference_region": 0,
    "reference_region_source": "anchored",
    "repeated_boilerplate": 0
  }
}
```

> Recent work with functional magnetic resonance imaging has implicated certain neuroanatomic structures when viewing others with facial anomalies.6 Laypersons with high levels of implicit bias toward those with facial anomalies demonstrated increased amygdala reactiv- ity.6 Although previous studies have used eye-tracking to characterize visual attention toward patients with craniofacial anomalies, visual at- tention has not been analyzed alongside assessments of biases and other social dispositions. This study aimed to characterize associations be- tween visual attention patterns and implicit biases (attitudes toward groups of people without conscious awareness) and explicit biases (at- titudes toward groups of people with conscious awareness), as well as social dispositions toward people with facial anomalies. We hypothe- sized that visual attention toward people with facial anomalies differs as a function of implicit bias. Specifically, we predicted visual attention would be directed away from areas of facial anomalies in those with high levels of implicit bias.

#### Chunk 43437

```json
{
  "chunk_id": 43437,
  "section": null,
  "chunk_type": "body_prose",
  "evidence_role": "scientific",
  "attachment_id": 60,
  "char_start": 1021,
  "char_end": 2645,
  "page_start": 1,
  "page_end": 1,
  "extraction_tool": "pymupdf",
  "extraction_version": "1.27.2.3",
  "source_attachment_checksum": "394f49e5e93e8ffdfc71c6c1aa2743071c46fa53a3eff1df83f5b9a005361923",
  "chunk_structure": {
    "chunk_id": 43437,
    "chunk_type": "body_prose",
    "evidence_role": "scientific",
    "reason_codes_json": "[\"shape.clear_prose\"]",
    "confidence": 0.7,
    "derivation_version": "chunk-structure-v1",
    "raw_sha": "3144c8a7327e901113201d698c68f6eddd148585e8f7b67c6c21ac8452c433bd",
    "chunk_version": "pymupdf-block-v2:pymupdf-1.27.2.3:394f49e5e93e8ffd",
    "reference_region": 0,
    "reference_region_source": "anchored",
    "repeated_boilerplate": 0
  }
}
```

> Background: Facial proportionality and symmetry are positively associated with perceived levels of facial attractiveness. Objective: The aims of this study were to conﬁrm and extend the association of proportionality with perceived levels of attrac- tiveness and character traits and determine differences in at- tractiveness and character ratings between “anomalous” and “typical” faces using a large dataset. Methods: Ratings of 597 unique individuals from the Chicago Face Database were used. A formula was developed as a proxy of relative horizontal proportionality, where a proportionality score of “0” in- dicated perfect proportionality and more negative scores indicated less proportionality. Faces were categorized as “anomalous” or “typical” by 2 independent reviewers based on physical features. Results: Across the ratings for all faces, Spearman correlations revealed greater proportionality was associated with attrac- tiveness (ρ = 0.292, P < 0.001) and trustworthiness (ρ = 0.193, P < 0.001), while lesser proportionality was associated with impressions of anger (ρ = 0.132, P = 0.001), dominance (ρ = 0.259, P < 0.001), and threateningness (ρ = 0.234, P < 0.001). Mann-Whitney U tests revealed the typical cohort had sig- niﬁcantly higher levels of proportionality (–13.98 versus –15.14, P = 0.030) and ratings of attractiveness (3.39 versus 2.99, P < 0.001) and trustworthiness (3.48 versus 3.35, P < 0.001). Conclusions: This study demonstrated that facial proportionality is not only signiﬁcantly associated with higher ratings of attrac- tiveness, but also associated with judgements of trustworthiness.


### Neighboring preserved context

| Context | Chunk | Section / type / page | Preserved neighboring content |
|---|---|---|---|
| p2/p11 | 34974 | null / body_prose / 1 | Full target-containing chunk reproduced above. |
| p40 | 33547 | null / unknown / 1 | Hemifacial microsomia (HFM) is an optimal condition for studying gaze patterns because of its effects on specific facial regions, most com- monly the mandible, chin, and ear.11 |
| p40 | 33548 | null / body_prose / 1 | Background: Facial attractiveness influences our perceptions of others, with beautiful faces reaping societal rewards and anomalous faces encountering penal- ties. The purpose of this study was to determine associations of visual attention with bias and social dispositions toward people with facial anomalies. Methods: Sixty subjects completed tests evaluating implicit bias, explicit bias, and social dispositions before viewing publicly available images of preoperative and postoperative patients with hemifacial microsomia. Eye-tracking was used to register visual fixations. Results: Participants with higher implicit bias scores fixated significantly less on the cheek and ear region preoperatively ( P = 0.004). Participants with higher scores in empathic concern and perspective taking fixated more on the forehead and orbit preoperatively ( P = 0.045) and nose and lips ( P = 0.027) preoperativel. Conclusions: Participants with higher levels of implicit bias spent less visual at- tention on anomalous facial anatomy, whereas participants with higher levels of empathic concern and perspective taking spent more visual attention on normal facial anatomy. Levels of bias and social dispositions such as empathy may pre- dict layperson gaze patterns toward those with facial anomalies and provide in- sights to neural mechanisms underlying the “anomalous is bad” paradigm. |
| p40 | 33549 | null / keyword_line / 1 | Key Words: eye-tracking, hemifacial microsomia, bias, empathy, visual attention |
| p40 | 33550 | null / body_prose / 1 | Full target-containing chunk reproduced above. |
| p40 | 33551 | null / unknown / 1 | Download boilerplate; inspected, no ownership evidence. |
| p40 | 33552 | methods / unknown / 1 | (Ann Plast Surg 2023;90: 482–486) O ur faces are important for forming impressions and have an im- pact on perceptions of social characteristics.1 Previous studies characterized relations between facial beauty and positive character traits, including perceived health and trustworthiness.2,3 Recent re- search has reported associations between facial anomalies and percep- tion by observers as having negative social characteristics (eg, anger, untrustworthiness, unfriendliness). Collectively, the social penalties as- sociated with facial anomalies have been described as the “anomalous- is-bad” bias.4–6 |
| p40 | 33553 | methods / unknown / 1 | Assessment of visual attention provides unique insight into unin- hibited behavior.7 Eye-tracking technology has been increasingly used |
| p41 | 43431 | null / unknown / 1 | ORIGINAL ARTICLE |
| p41 | 43432 | null / unknown / 1 | It is All Relative: Associations of Facial Proportionality, Attractiveness, and Character Traits |
| p41 | 43433 | null / unknown / 1 | Dillon F. Villavisanis, BA,*†‡ Clifford I. Workman, PhD,†‡§ Daniel Y. Cho, MD, PhD,* Zachary D. Zapatero, BS,*† Connor S. Wagner, BS,* Jessica D. Blum, MSc,* Scott P. Bartlett, MD,* Jordan W. Swanson, MD, MSc,* Anjan Chatterjee, MD,†‡§ and Jesse A. Taylor, MD*† |
| p41 | 43434 | null / unknown / 1 | Proportionality plays a role in evoking negative attributions of personality characteristics to people with facial anomalies. |
| p41 | 43435 | null / keyword_line / 1 | Key Words: Attractiveness, character traits, proportionality |
| p41 | 43436 | null / unknown / 1 | (J Craniofac Surg 2022;00: 000–000) F acial structure and anatomy are important to our engage- ment with and perceptions of others.1,2 Facial features play a role when character traits and attractiveness are inferred, and facial attractiveness is associated with societal beneﬁts to in- dividuals in the economic and political realms.3,4 Additionally, proportionality and symmetry are positively associated with perceived levels of facial attractiveness.5,6 |
| p41 | 43437 | null / body_prose / 1 | Full target-containing chunk reproduced above. |

All target chunks have null `section`, `body_prose` type, and `scientific` evidence role. Those coarse
metadata do not independently establish ownership. Some neighbors have “methods” section metadata
despite introductory prose; do not use that metadata to override the local text. Run-in labels and
the frozen structured abstract are more precise evidence for the bounded p41 determination.

For p2/p11, context is primarily inside the same preserved source paragraph. Frozen-library surrounding
title/author/publication blocks were inspected as identity context, not owner grants. For p40, packet
context includes 33547–33553; for p41 it includes 43431–43437. Nonsemantic download/footer boilerplate
is identified in the neighbor inventory without reproducing access tokens.

### What was supplied versus merely available

| Input / context | Actually supplied to assertion_authority in accepted v5? | Audit use |
|---|---|---|
| Sealed quote and localized target span | Yes | Existing assertion classification and attachment |
| p40's preceding Recent work sentence and both citation markers | Yes | Establish rule gap |
| p41's leading Results label and while coordination | Yes | Establish rule gap |
| p2/p11's preceding We examined paragraph context | No | Available in recorded packet; establishes recoverable input gap |
| Neighboring chunks, section/type/role metadata | No as ownership context | Inspect local structure and limits |
| Verified target-scoped owner_signal | No | A future caller must prove it, not guess it |
| Frozen JATS abstract structure | No | Independent local corroboration |
| p40 reference 6 text in frozen library | No | Corroborates separate external bibliographic identity |

## 4. Smallest proposed upstream ownership rules

No rule is implemented here. None belongs in support-policy evaluation.

### R1 — verified local antecedent ownership

For an otherwise unowned assertion with an explicit anaphoric reference to a locally enumerated set
of observations, resolve to the uniquely established owner of that set only when the evidence is
within the same preserved paragraph, the antecedent is unambiguous, and no owner/citation/reset
conflicts intervene. Preserve the source paragraph identity, hashes, antecedent spans, and target
span as the ownership proof. Keep support exact_text and quote coordinates unchanged.

Current ownership is not a privileged fallback: a uniquely established prior owner would yield external
attribution. Omitted context, an unowned antecedent, competing enumerations/owners, paragraph boundaries,
or conflicting target attribution remain unresolved under this rule. Explicit target ownership is
preserved. The p2/p11 counterfactual is justified by the actual local antecedent, not merely by finding
the word “we” somewhere in the document.

### R2 — adjacent cited continuation

For an otherwise unowned result assertion, use the immediately preceding explicitly external result
assertion only when both are in the same paragraph, carry the same nonempty citation-marker set,
and no discourse or owner reset intervenes. Explicit target ownership wins. Different/missing markers,
a marker alone, a current-owned predecessor, and cross-paragraph continuation do not qualify.

Normalize only recognized citation syntax, not arbitrary numerical tokens. The real reference text is
corroboration in this audit; the rule does not require inferring subject matter from a title or fetching
the cited paper. Preserve the exact citation spans and external framing as the proof.

### R3 — bounded Results coordination

For the first sentence under an explicit Results run-in label, permit a parallel result clause linked
by `while` or `whereas` to share that structural scope when the first assertion is current-document
evidence and the second independently satisfies the existing narrow resolver safeguards. Preserve
separate assertion identity, subject, kind, veto, and target attachment.

Do not extend to semicolon-separated clauses, later sentences, unrelated labels, an explicitly
prior-owned first clause followed by an unowned clause, or a conflicting second-clause owner/citation.
Keep existing hedge/modal/negation/kind/caption safeguards for this bounded proposal; do not redesign
them as part of this audit. Those are ownership-resolver safeguards, not a new global support-policy
veto. Explicit owners continue to parse independently, including current-document interpretations.

## 5. Domain-neutral minimal-pair audit: 32 cases

**Observed** means the unchanged classifier's output for the selected target.
**Proposed** is a manually adjudicated ownership expectation for R1/R2/R3, including preserving already
explicit owners. These are design checks, not a passing implementation suite for new rules. Each text
is domain-neutral; `\\n\\n` denotes a literal paragraph boundary in the input.
Kind is observed separately and is never promoted by these ownership proposals.

1. **context_same_owner**

   Text: We examined responses at levels A and B. At level A, scores increased. At level B, ratings decreased. Across these levels, scores correlated with ratings.

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `current_document`.

2. **context_prior_owner**

   Text: Previous studies examined responses at levels A and B. At level A, scores increased. At level B, ratings decreased. Across these levels, scores correlated with ratings.

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `attributed_external`.

3. **context_no_owner**

   Text: Responses were examined at levels A and B. At level A, scores increased. At level B, ratings decreased. Across these levels, scores correlated with ratings.

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

4. **context_omitted**

   Text: Across these levels, scores correlated with ratings.

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

5. **context_switch**

   Text: We examined responses at levels A and B. Previous studies examined responses at levels C and D. Across these levels, scores correlated with ratings.

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

6. **context_paragraph_boundary**

   Text: We examined responses at levels A and B.\n\nAcross these levels, scores correlated with ratings.

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

7. **context_target_citation**

   Text: We examined responses at levels A and B. At level A, scores increased. At level B, ratings decreased. Across these levels, scores correlated with ratings.6

   Target: scores correlated

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

8. **context_explicit_target**

   Text: We examined responses at levels A and B. Across these levels, previous studies found that scores correlated with ratings.

   Target: scores correlated

   Observed: `attributed_external` / `result`. Proposed ownership: `attributed_external`.

9. **citation_shared**

   Text: Recent work found that scores increased.6 Participants demonstrated higher ratings.6

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `attributed_external`.

10. **citation_different**

   Text: Recent work found that scores increased.6 Participants demonstrated higher ratings.7

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

11. **citation_alone**

   Text: Participants demonstrated higher ratings.6

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

12. **citation_explicit_current**

   Text: Recent work found that scores increased.6 We found higher ratings.6

   Target: higher ratings

   Observed: `current_document` / `result`. Proposed ownership: `current_document`.

13. **citation_no_prior_marker**

   Text: Recent work found that scores increased. Participants demonstrated higher ratings.6

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

14. **citation_paragraph_boundary**

   Text: Recent work found that scores increased.6\n\nParticipants demonstrated higher ratings.6

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

15. **citation_preceding_current**

   Text: We found that scores increased.6 Participants demonstrated higher ratings.6

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

16. **citation_missing_target**

   Text: Recent work found that scores increased.6 Participants demonstrated higher ratings.

   Target: higher ratings

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

17. **label_parallel**

   Text: Results: Scores increased, while ratings decreased.

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `current_document`.

18. **label_prior_override**

   Text: Results: Scores increased, while previous studies found that ratings decreased.

   Target: ratings decreased

   Observed: `attributed_external` / `result`. Proposed ownership: `attributed_external`.

19. **label_citation**

   Text: Results: Scores increased, while ratings decreased.6

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

20. **label_prior_first**

   Text: Results: Previous studies found that scores increased, while ratings decreased.

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

21. **label_wrong_label**

   Text: Discussion: Scores increased, while ratings decreased.

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

22. **label_semicolon**

   Text: Results: Scores increased; ratings decreased.

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

23. **label_new_sentence**

   Text: Results: Scores increased. Ratings decreased.

   Target: Ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

24. **label_absent**

   Text: Scores increased, while ratings decreased.

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

25. **label_explicit_current**

   Text: Results: Scores increased, while we found that ratings decreased.6

   Target: ratings decreased

   Observed: `current_document` / `result`. Proposed ownership: `current_document`.

26. **label_interpretation**

   Text: Results: Scores increased, while we suggest that ratings decreased.

   Target: ratings decreased

   Observed: `current_document` / `interpretation`. Proposed ownership: `current_document`.

27. **label_hedged**

   Text: Results: Scores increased, while ratings probably decreased.

   Target: ratings probably decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

28. **label_modal**

   Text: Results: Scores increased, while ratings could decrease.

   Target: ratings could decrease

   Observed: `unresolved` / `interpretation`. Proposed ownership: `unresolved`.

29. **label_negated**

   Text: Results: Scores increased, while ratings did not increase.

   Target: ratings did not increase

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

30. **label_unowned_interpretation**

   Text: Results: Scores increased, while this suggests that ratings decreased.

   Target: ratings decreased

   Observed: `unresolved` / `interpretation`. Proposed ownership: `unresolved`.

31. **citation_discourse_reset**

   Text: Recent work found that scores increased.6 By contrast, ratings decreased.6

   Target: ratings decreased

   Observed: `unresolved` / `result`. Proposed ownership: `unresolved`.

32. **citation_current_override**

   Text: Recent work found that scores increased.6 We found ratings decreased.6

   Target: ratings decreased

   Observed: `current_document` / `result`. Proposed ownership: `current_document`.


The positive gap cases are the current-owned antecedent, prior-owned antecedent, shared prior citation,
and parallel Results clause. Negative pairs demonstrate why absent ownership, a citation alone, or a
Results heading somewhere in a document cannot justify blanket inheritance. Explicit current ownership
with an interpretation kind remains an interpretation and still fails the empirical support default.

For every recoverable real case, the analogous positive and negative cases constrain a generic rule.
This finite manual battery is not a claim of general classifier accuracy; separate implementation and
regression validation remain prerequisites to I4-2b.

## 6. Counterfactual evaluation and revised consequences

The selected default remains exactly:

```text
kind == result
AND NOT (relation == unresolved AND aggregation == non_synthetic_or_unspecified)
```

The in-memory audit uses the existing offline replay harness, fixed recorded model nominations, and
the accepted v5 localization/relevance pipeline. The original guard prefilter is bypassed only within
a temporary process-local binder wrapper so successfully grounded/relevant excluded candidates can be
retained and flagged. Each candidate's existing guard flags and the selected policy are evaluated
independently. The corrected B9 derives state from attachment resolution plus both gates.
The patch is restored when replay completes; no module or artifact is rewritten.

The audit applies the explicit six-entry correction ledger in §2 to original supports. Other relations
are unchanged. Every original candidate is matched by its quote anchor and assertion span, and all
non-evaluation fields other than the justified relation change are compared for equality. The four
anchor/span keys include both p2 and p11 views of their shared assertion; semantically these are three
distinct assertion contexts and six role-instance uses.

The simulation reuses v5 dispatch for unchanged downstream machinery. It neither creates a v6 runtime
nor stamps these results as an actual v6 replay. Semantic versions, PLAN_VERSION, and saved replay
artifacts remain unchanged.

| Measure | Accepted v5 | Uncorrected-attribution projection | Relation-corrected projection |
|---|---:|---:|---:|
| Original candidates passing policy | Not evaluated | 4/10 | **10/10** |
| Original six exclusions remaining | Not evaluated | 6 | **0** |
| Filled evidence-role instances | 10 | 4 | 10 |
| Missing evidence-role instances | 16 | 22 | 16 |
| filled → missing / filled → ambiguous / missing → filled | — | 6 / 0 / 0 | **0 / 0 / 0** |
| Evidence-role states unchanged | — | 20/26 | **26/26** |
| Requirement states changed | — | 4/13 | **0/13** |
| Total instances | 46 | 39 | 46 |
| Total role bindings | 94 | 80 | 94 |
| Recovery targets | 48 | 39 | **48, identical** |
| ParentClaims | 17 | 13 | **17, identical** |
| AnswerPlan nodes | 9 | 9 | **9, identical plan** |
| Downstream invariants | 33 passing | 33 passing | **33 passing** |

### Requirement and instance accounting

| Requirement | v5 → corrected state | Instances | Complete instances |
|---|---|---:|---:|
| c1#suff:neural-manifestation | filled → filled | 1 → 1 | 1 → 1 |
| c10#suff:culture-existence | partially_filled → partially_filled | 2 → 2 | 0 → 0 |
| c11#suff:culture-operationalization-pairing | missing → missing | 3 → 3 | 0 → 0 |
| c12#suff:intervention-effectiveness | missing → missing | 6 → 6 | 0 → 0 |
| c2#suff:behavioral-manifestation | filled → filled | 3 → 3 | 1 → 1 |
| c3#suff:attitude-manifestation | filled → filled | 1 → 1 | 1 → 1 |
| c3#suff:implicit-explicit-coverage | partially_filled → partially_filled | 2 → 2 | 1 → 1 |
| c4#suff:specific-region | filled → filled | 2 → 2 | 2 → 2 |
| c8#suff:trait-construct | partially_filled → partially_filled | 11 → 11 | 5 → 5 |
| c5#suff:brain-behavior | filled → filled | 4 → 4 | 4 → 4 |
| c6#suff:brain-attitude | filled → filled | 4 → 4 | 4 → 4 |
| c6#suff:implicit-explicit-coverage | partially_filled → partially_filled | 2 → 2 | 1 → 1 |
| c9#suff:trait-scale-pairing | partially_filled → partially_filled | 5 → 5 | 0 → 0 |

c1 and both c4 instances keep filled evidence roles. c8's five p41-backed instances all remain complete.
Its requirement is an **atomic open_list**, so it remains partially_filled; there is no exists/cardinality
reinterpretation. c5/c6 inherited instances and c9 pairing opportunities remain unchanged.

Recovery has zero added, removed, or changed targets: all 48 records equal v5. Witnesses, relation
outcomes, direction observations/summaries, and effectiveness observations equal v5. In particular,
c4 retains two witnesses, c8 retains five, and c5/c6 do not acquire successful relation evidence merely
because supporting role states are filled. Effectiveness remains zero.

All 17 ParentClaims, the nine-node AnswerPlan, and rendered Layer 1 equal the baseline. No downstream
authoring or rendering repair is included. Candidate-level metadata must still survive into later I4-4,
as specified by I4-2b0.

### Retained guard exclusions and the limits of equality

Retain-and-flag exposes five additional candidates: one c3 interpretation and four c8 interpretations
from the p9/p20 assertion beginning “We suggest that dehumanization…”. All five independently fail
the existing hedge guard and the empirical result-kind policy. They remain excluded after the six
ownership corrections, but they are **not members of the original six exclusions**.

Thus the projected candidate count is 15: ten original passing candidates plus five excluded new
inspectable candidates. c3 stays filled because another candidate passes. Four previously missing
c8 bindings stay missing but gain an exclusion explanation in place of `not_found`. No role becomes
ambiguous. c10 and c12 gain no admissible support.

The entire map is consequently **not byte-identical** to v5: candidate metadata/list contents differ,
and four c8 missing reasons differ. A recursive comparison excluding candidate_supports finds precisely
those four reason differences and no other map differences. This supports the stronger equality
statements about witnesses, relations, direction, effectiveness, recovery, claims, and AnswerPlan
without falsely claiming full-map identity.

## 7. Frozen decisions, recommendation, and readiness

Recommendation **B: fix attribution first**. Do not choose C (redesign the default) to compensate for
these recoverable upstream defects. Keep the conservative predicate: it correctly rejects a genuinely
unresolved non-synthetic result, while admitting attributed evidence and unresolved literature synthesis.
This corpus contains no real literature-synthesis cases; I4-2b0's synthetic A/B/C controls remain required.

All other accepted I4-2b0 decisions remain frozen:

- Retain and flag guards after successful grounding/relevance; do not change the declared guards now.
- Explicit complete support policy replaces the absent default.
- Guard failure, policy failure, and attachment ambiguity remain orthogonal; only otherwise eligible
  attachment-ambiguous candidates can make a role ambiguous.
- Defer authority-veto gating until structured claim-goal authoring.
- Captions are metadata only.
- Defer same_local_assertion; support policy does not require its registration.
- Preserve the likely eventual v6 boundary and exact historical v5 replay.
- Share policy semantics between hierarchical Ask and future Simple Ask.

The revised real-map projection no longer supplies evidence of six intrinsic policy rejections.
It supplies evidence that attribution must be repaired before evaluating rollout consequences.
Zero real state changes after correction does not eliminate the semantic boundary: candidate evaluation,
guard inspectability, and synthetic/general policy behavior still change.

A future attribution repair must have explicit versioned compatibility: globally changing
assertion_authority and silently changing historical v5 replay is unacceptable. This report recommends
that separate work; it neither implements nor authorizes it. I4-2b remains **NOT READY** pending that work.

## 8. Verification, reproducibility, and stop

Checks performed on preserved local artifacts, with no network/model/retrieval calls:

1. Canonical branch/HEAD and clean starting worktree verified.
2. Frozen library bytes match the recorded fingerprint; SQL connection is read-only.
3. Replay harness checks all three ledger/map hashes before reading preserved inputs.
4. Baseline replay equals the accepted v5 JSON and recorded Windows-byte hash.
5. Existing classifier inspected on sealed and full source texts and on 32 neutral audit cases.
6. Fourteen orthogonal aggregation contract checks pass.
7. Original ten candidates preserved except the six justified relation changes and gate metadata.
8. All 26 evidence-role states and 13 requirement states match baseline after correction.
9. All 48 recovery targets, 17 claims, AnswerPlan, Layer 1, and 33 invariant results equal baseline.
10. Remaining non-candidate map differences are only the four explained c8 exclusion reasons.
11. Documentation-only diff and local report links checked during materialization.

For reproduction, use the committed `test_i4_2a_replay.remap('sufficiency-semantics-v5')` over the
hash-verified saved inputs, preserve recorded model nominations, apply §2's candidate corrections only
inside an audit wrapper after existing grounding/relevance, evaluate both gates independently, and
recompute through the existing harness. Repeat without ownership corrections for the historical
I4-2b0 projection. Do not edit the sealed corpus, classifier, or production mapper to reproduce this audit.

**STOP after I4-2b1.** No production code or behavior changes, no classifier/support-policy/guard
implementation, no version bump, no relationship registration, no ParentClaims/AnswerPlan changes,
and no I2-3.
