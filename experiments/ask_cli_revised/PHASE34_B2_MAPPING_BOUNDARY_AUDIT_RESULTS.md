# Phase 34 -- B2 scientific mapping boundary audit

Date: 2026-10-12. Read-only audit of the 17 propositions sealed by the two B2 live pilot runs
(Q1: 5, Q3: 12). No production change, no model call, no live run, no edit to a frozen contract,
library or run artifact.

## Conclusion

**MULTIPLE BLOCKERS ESTABLISHED.**

Three independent conditions sit between a sealed quote and scientific answer authority, applied in
sequence. All three are demonstrated on the preserved evidence:

1. **Result vocabulary.** A fixed, mostly past-tense verb pattern must match before any candidate
   exists. It matches none of the 17 quotes. It is the first block for all 17.
2. **Assertion join.** The matched span must fall inside exactly one assertion recognised by a
   separate classifier with its own closed verb list. This blocks Q1 p4 (the qualified up-to-2x
   finding) and Q1 p5.
3. **Owner rule.** The default support policy rejects a result whose owner is unresolved. The
   classifier resolves an owner only from an explicit local subject ("we", "this study"). This
   blocks Q1 p3 and Q3 p6.

**The suspected ownership-metadata blocker is not a cause.** Supplying valid, source-derived
ownership context changed nothing: the context resolver implements one narrow anaphor grammar that
none of the 17 quotes uses.

A bounded correction exists for blocker 1 only. On its own it produces a first cited answer for Q3
from one sentence of one paper, and leaves Q1 empty. It does not produce a scientifically adequate
answer to either question. Section 9 ranks the options; section 10 gives the recommendation.

## 1. Starting state and preservation checks

| Check | Result |
|---|---|
| Worktree / branch | unchanged (`experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`) |
| HEAD at start | `33004837e35dbe2642fd266b4b20e97f03566cb5` (as expected), worktree clean |
| Pilot library `library.sqlite` | sha256 `0ba4b183...9360` before and after; equals its fingerprint record |
| 103 files preserved by the pilot (Attempt 2 runs, inputs, protocol, bakeoff) | 0 changed |
| 62 pilot run files (`runs/Q1`, `runs/Q3`) | none modified since the audit began |
| Wiring check | the audit's condition A reproduces each live `17_sufficiency_map.json` exactly (dict equality), Q1 and Q3 |
| Focused tests (mapping, span matcher, assertion authority, B2 admission) | 264 passed, 9 xfailed; the broad suite was not rerun (no code changed) |

Method. The audit calls the unmodified v8 mapper
(`sufficiency_diagnostic.compute_diagnostic_sufficiency_map`, `sufficiency-semantics-v8`, the
version the live route uses) over each run's own sealed ledger, frozen contract and recorded
ownership index. Experimental conditions replace one module attribute in the audit process only.
Chunk types for the ownership counterfactual were derived by running the project's own
`tools/backfill_chunk_structure.py` against a **scratch copy** of the library; the frozen library
was opened read-only and is unchanged.

Artifacts (gitignored): `.local/phase34-b2-mapping-audit-20261012/` -- `audit.py`, `audit.json`,
`route_probe.py`, `route_probe.json`, `policy_probe.py`, `policy_probe.json`, `history_probe.py`,
`history_probe.json`, `preserve_check.py`, `preservation.json`, console logs, the scratch library.

### How the gates are arranged (observed in code)

Both contracts author one atomic requirement with one role, `finding`, mapping strategy
`achieved_outcome_predicate`, no disqualifying guards, model nomination not permitted, no authored
support policy. Q1 is `exists`; Q3 is `open_list`.

For that strategy the v8 path (`_bind_achieved_outcome_v7`) does this, per sealed quote:

| Step | Code | Passes when | Failure recorded as |
|---|---|---|---|
| 1 Recognition | `achieved_outcome_span.find_achieved_outcome_matches`, using `attribution._RESULT_PREDICATE` | the quote contains one of about 30 verb forms (`found`, `showed`, `demonstrated`, `observed`, `increased`, `associated`, `was greater`, ...) | nothing: the quote is skipped, role reads `missing / not_found` |
| 2 Join | `assertion_authority.locate_containing_assertion` | the matched span lies in exactly one assertion built around a verb from the classifier's own closed lists | counted as a join failure; no candidate |
| 3 Policy | `support_policy.default_support_policy` | kind is `result`, and the owner is not (`unresolved` and non-synthesis) | candidate kept, `admissible: false`, role reads `missing / candidate_supports_excluded` |

