# Phase 34 -- Mapping vocabulary experiment and Q1 NLI diagnosis

**Exit: CORRECTION UNSAFE OR INCOMPLETE.** The single-vocabulary variant does what it was meant to
do for present-tense findings and breaks none of the existing safeguards, but with the old verb gate
removed it also admits method and roadmap sentences as findings (9 of 25 newly admitted sentences
in unselected source text). It also cannot be installed as a selectable semantics version without
editing byte-pinned producer code.

**NLI false-negative mechanism: identified.** Both Q1 claims rename the subject. The source says
"our approach"; the claim says "the active learning procedure/approach". The isolated quote does
not say that the approach is an active-learning one, so the model returns *neutral*. Notation,
ordering, sentence boundaries and truncation play no part.

Nothing was run live. No model other than the pinned local NLI cross-encoder was called.

## 1. Starting HEAD and scope

- Start: `a3575b17fbdf80297f38c0e51bfc57e56b6ba844`, worktree clean.
- Tracked changes in this increment: one new test module
  (`test_phase34_vocabulary_experiment.py`), this report, and the lineage entry. **No runtime
  module changed.** v8, the default verifier, B2's opt-in status, `/summarize`, contracts and the
  library are untouched.
- Local, gitignored working files: `.local/phase34-vocab-nli-20261012/` (`qualify.py/.json`,
  `nli_diag.py/.json`, `preservation.json`).

### The versioning constraint (reported as required)

A registered experimental version was not created, because it cannot be done without modifying
pinned code:

- `sufficiency_mapping.py`, `sufficiency_engine.py`, `achieved_outcome_span.py` and
  `contract_directed/attribution.py` are four of the 26 files byte-pinned by the producer code
  manifest. `reproduce_accepted_v8` refuses to run if any of them drifts. A new version constant
  needs edits in at least the first two, plus the version lists in four more pinned files.
- Two static guards forbid any non-test module from naming the assertion classifier or the span
  matcher, other than the mapper itself.

The variant therefore lives in a test module, is reachable from no route, and substitutes the span
matcher on the mapper module for the duration of one call. Its identity,
`phase34-single-vocabulary-x1`, is deliberately not a supported semantics version, so nothing it
produces can be consumed. Making it selectable would need a deliberate re-enrolment of the producer
manifest. Given the result below, that is not recommended.

## 2. The mismatch and the experimental correction

`achieved_outcome_predicate` forms candidates with `attribution._RESULT_PREDICATE`: 29 alternatives,
almost all past tense. The classifier it then calls recognises results with its own sets,
`_RESULT_VERBS | _REPLICATION_VERBS` (78 forms, including present tense). A sentence whose only
result verb is "demonstrate" or "show" never reaches the classifier.

The variant forms candidates with exactly the classifier's two sets and nothing else. Sentence and
clause segmentation, the assertion join, the owner rule, the support policy and projection are the
unmodified v8 code.

Two things about the classifier's list matter for what follows:

- **It has inflection gaps.** It lists `yield`/`yielded` but not `yields`, `reported` but not
  `report`, `increase`/`increased` but not `increases`. "Our method yields a 1.5-2x reduction" forms
  no candidate. These were left alone rather than patched.
- **It treats generic verbs as result verbs.** `describe`, `provide`, `produce`, `express` are in
  the result set regardless of their object.

## 3. Positive and negative controls

44 tests, all passing. The control sentences were drafted first and explored with a throwaway
script before the tracked module was written, so the expectations were informed by observed
behaviour. The governing rule was fixed in advance: **the variant must decide a present-tense
sentence exactly as v8 decides its past-tense twin.**

