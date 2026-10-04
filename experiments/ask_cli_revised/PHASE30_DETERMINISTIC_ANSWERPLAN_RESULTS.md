# Phase 30 — Step 1: Deterministic AnswerPlan and Layer-1 Replay: Results

**Date:** 2026-10-04 · **Branch:** `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`
**Starting HEAD (verified, full):** `93f09d00905cec3360f1c5b35270ac5b31d35d68` (clean; 0 ahead / 0 behind origin)
**Governing audit:** `PHASE29_QUESTION_ORGANIZED_ANSWER_ARCHITECTURE_AUDIT.md`, accepted with decisions D1–D11 (§3).
**Scope:** offline, deterministic, no model, no network, no live run, no prompt change, no pin refresh, no frontend, no
upstream sufficiency-engine change. The preserved Phase-28 Attempt-2 artifacts are the only empirical input, and they are
not modified.

---

## 0. Summary

- Step 1 is implemented as pure functions over the preserved artifacts: a deterministic AnswerPlan, a
  question-organized Layer 1, Layer 2 supporting evidence, and a Layer-3 audit with 36 mechanical checks.
- The replay is deliberately conservative. It gives **no node a full answer**, **three nodes a partial answer** (3, 4B,
  7), and **six nodes "not established in the retrieved evidence"** (1, 2, 4, 4A, 5, 6). Every node is stated, every
  unestablished relation is stated as unestablished, and nothing is repaired by hand.
- The most consequential cost is visible in the output. The one brain area the evidence names, the amygdala, is reachable
  only through a referring phrase and a scope clause whose referent is outside the retrieved text. Step 1 correctly declines
  to state it. Recovering it needs an upstream binder change or neighbour-span retrieval (§14, item 1).
- All 36 mechanical checks pass. The plan hash is reproducible. The rebuilt ParentClaim ledger reproduces the 21 Phase-28
  claim ids exactly. Four engine-complete relation instances are recorded as unwitnessed in Layer 3.
- Tests: 24 synthetic, question-agnostic unit tests and 10 offline regression tests on the preserved artifacts.
- **Step 2 readiness:** READY to proceed to offline Layer-2/3 consolidation, conditional on the items in §13 and §14.
  **NOT READY** for the model child-answer and parent-synthesis stages (Steps 3–4). The authorized bindings support two
  verbatim findings plus limitations. A model would have to write around missing links.

---

## 1. Starting and final state

- **Starting state verified:** HEAD `93f09d00905cec3360f1c5b35270ac5b31d35d68`; branch correct; tree clean; 0 ahead / 0
  behind origin; Phase-29 audit present; Attempt-2 raw run present; frozen contracts unchanged. The sufficiency v9 frozen
  file was last changed by `40f45622` and the hierarchy frozen contract by `617699de`. Neither was modified in this phase.
- **State when this file was written:** the Phase-30 files were staged and the introducing commit had not yet been created.
  Committing was blocked by the pre-existing line-budget hook (`app/frontend/js/20_synthesis.jsx`, 615 lines, unchanged by this
  increment). The commit was then created with `--no-verify`, under an explicit approval for that single Phase-30 Step-1 commit.
  The resulting commit hash is reported in the handback, not inside this file, so the file does not carry a self-referential hash.
- **Scope of the change:** no existing module was modified. The changes are new files plus an appended entry in
  `CONTRIBUTION-LINEAGE.md`.
- **Files added:**
  - `experiments/ask_cli_revised/answer_plan/`: `__init__.py`, `overlay.py`, `text.py`, `relations.py`, `classify.py`,
    `plan.py`, `render.py`, `replay.py`
  - `experiments/ask_cli_revised/answer_plan/overlays/phase30_replay_decomposition_overlay.json`
  - `experiments/ask_cli_revised/test_answer_plan.py`, `experiments/ask_cli_revised/test_answer_plan_replay.py`
  - `experiments/ask_cli_revised/phase30_replay/`: `replay_decomposition_authorization.json`, `answer_plan.json`,
    `answer_plan_audit.json`, `deterministic_layer1.md`, `deterministic_layer2.md`,
    `comparison_against_phase29_hand_audit.md`
  - `experiments/ask_cli_revised/PHASE30_DETERMINISTIC_ANSWERPLAN_RESULTS.md` (this file)
- **Committed artifact size:** `answer_plan.json` is about 158 KB and `answer_plan_audit.json` about 64 KB. The Layer files
  are under 10 KB each. These are derived text, not raw run data, and the raw run is not committed.

---