Ownership context enters only as an annotation between steps 2 and 3. It can turn an `unresolved`
owner into a resolved one when `ownership_context.resolve_local_antecedent` returns a proof. That
resolver recognises a single preregistered form (a sentence opening "Across these levels ..."
following a listed introduction) and returns `unsupported_anaphor` for everything else.

The two verb lists disagree. The step-1 pattern is narrower than the step-2 classifier's result and
replication verbs: the classifier knows `show / shows / shown`, `demonstrate`, `observe`, `find`,
`confirm`, `improve`, `provide`, `yield`; step 1 knows only the past forms. Six step-1 words are
absent from the classifier's result and replication lists (`chose`, `exhibited`, `expected`,
`identified`, `rated`, `responded`).

**Is the vocabulary a heuristic, positive evidence, or an absolute requirement?** By origin it is a
heuristic: `has_result_predicate` was written to stop "a clean-but-unrelated clause" validating a
result stated elsewhere, and the v1-v4 mapper used it only to ask whether a passage states a
result. From v5 on the same pattern became the anchor that candidate formation requires. In
operation it is an absolute requirement with veto authority, and the veto is silent: an
unrecognised result and an absent result both read `not_found`.

## 2. Proposition exclusion matrix

"Reports a finding" and "relevant" are the auditor's reading of the quote in its source chunk; they
are not adjudicated labels. Papers: 82 = *Designing optimal perturbation inputs for system
identification in neuroscience*; 83 = *Active learning of neural population dynamics using
two-photon holographic optogenetics*. Every row has ownership context
`unavailable / paragraph_boundary_unavailable` in the live run.

| Row | Paper / chunk | What the quote is | Reports a finding | Relevant to the obligation | Step 1 | Step 2 if recognised | Step 3 if joined | First block | Next block |
|---|---|---|---|---|---|---|---|---|---|
| Q1 p1 | 83 / 5221 | limitation of the passive approach (introduction) | no | background only | no match | no classifier verb | -- | vocabulary | none needed: not a finding |
| Q1 p2 | 83 / 5221 | statement of need | no | background only | no match | no classifier verb | -- | vocabulary | none needed |
| Q1 p3 | 83 / 5502 | authors' summary of the simulation result ("it shows that ... we can effectively design stimuli to speed up the estimation") | yes | yes; no magnitude | no match | joins on `shows`, kind `result` | fails: owner unresolved (subject "it") | vocabulary | owner rule |
| Q1 p4 | 83 / 5591 | the qualified result: up to 2x fewer samples in many cases, not all; worst case matches baseline | yes | yes; the core answer | no match | fails: no classifier verb (`illustrate`, `give`, `matches` are in neither list) | not reached | vocabulary | assertion join; owner and the negated first clause are untested beyond that |
| Q1 p5 | 83 / 5591 | restated result ("confirms ... can improve estimation rates") joined to an expectation ("we believe ... would speed up ... in online settings") | mixed | partly | no match | fails: span covers two assertions (`confirms` + `believe`) | not reached | vocabulary | assertion join |
| Q3 p1 | 82 / 4669 | general claim, no result marker | no (interpretation) | topical | no match | no classifier verb | -- | vocabulary | none needed |
| Q3 p2 | 82 / 4400 | conditional possibility ("If ... can be systematically designed, it becomes possible") | no | topical | no match | no classifier verb | -- | vocabulary | none needed |
| Q3 p3 | 83 / 5222 | aim ("We seek to ...") | no | topical | no match | classifier: `aim_or_hypothesis` | would fail on kind | vocabulary | kind |
| Q3 p4 | 83 / 5222 | capability statement citing prior work [36, 39, 42-46] | no | background | no match | joins on `provide`, kind `interpretation` (modal) | fails: kind and owner | vocabulary | policy (correctly) |
| Q3 p5 | 83 / 5222 | description of the platform | no | background | no match | classifier: `method_or_description` | would fail on kind | vocabulary | kind |
| Q3 p6 | 82 / 4616 | simulation result ("The simulation results show that perturbation-based estimation enables the precise control of neural states") | yes | partly: about control precision, not estimation efficiency | no match | joins on `show`, kind `result` | fails: owner unresolved (subject "The simulation results") | vocabulary | owner rule |
| Q3 p7 | 82 / 4616 | recommendation ("it is more appropriate to ...") | no | topical | no match | no classifier verb | -- | vocabulary | none needed |
| Q3 p8 | 82 / 4669 | background on control theory citing [42, 51] | no (prior work) | background | no match | joins on `provides`, kind `result` | fails: owner unresolved | vocabulary | owner rule (correctly) |
| Q3 p9 | 83 / 5215 | background (abstract) | no | background | no match | no classifier verb | -- | vocabulary | none needed |
| Q3 p10 | 83 / 5215 | background capability (abstract) | no | background | no match | no classifier verb | -- | vocabulary | none needed |
| Q3 p11 | 83 / 5215 | gap statement (abstract) | no | background | no match | no classifier verb | -- | vocabulary | none needed |
| Q3 p12 | 83 / 5215 | contribution statement ("we demonstrate the efficacy of a low-rank linear dynamical systems model, and develop an active learning procedure ...") | yes, with a method clause | partly: model efficacy, not an efficiency gain | no match | joins on `demonstrate`, kind `result`, owner `this_study` | passes | vocabulary | nothing: becomes admissible |

