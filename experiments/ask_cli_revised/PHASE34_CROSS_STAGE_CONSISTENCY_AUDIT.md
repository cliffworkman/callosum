# Phase 34 — Cross-stage scientific consistency audit

Read-only. Basis: commit `377f9af2`, the October 12 sealed run, and the offline preview of the integrated
(reviewed) route made from it. No code changed, no model called, no E2E, no JUNO, reporting review untouched.

## A. Executive findings

1. **The answer is built from raw source sentences, and the model's own verified, self-contained statement is
   thrown away.** For every piece of evidence the worker model reads the surrounding passage and writes one
   standalone claim; that claim is what the verifier checks and what is sealed. The reviewed route's answer
   (Layer C → plan-v5) never reads it. It prints sentences cut from the quotation instead, and then needs a
   family of text rules to decide whether a raw sentence can stand as prose. For the amygdala finding the
   sealed claim is already *"The specific amygdala response to facial anomalies correlates with stronger
   just-world beliefs, less dispositional empathic concern, and less prosociality toward people with facial
   anomalies"* (verified 0.99). The anaphor problem had been solved at claim formation and was re-created at
   display. This is the root of most of what follows.

2. **Two classifiers judge epistemic status in the same route and disagree.** Sufficiency mapping decides,
   with the I4 assertion-authority work, whether a sentence is this study's result, prior work, an
   interpretation or an aim, and whether it can establish a requirement. The display step then re-decides
   with a cruder word list and vetoes. After the repair, 31 of 49 values are scientifically *established* and
   still not displayable; 13 of those are vetoed for attribution (8 prior work, 5 aim/hypothesis).

3. **A qualifier for prior-work evidence already exists and can never fire.** Plan-v5 carries a prefix,
   "The source reports prior evidence: ", driven by the sufficiency side's own attribution record. The
   display veto removes the same sentences first, so the mechanism built to report such evidence honestly
   is unreachable for them.

4. **Acronym expansion was built, tested, and left on the old plan.** Phase 30 Step 2 expands an acronym on
   first use when exactly one explicit definition exists in the same paper's sealed text. It is called by the
   Phase 30 plan only; plan-v5 does not call it. On the October 12 evidence the same function finds NAME,
   EBQ and IAT definitions. Meanwhile the *other* route's model wrote the expansion itself, correctly and
   cited: "The 'Normalizing Anomalies with Mobile Exposure' (NAME) intervention … produced a clear
   reduction in implicit bias".

5. **The two presentation layers fail on opposite findings.** On identical sealed evidence, child synthesis
   showed NAME (expanded) and "results suggest … culturally shared" and withheld the amygdala finding; plan-v5
   shows the amygdala finding (since `377f9af2`) and withholds or cannot place the other two. Neither is a
   superset of the other, and the integrated run writes both but selects only plan-v5.

6. **One "presentation limitation" is really a scientific one.** For personality traits (c8) the mapping
   marks values established from face-*rating* sentences (traits attributed to the perceived person). The
   display rule that blocks them is right; the mapping is what is wrong, and the answer then tells the reader
   "this is a presentation limitation, not scientific absence", which is false for that case.

7. **Context used to form a claim is not kept and not given to the verifier.** Unchanged since the
   active-learning case. The earlier experiment ended "TRADEOFF UNRESOLVED" and nothing was implemented. Not a
   Friday item.

## B. Existing-solutions inventory