## 2. Exact semantics implemented

**`overlay.py`.** Loads the replay-only overlay, hashes it canonically, and validates it against the sufficiency map and the
frozen contract. Validation refuses: a child in the map that no node owns (and is not folded); a child owned twice; a
human-review obligation the frozen contract does not record as a human-review meaning; a missing facet or role phrase; an
empty literal wording. The overlay carries the researcher-confirmed wording from the Phase-29 brief verbatim.

**`relations.py` (D3).** For every requirement with two or more required roles, and every instance, it records the operands
with their source (`own` or `parent_context`). The answer layer's joint witness is the intersection of every filled operand's
proposition support, **including inherited operands**. Statuses: `witnessed` (engine complete and a joint witness exists);
`unwitnessed_complete` (engine complete, no witness: a recorded disagreement); `incomplete`. The engine's `complete` flag is
recorded, never replaced.

**`text.py`.** Deterministic text checks and display transforms. Each is a named test, and none rewrites meaning.
- Sentence split on terminal punctuation followed by a capital, quote, or parenthesis.
- **Closure lexicon:** scope phrases that refer outside the text ("across these levels"); sentence-initial anaphors ("these",
  "such", "it", "they"); pronouns after a discourse marker ("Accordingly, they…"); in-sentence "this/these
  research/study/levels…".
- **Run-in heading removal:** a section heading fused to the front of a sentence, before a sentence-initial pronoun. Recorded
  as an edit.
- **Source-label substitution:** a sentence-initial "This research/study/work/paper" becomes the library source label
  (`Paper N`). Recorded as an edit; the rest of the verbatim sentence, including hedges, is untouched.
- **Caption detection:** a table or figure label at the start of a passage, or the passage's wording appearing after such a
  label in the same paper's sealed spans.
- **Truncation:** a passage that does not end in terminal punctuation.
- **Attribution (D4), lexical only:** caption, then `aim_or_hypothesis` (suggestion or aim cues, reusing
  `contract_directed/attribution.py`), then `prior_work` (prior-literature cues), then `this_study_result` (result language,
  including significance and comparison words, and reported statistics), otherwise `unknown`. The replay fixture has no
  section metadata, so no structural attribution is used.
- **Requested-construct identity (D7):** a witness is *direct* only if its passage, or its own paper's sealed text, contains
  a facet term from the overlay.
- **Stimulus-rating cue** (trait-role values only): "rated", "ratings", or "impressions" in the witness.
- **Display-only linebreak normalization (U15):** a line-break hyphen is joined only when the joined word occurs in the sealed
  corpus; otherwise the hyphen is kept.
- **Acronym support (U11):** an acronym is supported only by an explicit "Long form (ABBR)" or "ABBR (long form)" pattern in
  sealed text. Support is reported. It is never used to expand a term in a rendered sentence.

**`classify.py`.** Every candidate sentence is tested against its own verbatim passage. All checks are recorded, and a sentence
renders only if every check passes. The checks are: not a caption; complete passage; not a generic summary (the same passage
bound as a whole-passage predicate under two or more requirements); attribution is `this_study_result`; referentially closed;
requested construct direct; and, for trait roles, not a stimulus rating.
- **Relational claims** render only if one sentence of one passage contains every operand and the claim is witnessed under the
  D3 test. Otherwise they are suppressed (`unwitnessed_relation` or `operands_not_in_one_sentence`).
- **Value claims** render verbatim sentences. A bare keyword is never rendered; the sentence containing it is.
- **Enumeration (F2)** only when every value is a single complete phrase (at least two words, one sentence, no closing
  punctuation), each value's own sentence passes the polarity and hedge checks, and a facet phrase exists.
- **Direction (D1):** attaches to a relation only when the observation is in that relation's witnessed set. Otherwise it
  renders only as a value-level sentence containing both its subject and its sign, and only if it passes every check.
  Otherwise it is suppressed. The phrase "A direction finding (negative) was reported" cannot be produced: there is no such
  template, and a test and an invariant enforce this.

**`plan.py`.** Assembles facets (one per requirement), nodes (from the overlay), and renders.
- **De-duplication is node-scoped.** Identical normalized sentences collapse to the first. The kept render takes every
  duplicate's values. A value sentence contained in a displayed relation is subsumed.
- **Facet coverage** is by render roles, by containment of a filled binding's text in a displayed sentence, and, for
  cardinality requirements, by category value. A duplicate's kept sentence counts toward its own facet.
- **Facet states:** `answered` (all required roles covered, and the relation witnessed if relational), `partial`,
  `not_established`, `searched_empty` (from the scoped-search outcome, when present).