Counts. Of 17 sealed propositions, 4 report a finding (Q1 p3, p4; Q3 p6, p12) and one is mixed
(Q1 p5). The other 12 are background, aims, needs, recommendations, conditionals or descriptions.
B2 admitted them correctly as claim-supported-by-quote; that is a different property from being a
result. Excluding those 12 from the `finding` role is the right outcome, reached here only because
the vocabulary matched nothing at all.

Exact quotations, chunk and span identifiers, the model-written proposition text and the verifier
scores for all 17 rows are in `audit.json` (`cases.*.rows`). The quotations for the five
finding-bearing rows:

- **Q1 p3** (83 / 5502 / e9): "Furthermore, it shows that on a realistic simulation of neural
  population dynamics, we can effectively design stimuli to speed up the estimation of the dynamics."
- **Q1 p4** (83 / 5591 / e15): "As these results illustrate, though active learning does not give a
  substantial gain in all cases, in many cases it is able to give a gain of up to a factor of 2× in
  the number of samples required over the random baseline, and in the worst case, matches the
  baseline performance."
- **Q1 p5** (83 / 5591 / e16): "This further confirms that taking into account low-rank structure
  when choosing which measurements to take can improve estimation rates, and, we believe, is a
  strong indicator that our active learning procedure would speed up estimation of neural
  population dynamics in online settings."
- **Q3 p6** (82 / 4616 / e14): "The simulation results show that perturbation-based estimation
  enables the precise control of neural states."
- **Q3 p12** (83 / 5215 / e16): "Using neural population responses to photostimulation in mouse
  motor cortex, we demonstrate the efficacy of a low-rank linear dynamical systems model, and
  develop an active learning procedure which takes advantage of low-rank structure to determine
  informative photostimulation patterns."

## 3. Vocabulary-only exclusions

One: **Q3 p12.** With recognition supplied and nothing else changed, it passes the join and the
default policy and fills its instance.

The vocabulary is also the only mapping obstacle for two sentences that are **not sealed**, because
the verifier's NLI rejected them (support 0.005-0.06). Applied hypothetically, both join and pass
the default policy as this-study results:

- 83 / 5502: "In particular, on Mouse 1 and both datasets for Mouse 3, we observe a gain of between
  1.5-2× over baselines -- that is, to achieve a given estimation error, our approach requires
  between 1.5-2× fewer samples than baseline methods."
- 83 / 5215: "We demonstrate our approach on both real and synthetic data, obtaining in some cases
  as much as a two-fold reduction in the amount of data required to reach a given predictive power."

These are the clearest statements of the expected answer to Q1 in the library. Their path is
blocked upstream of mapping; the vocabulary would block them again if they were sealed
("we observe", "We demonstrate" are present tense).

## 4. Ownership-only exclusions

None.

No proposition is excluded by ownership alone, because the vocabulary excludes every proposition
first. More importantly, **missing ownership metadata excludes nothing even when the vocabulary is
set aside**:

- With chunk types derived on the scratch copy, 16 of 17 quotes get an available paragraph context
  (12 in `body_prose` chunks, 4 in `abstract_prose`). The 17th, Q3 p2 in chunk 4400, classifies
  `unknown` and stays unavailable.
- For all 16, the resolver returns `unsupported_anaphor`. No owner proof is produced.
- Conditions C and D are therefore identical to A and B in every requirement state and every
  candidate's admissibility. Only the recorded failure label changes
  (`paragraph_boundary_unavailable` becomes `unsupported_anaphor`).

