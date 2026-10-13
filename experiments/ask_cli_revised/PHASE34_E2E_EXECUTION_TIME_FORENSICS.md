# Phase 34 — Execution-time forensics of the fresh q_aib run

Read-only analysis of the completed run `phase34-deberta-fresh-e2e-attempt2-20261012` (2,065 s). Nothing was
rerun, tuned or changed. No optimization is implemented here.

**Headline.** Recovery took half the run (1,010 of 2,018 stage seconds). It did contribute science that
reached the answer: the whole interventions section and parts of three others. But 42% of its time
went to targets that added nothing, and 22% went to six targets that reissued a query already run for the
same subquestion. Model switching cost another 300 s. The DeBERTa verifier on the laptop CPU added roughly
250 s that the earlier MiniLM run did not pay.

## 1. How the numbers were obtained

- **Measured:** each stage's wall time (`stage_log.json`); each model call's end timestamp, wall time,
  model-load time and token counts (`qwen_calls.jsonl`, 684 calls, all assigned to a stage); model
  unload events (`15_run_manifest.json`).
- **Derived from measurements:** "local time" = stage wall time minus the sum of its call wall times.
  Gaps between consecutive calls are computed from the timestamps.
- **Estimated:** how local time divides among retrieval, embedding, quote location and NLI. The trace does
  not time those separately. Estimates are marked.

## 2. Timeline

| Stage | Model | Wall s | Calls | Call time s | of which model load s | Local s | Share of run |
|---|---|---|---|---|---|---|---|
| W1 initial pass | qwen3.5:9b | 373.8 | 213 | 236.8 | 42.4 | 137.0 | 18.5% |
| C1 coverage audit | phi4:14b | 118.8 | 1 | 118.8 | 23.3 | 0.0 | 5.9% |
| U1 sufficiency mapping | qwen3.5:9b | 67.9 | 19 | 67.5 | 41.2 | 0.4 | 3.4% |
| P1 recovery plan | gemma3:12b | 90.2 | 1 | 90.2 | 52.7 | 0.0 | 4.5% |
| **W2 recovery** | qwen3.5:9b | **1,010.0** | 420 | 628.1 | 45.1 | 382.0 | **50.1%** |
| C2 coverage audit | phi4:14b | 158.2 | 1 | 158.2 | 55.9 | 0.0 | 7.8% |
| U2 remap | qwen3.5:9b | 77.9 | 16 | 77.2 | 42.6 | 0.7 | 3.9% |
| S1 × 11 child syntheses | qwen3.5:9b | 67.9 | 11 | 58.5 | 0.0 | 9.4 | 3.4% |
| S2 parent claim realization | qwen3.5:9b | 37.5 | 1 | 37.5 | 0.0 | 0.0 | 1.9% |
| S3 narrative overview | qwen3.5:9b | 15.6 | 1 | 13.6 | 0.0 | 1.9 | 0.8% |
| **Stages total** | | **2,017.8** | 684 | 1,486.5 | 303.2 | 531.5 | |
| Setup, library hashing, final rendering, mechanical checks | — | 29.5 | 0 | | | 29.5 | |
| Working-copy creation and verification (driver) | — | 17.5 | 0 | | | 17.5 | |

Child syntheses individually: c1 6.5, c2 6.3, c3 8.7, c4 4.7, c5 7.8, c6 8.1, c8 7.8, c9 3.7, c10 3.0,
c11 2.7, c12 8.6 s. Final rendering of the hierarchical document is not timed separately; it falls inside
S3's 1.9 s of local time and is deterministic string assembly.

**Where the time goes, whole run:**

| Category | Seconds | Share |
|---|---|---|
| Model inference excluding loads | 1,183 | 59% |
| Local pipeline work (retrieval, embedding, quote location, NLI, I/O) | 532 | 26% |
| Model loads (7 loads, 23–56 s each) | 303 | 15% |
| Model unloads | 1.6 | 0.1% |

Nothing is unexplained at the stage level: every stage's wall time is the sum of its calls and its local
time. What is not resolved is the split inside local time.

**Per call type:**