| Mechanism | Built for | Where | Used by the integrated route? |
|---|---|---|---|
| Context growth before reading (`context_gate`: accept / before / after / both) | Pull neighbouring text when a passage is not a complete thought | `qwen.py`, `__main__.py` | Yes |
| Claim formation with surrounding context ("use surrounding context only to resolve what the excerpt means"; keep negation, uncertainty; "do not turn a hypothesis or method into a result") | Self-contained, faithful claim | `qwen.py::form_claim` | Yes; its output is sealed as `proposition_text` |
| Source verification (similarity, exact quote, NLI of claim against the isolated quote) | Admit only supported claims | `runtime` / `nli_verifier.py` | Yes |
| Continuation join across a chunk boundary | Sentences split by the chunker | `continuation.py` | Yes, initial pass and recovery |
| Referential-context NLI (score the claim against preceding sentence + quote, or with the subject reformulated) | The active-learning false negatives | Experiment only (`PHASE34_REFERENTIAL_CONTEXT_NLI_EXPERIMENT_RESULTS.md`) | **No. Never implemented** |
| Assertion authority (source: this study / prior / unknown; kind: result / method / aim / interpretation; negated-result veto) | Decide what may establish a requirement | `assertion_authority.py` via `sufficiency_mapping.py` | Yes (v8) |
| Direction target, relation witness, ownership context | Who relates to whom, in which direction, whose trait | `direction_target.py`, `relation_unit_v2.py`, `ownership_context.py` | Yes |
| Source-qualification prefix ("The source reports prior evidence: ") | Report attributed evidence honestly | `answer_plan/disclosure_v5.py`, `render_v5.py` | Present, but pre-empted (finding 3) |
| Display checks (complete passage, attribution, referential closure, stimulus rating) | Decide whether a raw quote sentence may be printed | `answer_plan/classify.py`, `text.py` | Yes; the source of most withholding |
| Self-reference repair ("This research" → source label), run-in heading strip | Make a raw sentence readable | `answer_plan/text.py` | Yes |
| Display corrections (closure after narrowing; qualified result ≠ aim) | Local repair, October 13 | `answer_plan/display_corrections.py` | Yes, fresh route only |
| Grounded acronym expansion | Reader should not need to know the acronym | `answer_plan/step2.py`, `text.py::definition_hits` | **No. Phase 30 plan only** |
| Lexical synthesis screens (novel terms, direction word, negation, hedge, causal cue, acronym-not-in-passage) | Stop a rephrasing from changing meaning | `overview_guards.py` | Child synthesis only; not the selected answer |
| Legacy ledger renderer (prints the verified claim with its quote) | Earliest answer format | `ledger_renderer.py` | Not selected on the reviewed route |

## C. Cross-stage compatibility matrix

Classes: (1) confirmed incompatibility, (2) missing propagation, (3) existing capability not wired, (4) legitimate
restriction, (5) unsolved, (6) uncertain.