- **Disclosures** are fixed human-language templates. A relational facet whose relation is not witnessed always says so.
- **Qualifications (D6):** a sealed sentence not contained in any verified quote, from the same paper, with a limitation cue
  and at least two content words shared with a displayed statement. Background (prior-work, aim, literature, or design
  rationale) is excluded. A qualifier is **promoted** to Layer 1 only if it carries a scope qualifier and stands on its own;
  otherwise the node carries a fixed pointer to it.
- **Plan hash:** SHA-256 over the canonical plan body.

**`render.py`.** Layer 1 is verbatim sentences and fixed disclosures, with numbered source markers and a source list. It
contains no proposition ids, claim ids, role names, snake_case identifiers, or reason codes. Layer 2 lists withheld candidates
with their verbatim passages and fixed reasons. The invariant report contains 36 named checks.

**`replay.py`.** Reads only the preserved artifacts. It validates the overlay, builds the plan **twice** to test determinism,
rebuilds the ParentClaim ledger and compares its ids with the Phase-28 `15a` record, and writes the outputs. It does not write
into the run directory.

---

## 3. Decisions D1–D11 as applied

| Decision | How applied | Where verified |
|---|---|---|
| **D1** direction | Attaches only through a witnessed relation. Otherwise value-level valence with subject and sign in one clean sentence. Otherwise suppressed. There is no "direction finding" template. | Synthetic direction test; replay `U10`; claim 7 becomes a verbatim valence sentence under 4B, not a brain–attitude direction |
| **D2** (modified) | Replay-only overlay `phase30_replay_decomposition_overlay.json`, hashed into `replay_decomposition_authorization.json` (overlay SHA-256 `3cca99b5ac7078f4ae7633f4e4b53360f0e5cd1ff6e0972e9cce7f71d0979c96`). Recorded as postdating the Attempt-2 run, with no claim that the live run had it. Layer 1 answers exactly the overlay's nine nodes. Historical statuses are recorded, not resolved (U13). | `test_answer_plan_replay.py::test_replay_authorization_is_bound_to_the_overlay_and_does_not_claim_the_live_run` |
| **D3** | Answer-layer joint witness over all operands, including inherited ones. Four disagreements recorded (§12). Relations not witnessed are stated as not established. No engine change. | §12; `unwitnessed_relation`; `U9` |
| **D4** | Every rendered sentence carries an attribution kind. `unknown` is never primary. Lexical only. | §2; `attribution_*` reasons; synthetic attribution test |
| **D5** | Every rendered sentence is verbatim quote text. Proposition restatements are never rendered. | Invariants `verbatim_from_passage` and `not_restatement_text` |
| **D6** (narrow) | Sealed non-verified sentences may qualify, never create. Three limitations are promoted to Layer 1 under node 7. One pointer. Background is excluded. | §2; node 7 in Layer 1; §14 item 8 (recall limit) |
| **D7** | Requested-construct terms are in the overlay. Paper 14's partner-biography evidence is construct-adjacent: Layer 2 only, and it does not answer nodes 2 or 4A. | `requested_construct_direct` reasons; `U7` |
| **D8** | Display phrases for facets, roles, categories, and obligations are in the overlay. No raw ontology names in Layer 1. No frozen-contract change; comparator attributes deferred. | Invariants `layer1_no_internal_terms_or_templates` and `layer1_no_snake_case_identifiers` |
| **D9** | No pins touched. No new prompt. | Not applicable (no generation) |
| **D10** (modified) | No count sentence in Layer 1. Node-state counts are stored in `answer_plan.json` under `parent.node_state_counts`. | `answer_plan.json` |
| **D11** | The current S1 is not invoked, read as an answer source, or modified. | Not applicable |

**Overlay mapping (confirmed by Cliff Workman).** The visible structure is applied to child ids as follows: 1→c1, 2→c2, 3→c3,
4→c4, 4A→c5, 4B→c6, 5→c8+c9 (c9 is the trait/scale pairing), 6→c10+c11 (c11 is the culture/operationalization pairing), 7→c12.
The c9→5 and c11→6 assignments were confirmed by the researcher and are recorded in the overlay's `mapping_confirmation` field.

---

## 4. Replay authorization and input hashes

