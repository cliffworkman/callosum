# Phase 29 — Question-Organized Answer Architecture: Design Audit

**Type:** fresh-context design audit. No implementation, no production-code or prompt change, no model
calls, no live E2E, no pin refresh. Read-only inspection of code and preserved artifacts.

**Date:** 2026-10-04 · **Branch:** `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`
**Base HEAD (verified, full hash):** `932a3ea00477f70a0a71cb34656b8a027cb9cef6` · tree clean · commit present on `origin`.

**Evidence base (all preserved, nothing re-run):**

- `PHASE28_ATTEMPT2_LIVE_PARENT_SYNTHESIS_RESULTS.md` and `…_FORENSIC_REPORT.md` (Attempt 2 is the evidence of record).
- `PHASE28_LIVE_PARENT_SYNTHESIS_*` (Attempt 1, documented as a harness failure; not evidence about the pipeline).
- Raw run directory `.local/e2e-runs/phase28-live-parent-synthesis-attempt2-20261004T014500Z/run/`, read directly:
  `11_verified_ledger.json`, `17_sufficiency_map.json`, `14a_overview.c*.json`, `14_final_answer.c*.md`,
  `15_parent_answer.md`, `hierarchy_contract.frozen.json` (repository copy).
- Code: `parent_synthesis.py`, `parent_synthesis_ledger.py`, `parent_synthesis_render.py`, `overview.py`,
  `overview_evidence.py`, `overview_guards.py`, `sufficiency_engine.py`, `sufficiency_mapping.py`, `e2e.py`.
- Governing documents: `.claude/CLAUDE.md` rule #9 gate; `.claude/PRINCIPLES.md` (commitments 1–10, Example 1).

Where a statement below is a hand-derived judgment rather than something a file states, it is labelled as such.

---

## 1. Executive verdict

**The direction is right; the implementation is not yet ready to start in full.**

- Phase 28 proved the authority boundary (deterministic ParentClaims, one bounded S2 call, deterministic
  citations, per-claim fallback). It did not produce an answer a researcher can read. The current parent output
  is organized by claim type, not by the researcher's subquestions; it repeats the same passages; it leaks
  internal ontology; it gives an unanswered subquestion no visible result; and, most seriously, its deterministic
  fallback can **invert a finding** (see §2.3, U2).
- The proposed architecture is a deterministic **AnswerPlan** between the semantic map and the user-facing text,
  a per-node **child answer**, and a **parent synthesis over validated child statements only**. It keeps every
  existing authority boundary and adds the missing ones: answerability as computed state, relation integrity,
  claimability, referential closure, and a human-readable fallback.
- Auditing the artifacts surfaced **upstream defects that the answer layer cannot repair** and must therefore
  expose rather than hide: a completeness rule that marks a relation "complete" with no witness of the relation
  (U9); deterministic binders that accept the same generic sentence for four different roles (U1); a keyword-level
  category binder that drops negation (U2); identity errors in trait bindings (U4); a table caption used as a
  finding (U5); and a decomposition whose approval status is not uniform in its own artifacts (U13).

**Verdict: NOT READY for implementation of the full architecture (child-answer and parent model stages).
READY for Step 1 only: an offline, deterministic AnswerPlan plus deterministic, facet-organized Layer 1, replayed
against the preserved Attempt-2 artifacts.** Step 1 is conditional on three decisions that change what the
answer layer is allowed to assert (§18, decisions D1–D3). Recommended defaults are stated; none needs a model
run to decide.

