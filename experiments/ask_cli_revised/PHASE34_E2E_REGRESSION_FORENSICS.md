# Phase 34 — Stage-by-stage regression forensics: Phase 28 vs Phase 34 q_aib runs

Read-only audit. No code changed, no model called, no run started.

## Verdict

**The evidence pipeline did not regress. The reader-facing answer did, and I introduced most of that
regression in the last increment.** Up to and including the sealed evidence, the Phase 34 run is equal or
better than Phase 28: the same papers, more verified claims (64 vs 54), and the same amygdala, Hadza and
Explicit Bias Questionnaire passages. The older run's parent output named those findings; the new run's
parent claim output still names them. They vanish only in the new hierarchical document, because its
overview is restricted to passages cited by child statements that survived screening, and the document does
not show the claim ledger at all.

Three causes account for nearly everything observed, in order of impact:

1. **New presentation layer (mine, `hierarchical_answer.py`, commit `555a1d31`)** hides the parent claim
   ledger and feeds the overview only from displayed child statements. Confirmed regression.
2. **Lexical paraphrase screens on synthesis statements** (unchanged since before Phase 28) reject faithful
   sentences. In Phase 34 they alone withheld 8 of 9 withheld child statements; DeBERTa supported each
   of the 8 at 0.92 or higher. Pre-existing, now the dominant loss, and no longer needed for what they were built to
   cover.
3. **Sufficiency semantics v2–v7 (Phases 32–33)** removed the intervention-outcome observation that Phase 28
   recorded, so the answer's gap list now denies an intervention the answer itself reports. Confirmed
   regression in the sufficiency state.

DeBERTa is a demonstrable improvement and should stay.

## 1. The two executions

| | Phase 28 Attempt 2 | Phase 34 Attempt 2 |
|---|---|---|
| Date | 2026-10-04 | 2026-10-12 |
| Executing commit | `7203b1a1` | `887b41ba` (code identical to `555a1d31`) |
| Profile, question, library | T5C, q_aib, Sept-30 copy | same |
| Flags | hierarchy, model-assist, recovery, parent synthesis | same, plus `nli_verifier=deberta`, `parent_narrative` |
| NLI | MiniLM, support ≥ 0.55 | DeBERTa, support ≥ 0.50 |
| Sufficiency semantics | unversioned (pre-v2) | v7 |
| Reader-facing parent output | `15_parent_answer.md` (claim ledger) | `19_hierarchical_answer.md` (new) |

Recovery reuse (`30088220`) postdates both runs and was used in neither.

## 2. What changed in code between the runs

63 commits. Of the modules on this run's execution path, **twenty are byte-identical** between the two
commits: retrieval, discovery, the worker prompts and tasks (`qwen.py`), claim formation and verification
(`propositions.py`), sealing (`stages.py`), coverage, supervisor prompts, topology, the hierarchy contract,
the child overview stage and all its lexical screens (`overview.py`, `overview_evidence.py`,
`overview_guards.py` apart from a threshold hook), the renderers and the audits. The shared application
verifier is unchanged.

What did change on the path:

| Phase | Change | Intended problem | Benefit shown on real answers? | Reached this run? | Can explain a regression? |
|---|---|---|---|---|---|
| 29–31 | Answer-plan and "question-organized answer" modules | Parent output was a flat list | Offline replays only | **No.** They serve the reviewed route, not the hierarchical one | No |
| 32 (I1–I3) | Relation witness, direction target, referent containment in `sufficiency_engine`/`sufficiency_mapping` | Relations and directions credited without a witnessing source | Synthetic and replay tests | **Yes** (semantics v7 is the default) | **Yes: R6**, the lost intervention outcome |
| 33 (I2) | Category polarity, result complement | Null and negative results miscounted | Synthetic tests | Yes | Possibly R6 |
| 34 (I4.x) | Assertion authority, support policy, Layer C, producer authorization, reviewed route | Attribution and ownership of claims | Offline; live Q1–Q6 runs returned empty answers | **No** for this route (v8 and Layer C are the reviewed route) | No |
| 34 | DeBERTa verifier, threshold 0.50 | MiniLM rejected correct support | Bakeoff, and this run | Yes | No; it improved outcomes |
| 34 | `hierarchical_answer.py`, stage S3 | No narrative parent, no combined document | **None before this run** | Yes | **Yes: R1, R2, R3, R7** |

Most of the 85,000 added lines between the two commits never executed in this run.

## 3. Stage by stage