| Item | Value |
|---|---|
| Overlay SHA-256 | `3cca99b5ac7078f4ae7633f4e4b53360f0e5cd1ff6e0972e9cce7f71d0979c96` |
| Authorization SHA-256 | `74ecd832ea88fce183e7c72762a926d84c61e77578ce73e20885389671a61509` |
| Sealed ledger hash | `1dce0e1c2dead992c631f9eb9bfaaa4fc29cabb30ec9304687df515cd4abeef8` |
| Sufficiency map SHA-256 | `28478500e485137cd6930b8010d274bb1da3afd48e7f4a6208dd183610d9ca0b` |
| Frozen hierarchy contract SHA-256 | `3e86cb8f0d7816bbc9aeac7d717e9ea4a709981a1e98406c577b8623aab1d0f2` |
| Phase-28 ParentClaim ledger SHA-256 | `8ee2e937756fb0762a3673112834b97c15cabd344f373b2555cde631b6db7ff0` |
| **AnswerPlan SHA-256** | `f083139b84f5d9b68f57375feb2e84eddac978e0f2d97be965a670795ed6a750` |

---

## 5. Tests and checks

- **Synthetic, question-agnostic (`test_answer_plan.py`): 24 tests**, using alpha/beta/gamma stand-in vocabulary. Each test names
  the rule it exercises: text rules, relations, direction, classification, qualification, overlay validation, determinism, and
  rendering invariants.
- **Offline regression on the preserved artifacts (`test_answer_plan_replay.py`): 10 tests.** They check invariants, node states,
  node presence and order, the four disagreements, the verbatim negated sentence, the adjacency and generic exclusions,
  value-level direction, the absence of internal identifiers, the authorization binding, and determinism. They skip if the
  gitignored run directory is absent. Expectations are structural and were not tuned to the Phase-29 prototype.
- **Lint and format:** `ruff check` and `ruff format --check` pass on the new files only (scoped, per the concurrent-session rule).
- **Existing `ask_cli_revised` suite under network refusal:** `python -m experiments.ask_cli_revised.contract_directed.offline_pytest experiments/ask_cli_revised -q`: **2596 passed, 11 skipped, 2 deselected** (endpoint-guard mechanics tests that need an unpatched socket), **3 failed**. All three failures are pre-existing and unrelated to this increment, and each still fails with the Phase-30 files moved out of the tree. (a) `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored` attempts a real connection to a local model endpoint, which is refused in this environment. (b) `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts` and (c) `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects` report `pin drift: code input hierarchy_contract.py changed since the pins were generated`, while that file is unmodified relative to HEAD. They are recorded for the maintainer and not repaired here.

---

## 6. Mechanical checks over the Phase-28 Attempt-2 replay

| Mechanical check | Result |
|---|---|
| `layer1_no_snake_case_identifiers` | pass |
| `layer1_no_proposition_ids` | pass |
| `layer1_no_claim_ids` | pass |
| `layer1_no_internal_terms_or_templates` | pass |
| `every_confirmed_node_appears_with_literal_wording` | pass |
| `nested_labels_visible` | pass |
| `no_linebreak_hyphen_artifacts` | pass |
| `no_acronym_expansion_printed` | pass |
| `verbatim_from_passage:category_list::9fd341f1bbff788b` | pass |
| `not_restatement_text:category_list::9fd341f1bbff788b` | pass |
| `verbatim_from_passage:direction_or_effectiveness::97e9b66f0fd3c1c2` | pass |
| `not_restatement_text:direction_or_effectiveness::97e9b66f0fd3c1c2` | pass |
| `verbatim_from_passage:category_list::d47465340e922bca` | pass |
| `not_restatement_text:category_list::d47465340e922bca` | pass |
| `verbatim_from_passage:category_list::d47465340e922bca` | pass |
| `not_restatement_text:category_list::d47465340e922bca` | pass |
| `verbatim_from_passage:qualification:e13` | pass |
| `verbatim_from_passage:qualification:e4` | pass |
| `verbatim_from_passage:qualification:e24` | pass |
| `U1_generic_summary_not_stated` | pass |
| `U2_no_bare_polarity_keyword` | pass |
| `U3_speculative_trait_list_not_stated` | pass |
| `U4_face_ratings_not_perceiver_traits` | pass |
| `U5_caption_not_a_finding` | pass |
| `U6_prior_work_not_stated_as_result` | pass |
| `U7_adjacent_construct_not_an_answer` | pass |
| `U8_bias_description_not_intervention_outcome` | pass |
| `U9_unwitnessed_relation_not_claimable` | pass |
| `U10_direction_names_its_subject` | pass |
| `U11_no_unsupported_expansion` | pass |
| `U14_task_description_not_a_result` | pass |
| `U15_display_hyphen_normalized` | pass |
| `U13_historical_status_recorded_separately` | pass |
| `replay_plan_deterministic` | pass |
| `parent_claim_ledger_rebuilds_identically` | pass |
| `no_model_calls` | pass |