**Principles gate (CLAUDE.md rule #9).** This is a claim-presentation change, so the gate applies.
It touches commitments 1 (every claim carries its evidence), 2 (signal, not verdict — "answered" must not read as
a verdict), 3 (facts vs. candidates — model-assisted bindings and parent prose are candidates), 4 (deterministic
substrate is the source of truth; the model narrates), 5 (human is the filter — the researcher's decomposition
is the skeleton), 6 (silence is not a certificate — "not established" must never read as "absent"), 7 (no opaque
scores — no "completeness %"), 8 (inspectability), 9 (defaults are the user's — unconfirmed nodes are not
silently answered), and 10 (local-first; zero new egress). The closest worked example is **Example 1**
(synthesizing across papers): its aligned path is verified claims with quote, NLI and visible confidence, with
failures flagged rather than dropped. Its misaligned path is "hand the model the sources and let it write a fluent
synthesis, then append citations." The Phase 28 parent is near the aligned path at the claim level but drifts toward
the misaligned one at the presentation level: the organization, the templates and the prompt's "each must be
stated" rule let structure be decided by the model and the claim list rather than by the question. The aligned
alternative in this document keeps the model as narrator inside a deterministic plan. The values layer
(`APPROACH-AVOIDANCE.md`) is not triggered: no value-level posture, accusation, access or egress change is
introduced.

---

## 2. Precise diagnosis of Phase 28's user-facing failure

### 2.1 Observed symptoms (from `15_parent_answer.md` and the child artifacts)

| # | Symptom | Artifact evidence | Mechanism (code) |
|---|---|---|---|
| S-a | **Organized by claim kind, not by question.** Sections are Overview / Qualified / Supporting findings / Unresolved parts. No section corresponds to any of the approved subquestions. | `15_parent_answer.md` headings | `parent_synthesis_render.render_answer` emits one segment per ParentClaim in ledger order. |
| S-b | **One passage, many segments.** Paper 60 (p41) yields five relational claims, rendered as five near-identical "A reported relationship (…)" blocks repeating the same ρ-values. | "A reported relationship" ×5; the ρ-string ×5 | `_accumulate_relational` keys relational claims by the full role-value tuple, so each trait value creates its own claim over the same witness. `_render_relational` renders each separately. |
| S-c | **Ontology leaks.** `individual_difference_trait_or_construct` ×5 and `relationship_to_bias_manifestation` ×5 appear verbatim. | counts in the answer | `_render_relational` interpolates `v['role']` raw. |
| S-d | **Contextless and anaphoric fragments.** "Across these levels of organization" ×2 (inherited from the source sentence's own anaphor); "This research confirmed earlier reports…" ×4 (paper 67 summarizing earlier work); "the specific amygdala response" as a bare noun phrase. | counts in the answer; propositions p1/p4/p8/p24 and p2/p11 | Operands are raw `exact_text` spans. No referential-closure check exists anywhere in the chain. |
| S-e | **Direction without operands.** "A direction finding (negative) was reported. [p14, p26]" — no subject, no object, no relation. | the sentence | `_render_direction_or_effectiveness` renders only `consensus_value`; the direction claim has `values: []`. The binder returns the first direction word in the passage (`_match_direction_word`). |
| S-f | **Epistemic labels added by templates.** "a definitive, non-speculative reported outcome:" is printed over values including "consistent with the possibility" (p31) and a bias description, not an outcome (p24). | 4 occurrences of the label | The category label is a role specification, not a checked property of the values. |
| S-g | **Hedge and negation lost in fallback.** "attitude category (implicit/explicit) evidence: implicit; explicit. [p36, p8]" — the source sentence for p36 says implicit biases "were slight and not significant." The fallback states implicit evidence as found. | the line; p36 quote | `_match_explicit_category_term` returns the bare keyword "implicit"; `_render_category_list` joins keywords; no polarity check exists. |
| S-h | **Repetition and noise.** "not established in the retrieved evidence" ×16; 39 gaps listed at the end, grouped by reason code; "attrac- tiveness" (a line-break artifact) ×5. | counts | Gap rendering is per gap; the hyphen artifact is in the operand text and is never normalized for display. |
| S-i | **Too long, and the answer is in the wrong place.** About 12,100 characters and 1,695 words in total; the Overview and Qualified blocks together are about 870 words. The researcher must do the synthesis. | file size | Layer 1 holds everything the ledger holds. |
| S-j | **Answerability is invisible.** All eleven children are `judged_responsive` in the sealed ledger, including c5 and c9, which produced zero grounded sentences. Nothing in the parent answer says which subquestions have an answer. | `11_verified_ledger.json` `obligation_states`; `14_final_answer.c5.md`/`c9.md` | `judged_responsive` is a whole-item judgment; the ledger's own `item_disclaimer` says "fulfilment of the individual obligations it owns is not assessed by this run." That disclaimer does not reach the answer. |
| S-k | **Silent non-assessment.** The frozen contract classes "documented nature or direction where supported" and the behavior and attitude measure scopes as human-review, not model-facing, not assessed (D-1, decided by Cliff). The parent answer says nothing about this, while it does print direction sentences. | `hierarchy_contract.frozen.json` `requirements` and `d1` | The answer layer has no concept of "obligation not assessed." |
| S-l | **Enumeration is instructed, not emergent.** The S2 prompt tells the model every value in a category list "must be stated." That forces lists even where the researcher needs one answer. | `parent_synthesis.authorized_claim_text`, `category_list` branch | Prompt text, hashed into `contract_sha256`, so the enumeration rule is part of the recorded contract identity. |

### 2.2 The child layer shows the same problems at a smaller scale

- **c1** (S1 Overview): the second clause, "a finding supported by correlations between implicit biases and neural
  responses … in regions implicated in processing disgust and facial beauty," is supported by p27 (chunk 35123)
  and p28 (chunk 35125). Those two lines are caption-like text; the same wording appears as the caption
  "Table S13 | Correlations between implicit biases and neural responses to facial anomalies." (chunk 35368).
  NLI accepted the clause. A cross-passage join (behavior sentence p1 plus a caption) produced a single
  "finding."
- **c4**: the cited passage reports a three-part association (just-world beliefs, empathic concern, prosociality).
  The child statement keeps one clause. Each kept clause is verbatim-true, but the operand set is silently narrowed.
- **c12**: the paper's stated caveat ("further research is needed to test durability and generalizability") is
  dropped from the child statement that calls the approach "promising, scalable."
- **c5 and c9**: honest zero outcomes, but the child answers show them only as "No overview statement passed screening,"
  with no statement of what was and was not established.

### 2.3 Upstream findings that must stay visible (not repaired by synthesis)

These are semantic-mapping and sufficiency-engine defects. Per the prompt, the new architecture must expose them,
and must not "fix q_aib" by prose. Each is verified against the artifacts.

| ID | Finding (verified) | Where it lives | Answer-layer behavior required |
|---|---|---|---|
| **U1** | One generic bias-summary sentence (p1/p4/p8/p24, paper 67: "This research confirmed earlier reports …") is bound by the **deterministic** mapper to four different roles: `neural_manifestation_evidence` (c1), `behavioral_manifestation_evidence` (c2), `attitude_manifestation_evidence` (c3), `observed_effect_or_outcome` (c12). | `17_sufficiency_map.json`, `candidate_source = deterministic_mapping`. Mechanism: `sufficiency_mapping._match_achieved_outcome` returns the whole passage whenever `attribution.has_result_predicate` holds ("confirmed"). Modality is never checked. The five roles that accepted it (`neural_manifestation_evidence`, `behavioral_manifestation_evidence`, `attitude_manifestation_evidence`, `observed_effect_or_outcome`, `region_bears_on_bias_evidence`) all use `achieved_outcome_predicate`. | Plan must refuse modality mismatch as a standalone fact; sentence appears once, attributed, under the facet its content supports. Flag in Layer 3. |
| **U2** | Keyword-level category binding drops negation. p36 ("implicit biases were slight and not significant") becomes `category_evidence = "implicit"` for c3. | `_match_explicit_category_term` returns the matched substring with no context. The binding's own guard recorded `negated: true` on p36, but `category_evidence` has no disqualifying guards (`explicit_category_terms`, guards `[]`), so the flag was detected and then ignored. | Polarity check: a value taken from a sentence containing a negation cue cannot render as a bare category. Re-render from the verbatim sentence (F1) or suppress. |
| **U3** | A speculative discussion sentence ("We suggest that dehumanization is underpinned by …", p9/p20) becomes a categorical trait list. The proposition text restates it without "We suggest." | proposition text vs. quote; c8 `category_list` (f1f51b4b). The binder's `hedged` guard was `True`, yet the category still rendered as an established list. The hedge lexicon also misses p31's "consistent with the possibility" (`hedged: false`; `overview_evidence._HEDGE` has no such cue). | Hedge check at render time against the verbatim quote, with a reviewed cue list, not the restatement alone. |
| **U4** | Identity errors. Face-rating dimensions from paper 60 (p41: "Across the ratings for all faces … impressions of anger, dominance, threateningness") are bound as individual-difference traits (c8), and the parent-context mechanism carries them into c9. "Negative attitudes (IAT and EBQ)" and "undesirable behaviors (less generosity in the DG)" are bound as traits too (a behavior and an attitude in a trait role). | `17_sufficiency_map.json` (c8, c9 `parent_context`). No subject-of-measurement attribute exists. | Trait-role values without a recorded measurement subject cannot be asserted as perceiver traits. Layer 3 identity flag. |
| **U5** | A supplementary-table caption (Table S13 wording, chunk 35368) supports an S1 child statement via p27/p28. | chunks 35123/35125 vs. 35368. | Caption-like sources are not findings. Source-kind flag at plan build; NLI cannot detect this (it accepted the clause). |
| **U6** | Background sentence presented as a result: p40 is paper 61's introduction summarizing prior fMRI work ("Recent work with functional magnetic resonance imaging has implicated …"), bound as a region-role value for c4. | `paper 61`, p40. | Attribution is mandatory: "prior work cited by that paper reports…", or Layer 2 only. |
| **U7** | Requested-construct mismatch. The behavioral evidence for c2/c5 (p46, p47; paper 14) comes from a study whose 182 sealed spans contain **no** mention of facial anomalies (0 matches for "anomal" or "facial"); its partners are distinguished by biography and trustworthiness ratings (9 and 11 matches). It is adjacent evidence about partner-based behavioral bias, not a measure of the requested bias. | sealed `evidence_spans` for paper 14 (exhaustive count) | Adjacent-construct evidence must be labelled as such. A facet's requested construct should be stated in the contract; this is not checkable from the sealed record alone (see D7). |
| **U8** | A bias description (p24) is bound as an intervention outcome (`observed_effect_or_outcome`, c12). | `17_sufficiency_map.json` c12; deterministic. | Role/content mismatch; suppress and flag. |
| **U9** | **Relation completeness without a witness.** c6's brain–attitude requirement is `complete`: the region operand is inherited from the parent (p11, `parent_context`) and the attitude operand is own evidence (p14). The `same_proposition` joint check is never run because `own_evidence_roles` excludes parent-context bindings and `_joint_grounded` returns True for fewer than two own roles. The engine's own comment says "a single own-evidence role paired with trusted parent context needs nothing further to link." c5 has the same shape (p11 region plus p46 behavior). | `sufficiency_engine.py` `own_evidence_roles` and `recompute_instance` (the joint check is guarded by `len(own_roles) >= 2`), and the comment there. | This is a deliberate engine semantic, and changing it is a separately gated upstream increment (D3). The answer layer applies its own joint-witness test over **all** operands, including the inherited one, and reports the disagreement. |
| **U10** | Direction attached to the wrong relation. c6's direction observations (p14, p26) are about the **valence of explicit attitudes**. The requirement is a brain–attitude relation, so the direction is attached to a relation it does not describe. | `direction_summary` for `c6#suff:brain-attitude`; observation proposition ids p14/p26. | Direction must attach to a relational claim whose joint witness includes the observation's proposition (D1). |
| **U11** | Terms without support. "NAME" is defined in paper 248's sealed spans ("Normalizing Anomalies with Mobile Exposure" (NAME)), but not in the cited passage. "IAT" is defined in paper 248. "EBQ" appears only as "Explicit Bias Questionnaire" in the same paper, with no stated abbreviation link. "DG" is never expanded in the sealed spans. | `11_verified_ledger.json` `evidence_spans` (exhaustive search). | Expansion requires an explicit definitional span; otherwise use the full verbatim name or disclose. |
| **U12** | Quote and proposition text disagree. p11's proposition text ("correlates with less prosociality") omits the just-world and empathy clauses present in its quote. p29/p53 quotes end mid-sentence ("…were better"); the proposition text repairs it. | `verified_propositions` `proposition_text` vs `quote`. | Render operands from the verbatim quote; use restatements only for ranking. |
| **U13** | **Decomposition authority is not uniform in the run's own artifacts.** Sealed ledger `obligation_states.status`: `candidate` for c1, c2, c3, c5, c6, c8, c10, c12; `pending_researcher_confirmation` for c9 and c11; `researcher_supplied` for c4. Frozen contract `execution_state`: `researcher_approved` for c4, c5, c6, c9, c11, c12 with approval refs CD-4, CD-5, (none for c6), CD-1, CD-3, CD-5; `runnable_by_construction` for c1, c2, c3, c8, c10. The two vocabularies are not reconciled. | `11_verified_ledger.json` and `hierarchy_contract.frozen.json`. | Layer 1 answers only nodes whose approval state is explicit (D2). The prompt's premise of a confirmed nine-part decomposition is not what the run's artifacts record. |
| **U14** | A neural contrast sentence (p35, paper 14: "several brain regions defined by strength of effect") is bound as a behavior measure (c2) through its task description. The regions are not named, so the named-region requirement cannot use it. | `17_sufficiency_map.json` c2 `behavior_or_behavioral_measure`. | A task description is not a behavioral result. Plan rejects it as a behavior operand. |
| **U15** | Line-break hyphenation artifacts ("attrac- tiveness", "anomalous-is- bad") appear in rendered operands. | parent answer; `overview_evidence._LINEBREAK_HYPHEN` exists but is used for matching, not display. | Normalize at display only; verification keeps canonical text. |

Two of these (U2, U3) are also **answer-layer-detectable** with deterministic checks (polarity and hedge against the
verbatim quote), so the answer layer can refuse them even before the upstream fix. U9 and U10 are detectable
by an answer-layer joint-witness test. U1, U4, U5, U6, U7, U8, U13 and U14 need upstream work or researcher
decisions; the answer layer can only flag them.

---

## 3. Existing architecture that should remain

Preserve these unchanged. Each is load-bearing and each already has the right shape.

- **Sealed verified ledger** (`11_verified_ledger.json`): verbatim quote, span, page and chunk locator, verification
  scores, and `canonical_text_contains` as the fidelity test. Never relaxed (Phase 29 must not weaken it).
- **Sufficiency map** (`17_sufficiency_map.json`): role specifications, completion rules, instances with
  provenance (`candidate_source`, `model_dependency_origins`), guards (hedged, negated, fragment, correlational,
  causal cues), and direction summaries. Read-only for the answer layer.
- **ParentClaim ledger** (`parent_synthesis_ledger.build_claim_ledger`): closed claim kinds; canonical SHA-256 claim
  ids; `admissible_proposition_ids` as the citation authority; fail-closed construction (`_resolve_proposition`
  raises rather than fabricate a citation). It is the audit substrate and the plan's input.
- **Recovery-target and gap inventory** and **ResolvedEmptyOutcome** (`searched_no_support_established`): the
  semantic distinction "searched, nothing established" versus "absent" is correct and must carry into Layer 1 wording.
- **S2 realization mechanics** (`parent_synthesis.realize`): one call at most; `item_reasons`,
  `claim_value_reasons`, `source_passage_reasons`, `heterogeneity_reasons`; one batched entailment pass; per-claim
  fallback with no cross-contamination; output budget and prompt-cap constants.
- **Citations are deterministic.** `format_citations` returns the sorted admissible set. The schema has no citation field.
- **S1 unit eligibility and screens** (`overview_evidence.build_units`, `passage_flags`, `eligibility`;
  `overview_guards.screen`, `nli_pair`, `nli_reasons`): reusable as the child-answer screens.
- **Closure rule and item disclaimer** (sealed ledger `hierarchy`): "A node's own obligations are closed only by
  that node's own answer." and "A judged-responsive claim addresses this item as a whole." Adopt both as design rules.
- **Human-review classes** (frozen contract D-1): obligations recorded but not model-facing. Surface them as "not assessed."
- **Schema budget rule** (inc 575): every growable field has a `maxLength`, and the worst case fits the output cap.
- **Audits**: `parent_synthesis_audit`, `overview_audit`, construction-record hashes, and the flat-path golden test
  (`test_flat_path_golden.py`), which keeps the non-hierarchical path byte-identical until migration.

---

## 4. Proposed authority chain

```
[A] Confirmed decomposition            authority: WHAT must be answered
     visible labels (1, 2, 3, 4, 4A, 4B …), approved literal wording (hash-bound),
     approval state + approval refs, nesting, obligations with classes (active / preserve /
     retained-scope / human-review)
          │  deterministic join; nodes without an explicit approval state are not answered in Layer 1 (D2)
[B] Sealed verified evidence           authority: WHAT THE SOURCES SAY
     verbatim quotes, spans, verification, chunk/page locators
          │
[C] Sufficiency map                    authority: WHICH fillers bind which roles (model-assisted bindings flagged)
          │
[D] ParentClaim ledger (deterministic) authority: claim identity; admissible citation set
          │
[E] AnswerPlan  (NEW, deterministic, no model)
     authority: what each node MAY assert; answerability states; claim roles (primary / operand /
     context / attributed / duplicate / subsumed / suppressed); relation witnesses; direction attachment;
     context (definition) obligations; mandatory disclosures; fallback text
          │
[F] Child answer  (model; one per owning node; declared claim ids per sentence; screened)
     verbalizes E only; cannot introduce a claim, relation, term or citation
          │
[G] Parent synthesis  (model; one call; over VALIDATED F-statements only; declares statement ids)
     summarizes F only; no new conclusion; no citations of its own
          │
[H] Deterministic assembly
     citations (from D via E), source labels (citeproc), disclosures (from E), Layers 1 / 2 / 3
```

**Invariants of the chain.**

1. A layer may not add a semantic assertion that the layer above does not license.
2. Citations are never model-chosen; they are the deterministic union of admissible ids of the declared claims (or of the witness set, for relations).
3. Answerability is computed in **E**, never written by a model. "Not established" is produced by E.
4. A model may choose *wording* and *which licensed claims a sentence realizes*. It may never choose *which relation holds* or *which passage supports it*.
5. Joins are never created by a model. A multi-claim sentence is allowed only over a join that E has already licensed (§7).

---

## 5. Proposed AnswerPlan schema

Working name; not final. Specification only, not code. One plan per run, derived from `[A]–[D]`.

```
AnswerPlan {
  plan_version: "answer-plan-v1"
  inputs: { sealed_ledger_hash, sufficiency_map_hash, parent_claim_ledger_hash,
            decomposition_hash (approved wording + approval refs), contract_sha256 }
  plan_sha256
  nodes: [AnswerNode]                    # one per decomposition node, presentation order
  parent: ParentPlan
  review_flags: [ReviewFlag]             # upstream issues (U1–U15), Layer 3 only
}

AnswerNode {
  node_id                                # internal id, e.g. "c4"
  display_label                          # approved visible numbering, e.g. "4A"
  parent_label, depth, nesting_kind      # clarified_antecedent | top_level
  literal_text                           # APPROVED wording (not run note); null → cannot answer
  approval { state, approval_ref }       # researcher_approved | researcher_supplied | candidate |
                                         # pending | runnable_by_construction   (D2)
  answerable_as_layer1: bool             # false unless approval state is explicit
  obligations: [{ obligation_id, class, owner_node,
                  state: assessed | not_assessed | human_review,
                  phrase }]              # phrase = human-authored disclosure text
  facets: [Facet]                        # one per requirement (the existing requirement id is the facet id)
  state: answered | partial | not_established | searched_empty
         | not_assessed | awaiting_confirmation     # DERIVED, never written by a model
  claim_roles: [ClaimRole]
  context: [ContextObligation]
  disclosures: [Disclosure]              # fixed templates, filled from facet phrases
  budget: { max_statements, max_chars }  # from the schema budget rule (inc 575)
}

Facet {
  facet_id                               # = requirement id, e.g. "c6#suff:brain-attitude"
  phrase                                 # human label (contract addition, D8)
  slots: [{ role, state: filled | missing | parent_context, source_claim_ids }]
  relations: [{ relation_claim_id | null, operand_roles,
                witness_ids,             # joint witness over ALL operands, incl. parent-context
                status: witnessed | unwitnessed | not_required }]
  direction: [{ attached_to_relation: claim_id | null, sign, observation_props,
                status: attached | value_level | unattached_suppressed }]
  status: answered | partial | not_established | searched_empty | not_assessed
  missing_phrases: [string]              # human text only
}

ClaimRole {
  claim_id                               # the ParentClaim id (unchanged)
  facet_ids                              # facets it may answer
  role: primary | attributed_primary | operand | context | attributed_only |
        duplicate_of | subsumed_by | suppressed
  suppression_reason: null | identity_suspect | misbinding_suspect | polarity_loss | hedge_loss |
                      speculative_source | caption_source | unwitnessed_relation | truncated |
                      modality_mismatch | construct_adjacent
  passage_group_id                       # (paper, chunk, span) grouping for de-duplication
  standalone_renderable: bool
  attribution: { kind: this_study_result | prior_work | aim_or_hypothesis | background |
                       caption | unknown, source: grobid | heuristic | none }
  render_as: relation | value | enumeration | valence | verbatim_sentence
}

ContextObligation {
  term, kind: expansion | definition | paradigm | population | source_identity
  required_by: [claim_id]
  support: null | { span_id, pattern, quote }   # explicit definitional pattern only
  status: supported | unsupported
}

Disclosure { kind, facet_id, text }      # fixed templates (§9); never model text

ParentPlan {
  allowed_statement_ids: [...]           # validated child statements only
  orientation: { answered_nodes, partial_nodes, not_established_nodes, not_assessed_nodes }
}
```

**Two notes on the schema.**

- The `state` values are a derived view of the facets and claim roles. They are not a score. Listing them
  as plain named states, with no aggregate percentage, is required by commitment 7.
- `relations[].witness_ids` is computed by E over **all** operands. The engine's own `complete` flag is recorded
  alongside it, not replaced. A disagreement is a Layer 3 fact (U9).

---

## 6. Child-answer contract

**Unit of generation.** One call per node that owns obligations and has at least one standalone-renderable claim
or one non-empty facet. Nodes with no renderable claim make **no** model call; their Layer 1 text is the
deterministic disclosure from E. (For Phase 28 this removes nothing that was honest: c5 and c9 already produced zero
sentences, and the answer now says why in plain language.)

**Closed input.**

- The approved literal subquestion text (not the run note).
- Facets with their plain phrases and status.
- The set of **standalone-renderable** claim ids (the schema's `claim_ids` enum is built from this set only).
- For each such claim, the **verbatim** admissible passages (bounded length), and their attribution kind.
- Context obligations with their supporting spans, if any.
- The fixed disclosure strings the node will append (the model does not write them).

**Closed output** (schema-enforced, no free citations):

```
{ "statements": [ { "text": string (maxLength),
                    "claim_ids": [enum ⊆ renderable set] (1..3),
                    "facet_ids": [enum] (1..n),
                    "context_ids": [enum] } ] }
statements.maxItems = min(4, renderable_claim_count)   # node-specific bound
```

**Required behavior, checked by E-side screens (§13).**

- Answer the literal subquestion, using only statements that realize declared claims.
- Keep every hedge and negation the verbatim passage carries.
- Include every operand of any relation the sentence realizes (no silent narrowing; the c4 case).
- Use source identity only through placeholders (`{SOURCE:<paper_id>}`), which the renderer replaces with the
  citeproc short citation from the paper's metadata. The model never invents an author or year.
- Use a term only in its source form, or with a supporting definitional span (`{CTX:<id>}`).
- Never use role names, snake_case identifiers, claim or proposition ids, reason codes, counts-as-scores, or
  "this research/study" without the source placeholder.

**Forbidden regardless of schema.** Any statement that asserts a facet's status (established, unestablished,
absent). The status sentence is deterministic (§9, §10), so the model cannot contradict it.

**Latency.** One call per owning node, sequential, consistent with the single-worker contract. No per-claim calls
(LATENCY.md: no per-item inference). The budget is the same order as today: 11 child calls.

---

## 7. Multi-claim realization contract

**Default is one claim per sentence.** A sentence may realize several claims only over a **join that E has
already licensed**. Three joins are allowed, and nothing else:

1. **Same relation.** A sentence realizes one relational claim; all of its operands must appear (or the sentence is
   rejected). This is the complete-relation case.
2. **Enumeration under one facet.** Several values of the same category, all from one facet, may be listed together
   (co-presence of values in a list is not a relation). Each value is checked individually for polarity and hedge.
3. **Pre-approved joint.** A joint is an explicit E-level record, produced by a deterministic rule or by the
   researcher-confirmed U-stage nomination. The model never creates one.

**Prohibited.** Any sentence that uses a relation cue (the existing `RELATION_CUES` lexicon in
`parent_synthesis.py`, which is generic English: "associated with", "correlated", "compared", "than", "linked", and
similar) without a relational or directional claim declared in the same sentence. This is the direct guard against
"the model cannot create a relationship merely because two atomic facts coexist."

**Witness rule.** A relation is licensed only by a **single passage** (the `same_proposition` joint witness,
over all operands including the parent-context one). Two passages that each mention one operand do not
license a relation between them. This is the rule that would have rejected c1's cross-passage join (a behavior
sentence plus a caption).

**Citation rule.**

- A relation sentence cites the **witness set** only.
- An enumeration sentence cites the union of its values' admissible sets.
- Neither cites a passage the sentence does not realize.

**Output bound.** Per the inc-575 rule, `maxLength` on every string and `maxItems` on every array, with the worst
case checked against the output cap by a test that recomputes it from the schema.

---

## 8. Standalone intelligibility and referential closure

Standalone intelligibility is a **first-class obligation** of each node, not a style preference. It is enforced by
four deterministic mechanisms.

**8.1 Referential-closure lexicon (deterministic).** A sentence fails closure if it opens with, or contains without
an in-sentence antecedent, any of: "this research", "this study", "these findings", "across these", "these levels",
"the specific", "the intervention" (when no intervention is named in the sentence or its facet phrase), and "such".
The lexicon is generic English. It contains no domain vocabulary. A failing sentence falls back to F0 or F1 (§10).

**8.2 Source identity by placeholder.** "This research" becomes `{SOURCE:67}`, rendered by the citeproc
short citation from the library's own metadata (`papers.csl_json`). This is grounded metadata, not model knowledge,
and it is the only way a source may be named.

**8.3 Context obligations (acronyms, named instruments, interventions, populations).** For each term matched by
the uppercase-or-named-entity detector in a sentence, E records a `ContextObligation`:

- **Supported** only by an explicit definitional pattern in a sealed span: "*Long Form* (ABBR)", "ABBR (*Long Form*)",
  or a "we developed/define … (NAME)" construction. The quoted span is shown in Layer 2 with its span id.
- **Unsupported** otherwise. An unsupported term is either (a) replaced by its verbatim source form, when the
  source uses the full name (preferred: "the Explicit Bias Questionnaire", not "EBQ"), or (b) the sentence is not
  standalone-renderable and the term is disclosed.

Applied to Phase 28's sealed spans, this gives: NAME supported (paper 248 span); IAT has a definition in paper 248
but is used in paper 67; this document treats a cross-paper definition as Layer 2 context only (a judgment: the definition is of the term, not of the passage cited); EBQ unsupported
(verbatim "Explicit Bias Questionnaire" is available); DG unsupported (no definitional span; the source's own
parenthetical "(less generosity in the DG)" is quoted, and "DG" is not expanded). The model is never allowed to supply
a description of a paradigm or population from world knowledge. Existing `novel_terms` logic
(`overview_evidence`) is the detector for terms in a sentence that appear in neither the quote nor the context support.

**8.4 Source-initial anaphora (inherited).** Some source sentences open with an anaphor whose referent is in the
preceding text (p2/p11: "Across these levels of organization…"). The referent is **not** in the retrieved evidence.
Such a claim is `standalone_renderable: false` in v1 and appears in Layer 2 with its verbatim quote and a note that
its referent is outside the retrieved passage. Recovering the referent would need neighbouring-span retrieval, which
is a v2 retrieval change and out of scope here.

**8.5 Definitions for populations and paradigms.** A population ("the Hadza") is named as the source names it, with
its location in the passage. A paradigm (for example, a partner-choice sharing task) is described only from the
source's own task description; if none exists, the answer names the task as the source names it. Nothing is added
from outside knowledge. This is the rule that keeps "do not hallucinate contextual definitions" enforceable.

---

## 9. Claimability, subsumption and salience rules

### 9.1 Slot fillability versus standalone claimability

A binding can **fill a slot** (the evidence layer is satisfied) without its value being **claimable** as a standalone
answer. E decides claimability. The rules are deterministic and keyed on role identity, claim kind, witness status
and guards, never on domain vocabulary.

| Situation | Plan role | Standalone? |
|---|---|---|
| Complete relation, all operands witnessed by one passage | `primary` (render as `relation`) | yes, if closure passes |
| Relation with a parent-context operand and no joint witness | `operand` of an `unwitnessed` relation; the own value is a value-level fact for its own facet, with the relation disclosed as not established | the value only, with its own subject |
| Single own-evidence value, single-slot facet | `primary` (render as `value`) | yes, if guards and closure pass |
| Value in a multi-slot facet with no relation | `operand` (Layer 2) | no |
| Constituent already subsumed by a rendered complete relation | `subsumed_by` | no |
| Context-only value (a population, a measure name used as an operand) | `context` | only inside another sentence |
| Enumeration value with polarity or hedge loss | `suppressed` (polarity_loss / hedge_loss) or re-rendered F1 | F1 only |
| Prior-work, background, aim or hypothesis passage | `attributed_only` (Layer 2), or `attributed_primary` with an attribution phrase | attributed only |
| Caption-like source | `suppressed` (caption_source) | no |
| Speculative source | `suppressed` (speculative_source) | no |
| Identity-suspect trait value (no measurement subject) | `suppressed` (identity_suspect) | no |
| Bias-summary sentence bound to a role whose modality differs | `suppressed` (modality_mismatch); the sentence may appear once as attributed `primary` under the facet its content supports | attributed only |

### 9.2 Direction attachment (decision D1)

**Recommended rule: direction is a property of a relation.** A directional observation attaches to a relational claim
only if its proposition is in that claim's joint witness set.

- If it attaches, the rendered direction names both operands, taken from the relation: "the amygdala response was
  associated with less prosociality."
- If it does not attach, the direction describes the **value** it is about, not a relation. "Explicit negative
  attitudes were reported" is a value-level valence, with its own subject. It is never rendered as a brain–attitude
  direction.
- A direction observation with neither a relation nor a subject is suppressed with `unattached_suppressed`.

This makes the Phase 28 sentence "A direction finding (negative) was reported" impossible to produce by construction.

Note: the relational claim in the Phase 28 ledger carries no sign field. The sign must come from the relation's own
witness, which requires either attaching direction to the relational claim (option B) or carrying operands on the
direction claim (option A). Option B is recommended because it reuses the witness set that already exists
(`relationship_witness_support_ids`), and it fails closed for c6 without any engine change.

### 9.3 Subsumption rules (deterministic)

- **S1.** A role value that is an operand of a rendered complete relation (same proposition, same text) is `subsumed_by`
  that relation. Phase 28 example: claim `role_value::1f1af648` (p11, "the specific amygdala response") is subsumed by
  `relational::5d178917`.
- **S2.** Claims with the same normalized operand text and the same passage group are `duplicate_of` one representative.
  Phase 28 example: four claims containing the paper-67 summary sentence (p1, p4, p8, p24), and the duplicate
  category claims over p3/p7/p14/p17/p26 (one passage, five propositions).
- **S3.** Relational claims over the same witness passage whose operand sets differ collapse into **one** relation
  group with enumerated operands. Phase 28 example: five trait relations over p41 become one group. Merge only on
  identical witness and identical operand *roles*; never merge two findings that merely share a passage, since
  one passage may report two distinct findings.
- **S4.** Constituents of an **unwitnessed** relation are never `primary` for the relation's facet.
- **S5.** A direction observation without operands is never rendered standalone (§9.2).
- **S6.** Heterogeneous or conflicting claims keep their `conflict_or_heterogeneity` marker and must state the
  disagreement (existing `COLLAPSE_CUES` and `ACKNOWLEDGE_CUES` lexicons, reused).

### 9.4 Salience rules (no benchmark weights)

- **R1.** A direct answer to an explicit facet outranks adjacent or contextual evidence. "Direct" means the claim's
  role identity equals the facet's required role identity, not that it is nearby.
- **R2.** A complete relation outranks its isolated constituents (S1, S4).
- **R3.** A requested construct outranks a merely nearby construct. Nearby means: bound through `parent_context`, or
  flagged `construct_adjacent` (U7). Adjacent evidence can appear, but labelled.
- **R4.** One underlying passage carries one unit of rhetorical weight, however many propositions or claims it
  generated (S2, S3).
- **R5.** Evidence supporting several facets is rendered once, in the facet it is primary for. Other facets reference
  it ("see 4A"). It is never repeated in prose.

**Facet ownership.** Each claim has one owning facet for rendering. Cross-facet reuse is by reference, not by
repetition. Cross-facet *routing* (sending p11's just-world operand to the trait facet) is not something E can do
deterministically: it needs a U-stage nomination of the same proposition for a second requirement. That is a
candidate, reviewed by the researcher, not an automatic link.

---

## 10. Human-readable fallback design

The current fallback is `literal_statement` (`_render_claim`). It is safe for citations but not readable and not
faithful to qualifiers (U2, U3, S-g). The replacement is a ladder. Each rung is deterministic and checked.

| Rung | Use | Text | Checks |
|---|---|---|---|
| **F0** facet disclosure | Facet has no standalone-renderable claim | "The retrieved evidence does not establish {facet phrase}." | Phrase from contract (D8), never a role name |
| **F1** verbatim sentence | A claim with a clean witness whose operands are in one source sentence | The minimal source sentence containing the operands, verbatim, with its own hedges and negations, labelled `{SOURCE:id}` | Sentence extracted by the existing sentence splitter; length cap (if over cap, F0 plus a Layer 2 quote). Closure is checked (a sentence starting with an anaphor fails; see §8.4). Display-only linebreak-hyphen normalization. |
| **F2** enumeration | A category facet whose values are complete phrases | "{facet phrase}: {v1}; {v2}; …" | Each value checked for polarity and hedge against its own sentence. Any failing value is dropped to Layer 2 with its reason. |
| **F3** searched-empty | `ResolvedEmptyOutcome` | "The scoped search completed without establishing {facet phrase}." | Same wording rule as today (no "absent") |

**Rules that apply to all rungs.**

- **Never** an epistemic adjective the source does not carry. "Definitive," "confirmed," "shows," "proves" appear only if
  the same source sentence contains them.
- **Never** a bare category word whose polarity is not checked (U2 cannot recur).
- **Never** a raw role name or snake_case token. Display labels come from the contract (D8). The current
  `category_description` values include ontology terms ("individual-difference trait or construct"), so a reviewed,
  additive display-label field is needed.
- **Parent fallback.** If parent synthesis fails for every sentence, the parent paragraph is **omitted**, not
  replaced with a claim list. The deterministic orientation sentence (§11) still appears.

Applied to Phase 28, this ladder would have produced, for the c3 implicit value, F1: "Participants expressed explicit
biases against people with facial anomalies, but their implicit biases were slight and not significant
{SOURCE:67}." That sentence is the source's own, so its negation is intact by construction. For the c12 outcome
group, F2 would have kept p30 and p31 as separate items, dropped the bias-description value p24 to Layer 2 with
reason `misbinding_suspect`, and removed the label "definitive."

---

## 11. Parent-synthesis contract

**Input (closed).** Validated child statements only: text, node display label, status, and the statement's own
claim-id set (for provenance). Not ParentClaims, not raw S1 prose, not the evidence pool, not unrelated claims,
not internal ids.

**Output (schema).**

```
{ "sentences": [ { "text": string (maxLength), "statement_ids": [enum ⊆ allowed] (1..4) } ] }
sentences.maxItems = min(4, count of nodes with ≥1 validated statement)      # judgment call, see §18 D10
```

**Screens (deterministic unless noted).**

1. Closed `statement_ids` (enum).
2. NLI entailment of each sentence by the **concatenated child statement texts** it declares (not by the sources;
   the child statements were already screened against sources). Batched, one pass.
3. No novel content term (against the union of declared statements and their context support).
4. No numerals that do not appear in the union.
5. No relation cue unless a declared child statement contains one.
6. No assertion of a status for a node whose status is `not_established`, `not_assessed` or `awaiting_confirmation`
   (lexicon check against the derived status).
7. No new citations: the parent's citations are the union of its declared statements' citations.

**Deterministic orientation sentence (always present, no model).** It names the counts of plain states in words
("Of your confirmed subquestions, two have an answer in full, four have a partial answer, and three are not
established by the retrieved evidence; one is awaiting your confirmation."). It is a count of named states, not a
score or percentage (commitment 7).

**Parent sentence job.** Summarize across the answered nodes and name the strongest established conclusions and their
limits. It does not represent every valid fact (the exhaustive ledger is in Layer 3). Its length is bounded by the
schema, not an arbitrary sentence limit.

---

## 12. Layer 1 / Layer 2 / Layer 3 information architecture

| | **Layer 1 — Answer** (forward) | **Layer 2 — Supporting evidence** (expandable, linked from each statement) | **Layer 3 — Audit** (full provenance) |
|---|---|---|---|
| Purpose | Read the answer without reading anything else | Check any statement; see what else the evidence says | Full scientific and system provenance |
| Contents | Orientation line; optional parent paragraph; per node: label + literal subquestion (bold), answer paragraph (≤4 sentences, citation markers), one deterministic answerability line, deterministic disclosures | Per statement: verbatim passages with paper, chunk, page, and quote; qualifiers and negations present in the source; operands and direction operands; definitions used and their span; suppressed or subsumed material, grouped under its facet, with a plain reason; the facet's missing phrases; statistics in the quote | ParentClaims with ids and kinds; roles and proposition ids; instance keys; sufficiency requirement ids; recovery target history; model-dependency origins; NLI and screen scores; prompt and schema hashes; realization state and fallback reasons; `review_flags` (U1–U15); the engine's `complete` next to E's witness status; the obligation closure map; the frozen-contract classes and D-1 items; earliest-error slots |
| What moves here from Phase 28's answer | nothing verbatim; the subquestion order and the statuses come up | Supporting findings list; the operand texts; the statistics; the qualifications | ParentClaim ids, role names, proposition ids, reason codes, the 39-gap list, `hierarchy_carriage` findings, the c8 tracer |

**Rules.**

- Layer 1 contains no proposition ids, role names, snake_case tokens, reason codes, or claim ids.
- Layer 1 contains a number only inside a quoted source sentence, or where the number changes the meaning (a
  reported sign, a null result).
- Statistics (ρ, *p*, *t*) stay in Layer 2 unless the qualitative significance is the finding ("did not reach significance").
- "Not established" must always say *what* was not established and *for which facet*. A generic "not established" line is a
  Layer 3 fact, never a Layer 1 sentence (commitment 6).
- Progressive disclosure is an information-design statement here only. Interaction design is out of scope for Phase 29.

---

## 13. Validation architecture

Each check is classed **D** (deterministic), **N** (NLI or model judgment), **F** (fail-closed: failure forces the
fallback rung or removes the claim, never silently passes), or **A** (advisory: recorded, not gating). Examples are
the Phase 28 cases each check would have caught.

| Check | Class | What it tests | Phase 28 example it would catch |
|---|---|---|---|
| Authorized-claim fidelity | D, F | Every rendered value is a substring of a declared admissible quote; every claim id is in the allowed set | enumeration values rendered without a checked source |
| Source-passage fidelity | D (+ N) | Quote-level `canonical_text_contains`; NLI sentence-vs-declared-quotes | — (existing; unchanged) |
| Polarity | D, F | A value from a negated sentence cannot render as a bare category | c3 "implicit" from "not significant" (U2) |
| Hedge preservation | D, F | Hedge cues in the quote must appear in the sentence; `hedged` guard honoured at render time; the cue list is reviewed against the corpus, since the current lexicon misses "consistent with the possibility" | p9/p20 "We suggest"; p31 under "definitive" (U3, S-f) |
| Speculative and aim sources | D, F | "We suggest", "we tested the hypothesis", "aimed to" are not findings | p9/p20; the paper-67 aim sentence (c8) |
| Caption and structural source | D (cue) + A | Caption-like lines and "Table S\d+ \|" patterns are not findings | p27/p28 (U5). NLI accepted the clause, so this cannot be N. |
| Attribution | D, F | Prior-work, background and aim markers force attribution or Layer 2 | p40 (paper 61 intro) (U6) |
| Measurement subject | D (absent → unknown) + upstream | Trait-role values need a recorded perceiver subject; unknown fails closed for trait facets | p41 face ratings; "negative attitudes" and "undesirable behaviors" in a trait list (U4) |
| Role modality | N (advisory) + D | The bound value must satisfy the role's own description; modality from the source sentence | p1/p4/p8/p24 in four roles (U1); p24 as outcome (U8). Advisory in v1 because the role check is semantic. |
| Relation witness | D, F | Joint witness over **all** operands, including parent-context | c6 and c5 "complete" with no witness (U9) |
| Direction attachment | D, F | Direction attaches only through a witness-containing relation | "A direction finding (negative) was reported" (U10, S-e) |
| Referential closure | D, F | Anaphor lexicon; source-initial anaphora; in-sentence antecedent | "Across these levels…" ×2; "This research…" ×4 (S-d) |
| Definition support | D, F | Every acronym or named instrument has a supporting span or is replaced by its verbatim source name | DG, EBQ unexpanded; NAME in c12 (U11) |
| Ontology leakage | D, F | No snake_case identifier, role name, claim kind, or reason code in Layer 1 (identifiers derived from the contract, not a list) | 5 + 5 occurrences (S-c) |
| Redundancy and subsumption | D, F | S1–S3 rules; identical normalized sentence | five trait relations over p41; four "This research…" (S-b, S-d) |
| Cross-claim inference | D, F + N | Relation cue without a declared relation fails; NLI against each single passage for relation sentences | c1's behavior sentence joined to a caption (§2.2) |
| Citation ownership | D, F | Cited ids = union of declared claims' admissible set (or witness set for relations) | any model-chosen citation (none in Phase 28 by construction; kept as a guard) |
| Answerability honesty | D, F | A facet's status and the sentence cannot disagree; no "shows/establishes" for an unestablished facet | "Across these levels" under an unestablished relation (S-j) |
| Qualifier and operand completeness | D (operands) + A (caveats) | Relations realize all operands; the paper's own stated limits for the answered facet are carried into Layer 1 or disclosed | c4 narrowing; c12 durability caveat (§2.2) |
| Obligation coverage | D, F | Every node obligation is `assessed` or has a disclosed `not_assessed` line | direction and measure obligations unstated (S-k) |
| Construct identity | A (v1) | Adjacent-construct evidence carries its label | paper 14 behavior evidence (U7). Not fail-closed in v1, because the sealed record cannot decide construct identity on its own (D7). |
| Responsiveness | A | Relevance of a statement to its facet's literal text | advisory only |

**Fail-closed semantics.** A failed F-class check never drops a node silently. It moves the statement to the next
lower rung (F1 → F0) or to Layer 2, and records the reason in Layer 3. A **D** check that cannot run (missing
metadata) is treated as a failure, never as a pass. This is the operational form of commitment 6.

---

## 14. Model-call and stage architecture

| | Phase 28 (measured) | Proposed (Phase 28 artifacts, same profile) |
|---|---|---|
| Generation calls | 15 supervisor calls: W/C/U/P unchanged; S1 ×11 (64.2 s total); S2 ×1 (61.0 s) | Same role calls before S. S-role: child-answer ×≤11 (fewer when a node has nothing renderable); parent ×≤1. Total S-role ≤12 |
| NLI | per-sentence overview screens; one batched S2 entailment | Two batched passes: child sentences against declared quotes; parent sentences against declared child statements |
| Deterministic work | ledger, gaps, render | ledger, **AnswerPlan**, claim roles, witness and direction checks, closure and ontology lexicons, citation placeholder substitution, Layer 1/2/3 assembly |
| Latency class | ~1.7 ks end to end, dominated by W2 and the model stages | Same order. S-stage cost is comparable. No per-claim calls. |

**Decisions implied by the table.**

- **Nested questions do not share a call.** Each owning node gets its own call. The closure rule requires that a node's
  obligations be closed by its own answer. A shared call invites cross-node joins.
- **Current S1 is replaced in Layer 1** by the child-answer call. The overview record is kept as an audit artifact,
  for comparison in Step 3 (A/B against the deterministic Layer 1), then retired from the ordinary path.
- **Parent-node bridges are deterministic** when a node has no obligations of its own (for example "4" when only
  "4A" and "4B" carry content): "See 4A and 4B."
- **The S-role binding envelope** (`PARENT_SYNTHESIS_S_OPTIONS`, `think=False`) is preserved. A new child-answer
  envelope is a new profile and needs its own pin (D9).

---

## 15. Migration from current S1 and S2

| Component | Disposition | Notes |
|---|---|---|
| Hierarchy contract (frozen) | **Extend** (additive) | Add reviewed display labels per facet and role (D8); normalize approval-state vocabulary (D2). Freeze process applies. |
| Sufficiency engine semantics | **Preserve** in Step 1 | U9 is an upstream change with a separate gate (D3). Do not change in Phase 29. |
| Sufficiency map | **Preserve**, read-only consumer | |
| ParentClaim ledger | **Preserve** as audit and plan input | Extend relational claims with `witness_ids` and `operand_roles` (already computed in `relationship_witness_support_ids`). Change direction attachment per D1, which changes claim ids and so the construction hashes. Requires an explicit re-construction step. |
| Gap report and ResolvedEmptyOutcome | **Preserve** as Layer 3 | Add facet aggregation for Layer 1 |
| Citations (`format_citations`) | **Preserve**; **extend** with `{SOURCE}` placeholder rendering (citeproc short cite) | |
| Provenance hashes | **Preserve**; add `plan_sha256` to the construction record | |
| S2 (parent realization) | **Replace** (new prompt, new schema, inputs = validated child statements) | Keep mechanics: per-item validation, batched screen, budget constants, single call |
| S1 Overview (child) | **Deprecate for Layer 1**; **retain** its units, eligibility and screens; **keep** the record as audit | The overview `PROMPT_TEMPLATE` is pinned (`overview.py` comment). Do not edit it. The child-answer prompt is a new pinned template. |
| Flat (non-hierarchical) path | **Preserve** byte-identical until migration (`test_flat_path_golden.py`) | Later: express as a single-node plan. Not in Phase 29 Steps 1–4. |
| Frontend | **Out of scope** | Layers 2 and 3 need UI. Gated by DESIGN, QA and EXPERIENCE (CLAUDE.md rules 8, 10, 11) at Step 5. |

---

## 16. Phase-28 counterfactual paper prototype

**Status.** A human-authored counterfactual, written only from the preserved Attempt-2 artifacts, with no model calls.
It shows what the proposed structure would let the answer say. It is **not** a benchmark answer, not runtime gold
text, and not for tests or prompts. Where the evidence is suspect or insufficient, it says so. It does not repair
upstream errors from outside knowledge. Citations use the library's paper ids, as in the artifacts. The
deliverable would show citeproc author–year labels instead.

**Node labels and literal subquestions** are taken from the researcher-approved conceptual decomposition in the
Phase 29 brief. The run's own child notes differ in wording and numbering (U13); the mapping is below.

| Visible label | Approved subquestion (brief) | Run child | Run status |
|---|---|---|---|
| 1 | How does the bias manifest in brain structure and function across regions and networks? | c1 (+ c4) | candidate |
| 2 | How does it manifest in behavior? | c2 | candidate |
| 3 | How does it manifest in implicit and explicit attitudes? | c3 | candidate |
| 4 | Which specific brain areas or networks are implicated? | c4 | researcher-supplied |
| 4A | How do those areas relate to behavioral measures, including direction where established? | c5 | researcher-approved (CD-5) in the frozen contract; candidate in the ledger |
| 4B | How do those areas relate to implicit and explicit attitude measures, including direction where established? | c6 | candidate; approved without approval ref in the frozen contract |
| 5 | Which personality or individual-difference traits relate to it, and which scales measured them? | c8 (+ c9) | c8 candidate; c9 pending confirmation |
| 6 | Is there cross-cultural evidence bearing on generalizability? Which populations, and how was the bias measured? | c10 (+ c11) | c10 candidate; c11 pending confirmation |
| 7 | Are there effective interventions aimed at reducing the bias? | c12 | candidate |

Because c1, c2, c3, c8, c9, c10, c11 and c12 are not all confirmed in the artifacts, the counterfactual labels them as
candidates. Under D2, Layer 1 would show "awaiting your confirmation" for the unconfirmed ones. This prototype shows
their content anyway, to demonstrate the structure. That is itself a choice D2 must settle.

---

### Parent synthesis (one paragraph, across the answers below)

> The retrieved evidence supports three findings most firmly. Participants expressed explicit negative attitudes
> toward people with facial anomalies, measured with the Explicit Bias Questionnaire [paper 67, p14, p26]. The one brain
> area named is the amygdala, whose response to facial anomalies is reported as correlated with less prosociality
> [paper 67, p11]. And one study reports a clear reduction in implicit bias toward people with anomalous faces after an
> exposure-based intervention its authors developed [paper 248, p30]. Much of the rest is limited or not established.
> No passage links the amygdala to either attitude measure. The cross-cultural evidence comes from a single study whose
> measurement is not shown. The personality scales are not named. Several behavioral statements come from a study of
> partner biographies rather than facial anomalies, and are labelled as adjacent below.

*Trace:* every clause is taken from a child statement below, and each child statement is from a sealed passage.

---

### 1. How does the bias manifest in brain structure and function across regions and networks?
**Answered in part.** The one brain area named in the retrieved evidence is the amygdala. A passage reports that the
amygdala response to facial anomalies correlated with stronger just-world beliefs, less dispositional empathic concern,
and less prosociality [paper 67, p11]. These are correlations; the passage does not describe a causal effect. No brain
network is named, and no brain-structure measure appears in the retrieved evidence.

Two things are **not** used as findings. One sentence about neural responses and implicit biases is a supplementary
table caption ("Table S13 | Correlations between implicit biases and neural responses to facial anomalies"), not text
describing results [paper 67, p28]. A separate paper's introduction reports increased amygdala reactivity in people with
high implicit bias, attributed there to earlier fMRI work [paper 61, p40]. It is not this study's own result.

*Facet status:* relation (amygdala–prosociality) established as a correlation; networks not established; structure not
established.

### 2. How does the bias manifest in behavior?
**Answered in part.** The paper states that it confirmed earlier reports of a behavioral manifestation of the bias,
"affecting prosociality" [paper 67, p1]. That is the paper's own summary of earlier work, not a separate measurement.
The behavioral measure in the retrieved evidence is a partner-choice sharing task: participants shared more with a "good"
than with a "bad" partner [paper 14, p46] and were faster to share with the good partner [paper 14, p47].

Two cautions apply. Those partners were described by biography, in a study of trustworthiness; the retrieved text does
not involve facial anomalies at all, so this is **adjacent** evidence about partner-based behavioral bias, not a measure of
this bias. And the brain contrast reported in that study names no regions in the retrieved text [paper 14, p35], so it
cannot be linked to these behaviors. The main study's authors also note that the dictator and ultimatum games "may be poor
proxies" for real-world discriminatory behavior [paper 67, sealed span e11, not a verified claim]. That qualification is
about the main study's own behavioral measures.

*Note on the run:* the parent answer's line "evidence: implicit; explicit" and the "This research confirmed" sentence
appear under other facets in the run. They are not used here.

### 3. How does the bias manifest in implicit and explicit attitudes?
**Answered, with a null result on implicit attitudes.** Explicit: the paper reports explicit negative attitudes toward people
with facial anomalies, both as individual character inferences and as group-level scores on the Explicit Bias
Questionnaire [paper 67, p14, p26]. Implicit: in the same study, participants' implicit biases "were slight and not
significant" [paper 67, p36]. The retrieved evidence therefore does **not** show an implicit effect in this study. An
intervention study reports reduced implicit bias after an exposure-based intervention, measured with the Implicit Association Test (answer 7).

*Why this matters:* the run's parent fallback printed "implicit; explicit" as evidence. That line drops the negation and
reads as an implicit finding. This answer keeps the source's own words.

### 4. Which specific brain areas or networks are implicated?
**Answered in part.** Only the amygdala is named [paper 67, p11]. No network is named. Another study reports several brain
regions from a neural contrast, but the retrieved text does not name them [paper 14, p35], so they cannot be listed here.

### 4A. How do those areas relate to behavioral measures, including direction where established?
**Answered in part.** One passage relates the amygdala response to behavior: it correlates with less prosociality
(a negative association) [paper 67, p11]. The passage does not name the prosociality measure.

**Engine note.** The sufficiency map did not bind this clause to the brain–behavior requirement. Its behavior slot was filled
instead by the partner-task passages [paper 14, p46], which the answer above does not connect to any region.
Here the prototype reads the sentence directly and says so. Under the design this would be a candidate for researcher
confirmation, not an automatic link (§9.4).

### 4B. How do those areas relate to implicit and explicit attitude measures, including direction where established?
**Not established.** No retrieved passage relates the amygdala to the Explicit Bias Questionnaire or to any implicit
measure. The "negative" direction that the run printed under this facet describes the explicit attitudes themselves, not an
association with the amygdala [paper 67, p14, p26]. The only passage linking amygdala reactivity to implicit bias is in
another paper's introduction, attributed there to earlier fMRI work [paper 61, p40].

### 5. Which personality or individual-difference traits relate to its manifestation, and which scales measured them?
**Partly answered; the scales are not established.** The paper reports that the amygdala response correlated with stronger
just-world beliefs and less dispositional empathic concern [paper 67, p11]. Neither construct's measure is named in the
retrieved passages.

The only named scale, the Explicit Bias Questionnaire, measures attitudes, not traits [paper 67, p14]. Three things that look
like traits are **not** used. The five face-rating dimensions (attractiveness, trustworthiness, anger, dominance, threateningness) are
reported as ratings of faces, not as characteristics of perceivers [paper 60, p41]. "Negative
attitudes (IAT and EBQ)" and "undesirable behaviors (less generosity in the DG)" appear in a discussion sentence the authors
introduce with "We suggest" [paper 67, p9, p20]. They are suggestions, and the second is a behavioral measure. "DG" is not
expanded in the retrieved text.

### 6. Is there cross-cultural evidence bearing on generalizability? Which cultures or populations, and how was the bias measured?
**Partly answered; the measurement is not established.** One study reports that the stereotype is culturally shared, with the
authors writing that results "suggest" it, and that this provides evidence against a universal pathogen-avoidance explanation
[paper 68, chunk 14388]. The population named is the Hadza. That study reports that Hadza people who regularly interact with
outside groups were more likely to judge Hadza people with facial scarring as less moral [paper 68, p29, p53]. The retrieved
text ends mid-sentence at that point.

How the bias was measured in that population is **not established** in the retrieved evidence. No other culture is named.

### 7. Are there effective interventions aimed at reducing the bias?
**Partly answered, from one study.** The study's authors developed an intervention called "Normalizing Anomalies with Mobile
Exposure" (NAME) [paper 248, sealed span]. Its anomalous-faces variant produced "a clear reduction in implicit bias" against
people with anomalous faces, while bias toward people of color in that condition "remained essentially unchanged" [paper 248,
p30]. The authors write that their data "are consistent with the possibility that repeated, targeted exposure … can help
reduce negative implicit biases" [paper 248, p31], and that durability and generalizability need testing
[paper 248, sealed span e14].

One item in the run's outcome list is a bias description, not an intervention result [paper 67, p24]. It is excluded here.

---

### Trace and suspect items in this prototype

- **Caption-derived clause (c1 in the run):** excluded (U5).
- **Speculative trait list (c8 in the run):** excluded (U3, U4); the "undesirable behaviors" item is a behavioral measure by its
  own wording.
- **Face ratings as traits (c8 in the run, carried into c9):** excluded (U4).
- **Negation loss ("implicit", c3 in the run):** corrected from the source sentence (U2).
- **Relation without witness (c6, c5 in the run):** reported as not established (U9, U10).
- **Adjacent-construct behavioral evidence (c2, c5 in the run):** included, labelled (U7).
- **Prior-work sentence (c4 in the run):** attributed (U6).
- **Term without support:** "DG" and "EBQ" not expanded (U11); "NAME" expanded from its paper's own definition.
- **Truncated passage (c10/c11 in the run):** labelled as truncated.
- **Decomposition status:** c9 and c11 are awaiting confirmation under D2; the prototype shows their content to illustrate
  structure only.

---

## 17. Generalizability audit

The required test: would the architecture work unchanged if the decomposition concerned architecture and buildings, a
language-learning difficulty question, or a placebo-effect question? Each question below was checked against the
mechanism, not assumed.

**What is generic.** Every rule in §§5–13 is keyed on role identity (the requirement's role specification), claim kind,
quantifier, witness status, guard flags, the decomposition's approved wording, and English-generic cue sets. The cue sets are
`RELATION_CUES`, the hedge, negation, direction and causal lexicons in `overview_evidence`, the caption pattern, and the
anaphor lexicon. None of them contains q_aib vocabulary. The closest domain-touching items are the caption pattern (a journal
convention, generic) and the GROBID section families (science-specific, so the attribution fallback must be `unknown`, not
guessed, for non-scientific sources).

**Architecture and buildings.** Facets map to requirements (e.g., "how does ventilation relate to occupant comfort, and
which measures?"). Relations, direction and enumerations work as before. Closure would catch "this building" and
"these floors" openers. The main risk is upstream and the same as U4: a rating of a space ("comfort ratings for rooms") bound
as an occupant trait. The answer layer could only flag it, because nothing in the sealed record says whether a rating is of
the room or of the occupant. That is the `measurement_subject` gap, and it is domain-general.

**Language-learning difficulty.** Acronyms (L2, CEFR, CAT) are handled by §8.3. A word-difficulty rating (a property of
items) is the same identity risk as face ratings. Direction works ("higher difficulty was associated with …").

**Placebo effect.** The rule that "an attempt is not an effect" (`c12#constraint:attempt-is-not-effect`) generalizes to: an
effect claim requires a declared comparator. A placebo group that improved, with no comparator, is an attempt-level finding.
This needs a `comparator` attribute in the effectiveness contract (an additive contract change, D8-class). Without it, the
architecture would render "placebo reduced pain" from a single-arm result. With it, the rule is generic.

**Conclusion.** The architecture is generic at the answer layer. Its correctness depends on upstream semantic mapping, which
is domain-sensitive, and the two gaps that matter for generalization are (a) a measurement-subject attribute and (b) a
comparator attribute for effect claims. Both are contract additions, not answer-layer logic, and both should be decided
before Step 1 is treated as domain-general.

---

## 18. Risks and unresolved design choices

**Decisions needed from Cliff** (recommended default in each; none requires a model run to decide):

| ID | Decision | Recommended default | Why it matters |
|---|---|---|---|
| **D1** | Direction representation | **Option B with a fail-closed attachment rule**: direction attaches to a relation only through its witness; otherwise it is a value-level valence on its own subject; otherwise suppressed | Determines whether "direction" can ever again be printed without operands |
| **D2** | Decomposition authority | Layer 1 answers only nodes with an explicit approval state (`researcher_approved` or `researcher_supplied` with a ref). Others show "awaiting your confirmation" and keep their evidence in Layer 2 | Changes what the current run would print: c1, c2, c3, c8, c10 are not explicitly approved in the artifacts; c9, c11 are pending. The prompt's premise of a confirmed decomposition is not what the artifacts record. |
| **D3** | Relation completeness (U9) | Answer layer applies the joint-witness test now (fail-closed). Engine change is a separate, gated upstream increment | Engine change would alter frozen sufficiency semantics and Phase 26–28 outputs |
| **D4** | Attribution requirement | Plan requires an attribution kind for every claim; `unknown` → Layer 2 only. Sources: GROBID section family where present (inc 479), otherwise lexical cues, advisory | Without it, background and prior-work sentences look like results |
| **D5** | Rendering authority: quote versus proposition text | Render operands from the verbatim quote. Proposition text is for ranking and display of the restatement only | U12 |
| **D6** | Qualification attachments from sealed spans not in any verified proposition (e.g., the "poor proxies" span) | Add a `qualification` record type attached by witness passage, authorized by being in the sealed ledger. Shown in Layer 2, and in Layer 1 where it bears on the answered facet | Expands which sealed evidence is displayed; needs an explicit decision because it changes authority |
| **D7** | Construct identity (U7) | Contract adds a requested-construct phrase per facet; evidence outside it is labelled `construct_adjacent`. Whether adjacent evidence may answer a facet at all is the researcher's call | The sealed record cannot decide construct identity on its own |
| **D8** | Display labels and comparator attributes in the frozen contract | Additive, reviewed fields: a human phrase per facet and per role; a comparator attribute for effect claims | Required to remove ontology terms from Layer 1 and to support the placebo case |
| **D9** | Pins and freezes | New child-answer and parent prompts/schemas are new pinned profiles. The S1 overview `PROMPT_TEMPLATE` stays untouched | Governance: pinned inputs and freeze precedents (inc 557, inc 575) |
| **D10** | Parent sentence bound and orientation wording | `maxItems = min(4, answered nodes)`; orientation line in count-of-named-states form only | Commitment 7; a bound must not look like a judgment about completeness |
| **D11** | S1 display retirement | Keep the S1 overview record as audit; A/B once against the deterministic Layer 1 in Step 3, then retire from the ordinary path | Avoids discarding its screens or its evidence trail |

**Risks (not decisions).**

- **NLI is blind to source kind.** It accepted the caption clause (U5). Source-kind checks must be deterministic.
- **NLI may accept a cross-passage join.** The single-passage witness rule is structural, not left to NLI.
- **Lexicon coverage.** A missing cue is a false negative. The NLI backstop and the fail-closed rung limit the damage, but do not eliminate it.
- **Over-merging.** S3 merges only on identical witness and identical operand roles. A passage that reports two distinct findings must not collapse. The test set must include such a passage.
- **Enumeration pressure returns.** If the child prompt keeps "each must be stated" in any form, lists will reappear. The new prompt must not reuse that sentence.
- **Anaphora in source** cannot be fixed without neighbouring-span retrieval (v2).
- **Latency and quality trade-off.** Two batched NLI passes and an extra deterministic stage are cheap. A second model pass for re-rendering failed sentences is not in this design, and should not be added without a measured reason (LATENCY.md).
- **The counterfactual is hand-derived.** Appendix A's roles and counts were assigned by reading the artifacts, not by running code. Step 1 must reproduce them mechanically before any claim about the counts is treated as a result.

---

## 19. Smallest sensible implementation sequence

Each step has a gate. No step changes frozen or pinned artifacts without its decision.

**Step 0 — decisions (no code).** Settle D1, D2, D3 (required); D5, D8 (required for Step 1 display labels); D4, D6, D7, D9–D11 as
needed by later steps. Record decisions in the increment notes.

**Step 1 — offline deterministic AnswerPlan and Layer 1 (no model, no pin change).**

- Pure builder: nodes, facets, claim roles, witness and direction checks, subsumption S1–S3, salience-independent
  dedupe, answerability states, closure lexicon, polarity and hedge checks against verbatim quotes, ontology check, F0/F1/F3
  rungs (F2 once display labels exist).
- Replay on the preserved Attempt-2 artifacts only. Output: a deterministic Layer 1 for the run.
- Tests: synthetic fixtures for each rule (not q_aib expected text); the preserved artifact as an offline regression fixture,
  with the Appendix A roles asserted.
- Gate: review of the replay output against §16. Any disagreement is recorded, not tuned to.

**Step 2 — offline Layer 2 and Layer 3 assembly, and citation placeholders.** Source labels via citeproc; Layer 2 quote
blocks; Layer 3 `review_flags`. No UI.

**Step 3 — child-answer model call (gated live run).** New pinned profile. Per-node calls with closed schemas, screens and
per-facet fallback. A/B against Step 1 Layer 1 on the same artifacts. Live run only after explicit approval.

**Step 4 — parent synthesis over validated statements (gated live run).** New pinned profile; deterministic orientation line
always present.

**Step 5 — interface for Layers 2 and 3.** Gated by DESIGN, QA and the experience pass (CLAUDE.md rules 8, 10, 11).

**Step 6 — upstream fixes, each separately gated.** U9 (completeness semantics), measurement-subject and comparator attributes
(D8), attribution at ingest (D4), caption and aim classification at ingest, role-specificity for `*_evidence` and
`observed_*` roles (U1, U8), polarity-aware category extraction (U2), restatement fidelity (U12).

---

## 20. Recommendation

**NOT READY** for implementation of the child-answer and parent-synthesis stages, or of the architecture as a whole.

**READY** for **Step 1 only** (offline, deterministic AnswerPlan and Layer 1, replayed on the preserved Attempt-2 artifacts),
once Cliff has settled **D1** (recommended: option B with fail-closed attachment), **D2** (recommended: explicit approval
required for Layer 1), and **D3** (recommended: answer-layer joint-witness test now; engine change later and gated).

Step 1 is the most valuable first increment for three reasons. It needs no model run and no pin change. It removes the
failures a reader sees first (organization, repetition, ontology leakage, the inverted negation, the direction without
operands, and silent unanswerability). And it tests whether the architecture's claims hold on real data before any
model stage is built on top of it.

---

## Appendix A — ParentClaim plan roles for the Phase 28 Attempt-2 ledger

**Hand-derived** from the artifacts in §2 and the propositions' verified quotes, not produced by code. Step 1 must
reproduce these mechanically. The counts are a check, not a result.

| # | ParentClaim (kind · child · props) | What the sealed text supports | Proposed role | Reason |
|---|---|---|---|---|
| 1 | relational::5d178917 · c4 · p11 | amygdala response correlated with stronger just-world beliefs, less empathic concern, less prosociality | **primary** (facet 4); closure repair needed for the leading anaphor | complete and witnessed by one passage |
| 2–6 | relational ×5 · c8 · p41 (paper 60) | rated impressions of faces (attractiveness, trustworthiness, anger, dominance, threateningness) correlated with facial proportionality | **suppressed** (identity_suspect), one passage group | face ratings are not perceiver traits (U4); five claims, one passage (S3) |
| 7 | direction::97e9b66f · c6 · p14, p26 | explicit negative attitudes (valence of the attitude measure) | **primary** as value-level valence for the attitude facet; **not** a brain–attitude direction | D1 rule; U10 |
| 8 | role_value::8d0ce9c4 · c1 · p1 | "This research confirmed earlier reports … behavioral manifestation … prosociality" (paper 67 summary) | **attributed_primary** under facet 2 with `{SOURCE:67}`; **modality_mismatch** for c1 | U1: bound to a neural role by a deterministic predicate |
| 9 | role_value::57b25a88 · c1 · p11, p2 | "the specific amygdala response" | **context** (operand of 1) | bare noun phrase |
| 10 | role_value::b9591e4f · c2 · p4 | same sentence as 8 | **duplicate_of** 8 | S2 |
| 11 | role_value::34d05796 · c3 · p8 | same sentence as 8 | **duplicate_of** 8 | S2; U1 (attitude role) |
| 12 | role_value::161d9d58 · c4 · p40 (paper 61) | "Laypersons with high levels of implicit bias … increased amygdala reactivity" (paper 61 intro, prior work) | **attributed_only** (Layer 2) | U6; a region role accepting a finding phrase |
| 13 | role_value::1f1af648 · c4 · p11 | "the specific amygdala response" | **subsumed_by** 1 | S1 |
| 14 | role_value::c33c4ccf · c6 · p17 | "explicit" (keyword) | **context** (folded into 21) | keyword, no predicate (U2 family) |
| 15 | category_list::775fda77 · c10 · p29, p53 (paper 68) | "Hadza" (named population) | **context** (population operand); **truncated** flag | quote ends mid-sentence |
| 16 | category_list::d4746534 · c12 · p24, p30, p31 | p30: NAME reduced implicit bias in the anomalous-faces condition; p31: "consistent with the possibility" of reduction; p24: a bias description | **primary** for p30 and p31 (hedge kept; NAME from its paper's definition); **suppressed** (misbinding_suspect) for p24; label "definitive" removed | U8; F2 with per-value checks |
| 17 | category_list::10ddc38d · c2 · p35, p46, p47 | p46 and p47: partner-task sharing and speed (paper 14); p35: an fMRI contrast's task description | **primary** for p46 and p47 with `construct_adjacent`; **suppressed** (modality_mismatch) for p35 | U7, U14 |
| 18 | category_list::7af59a3e · c5 · p46, p47 | the same partner-task passages as 17 | **duplicate_of** 17, for facet 4A only; facet 4A relation **not established** | S2; U9 |
| 19 | category_list::f1f51b4b · c8 · p20, p9 (paper 67) | "We suggest that dehumanization is underpinned by …" (emotional dispositions; negative attitudes IAT/EBQ; social cognitive biases; undesirable behaviors DG) | **suppressed** (speculative_source, identity_suspect) | U3, U4; IAT is defined only in paper 248; EBQ and DG are not defined |
| 20 | category_list::9fd341f1 · c3 · p36, p8 | p36: "implicit biases were slight and not significant"; p8: explicit | **primary**, re-rendered F1 from the verbatim p36 sentence (negation intact) for the implicit facet | U2: the one fallback fault that inverts a finding |
| 21 | category_list::f453ebb7 · c6 · p14, p17, p26, p3, p7 (paper 67) | the named measure, Explicit Bias Questionnaire, for explicit negative attitudes | **primary** for the attitude-measure facet (verbatim measure name); five propositions, one passage (S2) | the label "a named attitude type or measure" is not printed; the name is |

**Tally (hand-derived).** 21 ParentClaims resolve to: **7** answer-level statements (claims 1, 7, 8, 16, 17, 20, 21, with
16 and 17 each split); **4** duplicates or subsumed (10, 11, 13, 18); **3** context operands (9, 14, 15); **1** attributed-only
(12); **6** suppressed (2–6 as one identity group, and 19). Partial suppressions inside 16 (p24) and 17 (p35) are counted with
their claim.

## Appendix B — Key sealed evidence used in this audit

| Proposition / span | Paper | Verbatim (abridged) | Used for |
|---|---|---|---|
| p11 | 67 | "Across these levels of organization, the specific amygdala response to facial anomalies correlated with stronger just-world beliefs …, less dispositional empathic concern, and less prosociality …" | 1, 4, 4A, 5 |
| p14, p26 | 67 | "…found evidence for the 'anomalous-is-bad' stereotype in explicit negative attitudes … Explicit Bias Questionnaire" | 3, 4B |
| p36 | 67 | "…their implicit biases were slight and not significant." | 3 (negation case) |
| p1, p4, p8, p24 | 67 | "This research confirmed earlier reports … behavioral manifestation … prosociality" | U1 |
| p9, p20 | 67 | "We suggest that dehumanization is underpinned by a suite of negative attitudes (IAT and EBQ) … undesirable behaviors (less generosity in the DG) …" | U3, 5 |
| p27, p28 | 67 | "Neural responses to facial anomalies …"; "Correlations between implicit biases and neural responses …" (caption wording, chunks 35123/35125; "Table S13" caption in chunk 35368) | U5 |
| sealed span e11 | 67 | "It may be that the Dictator and/or Ultimatum Games are poor proxies for the kinds of real-world discriminatory behaviors …" (not a verified proposition) | D6; 2 |
| p41 | 60 | "Across the ratings for all faces, Spearman correlations revealed …" | U4 |
| p40 | 61 | "Recent work with functional magnetic resonance imaging has implicated … Laypersons with high levels of implicit bias … increased amygdala reactivity." | U6; 4B |
| p29, p53 | 68 | "…Hadza who regularly interact with outside cultural groups were more likely to think Hadza with facial scarring were less moral and were better" (truncated) | 6 |
| chunk 14388 | 68 | "results suggest the anomalous-is-bad stereotype is culturally shared, providing evidence against a universal pathogen avoidance byproduct hypothesis." | 6 |
| p30, p31 | 248 | "…the anomalous faces variant of the NAME intervention produced a clear reduction in implicit bias…"; "…consistent with the possibility that repeated, targeted exposure … can help reduce negative implicit biases…" | 7 |
| sealed span (NAME definition) | 248 | "We developed the 'Normalizing Anomalies with Mobile Exposure' (NAME) intervention …" | 7, U11 |
| sealed span e14 | 248 | "…may offer a promising, scalable approach … although further research is needed to test durability and generalizability…" | 7 |
| p46, p47, p35 | 14 | sharing-decision and reaction-time results (t11 statistics); "…yielded several brain regions defined by strength of effect…" | 2, 4, U7, U14 |
| paper 14, all 182 spans | 14 | 0 matches for "anomal" or "facial"; 9 for "biograph", 11 for "trustworth" | U7 |

## Appendix C — Contribution lineage

Recorded as an entry in `CONTRIBUTION-LINEAGE.md` (appended; prior entries unchanged).