| Call | n | Total s | Mean s | Mean prompt tokens | Mean generated tokens |
|---|---|---|---|---|---|
| W1 context gate | 110 | 111.6 | 1.01 | 452 | 6 |
| W1 select evidence | 47 | 42.0 | 0.89 | 504 | 9 |
| W1 form claim | 56 | 83.2 | 1.48 | 519 | 32 |
| W2 recovery query | 24 | 63.0 | 2.62 | 220 | 15 |
| W2 select evidence | 149 | 161.9 | 1.09 | 891 | 11 |
| W2 form claim | 247 | 403.2 | 1.63 | 1,091 | 33 |
| Coverage audit (phi4) | 2 | 277.0 | 138.5 | 4,036 | 445 |
| Recovery plan (gemma) | 1 | 90.2 | 90.2 | 3,923 | 228 |
| Sufficiency nomination | 35 | 144.7 | 4.13 | 514 | 39 |

phi4 generates at about 4.5 tokens per second because 18 of its 41 layers run on the CPU; qwen, fully on
the GPU, generates at 20–33.

## 3. W2 in detail

1,010 s = 583 s of Qwen inference + 45 s reloading Qwen after gemma + 382 s of local work.

**Why hundreds of calls.** The plan produced 24 recovery targets (one per unmet requirement, not one per
subquestion). Each target writes a query (24 calls), retrieves up to eight passages from the same
25-paper pool, selects evidence in each packet (149 calls), and forms one claim per selected span
(247 calls). No new paper was nominated by any target (`new_hits: 0` throughout): recovery re-searched the
papers the first pass had already found.

**Repetition, measured:**

| | Count |
|---|---|
| Recovery retrieval hits | 183, on only 65 distinct chunks from 16 papers |
| Hits on a chunk the initial pass had already processed | 60 |
| Hits repeating a chunk hit earlier in recovery | 118 (one chunk 17 times) |
| Packets with the same chunk set as an earlier packet | 119 of 183 |
| … for the same subquestion | 82 of 183 |
| Claims formed on a quote already used by an earlier claim | 125 of 240 |
| … for the same subquestion | 96 of 240 |
| Targets whose query string repeats an earlier target's for the same subquestion | 6 of 24 |

**Per target** (seconds from call timestamps; "new verified" from the recovery log):

| # | Child | Seconds | Claims formed | New verified | Query |
|---|---|---|---|---|---|
| 1 | c9 | 65.5 | 5 | 1 | which scales measure the specific personality traits… |
| 2 | c1 | 35.6 | 8 | 1 | specific named brain area anomalous is bad bias |
| 3 | c10 | 24.0 | 5 | 1 | cross-cultural evidence … specific culture |
| 4 | c10 | 19.0 | 5 | 0 | cross-cultural evidence … generalizability |
| 5 | c11 | 22.0 | 5 | 0 | in which cultures is there evidence… |
| 6 | c11 | 19.3 | 5 | 0 | how was the … bias measured in each culture |
| 7 | c11 | 18.1 | 5 | 0 | *repeat of 5* |
| 8 | c11 | 17.8 | 5 | 0 | *repeat of 6* |
| 9 | c12 | 38.8 | 10 | 4 | effective interventions aimed at reducing… |
| 10 | c12 | 46.6 | 11 | 0 | effective interventions targeting … aspects |
| 11 | c12 | 42.8 | 11 | 0 | effective interventions reducing… |
| 12 | c12 | 40.8 | 10 | 0 | *repeat of 9* |
| 13 | c12 | 58.0 | 11 | 0 | *repeat of 10* |
| 14 | c12 | 59.6 | 11 | 0 | *repeat of 11* |
| 15 | c2 | 61.4 | 14 | 1 | observed behavior behavioral choice action task measure |
| 16 | c2 | 29.1 | 8 | 5 | how does the … bias manifest in behavior |
| 17 | c3 | 54.0 | 16 | 5 | how does … manifest in attitudes implicit explicit |
| 18 | c4 | 40.8 | 9 | 1 | specific named brain areas where … manifests |
| 19 | c8 | 34.5 | 8 | 2 | specific personality traits relate to … manifestation |
| 20 | c8 | 25.4 | 8 | 0 | *repeat of 19* |
| 21 | c5 | 92.8 | 28 | 6 | specific named brain areas relate to behaviors |
| 22 | c6 | 55.6 | 16 | 3 | specific brain areas attitudes kinds of attitudes |
| 23 | c6 | 57.4 | 17 | 3 | attitude category implicit explicit evidence |
| 24 | c6 | 47.4 | 16 | 0 | whether implicit or explicit attitude categories were found |