The U-checks are properties of the rendered output. For example, `U2_no_bare_polarity_keyword` tests the rendered text, not
the binder.

---

## 7. Mechanically derived replacement for Appendix A

Mechanically derived by `answer_plan/replay.py`. The 'Agree' column compares only whether a claim appears in
Layer 1. Duplicates and subsumed claims fold into another claim and are not compared separately.

| # | ParentClaim | Child | Phase-29 hand role | Mechanical role | Hand: in Layer 1? | Mechanical: in Layer 1? | Agree |
|---|---|---|---|---|---|---|---|
| 1 | `relational::5d178917787a…` | c4 | primary | suppressed: referentially_closed | yes | no | **NO** |
| 2-6 | `relational::6d3e9d91766c…` | c8 | suppressed (identity: stimulus ratings) | suppressed: not_stimulus_rating | no | no | yes |
| 2-6 | `relational::bac1b3e1196e…` | c8 | suppressed (identity: stimulus ratings) | suppressed: not_stimulus_rating | no | no | yes |
| 2-6 | `relational::99d44d22bc14…` | c8 | suppressed (identity: stimulus ratings) | suppressed: not_stimulus_rating | no | no | yes |
| 2-6 | `relational::629c3c06bf89…` | c8 | suppressed (identity: stimulus ratings) | suppressed: not_stimulus_rating | no | no | yes |
| 2-6 | `relational::6e5d1f4ca669…` | c8 | suppressed (identity: stimulus ratings) | suppressed: not_stimulus_rating | no | no | yes |
| 7 | `direction_or_effectivene…` | c6 | primary as value-level valence | displayed (value-level) | yes | yes | yes |
| 8 | `role_value::8d0ce9c4405f…` | c1 | attributed_primary (facet 2) | suppressed: passage_not_generic_summary | yes | no | **NO** |
| 9 | `role_value::57b25a887d32…` | c1 | context (operand of 1) | suppressed: referentially_closed | no | no | yes |
| 10 | `role_value::b9591e4fba42…` | c2 | duplicate_of 8 | suppressed: passage_not_generic_summary | n/a | n/a | n/a (folds into another claim) |
| 11 | `role_value::34d05796cc1d…` | c3 | duplicate_of 8 | suppressed: passage_not_generic_summary | n/a | n/a | n/a (folds into another claim) |
| 12 | `role_value::161d9d5825b7…` | c4 | attributed_only | attributed_only | no | no | yes |
| 13 | `role_value::1f1af648ebc4…` | c4 | subsumed_by 1 | suppressed: referentially_closed | n/a | n/a | n/a (folds into another claim) |
| 14 | `role_value::c33c4ccf244a…` | c6 | context (keyword operand) | displayed via another claim's identical sentence | no | yes | **NO** |
| 15 | `category_list::775fda777…` | c10 | context (population operand) | suppressed: passage_complete | no | no | yes |
| 16 | `category_list::d47465340…` | c12 | primary for p30/p31; p24 suppressed | displayed | yes | yes | yes |
| 17 | `category_list::10ddc38db…` | c2 | primary for p46/p47 (construct-adjacent labelled) | suppressed: requested_construct_direct | yes | no | **NO** |
| 20 | `category_list::9fd341f1b…` | c3 | primary (verbatim p36 sentence) | displayed | yes | yes | yes |
| 19 | `category_list::f1f51b4ba…` | c8 | suppressed (speculative, identity) | suppressed: attribution_aim_or_hypothesis | no | no | yes |
| 18 | `category_list::7af59a3e5…` | c5 | duplicate_of 17 (facet 4A) | suppressed: requested_construct_direct | n/a | n/a | n/a (folds into another claim) |
| 21 | `category_list::f453ebb75…` | c6 | primary (measure name) | displayed via another claim's identical sentence | yes | yes | yes |

---

## 8. Disagreements with the Phase-29 hand audit

1. **Claim 1, amygdala–prosociality relation (c4).** Hand: primary. Mechanical: suppressed. The only passage that states it begins
   "Across these levels of organization," and the retrieved text does not identify those levels. Step 1 does not repair the
   anaphor, because the brief forbids editing meaning. Node 4 is therefore not established, and the disclosure says why. This is
   the most consequential disagreement.