What ownership metadata is actually for. It feeds one rule, `owner.local_antecedent.v1`, which
attributes a sentence beginning "Across these levels ..." to the study that introduced the listed
levels. It decides nothing else. It was never a general statement of which paper a passage belongs
to.

Why the evaluation library has no `chunk_structure` rows. The table is written only by
`tools/backfill_chunk_structure.py` (`replace_paper_structure` has no other caller). Ingestion,
import and indexing do not write it; the evaluation library was built by ingest plus indexing. The
same is true of any ordinary user library that has not had the developer backfill run, so
`paragraph_boundary_unavailable` is the normal state outside a prepared research copy, and the
local-antecedent rule cannot fire there. That is a real gap in generality, but it is not on the
path to a Q1 or Q3 answer.

There is no fallback in the current implementation: a chunk whose type is not `body_prose` or
`abstract_prose` yields no context, by design, and verified physical provenance of the quote is not
treated as a substitute.

## 5. Joint exclusions and other conditions

| Row | Conditions, in order | Scientifically right outcome? |
|---|---|---|
| Q1 p3 | vocabulary, then owner rule | no: a reported result of the paper is lost |
| Q3 p6 | vocabulary, then owner rule | no, for the same reason; its relevance to efficiency is partial |
| Q1 p4 | vocabulary, then assertion join (no verb the classifier knows) | no: the core finding is lost |
| Q1 p5 | vocabulary, then assertion join (two assertions in the matched span) | arguable: the sentence fuses a result with an expectation |
| Q3 p8 | vocabulary, then owner rule | yes: cited background |
| Q3 p4 | vocabulary, then kind and owner | yes: cited background capability |
| Q3 p3, p5 | vocabulary, then kind | yes: aim, description |

Two further conditions were observed that are not exclusions but bear on answer quality:

- **Relevance is not checked by this role.** The role has no target dependency, so any recognised
  this-study result in a quote the model tagged responsive fills it. Q3 p12 is about model efficacy
  and method development, not an efficiency gain, and it fills the role.
- **The classifier's hedging flag does not affect the default policy.** Q1 p3 ("we can effectively
  design") is flagged `hedged` and still classifies as `result`. A modal directly governing the
  result verb does demote to `interpretation` (Q3 p4, "can provide").

## 6. Offline counterfactual results