| Target outcome | Targets | Seconds | Claims formed | New verified |
|---|---|---|---|---|
| Added verified evidence | 12 | 589 | 144 | 33 |
| New query, nothing new | 6 | 197 | 53 | 0 |
| Repeated query, nothing new | 6 | 220 | 50 | 0 |

## 4. What recovery bought scientifically

The run sealed 64 verified, responsive claims: 31 from the initial pass and 33 from recovery. Of the 34
child assignments of recovery claims, 28 rest on passages the initial pass had not sealed.

| Child | Initial sealed | Recovery sealed | Recovery on new passages | Recovery claims cited in the displayed child synthesis | Recovery passages in the parent overview |
|---|---|---|---|---|---|
| c1 brain | 3 | 1 | 1 | 0 (nothing displayed) | 0 |
| c2 behavior | 5 | 5 | 4 | 2 | 0 |
| c3 attitudes | 5 | 6 | 3 | 3 | 1 |
| c4 brain areas | 2 | 1 | 1 | 0 (nothing displayed) | 0 |
| c5 brain ↔ behavior | 6 | 6 | 6 | 0 | 0 |
| c6 brain ↔ attitudes | 3 | 6 | 6 | 0 | 0 |
| c8 traits | 2 | 2 | 1 | 1 | 0 |
| c9 scales | 0 | 1 | 0 | 0 (nothing displayed) | 0 |
| c10 cross-cultural | 1 | 1 | 1 | 0 | 0 |
| c11 which cultures | 2 | 1 | 1 | 0 | 0 |
| c12 interventions | 2 | 4 | 4 | 3 | 3 |
| **All** | **31** | **34** | **28** | **9** | **4** |

For comparison, 12 initial-pass claims are cited in displayed child statements.

**Reading.** Recovery is not waste: without it the answer has no interventions section (all three of
c12's sentences, and two of the parent overview's four, cite recovery evidence), and c2 and c3 would be
thinner. But the yield is concentrated. Twelve new passages for c5 and c6 cost 253 s and none reached a
displayed statement, because those children's syntheses did not answer their question. Recovery for c1 and
c4 found the amygdala evidence again and the synthesis screens then withheld it. Recovery for c10 and c11
(120 s, 6 targets) added one claim and did not find the Hadza result in a usable form. One caveat on the
intervention content: the c2 sentence that presents a prediction as a finding also cites recovery evidence,
so recovery contributed one of the answer's errors as well as its best section.

So 28 new passages cost 1,010 s, about 36 s each; 9 claims that reached the answer cost about 112 s each.

## 5. Inference versus everything else

- **Model switching.** Seven loads, 303 s, 15% of the run. The sequence is qwen → phi4 → qwen → gemma →
  qwen → phi4 → qwen: every non-Qwen stage costs its own load plus a Qwen reload of about 42 s afterwards.
  The three non-Qwen stages (C1, P1, C2) take 367 s for three calls, 132 s of it loading, and they are the
  stages that push the CPU to its thermal limit.
- **Local work.** 532 s. In W1 and W2 it sits almost entirely in the gap after a claim is formed and
  before the next packet: 83 s after W1's 56 claims (1.5 s each) and 274 s after W2's 247 (1.1 s each).
  That gap contains claim embedding, the similarity search, quote location in the PDF and the NLI call.
  A further 59 s follows the 24 recovery queries (retrieval and query embedding, 2.5 s each).
- **Estimate of the DeBERTa share.** The first pass was token-for-token identical to Phase 28's (213 calls,
  102,545 prompt tokens, 2,876 generated), so it is a like-for-like comparison: local time was 72.5 s with
  MiniLM and 137.0 s here, 1.15 s more per claim. Applied to W2's 247 claims that is about 280 s; W2's
  local time actually rose by 254 s. I estimate DeBERTa on the laptop CPU added roughly 250–320 s to the
  run. This is an inference from two runs on a laptop whose load I did not control, not a measurement.

## 6. Comparison with Phase 28