2. **Claim 8, the paper-67 summary sentence (c1).** Hand: attributed primary. Mechanical: suppressed. The same passage is bound as
   a whole-passage predicate under four requirements (U1), and it is attributed to prior work.
3. **Claim 17, partner-task behavior (c2).** Hand: primary, labelled construct-adjacent. Mechanical: suppressed. Under D7, adjacent
   evidence does not answer a facet. It remains a Layer-2 candidate.
4. **Claim 14, the keyword "explicit" (c6).** Hand: context. Mechanical: its sentence is displayed once, under claim 21's facet, with
   both values merged. This is the same verbatim sentence, so nothing is duplicated in Layer 1.
5. **Claim 16, intervention outcomes.** Agreement in substance: the hand audit's split between p30/p31 (displayed) and p24
   (suppressed) holds.
6. **Claim 9, the amygdala fragment (c1).** Agreement in outcome: suppressed, not displayed. Mechanically, the reason is the anaphor
   in the relation sentence, not the fragment alone.
7. **Claim 21, the measure name (c6).** Agreement: displayed, through the same sentence as claim 7.

---

## 9. Complete deterministic Layer-1 replay text

The text below is `phase30_replay/deterministic_layer1.md`, copied verbatim. No model wrote it.

---

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

## Sources

[1] Paper 67, page 10.
[2] Paper 67, page 10.
[3] Paper 248, page 13.
[4] Paper 248, page 13.
[5] Paper 248, qualifying passage.
[6] Paper 248, qualifying passage.
[7] Paper 248, qualifying passage.

---

---

## 10. Node-by-node answerability states (derived)

| Node | Confirmed subquestion (overlay wording) | Node state | Facet | Facet state | Covered roles | Relation |
|---|---|---|---|---|---|---|
| 1 | How does the anomalous-is-bad bias manifest in / relate to measures of brain structure and function across regions and networks? | not_established | `c1#suff:neural-manifestation` | not_established | — | — |
| 2 | How does it manifest in / relate to measures of behavior? | not_established | `c2#suff:behavioral-manifestation` | not_established | — | incomplete |
| 3 | How does it manifest in / relate to implicit and explicit attitudes? | partial | `c3#suff:attitude-manifestation` | not_established | — | — |
|  |  |  | `c3#suff:implicit-explicit-coverage` | answered | category_evidence | — |
| 4 | Which specific brain areas or networks are implicated? | not_established | `c4#suff:specific-region` | not_established | — | witnessed |
| 4A | How do specific brain areas/networks relate to behavioral measures, including direction where established? | not_established | `c5#suff:brain-behavior` | not_established | — | unwitnessed_complete |
| 4B | How do specific brain areas/networks relate to implicit and explicit attitude measures, including direction where established? | partial | `c6#suff:brain-attitude` | partial | attitude_type_or_measure | unwitnessed_complete |
|  |  |  | `c6#suff:implicit-explicit-coverage` | partial | category_evidence | — |
| 5 | Which specific personality / individual-difference traits relate to its manifestation, and which scales measured them? | not_established | `c8#suff:trait-construct` | not_established | — | witnessed |
|  |  |  | `c9#suff:trait-scale-pairing` | not_established | — | incomplete |
| 6 | Is there cross-cultural evidence bearing on generalizability? Which cultures/populations, and how was the bias measured/operationalized? | not_established | `c10#suff:culture-existence` | not_established | — | incomplete |
|  |  |  | `c11#suff:culture-operationalization-pairing` | not_established | — | incomplete |
| 7 | Are there effective interventions aimed at reducing manifestations of the bias? | partial | `c12#suff:intervention-effectiveness` | partial | observed_effect_or_outcome | incomplete |

A node is `answered` only if all its facets are answered. It is `partial` if any facet is answered or partial. Otherwise it is
`not_established`.

---

## 11. Every suppression, attribution, subsumption, and de-duplication reason

Ordered as in the ParentClaim ledger. `Failing checks` lists every check that failed for the claim. `Rendered status` shows what
happened to each rendered sentence: `displayed`, `duplicate` (folded into an identical displayed sentence), or `subsumed`.
Per-value and per-sentence attempts are in `answer_plan_audit.json`.