| Stage | Phase 28 | Phase 34 | Finding |
|---|---|---|---|
| W1 retrieval and claims | 213 calls, 56 claims | **Token-identical**: same 213 calls, same 56 claims in the same order | No change |
| Initial verification | 25 verified / 20 weak / 11 unverified | 31 / 14 / 11 | **Improvement.** Six identical claims flipped weak → verified with DeBERTa; none flipped the other way. Two are amygdala claims MiniLM had scored 0.01 |
| C1 coverage | all 11 children judged responsive | same | No change |
| U1 mapping | 18 scopes | 19 scopes | Comparable |
| P1 plan | DEEPEN for all 11 | same | No change |
| W2 recovery | 21 targets, 208 claims, 44 verified | 24 targets, 240 claims, 57 verified | More evidence. Same repetition pattern in both |
| C2 / sealed ledger | 54 claims, 9 papers | 64 claims, 10 papers | **Improvement.** Amygdala ×5, Hadza ×4, EBQ ×7 in both |
| U2 final sufficiency | c12 intervention *partially filled*, c2 behavior *partially filled*, c1 neural *partial* | c12 **missing**, c2 **missing**, c1 **filled** | **Regression** for c12 (code) and c2 (model nomination); improvement for c1 |
| S1 child syntheses | 9 of 11 show a statement; 10 withheld | 8 of 11; 9 withheld | Same screens. Different wording tripped them on different children |
| S2 claim realization | 21 claims, 7 grounded, 9 rejected by MiniLM | 17 claims, 10 grounded, 1 rejected by NLI | **Improvement** from DeBERTa |
| Parent claim output | names amygdala, Hadza, EBQ, IAT, just-world, dictator game, NAME | names all of those **except NAME** | One loss (R6) |
| S3 overview | — | 4 sentences; no amygdala, Hadza, EBQ | **New regression** |
| What the reader received | the claim ledger | the hierarchical document | **Regression**: findings the system holds are not shown |

## 4. Evidence-loss table

| Finding | In sealed evidence | Phase 28 output | Phase 34 reader output | Earliest failure | Cause | Class | Confidence |
|---|---|---|---|---|---|---|---|
| Amygdala response correlates with just-world beliefs, less empathic concern, less prosociality | both | parent ledger ×4; child c4 | absent from the document (present in the unshown ledger) | S1 screen, then S3 evidence rule | `direction_word_not_in_passage` and `negation_dropped` withheld faithful sentences; S3 then excluded the evidence | presentation regression on top of an existing screen limitation | high |
| Increased amygdala reactivity with high implicit bias | both | parent ledger | absent | same | same | same | high |
| Hadza finding | both, cut mid-sentence at a chunk boundary | parent ledger names "Hadza" | absent; "culturally shared" shown without the Hadza result | evidence extraction (truncated passage), then S3 | truncation makes the passage ineligible for synthesis in **both** runs; the ledger carried the name, the new document does not | pre-existing defect made visible by the presentation regression | high |
| "Culturally shared" sentence | both | identical child sentences in both runs | same sentences, now also promoted into the overview without its qualifier | S3 | the overview model shortened it | new presentation regression | high |
| Explicit Bias Questionnaire | both | parent ledger ×2 | absent | S1 screen, then S3 | the EBQ child sentence was withheld for `too_many_novel_terms` in **both** runs, word for word | pre-existing, exposed by the presentation regression | high |
| NAME intervention reduces implicit bias | both | child withheld by MiniLM (0.11); ledger carried the outcome | **shown** in child c12 and in the overview | — | DeBERTa | **improvement** | high |
| Intervention outcome in the sufficiency state | both | partially filled, outcome "supported" | **missing** | U2 | semantics v7 drops the effectiveness observation unless the relation is witnessed | **confirmed code regression** | high |
| Behavior measures (share decisions, dictator game) | both | sufficiency partially filled; ledger | ledger only; sufficiency missing | U2 | the model nominated nothing this time | generated-output variance | medium |

## 5. The seven regressions

**R1 Amygdala.** The lexical screens are byte-identical in both commits, so this is not a changed screen.
In Phase 28 the model wrote a short single-passage sentence for c4, which passed; the same `negation_dropped`
rule withheld its second sentence. In Phase 34 the model joined the two passages into one sentence and the
rule fired on the whole thing. The rule fires when the cited passage contains a negated clause that shares
two content words with the statement and the statement has no negation, whether or not the statement used
that clause. The other rejection, `direction_word_not_in_passage`, is "reduced" for "less". Under Phase 28's
presentation the loss would have been invisible, because the ledger carried the finding. The S3 evidence
rule converted a child-screen miss into a parent-level omission. *Existing limitation triggered by wording
+ new presentation regression.*

