# Phase 34 — Recovery reuse and measured latency

**Disposition: OFFLINE QUALIFICATION PASSED. Not yet exercised in a live run.** With reuse enabled, an
offline replay of the preserved q_aib recovery round makes 263 worker calls instead of 420 and verifies the
same 35 distinct claims on the same 37 passages, with every recovery target keeping its own row and its
original outcome. No full E2E run was started. Reuse and timing are both opt-in; defaults are unchanged.

One correction to the earlier forensics report: I estimated that DeBERTa added 250–320 s to the run. Measured
directly, DeBERTa inference in the recovery round is **72 s**. That estimate was wrong, and the local
bottleneck is quote location, not the NLI model.

## 1. What was changed

All in the experimental Ask route. Nothing runs unless `--recovery-reuse` or `--timing` is passed.

| Piece | File | What it does |
|---|---|---|
| A. Shared search | `__main__.py` (`_recover`), `recovery_reuse.py` | A `DEEPEN` target whose search is identical to one already run in this round does not search again. |
| B. Identical worker call | `qwen.py` (`_call`), `recovery_reuse.py` | A worker call whose full inputs equal an earlier call's in this round returns the earlier result. |
| B. Identical verification | `recovery_reuse.ReusingVerifier` | A (claim, cited chunk, quote) item already verified in this round returns that result. |
| Timing | `timing.py`, spans in `__main__.py`, `qwen.py`, `nli_verifier.py` | Wall-clock spans, written to `20_timing.json` and the manifest. |
| Wiring | `e2e.py` | `--recovery-reuse`, `--timing`; reuse is attached for the recovery round only and detached afterwards. |

**Identity rules (exact, question-agnostic, no similarity threshold):**

- **Search:** child id, action, query string, candidate paper ids, the subquestion text, the
  requested-information list sent with each packet, and the retrieval caps. Only `DEEPEN` is ever shared;
  `NOMINATE` and `LEGACY` depend on nomination state and always run.
- **Worker call:** the full prompt, the output schema, the output cap, and the worker's model, thinking
  setting and options. The prompt already contains the child's question and its requested-information
  list, so the same passage examined for another obligation is a different call by construction.
- **Verification:** claim text, cited chunk id, chunk version, a hash of the chunk text, and the quote.
- A failed call or a mechanical no-answer is never stored, so it is attempted again exactly as before.
  An item whose chunk is not in the pool handed to the verifier is never reused.

**Query versus requirement.** A target that shares a search still gets its own log row with its own gap
and `_recovery_target_id`, the query, the hit count of the shared search, `new_verified: 0`,
`reason_code: recovery_no_new_evidence` and a new field `search_shared_with_target` naming the target whose
search it shares. The downstream requirement-completion logic reads one row per target and needs nothing
else. A reused worker call still writes its own trace row, marked `reused_identical_call`.

**Two housekeeping edits, behavior-neutral,** needed for `__main__.py` to pass the commit hooks it
already failed before this change: import order, and binding the loop variable in two lambdas
(`lambda hit, query=query:`), which are called immediately inside the loop iteration that defines them.

## 2. Offline qualification method

`.local/phase34-deberta-e2e-20261012/r1_recovery_replay.py` runs the real recovery code path
(`e2e._recover_round` → `_recover` → `_process_hits` → `marshal_and_verify`), real retrieval and context
building on the preserved library copy, and the real DeBERTa verifier. The one stand-in is the worker
model: each prompt is answered with the output the live run recorded for that exact prompt, in recorded
order. The network is refused throughout and the library copy is verified unchanged afterwards.

**The replay reproduces the live run exactly with reuse off:** 420 calls, 240 claims with the same text in
the same order, the same verification statuses, a largest support-score difference of 0.0, and log rows
equal to the live `13_gap_recovery.json`. So the comparison below is against the run as it happened.

## 3. Before and after (recovery round, offline replay)

| | Reuse off | Reuse on | Change |
|---|---|---|---|
| Recovery targets | 24 | 24 | — |
| Targets that searched | 24 | 18 | −6 |
| Retrieval hits / packets | 183 | 138 | −45 |
| Worker calls made | 420 | 263 | −157 (−37%) |
| … recovery query | 24 | 19 | −5 |
| … select evidence | 149 | 90 | −59 |
| … form claim | 247 | 154 | −93 |
| Trace rows written | 420 | 336 (73 marked reused) | |
| Verification items computed | 240 | 132 | −108 |
| NLI calls / pairs | 82 / 240 | 50 / 132 | |
| Claim records formed | 240 | 190 | −50 |
| Records verified | 57 | 47 | −10 (all duplicates) |
| **Distinct verified claims** | **35** | **35** | **identical set** |
| **Distinct verified (child, paper, passage)** | **37** | **37** | **identical set** |
| New verified evidence credited in the log | 33 | 33 | identical per target |
| Log rows (reason code, new verified, hits, query) | | | identical for all 24 |