| | Phase 28 (2026-10-04) | This run | Nature of the difference |
|---|---|---|---|
| Stage total | 1,641.6 s | 2,017.8 s | |
| W1 calls / tokens | 213 / 102,545 | 213 / 102,545 | identical |
| W1 local time | 72.5 s | 137.0 s | configuration: DeBERTa on CPU (estimated cause) |
| Recovery targets | 21 | 24 | execution: a different sufficiency map |
| W2 calls | 364 | 420 | execution |
| W2 inference | 542.8 s | 628.1 s | execution, proportional to calls |
| W2 local time | 128.2 s | 382.0 s | mostly configuration (verifier), partly more claims |
| Model loads | 349 s | 303 s | execution (phi4's first load was 65 s then, 23 s now) |
| C1 + C2 + P1 | 394 s | 367 s | execution |
| S2 | 61.0 s | 37.5 s | execution: 2,009 vs 1,233 generated tokens |
| S3 | — | 15.6 s | configuration: new stage |
| Repeated-query targets | 4 of 21, 84 s | 6 of 24, 220 s | same behaviour in both |
| Same-child duplicate packets | 64 of 160 | 82 of 183 | same behaviour in both |

The repetition is not new. It was present in Phase 28 at the same rate; this run made it more expensive
because each redundant claim now also pays the slower verifier.

## 7. Ranked diagnosis

1. **Recovery re-reads the same passages for the same subquestion.** 82 of 183 packets and 96 of 240
   claims repeat work already done for that child. Roughly 40% of W2.
2. **Duplicate targets.** Six targets reissued an earlier query for the same child: 220 s, zero evidence.
3. **Model switching.** 303 s of loads, and three calls on CPU-split models at a fifth of Qwen's speed.
4. **Verifier on the laptop CPU.** An estimated 250–320 s; on JUNO's GPU the measured cost is 7 ms per pair.
5. **Targets that find nothing are run to the end.** Six new-query targets, 197 s, nothing verified.
6. Everything after U2 (thirteen synthesis calls) is 121 s, 6% of the run. Synthesis is not the problem.

## 8. Candidate simplifications for review (none implemented)

Savings are estimates from this run's own numbers. "Risk" is to evidence quality.

| # | Change | Estimated saving | Risk | Notes |
|---|---|---|---|---|
| A | Skip a recovery target whose query for the same subquestion has already run in this round | ~220 s (22% of W2) | none observed | The repeats returned the same passages and verified nothing in either run. Question-agnostic. |
| B | Within a subquestion, do not re-select or re-form claims on a packet already processed for that subquestion | ~150–250 s | low | 82 packets and 96 claims. The second pass over the same packet could in principle select a different span for a different requirement, so this needs a check that requirement-specific prompts are not lost. |
| C | Run the verifier on a GPU, or batch one pass's claims into a single NLI call | ~250–300 s | none | No change to scores (parity was measured at 8e-06). Needs the pipeline process, or a verifier service, where a GPU is. |
| D | Order stages so Qwen is loaded once per contiguous block | ~85–130 s | none if dependencies allow | For example, if U1 does not need C1's output it can run before C1. I have not checked the dependency. |
| E | Stop a target after its first packets verify nothing new | up to ~200 s | moderate | This is the one that can cost evidence: target 15 found its only claim late. Needs data from more questions. |
| F | Bind the coverage and planning roles to a model that fits the GPU | ~260 s and removes the thermal problem | changes the pipeline's models | Not small and not question-agnostic in effect; listed because it is the largest single lever. Out of scope without a model decision. |

A, B and C together would take this run from about 34 minutes to roughly 22–24, with no change to which
evidence is admitted. A is the only one I would call free.

## 9. Limits of this analysis

- One run of one question. The Phase 28 comparison is one more run of the same question.
- Local time is not broken down by the trace; the verifier estimate is an inference.
- The laptop's own load during the run was not recorded.
- "Reached the answer" means cited by a displayed statement. It does not mean the statement was correct
  or responsive; see `PHASE34_DEBERTA_FRESH_E2E_RESULTS.md` sections 7–9.

Scripts and their outputs are in `.local/phase34-deberta-e2e-20261012/` (`t1_timing_forensics.py`,
`t2_recovery_targets.py`, and the `t1_*`/`t2_*` logs).