| Requirement | Existing mechanism | Where | Reached? | What downstream receives | Incompatibility or gap | Evidence |
|---|---|---|---|---|---|---|
| A. Referent resolved at claim formation | `form_claim` with context | `qwen.py` | Yes | `proposition_text`, sealed | **(1)(2)** Layer C / plan-v5 never read it; they re-derive display text from the quote and reject the anaphor | p2/p14 claim text vs the `referentially_closed` restriction; no `proposition_text` reference anywhere in `layerc_*`, `claim_v2`, `plan_v5`, `render_v5` |
| A. Antecedent text | Context growth, chunk read | `__main__.py` | Yes | Only the chunk id (`provenance.context_read`); the sealed span is the 265-character sentence | **(2)** "these levels" = brain, behavior, attitudes is three sentences earlier in the same chunk (34974); no stage after claim formation holds that text | Chunk read from the library copy |
| A. Verification with context | none live | experiment | No | Claim vs isolated quote | **(5)** resolved terms can fail NLI (active-learning) | Earlier experiment: tradeoff unresolved |
| A. Narrowed display | `display_corrections` | fresh route | Yes | Clause without its scope phrase | Partial local repair; does not resolve the referent | `377f9af2` |
| B. Acronym definition | `definition_hits`, Step 2 expansion | `answer_plan/step2.py` | **No** | Nothing | **(3)** NAME, EBQ, IAT definitions are found deterministically in the sealed spans; v5 prints bare acronyms | Function run on the sealed ledger |
| B. Definition sentence itself | display attribution | `classify.py` | Yes | Vetoed | **(1)** "We developed the 'Normalizing Anomalies with Mobile Exposure' (NAME) intervention…" is `attribution_unknown` (a method statement, not a result), so the one sentence that defines the term cannot be shown | p37 |
| B. Expansion written by the model | child synthesis + screens | `overview*.py` | Yes, not selected | Shown in c12 synthesis | Works when the model cites the defining passage; `acronym_not_in_passage` and novel-terms screens would reject it otherwise | c12 proposals |
| C. Result / prior / aim / interpretation | assertion authority | `sufficiency_mapping.py` | Yes | Establishment state, attribution record | **(1)** display re-classifies with `attribution_kind` and vetoes 13 established values | Value table: established × restricted |
| C. Prior-work evidence | qualification prefix | `disclosure_v5.py` | Present | Never applied to vetoed sentences | **(1)** two mechanisms, same route, opposite outcomes | The prefix is applied in `render_v5.py`; the same sentences carry `attribution_prior_work` |
| C. This-study replication read as prior work | display word list | `text.py` | Yes | Vetoed | **(1)** "This research confirmed earlier reports that people with anomalous faces are imbued with negative personality…" is classed prior work | Sealed sentence |
| C. "We suggest" | display word list | `text.py` | Yes | Vetoed as aim | **(1)** an author interpretation is treated as unusable rather than reportable as an interpretation | paper 67 left-amygdala sentence |
| C. Hypothesis kept as hypothesis | `form_claim` instruction | `qwen.py` | Yes | "The hypothesis predicts that…" sealed as a claim | **(4)** correct through sealing; display withholds; acceptable | p59 |
| C. Hedge preserved in rephrasing | `hedge_dropped`, `negation_dropped`, `direction_word` screens | `overview_guards.py` | Child synthesis | Withheld sentences | **(1)** false positives: amygdala synthesis withheld because the model wrote "reduced" for "less"; another for a negation word | 22 proposals, 9 withheld; 6 carry one of these three reasons, and 5 of those 6 passed NLI |
| D. Relation inside one sentence | relation witness (same proposition) | `relation_unit_v2.py` | Yes | Requires both role values to accept the *same* display sentence | Worked once `377f9af2` shared the narrowed clause | c1, c4 statements 0 → 1 |
| D. Relation across parent and child | inheritance of the parent's value | Layer C | Yes | c5/c6 inherit only the region literal from c4 | **(4)/(6)** pairing amygdala with share decisions from another paper is correctly "relation unestablished"; whether the amygdala–prosociality relation stated in c4's own sentence reaches c5 depends on live nomination | c5/c6 relation units |
| D. Perceiver vs perceived trait | `not_stimulus_rating` | `classify.py` | Yes | Display veto | **(4)** the veto is right. **(1)** the mapping established the value anyway and the disclosure mislabels it | c8, 15 restricted values |
| E. Established but not shown | all of the above | — | Yes | "presentation limitation" | 31 of 49 values: stimulus rating 15, prior work 8, truncated 5, aim/hypothesis 5, unknown 1 (reasons can co-occur) | Preview after `377f9af2` |
| E. Truncated passage | continuation join | `continuation.py` | Yes | Hadza quote still cut | **(6)** join did not fire or the cut is not at a chunk boundary | Not investigated |

## D. Root causes

**D1. Display text is re-derived from the quotation instead of reusing the verified claim.**
- *Addressed earlier:* claim formation, from the first Ask CLI; the legacy ledger renderer prints claim + quote.
- *Stops being respected:* Layer C. It was designed around proof that a specific *value* appears in a specific
  *sentence*, so it took the sentence as the thing to print.
- *Why:* a deliberate Phase 30 rule that verbatim quotes are the semantic authority and nothing rewrites meaning.
  Reasonable as authority; costly as prose, because raw sentences carry anaphors, headings, truncation and
  acronyms that the claim had already resolved.
- *Consequence:* the closure, completeness, opener and self-reference rules, the October 13 narrowing repair,
  and most "presentation limitation" lines.
- *Correction type:* **reuse.** The claim text exists, is verified against that exact quote, and is sealed.

**D2. Epistemic status is decided twice.**
- *Addressed earlier:* I4-1 through I4-2 (assertion authority, ownership, support policy), with
  far more care than the display word list.
- *Stops being respected:* `classify.evaluate_sentence` calls `text.attribution_kind` and requires
  `this_study_result`.
- *Why:* the display checks predate I4 (Phase 30) and were never retired when I4 took over the question.
- *Consequence:* established prior-work, interpretation and method/definition evidence is withheld; the
  prefix mechanism meant to qualify it is dead code for those cases; a this-study replication is misread.
- *Correction type:* **removal plus wiring.** Let the sufficiency-side record decide; let display qualify
  rather than veto.

**D3. Acronym expansion is on the wrong plan.** Built in Phase 30 Step 2, not carried into v5.
*Correction type:* **wiring.**

