# Phase 34 — B2 live pilot and downstream safety check

**Disposition: B2 PILOT PARTIAL.**

B2 does what it was chosen to do at verification: on the live Q1 and Q3 runs it more than
doubles the sealed evidence, admits the qualified "up to 2×" finding that Attempt 2 dropped,
and admits nothing I judge unsupported. The downstream safety check found no path by which
the fabricated causal control's wording reaches a selected answer. **Both selected answers are
still empty.** The limiting boundary has moved one stage downstream, to scientific mapping.

This is not release qualification, and B2 is not promoted to any wider path.

## 1. Starting HEAD and worktree state

- Worktree: `.claude/worktrees/ask-060-hier11-recpm3-citefix-20260929T212442Z`
- Branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`
- Starting HEAD: `60b2aff3301cf1099413ed96395ab570eb101f5c`, clean at entry. The only workflow
  recorded for that commit (CodeQL) completed successfully.
- Live runs executed from `18e25be27db6a812057b5ce28a383a82d997e038` (the configuration commit
  below), clean tree, recorded in each run manifest.

## 2. Configuration change and scope

Two tracked source changes, one new test file:

- `reviewed_ask_admission.py` (new): one constant,
  `B2_PILOT_VERIFICATION_CONFIG = VerificationConfig(retrieval_threshold=0.0, support_threshold=0.90)`.
- `runtime.py`: `build_runtime` gains an optional `verification_config` parameter. Omitted, it
  constructs `VerificationConfig()` exactly as before.
- `test_reviewed_ask_admission.py` (new): 13 tests.

Nothing selects the policy by default. The pilot driver passes it explicitly and asserts the
constructed verifier carries it. Not touched: `app/backend/summarization/verification.py` and its
defaults, the application summarize pipelines, `reviewed_ask.py`, `e2e.py`, `propositions.py`,
`stages.py`, any contract, any v8 / Layer C v2 / parent-synthesis-v2 / plan-v5 code, and every
file in the producer-code input manifest. Neither changed file is in that manifest.

**What is and is not avoided.** Setting the threshold to 0.0 disables the logical gate only. The
verifier still embeds each claim, still runs the vector search, and still records the
claim-to-chunk similarity; a test pins that the search still executes. No model work is saved.
One labelling side effect: with the gate always satisfied, a non-admitted record is labelled
`weak`, never `unverified`. Only `verified` records are sealed, so this changes no admission.

## 3. Baseline versus B2 verification behaviour

Tests run the shared verifier's own `_status` and `verify_many`:

| Case | Default | B2 |
|---|---|---|
| Exact quote, NLI 0.994, similarity 0.657 (live Q1, chunk 5591) | weak | verified |
| Exact quote, NLI 0.89, similarity 0.95 | verified | weak |
| Quote not in the cited chunk, NLI 0.99 | not verified | not verified |
| Contradiction 0.60 above support 0.30 | contradicted | contradicted |
| Contradiction 0.93, support 0.05, similarity 0.20 | contradicted | contradicted |

Also tested: the default runtime still carries the shared defaults; eleven other runtime
surfaces (application pipelines, the legacy CLI runtime, `e2e.py`, `reviewed_ask.py` and
others) neither import the policy nor pass a verification config.

## 4. Negative causal-control reproduction

The control is bakeoff packet item **E009** (`ctl45378c69e7efc`, synthetic, written by Claude as a
minimal edit of a verified claim; q_aib library, paper 67, chunk 34974).

- **Claim:** "Stronger just-world beliefs cause an increased amygdala response to facial anomalies."
- **Quote (exact source text):** "Across these levels of organization, the specific amygdala
  response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what
  they deserve), less dispositional empathic concern, and less prosociality toward people with
  facial anomalies."
- **Intended and adjudicated status:** unsupported (ChatGPT, high confidence: a correlation does
  not establish causation). The claim adds a causal direction the source does not state.
- **Scores:** similarity to chunk 0.681, quote 1.0, NLI support 0.981, contradiction 0.003.
  Recomputed with the pinned local models: NLI identical, similarity equal to 1e-7.
- **Decision:** default `weak` (similarity under 0.70); **B2 `verified`**. Reproduced.

For reference, NLI over the quote plus neighbouring sentences scored this claim 0.54.

## 5. Downstream relationship and answer-authority safety

**Structural finding.** In the reviewed route, the model-written claim sentence is not what
downstream science reads. The v8 mapper, the relation witness, Layer C projection and the
renderer all operate on the sealed **physical quote**. The claim sentence is used for
verification, for de-duplication, and by the coverage model that tags which obligation a
proposition is responsive to. So an over-admitted claim admits its *quote*, and every later
decision is made on source text.

**Probe.** The control was handed, as an already-verified proposition, to the public
`reviewed_ask.run_reviewed_request` with explicitly synthetic reviewed contracts. Real: sealing,
ownership context, v8 mapping, witnessing, Layer C v2, plan-v5, rendering. Scripted: retrieval and
the coverage/mapping model roles. Each case was run twice, once with the fabricated causal claim
and once with the faithful original claim, over the same quote.

| Case | Requirement | Layer C claim | Relation witnessed | Rendered as cited finding |
|---|---|---|---|---|
| Real control, real source chunk as context, atomic result contract | filled | 1 role value | n/a | No. "cannot be displayed with an authorized quotation"; no citation |
| Real control, relational contract | partially filled | 1 role value | **No** | No. "does not establish the requested relationship" |
| Real control, question worded causally | filled | 1 role value | n/a | No. Same presentation limitation; no citation |
| Synthetic first-person correlational quote, relational contract | filled | relational | Yes (the quote's own association) | Yes: the quote verbatim, cited |
| Same synthetic quote, question worded causally | filled | relational | Yes | Yes: the quote verbatim, cited |

In all five cases the selected answer and the scientific map are identical for the fabricated
and the faithful claim (the map differs only in the sealed-input hash, which covers the claim
text by construction). The fabricated sentence appears in the sealed ledger and model-call log
and nowhere in the selected answer; the word "cause" appears only inside the question itself.

**The six required distinctions, for the E009 control:**

1. Passes B2 verification: **yes**.
2. Becomes eligible scientific evidence: **its quote does**, when its source context is
   available. Without that context the support-policy guard rejects it.
3. Satisfies a relationship requirement: **no** (partially filled).
4. Receives an authorized relationship witness: **no**.
5. Becomes a Layer C claim: **yes, as a role value drawn from the quote**, not as a relation.
6. Appears as a cited causal conclusion: **no**. Nothing is displayed or cited.

No release-blocking failure was demonstrated. Three limits on that statement:

- **The causally worded question is a real weakness, but not a B2 one.** In the synthetic case
  the answer prints "Do stronger just-world beliefs cause…?" followed by a cited sentence saying
  "positively associated". The text is honest, but a reader could take the quote as an answer to
  the causal question. This happens identically with the faithful claim and under the default
  thresholds. The contract vocabulary has no causal role, so nothing checks that an associational
  quote answers a causal question.
- **Claim text still steers attachment.** The coverage model reads the claim sentence when
  tagging responsiveness. An overstated claim could attach an otherwise unrelated quote to an
  obligation. Quote-level role guards then apply; this path was not exercised with a live model.
- **Highest authentic boundary.** The real control's quote did not reach display in any
  configuration, so claim-to-citation rendering was exercised only with the synthetic quote.

**Baseline comparison.** The default rule admits four other controls of comparable seriousness
(E004, an added "and against people of colour" the source denies; E092 and E078, referent swaps;
E035, a dropped "is often taken as evidence"). By the same mechanism their claim wording cannot
reach an answer either; their quotes can. B2 admits those four as well.

**Smallest plausible remedy if causal questions matter** (not implemented): a contract-level
relation type so a causal requirement cannot be witnessed by associational wording. For
over-admission at verification itself, the bakeoff's context-confirmation rule is the only tested
mechanism that rejected this control.

## 6. Q1 live result

One run, `runs/Q1/attempt-03-b2`. Same reviewed inputs, library, models and settings as Attempt 2.

Complete selected answer (identical to Attempt 2):

```text
1. What did the study of active learning of neural population dynamics using two-photon holographic optogenetics find about data efficiency?
The available evidence does not establish an answer to this part.
The scoped search completed, but this obligation remains unresolved.
```

**FAIL** as a scientific answer: no gains, no scope.

The pipeline formed the same nine claims as Attempt 2. Sealed propositions rose from 2 to 5, all
from paper 83 and all tagged responsive. Newly sealed:

- chunk 5591: "…though active learning does not give a substantial gain in all cases, in many
  cases it is able to give a gain of up to a factor of 2× in the number of samples required over
  the random baseline, and in the worst case, matches the baseline performance."
- chunk 5502: "…on a realistic simulation of neural population dynamics, we can effectively
  design stimuli to speed up the estimation of the dynamics."
- chunk 5591: "…taking into account low-rank structure when choosing which measurements to take
  can improve estimation rates…"

The first is the expected finding with its qualifications. Recovery now reports
`recovery_added_evidence` instead of `recovery_no_new_evidence`.

**New limiting boundary.** The requirement's `finding` role is `missing / not_found`. The frozen
contract maps that role with `achieved_outcome_predicate` and does not permit model nomination.
That strategy looks for a fixed set of result verbs (`found`, `showed`, `demonstrated`,
`correlated`, `increased`, `were more`, and similar, mostly past tense). None of the five sealed
quotes contains one: this paper writes "is able to give a gain", "shows that", "can improve".
No candidate was formed, so witnessing, Layer C and rendering had nothing to work on.

A second downstream condition is untested: ownership context is `paragraph_boundary_unavailable`
for every sealed proposition, because this evaluation library has no chunk-structure rows. The
safety probe showed the same guard rejecting a quote with no ownership context. Fixing the
vocabulary alone might not be enough.

Still rejected by NLI under B2: the abstract's "as much as a two-fold reduction" (support 0.009)
and "between 1.5–2× fewer samples" (0.062).

## 7. Q3 live result

One run, `runs/Q3/attempt-03-b2`.

Complete selected answer (identical to Attempt 2):

```text
1. What evidence supports actively designing perturbation inputs to estimate neural dynamics more efficiently across the optogenetic active-learning and optimal perturbation-input studies?
The available evidence does not establish an answer to this part.
The scoped search completed, but this obligation remains unresolved.
```

**FAIL** as a scientific answer: no two-study synthesis, no attribution, no settings.

The same twenty claims were formed. Verified events rose from 7 to 14; unique sealed
propositions from 6 to 12 (five from paper 82, seven from paper 83), all tagged responsive. Newly sealed
results include:

- paper 82, chunk 4616: "The simulation results show that perturbation-based estimation enables
  the precise control of neural states."
- paper 83, chunk 5215: "Using neural population responses to photostimulation in mouse motor
  cortex, we demonstrate the efficacy of a low-rank linear dynamical systems model, and develop an
  active learning procedure…"

The other newly sealed items are aims, motivation and method statements, faithfully worded.

**Same limiting boundary.** `finding` is `missing / not_found`; none of the twelve quotes contains
a result verb in the fixed vocabulary ("show" and "demonstrate" are present tense; the vocabulary
has "showed" and "demonstrated"). Ownership context is unavailable for all twelve.

Still rejected by NLI: the "up to a two-fold reduction" claim (0.005), a faithful "developed
methods to efficiently select which neurons to stimulate" (0.697), and the conditional form of
the chunk 4400 statement (0.003).

## 8. Scientific citation and qualification review

- **Citations:** both answers have zero Layer C claims, zero relation units and zero citations.
  Claim-to-citation fidelity, attribution between studies and qualification retention in a final
  answer are **unexercised**, as in Attempt 2.
- **Newly admitted pairs:** I read all nine newly admitted records (three in Q1, six unique in
  Q3) against their quotes. Each claim is a close restatement; I found no unsupported, reversed
  or mis-attributed claim, and the Q1 2× claim keeps "not in all cases" and "worst case matches
  baseline". This is my reading, not an independent adjudication. Generation is deterministic, so
  these are the same nine pairs the bakeoff already scored, each labelled supported there. The
  live runs therefore confirm the policy is installed and show its downstream effect; they are
  not new out-of-sample evidence about B2's accuracy.
- **Pre-existing qualification loss:** Q3's chunk 4400 proposition states as fact what the source
  states conditionally ("If the optimal perturbation input can be systematically designed, it
  becomes possible…"). It was admitted in Attempt 2 and is admitted under B2. Not rendered.
- **Source integrity:** all sealed evidence spans in both runs validate against the library copy.
- **Unsupported relationships or extrapolations in the answer:** none; there is no answer content.

## 9. Evidence-admission counts

| | Q1 Attempt 2 | Q1 B2 | Q3 Attempt 2 | Q3 B2 |
|---|---:|---:|---:|---:|
| Claims verified (events) | 9 | 9 | 20 | 20 |
| Status verified | 2 | 5 | 7 | 14 |
| Status weak / unverified | 4 / 3 | 4 / 0 | 12 / 1 | 6 / 0 |
| Unique sealed propositions | 2 | 5 | 6 | 12 |
| Requirement state | missing | missing | missing | missing |
| Layer C claims / citations | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

Claims and scores were the same in both attempts, so the difference is the rule alone. Applying
each rule to the other attempt's recorded scores reproduces the other attempt's counts exactly.

## 10. Model calls, time and cost

| | Q1 Attempt 2 | Q1 B2 | Q3 Attempt 2 | Q3 B2 |
|---|---:|---:|---:|---:|
| Generation calls (Qwen / Phi4 / Gemma) | 27 (25/1/1) | 28 (25/2/1) | 38 (35/2/1) | 38 (35/2/1) |
| Unusable calls | 0 | 0 | 0 | 0 |
| Run seconds | 284.5 | 389.4 | 378.7 | 348.0 |

Q1's extra Phi4 call is a second coverage pass triggered because recovery now adds evidence.
Timings include model loading on a shared machine and are not a like-for-like latency
measurement; B2 itself adds no model pass. Total live time 737 seconds, 66 calls.

Environment: Ollama 0.34.3 on JUNO's isolated service through a task-owned forward to
`127.0.0.1:11435`; `qwen3.5:9b`, `phi4:14b`, `gemma3:12b` with digests equal to Attempt 2;
`all-MiniLM-L6-v2` and `cross-encoder/nli-MiniLM2-L6-H768` at their pinned revisions; NLI
preflight passed in both runs. No model was resident before or after; the forward is closed.

The bakeoff's SSH failure was a client-side cause: the shell used then could not reach the
Windows ssh-agent. The already-configured `juno` host works through the system OpenSSH client.
No credential, key or remote setting was changed.

## 11. Regression and historical integrity

- Focused: 46 passed (`test_reviewed_ask_admission.py`, `test_e2e_support.py`,
  `test_reviewed_fresh.py`, `test_continuation_verifier_receipt.py`).
- Broad offline suite over `experiments`: **5,522 passed, 5 failed, 12 skipped,
  9 xfailed, 276 passing subtests** in 311.9 s. The five failures are exactly the established
  known-five inventory; the 13 additional passes over the previous 5,509 are this increment's
  new tests. Historical replay, D1/D2 identity and recorded-qualification protections run inside
  this suite. The optional, fully mocked `test_run_gate_integration_live.py` was excluded as before.
- Ruff format and check pass on the three changed files.
- Working library SHA-256 `0ba4b18364a532ab132dded173a93442ca75cc58d94f549eae3f9ac2b1809360`
  before and after both runs; equal to the indexed checkpoint.
- 103 preserved files re-hashed unchanged after the runs: Attempt 2's Q1/Q3 run directories, the
  original Q1/Q3 reviewed inputs, the frozen protocol, the indexed checkpoint, Attempt 2's working
  library and every bakeoff file.
- No retry, no altered prompt, threshold, candidate pool or contract. Each question ran once.
- Commit hooks: the only failing hook was the unchanged frontend line-budget check
  (`app/frontend/js/20_synthesis.jsx`, 615 lines, not touched here), skipped under the standing
  narrow exception. All other hooks ran and passed.

## 12. Remaining defects and uncertainties

1. **Scientific mapping cannot see these results.** A fixed past-tense result-verb vocabulary
   finds no achieved outcome in two papers that report findings in the present tense. This now
   blocks Q1 and Q3 regardless of how much evidence is admitted.
2. **Ownership context is unavailable on this library** (no chunk-structure rows), a second
   condition that may block the same evidence after the first is addressed.
3. **NLI still rejects the cleanest statements of the expected finding** (support 0.005–0.06 on
   the two-fold and 1.5–2× claims). B2 does not address this.
4. **A causally worded question can be answered with an associational quote**, under either
   policy. No contract relation type distinguishes them.
5. **Evidence-bearing answers remain untested end to end.** No live run has yet produced a Layer C
   claim, a relation witness or a citation.
6. **Limits of this pilot:** two questions, one run each, two papers. The safety probe is
   synthetic and scripted the coverage model. Bakeoff labels are one blinded ChatGPT pass. My
   reading of the newly admitted pairs is not independent.

## 13. Recommended next bounded action

A read-only audit of the achieved-outcome boundary on the seventeen quotes sealed in these two
runs: for each, which condition excludes it (result-verb vocabulary, ownership context, or
both), and which would remain excluded if each condition were met. That says whether one bounded
change could yield a first evidence-bearing answer, before any change to v8 semantics is
proposed. It needs no live run.

B2 should stay where it is: an opt-in configuration for the reviewed experimental route.

## Artifacts

Gitignored, in `.local/phase34-b2-live-pilot-20261012/`: both run directories with full traces,
console logs, the driver and its diff against the Attempt 2 driver, per-question comparison and
inspection files, the causal-control probe and its output, the mapping-boundary probe, the
before/after preservation hashes and the regression log.