| # | ParentClaim (prefix) | Kind | Child | Role | Layer | Failing checks | Rendered status |
|---|---|---|---|---|---|---|---|
| 1 | `relational::5d178917787a…` | relational | c4 | suppressed | layer2 | referentially_closed | — |
| 2 | `relational::6d3e9d91766c…` | relational | c8 | suppressed | layer2 | not_stimulus_rating | — |
| 3 | `relational::bac1b3e1196e…` | relational | c8 | suppressed | layer2 | not_stimulus_rating | — |
| 4 | `relational::99d44d22bc14…` | relational | c8 | suppressed | layer2 | not_stimulus_rating | — |
| 5 | `relational::629c3c06bf89…` | relational | c8 | suppressed | layer2 | not_stimulus_rating | — |
| 6 | `relational::6e5d1f4ca669…` | relational | c8 | suppressed | layer2 | not_stimulus_rating | — |
| 7 | `direction_or_effectivene…` | direction_or_effectiveness | c6 | value_level | layer1 | — | displayed |
| 8 | `role_value::8d0ce9c4405f…` | role_value | c1 | suppressed | layer2 | passage_not_generic_summary, attribution_prior_work | — |
| 9 | `role_value::57b25a887d32…` | role_value | c1 | suppressed | layer2 | referentially_closed | — |
| 10 | `role_value::b9591e4fba42…` | role_value | c2 | suppressed | layer2 | passage_not_generic_summary, attribution_prior_work | — |
| 11 | `role_value::34d05796cc1d…` | role_value | c3 | suppressed | layer2 | passage_not_generic_summary, attribution_prior_work | — |
| 12 | `role_value::161d9d5825b7…` | role_value | c4 | attributed_only | layer2 | attribution_prior_work | — |
| 13 | `role_value::1f1af648ebc4…` | role_value | c4 | suppressed | layer2 | referentially_closed | — |
| 14 | `role_value::c33c4ccf244a…` | role_value | c6 | primary | layer1 | — | duplicate |
| 15 | `category_list::775fda777…` | category_list | c10 | suppressed | layer2 | passage_complete | — |
| 16 | `category_list::d47465340…` | category_list | c12 | primary | layer1 | — | displayed; displayed |
| 17 | `category_list::10ddc38db…` | category_list | c2 | suppressed | layer2 | requested_construct_direct | — |
| 18 | `category_list::9fd341f1b…` | category_list | c3 | primary | layer1 | — | displayed |
| 19 | `category_list::f1f51b4ba…` | category_list | c8 | suppressed | layer2 | attribution_aim_or_hypothesis | — |
| 20 | `category_list::7af59a3e5…` | category_list | c5 | suppressed | layer2 | requested_construct_direct | — |
| 21 | `category_list::f453ebb75…` | category_list | c6 | primary | layer1 | — | duplicate |

---

## 12. Engine-complete versus AnswerPlan-witnessed disagreements

These are instances where the sufficiency engine marks the relation complete and the answer layer's joint witness is empty (D3).
Each is recorded in Layer 3. None is stated as a relation in Layer 1.

| Child | Requirement | Instance | Engine `complete` | AnswerPlan relation witnessed | Parent-context operands |
|---|---|---|---|---|---|
| c5 | `c5#suff:brain-behavior` | `i::b140e60509ac4c8b::4a3f8…` | true | false | named_brain_region_or_network |
| c5 | `c5#suff:brain-behavior` | `i::b140e60509ac4c8b::e4796…` | true | false | named_brain_region_or_network |
| c6 | `c6#suff:brain-attitude` | `i::b140e60509ac4c8b::2f2b0…` | true | false | named_brain_region_or_network |
| c6 | `c6#suff:brain-attitude` | `i::b140e60509ac4c8b::9fe92…` | true | false | named_brain_region_or_network |

All four are in c5 (4A) and c6 (4B), where the region operand is inherited from c4. This is the engine's documented exemption for
a single own-evidence role paired with parent context. The answer layer does not adopt it.

---

## 13. Information density versus hidden uncertainty

**Density.** The Phase-28 parent answer is about 1,695 words. Its Overview and Qualified blocks together are about 870 words. The
Layer-1 replay is about 1,007 words, including headings and disclosures. Layer 1 is therefore shorter than the full Phase-28
artifact, but not shorter than its Overview block. The excess is repetition in the disclosure templates, not in the answers.
"Earlier work reports this…" appears five times, and "A passage gives only a general summary…" four times. The architecture
removed the repetition of **claims**: the five trait relations over one passage, and the four copies of the paper-67 summary,
now produce no displayed sentences. Its **disclosure text** still repeats. Consolidating reason lines per node, or per source,
is the first Step-2 task.

**Uncertainty is not hidden.** Every node has an explicit state. Every relation the engine marked complete without a joint witness
is stated as not established. Adjacent-construct evidence is labelled and does not answer a facet. The negated implicit result is
kept verbatim (U2 fixed). The one limitation of the intervention study that is promoted to Layer 1 is kept as the authors wrote it.
Every withheld item is listed in Layer 2 with a fixed reason, and every decision is in Layer 3.