The 157 calls removed are the 157 the trace showed as exact-prompt repeats. Of them, 84 were inside the six
shared searches and 73 were identical calls inside searches that still ran.

**Costs:**

| | Reuse off | Reuse on | Saving | Kind of number |
|---|---|---|---|---|
| Worker inference for the calls made | 628.1 s | 428.4 s | 199.7 s | recorded live per call, summed over the calls each mode makes |
| Local work in the round | 336.4 s | 164.3 s | 172.1 s | measured in the replay on this laptop |
| … source verification total | 228.1 s | 95.6 s | 132.5 s | measured |
| … retrieval | 43.7 s | 28.9 s | 14.8 s | measured |
| … candidate spans + context build | 29.0 s | 18.3 s | 10.7 s | measured |

A projection, not a measurement: the live recovery round took 1,010 s; removing 200 s of inference and about
170 s of local work would put it near 640 s, and the run near 28 minutes instead of 34. The live round's
local time was 382 s against the replay's 336 s, so the laptop was somewhat slower on the day.

## 4. What was retained, and why

- **31 select-evidence calls saw excerpts identical to an earlier call's and were kept.** In every case the
  question and the requested-information list differed, because another child was examining the same
  passage. They are different scientific evaluations and reuse does not touch them.
- **All 24 targets keep a row.** The six that share a search serve these requirements: for c11, "a named
  culture or population" and "how the bias was measured/operationalized there"; for c12, "a named
  intervention", "which aspect of the bias the intervention targets" and "a definitive, non-speculative
  reported outcome"; for c8, "evidence relating the trait/construct to the bias's manifestation".
- **The c8 case is the one where two different requirements share a query.** "A named individual-difference
  trait" and "evidence relating the trait to the bias" produced the same retrieval phrase. They are shared
  because everything sent downstream was identical — same child, same query, same candidate papers, same
  requested-information list. The requirement's wording reaches the pipeline only through the query, so
  once the queries are equal no input distinguishes the two searches. Both requirements keep their own row.
- **The five other shared targets differ from their partner in nothing but the target id**: a second target
  for the same child with the same requirement wording, from a second requirement that asks for the same
  kind of thing.
- **Duplicate claim records are no longer re-created for a shared search.** In the original run those 50
  records existed, 10 of them verified and all 10 marked `duplicate_of_existing_evidence`. They carried no
  attribution the first copies lack: evidence is attributed to a child, not to a recovery target.

## 5. Risk: reuse removes incidental variation

At temperature 0 with a fixed seed the worker is still not perfectly repeatable on the GPU. Of the 157
repeated prompts in the live run, 148 returned byte-identical output and 9 claim formations returned a
differently worded claim for the same passage. Reuse returns the first answer.

In this run the effect on evidence was nil: the verified sets are identical. Two unverified passages that
the original run formed claims on (one for c6, one for c8) are not formed with reuse. In another run a
second, differently worded claim could verify where the first did not, and reuse would not see it. That
would be evidence obtained by resampling, not by any designed step, and it is the only way reuse can change
what is admitted.

## 6. Measured local time (recovery round, reuse off)

First direct measurement of these steps. 240 claims, DeBERTa on the laptop CPU.

| Step | Calls | Seconds | Share of local |
|---|---|---|---|
| Quote match and location in the PDF | 240 | 103.1 | 31% |
| DeBERTa NLI (tokenization + inference) | 82 | 72.2 | 21% |
| Retrieval for the 24 queries (query embedding + vector search + DB) | 24 | 43.7 | 13% |
| Similarity search for the claim | 240 | 38.2 | 11% |
| Claim-processing outside verification (anchor checks, record building) | 183 | 35.6 | 11% |
| Candidate spans | 183 | 16.8 | 5% |
| Context build | 183 | 12.2 | 4% |
| Chunk-embedding lookup (DB) | 82 | 9.6 | 3% |
| Claim embedding and verifier overhead (verification total minus its timed steps) | 82 | 5.0 | 1% |
| **Local total** | | **336.4** | |