| Category | Example | v8 | Variant |
|---|---|---|---|
| Present-tense this-study finding | "We demonstrate the efficacy of the method." | no candidate | admitted, this study |
| Past-tense this-study finding | "We demonstrated the efficacy ..." | admitted | unchanged |
| Aim / hypothesis | "We hypothesize that active design improves estimation." | no candidate | excluded, `non_result_kind` |
| Proposed, untested method | "We propose a method that improves accuracy." | no candidate | excluded, `non_result_kind` |
| Conditional / modal | "Active design may improve estimation accuracy." | no candidate | excluded, `non_result_kind` |
| Negated finding | "We do not find that active design improves it." | no candidate | admitted as a null result, negation and veto marker kept (same as v8 past tense) |
| Prior work | "Previous studies show that design improves it." | no candidate | admitted, labelled external, never this-study (same as v8 past tense) |
| Background / theory | "Optogenetics provides precise control ..." | no candidate | excluded, unresolved owner |
| Result language, unresolved owner | "The results show a two-fold reduction ..." | no candidate | excluded, unresolved owner |
| Result without a listed verb | "Estimation error was halved with active design." | no candidate | no candidate (documented, unsupported) |

All seven tense-twin pairs match. A recognised verb never supplied an owner. The forms that only
the old pattern lists ("was lower", "identified", "responded", "expected") never reached admission
under v8 either, because the classifier cannot join them; nothing is lost by dropping them.

**The controls that fail the purpose.** Five sentences are recorded in the test module as a known
defect, not accepted behaviour:

- "We describe a new algorithm for input design."
- "We provide open-source code for the method."
- "We produce synthetic data from a linear model."
- "Our model describes the dynamics of the population."
- "We show the estimation error for each method in Figure 3."

v8 forms no candidate for any of them. The variant admits all five as owned findings. The old
pattern was, by accident, acting as a second filter on the classifier's over-broad result set.

Two owner-rule oddities were observed and left untouched: "Here we show ..." is owned but "In this
paper we show ..." is not, and "This study confirms ..." is unresolved while "The present study
shows ..." is owned.

## 4. Before and after on the 17 sealed quotes

Both live sufficiency maps were reproduced exactly before anything was varied.

| | v8 | Variant |
|---|---|---|
| Q1 requirement | missing | **missing** |
| Q3 requirement | missing | partially filled, one instance (p12) |
| Candidates formed (17 quotes) | 0 | 5 (plus one hit that fails the join) |
| Admitted | 0 | 1 |

| Quote | Anchor verb | Outcome under the variant |
|---|---|---|
| Q1 p3 | shows | excluded, unresolved owner |
| Q1 p4 (the up-to-2x finding) | none | no candidate: "illustrate", "give", "matches" are in neither list |
| Q1 p5 | confirms | assertion join fails |
| Q3 p4 | provide | excluded, unresolved owner and not a result |
| Q3 p6 | show | excluded, unresolved owner |
| Q3 p8 | provides | excluded, unresolved owner (cited background, correctly out) |
| Q3 p12 | demonstrate | **admitted** |
| other 10 | none | no candidate |