**What the density gain costs.** The replay under-states what the sources say in four places, and a reader of Layer 1 would not
learn these findings:
(a) the amygdala relation (§14, item 1);
(b) the Hadza cross-cultural statement, which is truncated in the retrieved text;
(c) the specific attitude finding for facet 3's attitude-manifestation requirement. Its only binding is the general summary sentence,
so the replay shows the implicit result and says a specific attitude finding is not established. The explicit biases are reported
inside the implicit sentence, but the facet is not credited with them;
(d) two limitations of the intervention study that share only one content word with the displayed findings (§14, item 8).
These are conservative, mechanical outcomes. They are disclosed as such. They are not a judgment that the findings are false.

---

## 14. Limitations requiring upstream fixes or decisions

1. **Referring-phrase binding and an out-of-text scope referent (the most important).** The region role binds "the specific amygdala
   response", a referring phrase rather than a named region. The only relation sentence begins with a scope clause whose referent
   is not in the retrieved text. Fixing this needs an upstream named-entity binder change and/or neighbour-span retrieval for scope
   referents (a v2 retrieval change). Neither is in Step 1.
2. **Whole-passage predicate binder (U1).** The deterministic achieved-outcome binder returns the whole passage whenever a result word
   is present, so one generic summary is bound under four requirements. Fix: role-specific binders and a modality check.
3. **Keyword category binder (U2).** The explicit-category binder returns a keyword without its predicate, and the `category_evidence`
   role has no guard that uses the `negated` flag the engine records (the flag was recorded `true` for p36 and then ignored). Fix:
   bind the predicate sentence and apply a polarity-aware guard.
4. **Engine completeness semantics (U9, D3).** Four relation instances are complete without a witness. Changing this is a separately
   gated engine increment that would alter the Phase-26–28 frozen outputs.
5. **No subject-of-measurement attribute (U4).** Face-rating dimensions and attitude measures are bound as trait values. The replay
   catches only the stimulus-rating cue.
6. **Lexical attribution only (D4).** The replay fixture has no section structure. A result stated in an Introduction would be read as
   this study's result if it carried result language. Structural section metadata should be used wherever it exists.
7. **Paper-level requested-construct identity (D7).** Any requested term anywhere in a paper's sealed text makes all of its passages
   direct. This is coarse. A per-facet construct phrase in the contract is the proper fix (a D8-class addition).
8. **Qualification recall (D6).** The two-word overlap rule under-recalls. Two genuine limitations of the intervention study, one on
   the single-sample design and one on scar-specific connotations, share only one content word with the displayed statements. They are
   not attached, and the node pointer does not fire for them. Node 7 therefore understates its own limitations. Fix: a paper-level
   pointer for same-paper scope qualifiers, designed in Step 2.
9. **Acronyms.** "DG" is unexpanded and unsupported in sealed text. "EBQ" is supported only cross-paper (paper 248's own definition), so
   it is not expanded in Layer 1. The rule is conservative by design.
10. **Density (§13).** Disclosure templates repeat across nodes.
11. **Overlay mapping (§3).** Resolved: c9 is assigned to node 5 and c11 to node 6, as confirmed by the researcher.
12. **Not regenerated.** The recovery-target inventory is not persisted in the run, so the gap report is not regenerated. Layer 3 lists
    missing roles from the sufficiency map instead.
13. **No frozen-contract display labels.** The overlay carries the display phrases. Production use needs additive, reviewed contract
    fields (D8).

---

## 15. Step 1 verdict

- **Functions as specified on the replay.** Deterministic, auditable, fail-closed, no model. The plan hash is reproducible. The
  ParentClaim ids are identical to Phase 28. Every candidate is classified with its reasons.
- **READY to proceed to Step 2**: offline Layer-2/3 consolidation (merge repeated reason lines, design the paper-level limitation
  pointer, and set up citeproc source labels as a placeholder substitution). Conditions: (i) the repeated disclosure templates are
  consolidated; (ii) the qualification recall rule is decided (§14, item 8); (iii) the overlay mapping in §3 is confirmed.
- **NOT READY for Steps 3–4** (model child-answer and parent generation). On this replay the authorized bindings yield two verbatim
  findings, three limitations, and one implicit-result sentence. A model verbalizer would add little and would be asked to answer
  questions the authorized map does not support. §14 items 1–4 should be addressed first.