**D4. The mapping lacks the perceiver/perceived distinction that display enforces.**
- *Consequence:* c8 reports a presentation limit where the truth is "no responsive evidence".
- *Correction type:* the restriction is legitimate; only the **disclosure wording** is wrong. Fixing the
  mapping itself is new scientific work.

**D5. Rephrasing screens duplicate the NLI screen with a word list.** DeBERTa already scores each rephrased
sentence against its passages. The direction, negation and hedge screens then reject paraphrases such as
"reduced" for "less". *Correction type:* **removal or demotion to a recorded note.** Affects the child
syntheses, which are not the selected answer.

**D6. Context is not carried past claim formation.** Only a chunk id survives. *Correction type:* genuinely
new if the verifier is to use it; trivial if only the reader is to see it (the chunk is addressable).

## E. Prioritized repair candidates (not implemented)

| # | Change | Type | Recovers | Risk | Friday? |
|---|---|---|---|---|---|
| 1 | In the reviewed answer, print the sealed claim as the statement and keep the verbatim sentence directly beneath it as its evidence. Text-form checks (closure, completeness) then apply to nothing and can stop vetoing. | Reuse | Amygdala in full, without losing its meaning to narrowing; Hadza if its claim is whole; every anaphor case, for any question | The claim is a model paraphrase. It is the text the verifier approved, but only against the isolated quote. Must confirm the claim asserts no more than the value Layer C authorized for that slot. | **Release-critical, if you accept paraphrase as the statement.** It is the one change that addresses the cause rather than a symptom. |
| 2 | Stop vetoing on display attribution; take the kind from the sufficiency record and apply the existing prefix ("The source reports prior evidence: "; an equivalent for author interpretation). | Removal + wiring | 13 established values, including the second amygdala finding and "we suggest" sentences, shown as what they are | Needs one new prefix string for interpretation; the prior-work one exists | **Release-critical.** Small, and it replaces a duplicate with the better classifier. |
| 3 | Call the existing Step 2 acronym expansion from the v5 renderer. | Wiring | NAME, EBQ, IAT expanded on first use from sealed definitions | Low; deterministic, already tested; refuses when the definition is not unique | **Release-critical** for readability; smallest of the three. |
| 4 | Reword the c8-type disclosure so a stimulus-rating restriction is not called a mere presentation limit. | Wording | Honesty of one line | None | Yes, if 1–3 are done; minutes. |
| 5 | Drop or demote the direction / negation / hedge word screens on child syntheses, leaving NLI. | Removal | Up to 5 of the 9 synthesis sentences withheld on October 12 (those that passed NLI) | Loses a cheap second opinion on meaning change | Only if the child syntheses are shown to users in 0.6.0. Otherwise post-release. |
| 6 | Context-aware verification. | New | Active-learning-type false negatives | Earlier experiment admitted contradicted claims | **Post-release.** |
| 7 | Teach the mapping perceiver vs perceived. | New | Correct c8 establishment | Scientific work | **Post-release.** |

Candidates 1 and 2 overlap with, and would largely supersede, the two local repairs in `377f9af2`.
Candidate 1 changes what Layer C displays, which your last instruction said not to redesign; I list it
because the audit points there, not because it is pre-approved.

If only one thing is done before Friday, do 2 and 3 together: both are wiring of things already built, and
neither introduces paraphrase into the selected answer.

## F. Remaining uncertainties that bear on Friday

1. **Does the sealed claim ever say more than its quote supports in a way NLI missed?** Decides candidate 1.
   Cheapest check: read the 64 sealed claim/quote pairs from October 12 side by side (no model; under an hour).
2. **Will live nomination place the displayable sentences?** Thirteen of 31 nominations were not replayable,
   so the intervention, behavior and cross-cultural parts are unknown. Only the E2E answers this.
3. **Why is the Hadza passage truncated despite the continuation join?** One deterministic look at the chunk
   boundary and the join record for that packet.
4. **Is the selected answer for 0.6.0 plan-v5, the child syntheses, or both?** The audit's priorities change
   with this: candidates 1–4 serve plan-v5, candidate 5 serves the syntheses. This is your decision, not a
   measurement.
5. **Generality.** Every count here is from one question on one library.