All four conditions ran through the real v8 mapper. "Recognition" was tried two ways: an **oracle**
(one anchor verb chosen by the auditor for each quote read as a result) and the **classifier
lexicon** (the classifier's existing result and replication verbs used as the step-1 pattern). Both
are experimental and exist only in the audit process.

| Condition | Q1 requirement | Q1 admissible | Q3 requirement | Q3 admissible |
|---|---|---|---|---|
| A current vocabulary + recorded context | `missing / not_found` | none | `missing / not_found` | none |
| B recognition + recorded context | `missing`, 1 candidate excluded (p3, owner) | none | `partially_filled` | **p12** |
| C current vocabulary + derived context | identical to A | none | identical to A | none |
| D recognition + derived context | identical to B | none | identical to B | **p12** |

Candidates formed under B / D:

| Recognition | Candidate | Relation | Kind | Outcome |
|---|---|---|---|---|
| oracle and lexicon | Q1 p3 | unresolved | result | excluded: `unresolved_non_synthetic` |
| oracle | Q1 p4 | -- | -- | no candidate: no governing assertion |
| oracle and lexicon | Q1 p5 | -- | -- | no candidate: multi-assertion span |
| oracle and lexicon | Q3 p6 | unresolved | result | excluded: `unresolved_non_synthetic` |
| oracle and lexicon | Q3 p12 | current_document | result | **admissible** |
| lexicon only | Q3 p4 | unresolved | interpretation | excluded: kind and owner |
| lexicon only | Q3 p8 | unresolved | result | excluded: owner |

So the wider lexicon surfaced two extra non-findings (Q3 p4, p8) and the existing downstream gates
excluded both.

Two supplementary probes go beyond the four requested conditions. Both are counterfactual.

**Does an admissible candidate reach a displayed, cited answer?** Yes. `route_probe.py` ran the
public reviewed route offline over the frozen Q3 inputs and the 12 live-sealed rows (no retrieval,
extraction or model; the responsiveness role scripted to tag every row, as the live run did).
Under the current vocabulary it returns the live answer's first two lines; the third differs
because the offline probe runs no recovery ("Recovery has not completed the scoped search" in place
of "The scoped search completed, but this obligation remains unresolved"). Under lexicon
recognition it returns, before that same recovery line:

> 1. What evidence supports actively designing perturbation inputs to estimate neural dynamics more efficiently across the optogenetic active-learning and optimal perturbation-input studies?
> we demonstrate the efficacy of a low-rank linear dynamical systems model, and develop an active learning procedure which takes advantage of low-rank structure to determine informative photostimulation patterns. [1]
> These are reported examples; completeness of the list is not established.
> Some relevant evidence does not meet this requirement's support rules and is not used as support.

Plan node `partial`, one Layer C `role_value` claim, one citation to p12, no relation unit. Q1 under
the same recognition stays "does not establish an answer", with the added line that some relevant
evidence did not meet the support rules. This is the first Layer C claim and citation produced from
Q1/Q3 evidence, and it is an offline experimental result, not a live one.

**What would the two obvious owner shortcuts admit?**

| Shortcut (existing mechanism) | Newly admissible | Problem demonstrated |
|---|---|---|
| A contract-authored support policy that permits an unresolved owner (`policy_probe.py`, on an in-memory copy of the contract, with lexicon recognition) | Q1 p3; Q3 p6, **p8** | p8 is cited background on control theory; it would be presented as a finding |
| A blanket this-study owner signal through the classifier's legacy `structural_context` input (not used by the v8 path) | the same three | the same; and section labels cannot scope it (chunks 5502 and 5591 are results text labelled `introduction`) |

Neither shortcut changes anything under the current vocabulary: no candidate exists to evaluate.

## 7. Which scientifically useful findings could become eligible

| Finding | Question | Becomes eligible with | Status |
|---|---|---|---|
| Model efficacy and the active-learning procedure (p12) | Q3 | recognition alone | demonstrated offline, including display and citation |
| Simulation shows stimuli can be designed to speed estimation (p3) | Q1 | recognition + a sound owner rule | counterfactual; the owner rule does not exist |
| Simulation shows perturbation-based estimation enables precise control (p6) | Q3 | recognition + a sound owner rule | counterfactual; relevance to efficiency is partial |
| Up to 2x fewer samples in many cases, not all (p4) | Q1 | recognition + an assertion the classifier can build + owner, at least | untested past the join |
| 1.5-2x fewer samples; two-fold data reduction (not sealed) | Q1, Q3 | a verifier that admits them + recognition | hypothetical on both counts |

Even with every mapping condition satisfied, Q3 would rest on p12 and p6: one sentence per paper,
neither stating an efficiency gain. The sentences that do state the gain are not in the sealed set.
A correct mapper cannot supply the two-study efficiency synthesis Q3 asks for from this evidence.

## 8. Is the next blocker demonstrated or hypothetical

| Boundary | Status | Basis |
|---|---|---|
| Result vocabulary blocks all 17 | demonstrated | condition A equals the live map; pattern has zero hits |
| Owner rule blocks p3, p6 once recognised | demonstrated (counterfactual run) | conditions B / D |
| Assertion join blocks p4, p5 once recognised | demonstrated (counterfactual run) | oracle trace |
| Missing ownership metadata blocks anything | **refuted for these 17** | C = A, D = B |
| Layer C, plan or rendering blocks an admissible candidate | not observed | route probe produced a cited answer |
| Layer C behaves the same with a live coverage model | untested | the probe scripts the model roles |
| p4 would pass owner and negation handling after a join | untested | never reached |
| The verifier would seal the 1.5-2x and two-fold sentences under any policy considered so far | known not to (pilot report) | NLI 0.005-0.06 |

## 9. Smallest defensible correction, ranked

All options below are regex or pure-function work. None adds a model call, so none adds measurable
latency. The pilot runs averaged roughly 9-14 s of wall time per model call on JUNO (348 s / 38
calls and 389 s / 28 calls); any option that adds a per-role model call would cost on that order.

| Rank | Correction | Expected benefit | Scientific risk | Runtime cost |
|---|---|---|---|---|
| 1 | **One vocabulary instead of two.** Form achieved-outcome candidates from the assertion classifier's own result and replication verbs (plus the six current words it lacks), leaving kind, owner, veto and policy gates as they are. A new semantics version, not an edit to v8. | Q3 gains p12 and a cited answer. Removes the block on "we observe / we demonstrate" sentences if they are ever sealed. Converts silent `not_found` into visible `candidate_supports_excluded` for recognised-but-excluded evidence. | Low to moderate. On 56 unique sealed quotes from three preserved q_aib runs: 3 admissible now, 6 under the wider lexicon, 0 lost, 14 moved from unrecognised to policy-excluded. Of the 3 new admissions, two are this-study results and one is a prior-work sentence ("Recent work ... has implicated ...") that the default policy already permits as attributed-external. Weak verbs (`described`, `provides`) become anchors. No labels exist for "is a finding", so these are counts, not accuracy. | none |
| 2 | **A bounded owner rule for results-noun subjects** ("the / these / our [simulation] results / findings / analysis show ..."), with the classifier's existing citation and prior-framing vetoes. | Would resolve p6. Would not resolve p3 ("it shows") or "This demonstrates". | Moderate to high without new negative controls: "these results" can refer to cited work. The two blunt alternatives were shown to admit cited background (section 6). Needs preregistration, like the existing local-antecedent rule. | none |
| 3 | **Assertion construction for results stated without a listed verb** (p4) or fused with an expectation (p5). | The core Q1 finding. | High: this widens what counts as an assertion, and p4 carries a negated clause and a qualification that must survive intact. Not a small change. | none |
| 4 | **Author the contract differently** (permissive support policy, or `model_nomination_only`). | Policy: p3, p6. Nomination: unknown. | Policy route demonstrated to admit p8. Nomination moves result recognition to a model and bypasses the deterministic kind and owner gates; not shown to be needed. | policy: none; nomination: one model call per role |
| -- | Backfill or auto-derive `chunk_structure` | none for Q1 / Q3 | none | minutes per library |

Why rank 1 is more than adding "shows" and "demonstrate" to the pattern. Adding two words would fix
p12 and nothing structural. The defect is that a narrow list has veto authority ahead of a
classifier that already separates results from aims, methods, interpretations, modally governed
claims, negated results and absence-of-evidence statements. The correction is to stop the first
list overruling the second, not to lengthen it. On this evidence that distinction-keeping machinery
did its job under wider recognition: it excluded the aim, the description, the modal capability
statement and the cited background, and admitted one explicit this-study result.

What rank 1 does not settle: whether a verb should have veto authority at all. It still requires a
listed verb. p4 shows the limit: a result stated with "is able to give a gain of" has no listed
verb in either vocabulary.

Runtime defect versus contract defect. The Q1 and Q3 contracts chose the only deterministic
strategy the engine offers for a reported result, with defaults. That choice is reasonable; the
audit found no authoring error that explains the empty answers. Two contract-level observations
remain: the role carries no target terms, so relevance rests entirely on the upstream
responsiveness tag; and the reviewer could not have seen from the contract that the strategy
recognises only past-tense verbs.

## 10. Recommendation

1. **Authorize rank 1 as a bounded, versioned experiment**, in this order: a new non-current
   semantics version; offline replay on the preserved q_aib and Q1/Q3 ledgers with the frozen v8
   results unchanged; negative controls for aims, hypotheses, conditionals, modal claims, methods
   and cited prior work, written before the replay; then Q1 and Q3 live, once each.
2. **Set the expectation before that run.** Q3 should return one cited sentence from paper 83, with
   no two-study synthesis and no efficiency figure. Q1 should stay empty. A different result would
   itself need explaining.
3. **Do not take either owner shortcut.** Both admit cited background as a finding.
4. **Treat the Q1 answer as a verification problem first.** The sentences that state the answer
   cleanly ("we observe a gain of between 1.5-2×", "as much as a two-fold reduction") pass every
   mapping gate under rank 1 and are rejected by NLI. That is the shorter path to a useful Q1
   answer than teaching the mapper to parse p4, and it needs its own bounded diagnosis.
5. **Defer ranks 2 and 3** until rank 1 has been observed live. Each needs preregistered rules and
   controls of its own.
6. **Record, do not fix, the `chunk_structure` gap**: the local-antecedent owner rule cannot fire
   in a library that has not had the developer backfill.

## Limits of this audit

- "Reports a finding" and "relevant" are one reader's judgments, not adjudicated labels.
- The oracle anchors are the auditor's choices; the lexicon variant is the reproducible one.
- The historical counts come from one question on a different library and have no finding labels.
- The route probe scripts the model roles; no live run tested any counterfactual.
- Bakeoff labels behind B2 remain one blinded ChatGPT adjudication, not independent human
  scientific approval.
- B2 remains an opt-in experimental configuration; nothing here changes that.