Preserved q_aib quotes (56 unique, a different library): candidates formed 16 -> 32, admitted
5 -> 7, none lost. (The audit reported 3 -> 6 using a stricter direct probe; these figures come from
the full binder.) The two new admissions are both genuine findings ("This analysis shows that ...
those who choose to purchase a photo are more trusting"; "This research confirmed earlier reports
... and described a behavioral manifestation ...").

## 5. Useful gains versus irrelevant gains

**On the sealed evidence the gain is one sentence, and it is weak.** Q3 p12 is "we demonstrate the
efficacy of a low-rank linear dynamical systems model". It comes from one of the two studies, says
nothing about efficiency, and does not satisfy a request for demonstrated efficiency improvements
across both. Q1 gains nothing.

**Independent check on unselected text.** Every sentence of every chunk of the two pilot papers
(1,982 sentences, none chosen by a run) was put through both versions. 254 decisions changed; none
was lost. 28 sentences became admissible, 25 of them distinct. One reader's classification:

| Class | Count | Examples |
|---|---|---|
| Specific findings | 7 | "we observe a gain of between 1.5-2x over baselines ..."; "obtaining in some cases as much as a two-fold reduction ..."; "our results consistently show that passive observation requires substantially longer recordings ..." |
| Contribution claims with no outcome content | 9 | "We demonstrate the effectiveness of this framework ..."; "This study provides a theoretical foundation ..." |
| **Nonfindings** | **9** | "We describe the model details next."; "In this section, we show how ..."; "Given this, we increase the weight of playing ..."; "we provide our learned dynamics model with the initial state ..."; two proof steps |

By verb: `demonstrate`, `show`, `find` and `observe` carry every specific finding. `provide` and
`describe` carry none (six admissions, all contribution claims or nonfindings). The sample is small
and from two papers.

Remaining exclusions among the changed sentences: 209 candidates excluded for an unresolved owner,
27 as not a result, 4 join failures. The owner rule is doing most of the excluding and was not
weakened.

**Obligations that could now be satisfied.** At the mapping layer, four of the seven specific
findings are the Q1 core results, and they pass every mapping gate under the variant. They are not
sealed, because verification rejects them first (section 7). So the variant removes a mapping
obstacle that Q1's best evidence never reaches.

## 6. Historical and regression integrity

- Focused regression: **2,267 passed, 9 xfailed** across the span matcher, assertion authority,
  I4-2/I4-3 mapping and replay, producer authorization and reproduction, semantics-version,
  reviewed-fresh and the new controls. This includes both static guards and the pinned producer
  reproduction, which confirms the pinned files are byte-identical.
- The broad suite was not rerun: no tracked runtime code changed, so the known-five inventory and
  the frontend hook exception were not needed.
- 103 preserved files unchanged; 62 pilot run files unchanged; pilot library
  `0ba4b183...9360` unchanged.
- `ruff format` and `ruff check` pass on the new file.

## 7. Q1 NLI diagnostic results

Model `cross-encoder/nli-MiniLM2-L6-H768`, premise = quote, hypothesis = claim, as the verifier
pairs them. All nine frozen Q1 scores were recomputed and match. Longest input in any probe was 128
tokens against a 512 limit.

**Case A** -- claim: "The study found that in some cases, *the active learning procedure* resulted
in as much as a two-fold reduction in the amount of data required ..."
quote: "We demonstrate *our approach* on both real and synthetic data, obtaining in some cases as
much as a two-fold reduction in the amount of data required ..."

**Case B** -- claim: "The study found that on Mouse 1 and both datasets for Mouse 3, *the active
learning approach* required between 1.5-2x fewer samples than baseline methods ..."
quote: "... we observe a gain of between 1.5-2x over baselines -- that is, to achieve a given
estimation error, *our approach* requires between 1.5-2x fewer samples than baseline methods."

| Probe | A entailment | B entailment |
|---|---|---|
| Original pair | 0.009 (neutral 0.975) | 0.062 (neutral 0.936) |
| Premise and hypothesis swapped | 0.008 | 0.046 |
| Notation rewritten (twofold, 2-fold, "1.5 to 2 times", "x") | 0.008-0.010 | 0.019-0.068 |
| Dash replaced by a sentence break; either half alone | n/a | 0.002-0.042 |
| "The study found that" removed, subject unchanged | 0.013 | 0.027 |
| Subject changed to "our approach", frame kept | 0.119 | **0.920** |
| Subject changed to "our approach", frame removed | **0.993** | **0.985** |
| Final clause of the quote, verbatim, as the claim | 0.992 | 0.987 |
| Same verbatim clause with "the active learning approach" | n/a | 0.010 |
| Preceding source sentence added to the premise | **0.953** | **0.972** |

The preceding source sentences are real adjacent text and are what identify the approach: "...
develop an active learning procedure which takes advantage of low-rank structure ..." (A) and "...
our active learning approach yields a non-trivial gain ..." (B).

**The same substitution breaks a pair that passes.** The verified Q1 pair "... one can effectively
design stimuli to speed up the estimation ..." scores 0.906. Rewriting its subject as "the active
learning approach can ..." drops it to 0.014. A verified sibling pair whose quote itself says
"active learning" scores 0.994 and is unaffected by adding the "The study found that" frame (0.990).

**Negative controls** (entailment; the verifier's bar is 0.55, B2's is 0.90):

| Altered claim | Original framing | Subject "our approach" | With preceding sentence |
|---|---|---|---|
| A: ten-fold instead of two-fold | 0.003 | 0.002 | 0.005 |
| A: increase instead of reduction | 0.001 | 0.002 | 0.002 |
| A: "in all cases" | 0.004 | 0.011 | 0.077 |
| A: subject is "the passive baseline" | 0.033 | 0.093 | **0.681** |
| B: 5-10x | 0.003 | 0.001 | -- |
| B: more samples | 0.007 | 0.004 | -- |
| B: Mouse 2 | 0.023 | 0.085 | -- |
| B: baselines need fewer samples than the approach | 0.025 | **0.805** | -- |

Magnitude and direction errors stay rejected under every representation. Two do not: a
role-reversed claim reaches 0.805 once the subject matches, and a wrong-subject claim reaches 0.681
once context is added. Under the original framing both stayed low only because the subject
mismatch was already forcing neutral.

## 8. Established versus hypothesised

**Established for these two cases**

- The score is neutral, not contradiction.
- The cause is the renamed subject. Changing it alone moves B from 0.06 to 0.92; restoring the
  renamed subject to an otherwise verbatim clause moves it from 0.99 to 0.01.
- Numerical notation, premise/hypothesis order, the dash, sentence boundaries and truncation do not
  contribute.
- The model's behaviour is defensible on its own terms: the isolated quote does not state what the
  approach is. The failure is in what is being compared, not in the score.
- The same model lets a role-reversed claim through at 0.805 when the wording otherwise overlaps.

**Hypotheses, not established**

- How much of the wider verification loss this explains. Two cases plus one confirming reversal is
  not a rate. The earlier bakeoff found that adding context to every pair recovered *fewer*
  supported pairs overall, which cautions against generalising from these two.
- Whether the "The study found that" frame matters independently. It cost a great deal in case A
  and nothing in case B or the sibling pair.
- Where the renaming enters. The claims are written to stand alone, which would explain it, but the
  proposition-writing step was not examined here.

## 9. The smallest justified next scientific improvement

The decisive obstacle for Q1 is in verification, not mapping. Its four best findings pass the
mapping gates under the variant and are rejected before they get there.

Two repairs are visible in the probes: give the premise the source sentence that identifies the
subject, or keep the source's own referring expression in the claim. Each recovered both cases.
Each also let one constructed negative through. Neither is ready to implement.

The next step the evidence supports is a measurement, not a change: **on the already-labelled
bakeoff packet, which contains referent-swap and role-reversal negatives, score the two repairs
only on pairs where the claim's subject does not appear in the quote, and count supported pairs
recovered against negatives admitted.** It needs no new labels and no model beyond the local NLI
pass.

The vocabulary correction should not proceed as it stands. Making it safe means teaching the
classifier that "describe X", "provide code" and "show how" are not results, which is a change to
the classifier's kind decision rather than a vocabulary swap, and it would still leave Q1 empty.

## 10. Does the evidence warrant another live E2E?

No. With the variant, Q1 remains empty and Q3 gains one sentence that does not answer the question.
Nothing learned here changes what a live run would produce.

## Limits

- Finding/nonfinding labels in section 5 are one reader's judgment over two papers.
- The NLI diagnosis covers two false negatives and a handful of constructed controls. It identifies
  a mechanism for these cases and does not estimate its prevalence.
- The variant was qualified offline through in-process substitution. It was never run through the
  reviewed route.