Generative inference and model loading were already recorded per call: 628 s of worker calls in the round,
45 s of it reloading Qwen. Tokenization is not timed separately inside the pipeline; the benchmark below
measures it at 0.08 s for all 296 pairs, so the NLI figure is inference.

The largest local cost is locating each verified quote in its PDF, at 0.43 s per claim. It is unchanged
application code and I did not touch it.

## 7. Option C: where and how DeBERTa runs

296 preserved claim–quote pairs from the run, laptop CPU, four threads, FP32, best of two passes. The
reference shape reproduces the live run's recorded scores exactly (difference 0.0).

| Execution shape | Seconds | ms per pair | Largest score difference | Decision changes |
|---|---|---|---|---|
| Today: one call per packet (119 calls) | 78.5 | 265 | reference | — |
| One call, original order, batch 1 | 105.2 | 355 | 1.2e-06 | 0 |
| One call, original order, batch 4 | 71.6 | 242 | 2.4e-06 | 0 |
| One call, original order, batch 8 | 73.0 | 247 | 2.4e-06 | 0 |
| One call, original order, batch 16 | 76.2 | 258 | 2.3e-06 | 0 |
| One call, original order, batch 32 | 81.4 | 275 | 2.4e-06 | 0 |
| One call, sorted by length, batch 4 | 55.7 | 188 | 9.5e-07 | 0 |
| One call, sorted by length, batch 8 | 49.2 | 166 | 9.5e-07 | 0 |
| One call, sorted by length, batch 16 | 46.9 | 159 | 9.5e-07 | 0 |
| One call, sorted by length, batch 32 | 50.1 | 169 | 6.6e-07 | 0 |

- **Ordinary batching does not help.** In original order the best case is 9% faster and batch 32 is slower
  than today, the padding cost seen earlier with MiniLM.
- **Length-aware batching is 40% faster** (about 32 s over a whole run) with scores equal to 1e-06.
- **It is not worth doing on the laptop.** It needs every claim of a pass in hand at once, but the pipeline
  verifies packet by packet because later steps in the same loop read each claim's status. Deferring
  verification to the end of a pass is a restructuring, for about half a minute of a 34-minute run. With
  reuse on, NLI in the recovery round is already down to 31 s.
- **GPU execution would need a new boundary.** The pipeline process runs on the laptop and the GPU is on
  JUNO, so the verifier would have to become a service or the pipeline would have to move. At the measured
  7 ms per pair that would save roughly 75 s per run. Not recommended on latency grounds alone.

## 8. Tests

- `test_recovery_reuse.py`, 21 tests: an identical call is reused and marked; any change to prompt, cap,
  schema, model, thinking or options is a different call; a failed call is retried; a reused call writes its
  own trace row; verification reuse keeps order and refuses a changed claim, quote, chunk or chunk text; two
  requirements with one search run it once and keep two rows; another child, another query, another
  retrieval configuration or a non-`DEEPEN` action is never shared; with reuse off nothing changes; spans
  record nothing unless collecting; the timed verifier is the same verifier; through `run_topology`, a default
  run gets no reuse object, no timing file and no new manifest key, and the flags reach the recovery round.
- Ask suite, offline, `contract_directed` excluded, one network-dependent test deselected: 4,775 passed, 2 failed.
  The two failures are the hierarchy pin-drift tests that fail on the unmodified baseline.

## 9. Remaining bottlenecks and risks

1. **Model switching: 303 s per run.** Untouched (D and F deferred).
2. **Targets that find nothing: 197 s.** Untouched (E deferred).
3. **Quote location: 103 s in recovery before reuse, 41 s after.** The next local target; it is application
   code shared with the product, so it needs its own review.
4. **Reuse has not run live.** The replay holds the worker's answers fixed. A live run will differ in the
   nine-in-157 way described in section 5.
5. **One question.** The duplication rate comes from q_aib's hierarchy, where several requirements of one
   child ask for the same kind of thing. Other questions may repeat more or less.
6. **Timing spans nest.** Totals for an outer span include its inner spans; the table in section 6 does the
   subtraction explicitly.

Deferred as instructed: stage reordering (D), early exit for unproductive targets (E), and replacing the
coverage and planning models (F). No synthesis prompt, verification threshold, sufficiency rule or frozen
contract was changed.

## 10. Artifacts

`.local/phase34-deberta-e2e-20261012/`: `r1_recovery_replay.py` with `r1_replay_baseline.json` and
`r1_replay_reuse.json`; `c1_nli_batching_benchmark.py` and its JSON; suite log `suite_after5.log`.