**R2 Hadza.** The passage ends "…were less moral and were better" in both runs: the chunk boundary cuts the
sentence, the continuation join did not repair it, and a truncated passage is ineligible for synthesis. So
neither run could synthesize the Hadza result. Phase 28's ledger still printed "a named culture or
population: Hadza". The new document prints only "culturally shared". The paper's own abstract says
"culturally shaped"; both strings are verbatim in the PDF. *Pre-existing extraction defect + new
presentation regression.*

**R3 Named scales.** The model proposed the same EBQ sentence for c9 in both runs and
`too_many_novel_terms` withheld it both times for the words "supports, existence, regarding, toward,
observed, level". The ledger named the instrument in both runs. *Pre-existing screen false rejection,
exposed by the presentation regression.*

**R4 Unresponsive children.** c6, c10 and c11 show the **identical** sentences in both runs. Nothing checks
that a displayed statement addresses its subquestion: the screens test fidelity to the passage, and the
coverage audit judges evidence, not the synthesis. *Pre-existing, unrecognized until now.*

**R5 Distortions.**
- *Prediction as finding:* new in Phase 34. The claim kept "were predicted to elicit" and was verified
  correctly; the child synthesis dropped "predicted". "Predicted" is not treated as a hedge, so
  `hedge_dropped` did not fire. Phase 28 did not retrieve that passage. *Existing gap, triggered by content.*
- *"This bias" for "dehumanization":* **present in Phase 28's claims too** (same substitution, MiniLM 0.84
  and 0.89). No check compares referents. *Pre-existing claim-formation error.*
- *Dropped left-amygdala link, perceived traits as perceiver traits:* synthesis and coverage choices with no
  check behind them. *Pre-existing limitations.*

**R6 Answer contradicts its sufficiency state.** In both runs the model nominated nothing for the
"intervention" role, and the NAME passages found in recovery were never offered to it (status
`held_fixed_no_valid_prior`). Phase 28 still recorded "outcome reported: supported" for three intervention
passages from a deterministic observation, which gave a partial fill and a parent claim. Under v7 those
observations are empty and each instance carries `relation_witnessed: false`. *Confirmed code regression
(Phase 32–33), sitting on a pre-existing U2 limitation.* The child synthesis is right and the gap list is
wrong.

**R7 Parent synthesis.** The old parent output was an unreadable but complete list of 21 claims. The new
overview is four screened restatements of single passages placed side by side: no relationship between
findings, no brain, no traits. It is not synthesis. The 12-passage cap removed 2 passages; the
displayed-children rule removed every passage belonging to a child that showed nothing. *New presentation
regression.*

## 6. Safeguard disposition

| Mechanism | Error it targets | Evidence it works | Observed harm | Disposition | Scope | Risk |
|---|---|---|---|---|---|---|
| Exact-quote verification | fabricated quotations | every displayed sentence traces to a real passage | none | **Keep** | — | — |
| DeBERTa NLI, source and screens | unsupported claims | 6 correct claims recovered at W1, 8 fewer false rejections at S2, the 0.99 contradiction excluded | passes a copied prediction | **Keep** | — | — |
| Contradiction veto | source disagrees | 4 records excluded in Phase 34, 15 in Phase 28 | none seen | **Keep** | — | — |
| `hedge_dropped`, `causal_cue_not_in_passage`, `negation_introduced` | overstatement | caught one over-causal sentence in Phase 28 (c8) | one debatable rejection | **Keep** | — | — |
| `too_many_novel_terms` | invented content | none in either run that NLI did not also catch | 7 hits across the two runs, 5 on sentences the NLI model supported | **Simplify**: note it, do not withhold, when NLI passes | one rule | low now that the NLI model is reliable |
| `direction_word_not_in_passage` | reversed direction | none in either run | 5 hits, all "reduced/reducing" for "less"; 2 on sentences the NLI model supported | **Simplify** the same way | one rule | low; a true reversal is a contradiction and NLI scores it |
| `negation_dropped` | dropped null result | none in either run | 5 hits, 4 on sentences the NLI model supported, including an amygdala sentence in each run | **Repair minimally** (only when the statement uses the negated clause) or simplify as above | one rule | low |
| `preposition_shift` | actor/recipient swap | one hit, on a sentence NLI also rejected | — | Defer | — | — |
| Similarity gate 0.70 | off-topic citation | none shown | 92 exact-quote, NLI-supported claims discarded in Phase 34 | **Defer**; the B2 pilot already showed the trade-off | — | — |
| Truncated-passage ineligibility | fragments as evidence | sound in principle | hides the Hadza result in both runs | **Repair minimally** at the chunk join, or defer | medium | medium |
| Sufficiency v7 effectiveness witness | outcome credited without a witnessed relation | synthetic tests only | removes a true, verified intervention outcome | **Revert for the hierarchical route** (run it on the pre-v2 semantics) or defer the gap list | config-level if selectable | low for this route |
| U2 held-fixed remap | cost of re-nomination | — | recovery evidence is never offered for role nomination | Defer | — | — |
| S3 displayed-children evidence rule (mine) | parent sentences without child backing | none | hides ledger findings | **Revert / replace** | small | low |
| Parent claim ledger and S2 | parent claims without authority | carries every key finding in both runs | unreadable as prose | **Keep**, and show it | — | — |

Across both runs the three paraphrase rules fired 17 times, 11 of them on sentences the run's NLI model
supported. Of those 11 I found one debatable catch (Phase 34 c2, a sentence that files attitudes under
behavior) and none that was clearly an error. The Phase 28 figures use MiniLM's scores, which were unreliable.

## 7. Friday repair candidates, ranked

1. **Show the ledger in the reader-facing document.** Under each subquestion, list the parent claims that
   belong to that child (they carry `child_ids`), with their citations, beneath the child synthesis.
   Recovers amygdala, Hadza, EBQ, IAT, just-world and the dictator game in the next run with no new model
   call and no change to any safeguard. Renderer-only, in a module that is one day old. *Highest impact,
   lowest risk.*
2. **Feed the overview from the ledger's evidence**, not only from displayed child statements: the passages
   cited by parent claims plus those cited by children. One function (`parent_view`). Removes the mechanism
   by which a child-screen miss erases a finding from the overview.
3. **Stop the three paraphrase rules from withholding a statement that DeBERTa supports.** Record the rule
   hit in the inspection file instead. By the preserved records this would have displayed 8 more child
   statements in Phase 34, including both amygdala sentences and the EBQ sentence. Three rules, one place.
   This is a simplification, not a new check.
4. **Suppress or correct the gap list for intervention outcome.** Either run the hierarchical route on the
   v1 sufficiency semantics, which the engine still accepts, or drop per-child gap lines where the child
   synthesis displays a statement, pending a real fix. Removes the self-contradiction.
5. **Treat "predicted", "hypothesized", "expected to" as hedges** in the existing `hedge_dropped` rule, so a
   dropped prediction is caught. One word list.

Not for Friday: the similarity gate, the chunk-boundary join, U2 nomination scope, a responsiveness check on
child statements, and a real cross-finding synthesis. Items 1–3 change what the reader sees without any of
them.

Two caveats. Items 1 and 2 are presentation repairs to code I wrote; they restore information, they do not
make the overview a synthesis. And the R4 problem, faithful sentences that do not answer the subquestion,
has no small repair here; it is a property of the system that both runs share.

## 8. Open uncertainties that matter for Friday

| Uncertainty | Cheapest resolution |
|---|---|
| Does `sufficiency-semantics-v1` reproduce Phase 28's behavior? The engine still accepts v1, and `execute` passes one constant, so selecting it is a one-parameter change | Offline: map the preserved Phase 34 sealed ledger under v1 and check that the intervention outcome returns |
| How many of the 17 paraphrase-rule rejections were truly faithful? I read the Phase 34 ones; the Phase 28 ones I classified from the records | Read the 10 Phase 28 sentences against their passages; under an hour |
| Do the repairs hold beyond q_aib? | Offline: replay the preserved Phase 34 S1 proposals through the changed screens and re-render; then one authorized run on q_lld |
| Does a Qwen-only run (no phi4, no gemma) change coverage and planning quality? | Not answerable offline; it is the next run's question |
| Why did the model nominate behavior measures in Phase 28 and not in Phase 34? | Unresolved; compare the two nomination prompts if it matters |

## 9. Method and limits

Compared the two runs' preserved artifacts stage by stage; diffed the two commits; read every proposed child
statement in both runs with its screen result; compared sufficiency state per requirement and the model
nomination receipts. Counterfactual checks were limited to facts that need no execution: the screen code is
byte-identical between the commits, and the first-pass claims are token-identical, so the NLI comparison on
those 56 claims is controlled. Faithfulness judgments are mine, from reading sentences against passages.
Two runs of one question.

Scripts: `.local/phase34-regression-forensics-20261012/f1_compare.py`.
