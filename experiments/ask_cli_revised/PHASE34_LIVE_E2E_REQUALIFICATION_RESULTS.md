# Phase 34 — Live E2E requalification, Attempt 2

**Disposition: LIVE E2E NOT QUALIFIED.** All six original questions were attempted
once under the newly indexed evaluation condition. Q1, Q3 and Q6 completed with
scientifically inadequate empty answers: **FAIL**. Q2, Q4 and Q5 stopped at a
deterministic authored-contract/runtime incompatibility: **BLOCKED** for scientific
assessment. None passed. No production code, contract or evaluation criterion changed.

The F1/F2 repairs work within their demonstrated scope. Relevant papers now enter
ordinary discovery. Structured recovery retains the scientific target while resolving
its actual retrieval owner, and records completed searches and their evidence gains.
The next failures are observable further downstream: useful results lost at verification,
accepted input combinations rejected during mapping, and targeted source passages missed
by retrieval/context selection. Safe abstention does not qualify an answerable question.

This is qualification of the **reviewed-authored scientific pipeline**, not the product
UI, `/summarize`, unattended contract authoring, or a complete release. No fabricated
relationship, citation laundering, null-to-positive conversion or false clinical answer
was emitted. Since every completed final answer is empty of scientific claims, this
does not establish those safeguards on useful evidence-bearing final answers.

## Checkpoint, authority and preservation

Canonical worktree:
`C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum\.claude\worktrees\ask-060-hier11-recpm3-citefix-20260929T212442Z`.

Branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
Starting HEAD: `8645a818d18e8bdbb2ef1ed7bc2d7eb306443fcd`, clean at entry.
The starting-HEAD [remote workflow](https://github.com/cliffworkman/callosum/actions/runs/38178278695)
completed successfully. CI is separate from the failed live scientific gate.
Prior offline regression counts are not relabeled as live qualification or rerun for
this documentation-only increment.

Read the first qualification, blocker remediation, accepted E2/I2-3 reports, existing
live driver/runtime, relevant verification/mapping code, contribution lineage and
`.claude/CREDIT-THE-LINEAGE.md`. The user supplied the experimental framing and
authorization. Codex reused its previously authored experimental review, executed the
tests and assessed the sources. **No independent human scientific approval is claimed.**

The original `.local/phase34-live-e2e-20261011/` remains immutable, including its failed
Q1, protocol, source exports, all six questions and all five reviewed files per question.
The new driver reads those **same original input files**, never the expected-answer
protocol. All 89 original files and all 30 reviewed input bodies match their hashes
after the battery. No question, source, criterion, citation expectation or contract was
rewritten after observing results.

New output root: `.local/phase34-live-e2e-attempt2-20261011/`.
Each actual run is `runs/Q1/attempt-02` through `runs/Q6/attempt-02`. No retry or
replacement scientific attempt occurred. The driver differs from the original only
in output/working-library location, original-input path, attempt label and a strict
installed-model-digest equality check. `driver_delta.patch` preserves that comparison.

## Library and installed runtime

The read-only indexed checkpoint remains at
`.local/phase34-live-e2e-remediation-20261011/library.indexed.sqlite`.
Its SHA-256, and the new separate working copy's SHA-256, are:

`0ba4b18364a532ab132dded173a93442ca75cc58d94f549eae3f9ac2b1809360`.

Both contain 86 papers / 69 active / 17 deleted, 17 attachments, 6,610 chunks,
6,863 embeddings, 210 axis memberships and zero chunk-structure rows; size 74,424,320
bytes, zero WAL bytes at fingerprinting. All 69 active papers have current paper
embeddings; all 6,610 chunks have current embeddings and correctly sized vector payloads.
Foreign-key checks are empty, SQLite integrity is `ok`, and every chunk's paper agrees
with its attachment's paper. Papers 82/83 retain their correct titles and source identities.

The original library still has SHA-256
`6598c4798cc35a8364da48b9a0215c3777a9e25c31add09aaaa512a111e8c529`.
The working copy exactly matches the new checkpoint before and after **every** run.
**No operational database mutation or additional indexing occurred.** The existing
verifier's idempotent embedding lookup found already indexed material. No ranking,
threshold, limit, source or candidate-list modification was made.

A disposable readiness diagnostic initially queried the vector table before loading
SQLite's vector extension and failed with `no such module: vec0`. Loading the installed
extension for read-only checks resolved this diagnostic error. The working fingerprint
was reverified before Q1; this was not a scientific attempt or a product change.
`readiness.json`, `preflight_diagnostic_error.json` and `final_integrity.json` preserve
these facts. The initial remote service inventory also distinguished JUNO's older
shared port 11434 from the original **isolated port 11435** actually used throughout.

Public entry: `reviewed_ask.run_reviewed_request`, with real discovery, retrieval,
context selection, verification, sealing, current v8 U1/U2, recovery, Layer C v2,
parent-synthesis-v2, plan-v5 and I2-3 rendering wherever the run reached those stages.
No scientific worker was mocked or supplied selected evidence. Failed Q2/Q4/Q5 do not
claim execution of the downstream stages their exceptions prevented.

| Binding | Actual installed model / digest |
|---|---|
| W, thinking off | `qwen3.5:9b` / `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` |
| C | `phi4:14b` / `ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba` |
| P | `gemma3:12b` / `f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a` |
| Local embedding | `all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` |
| Local NLI | `cross-encoder/nli-MiniLM2-L6-H768`, revision `b95119ce93d3e065de6214e38cd4a97b0f2f2c6d` |

Original T5 profile (`T5*` resolved name), Ollama **0.34.3**, isolated JUNO service
through the task-owned `127.0.0.1:11435` SSH forward. R and legacy S remain off;
fresh Layer C is deterministic. Base options remain context 12,288, prediction cap
4,096, temperature 0, seed 42, six threads, batch 512, keep-alive 30 minutes and
1,200-second per-call watchdog. Existing task-specific caps are unchanged and recorded
per call. Cached local models use the original offline Hugging Face flags.

All six runs passed actual NLI preflight and exact installed generation-model digest
checks. Across the battery: **122 usable generation calls**, comprising **115 Qwen,
4 Phi4 and 3 Gemma**; zero unusable calls or generation timeouts. Q1/Q3 retain **29 actual
claim-verification records**, all with NLI contradiction probabilities, not embedding
fallback. Q2's coverage prompt contains one verified proposition, but its exception
prevented serialization of detailed verification scores. Q4/Q5/Q6 formed no claims;
their NLI preflight is not substantive claim verification. Summed run duration is
**1,156.422 seconds**, including per-run preflight/loading/cleanup, excluding inspection.

## Frozen protocol and actual outcomes

The original `predeclared_protocol.json` is authoritative. Source IDs below are
assessment references only; they were not supplied to retrieval or the models.

| Case | Frozen expected finding / principal sources | Actual outcome | Seconds | Calls |
|---|---|---|---:|---:|
| Q1 ordinary finding | Variable data-efficiency gains, sometimes up to twofold fewer samples; offline mouse data/simulation scope. 5215, 5223, 5440, 5504, 5591, 5593. | **FAIL**: empty answer after relevant results were retrieved and rejected at verification. | 284.531 | 27 |
| Q2 relationship | Excitation/state covariance linked to lower estimation error with model assumptions and simulation scope. 4424, 4438, 4461. | **BLOCKED**: category-role/quantifier incompatibility during U1 mapping. | 149.047 | 11 |
| Q3 multiple sources | Separate attribution and settings for both studies; no patient-benefit inference. 4392, 4438, 4461, 5215, 5440, 5504, 5593. | **FAIL**: six verified propositions, no supported result role or final synthesis. | 378.719 | 38 |
| Q4 clinical extrapolation | Do not establish human motor recovery; distinguish missing clinical evidence from proof of no effect. 4392, 5215, 5255, 5504, 5593. | **BLOCKED**: same U1 incompatibility; no final refusal to assess. | 78.031 | 11 |
| Q5 multipart comparison | Worse evaluated GRU performance than AR-k; possible tuning explanation, not intrinsic inferiority. 5313, 5315, 5593, 6023. | **BLOCKED**: qualification role has same incompatibility; initial reading also produced no claims. | 115.110 | 18 |
| Q6 attributed prior result | Prior sparse-estimation minimax result, at most logarithmic gains for hard problems, not matrix recovery. 5253. | **FAIL**: desired passage never read; empty answer after new-paper recovery. | 150.984 | 17 |

Q1 was assessed before continuing. Its scientific failure did not invalidate the
environment. Q2's exception was isolated to an accepted but runtime-unsupported input
combination, so Q3 proceeded. The serial launcher paused at Q4's exception; inspection
confirmed the same bounded cause before Q5 and Q6 were started separately. No shared
infrastructure/provenance failure required stopping the entire battery. The expected
Q4/Q5 incompatibility was not repaired or worked around before their actual runs.

## Complete selected answers

The three completed answers below are exact text from `14_final_answer.md`, each equal
to the returned `selected_answer` and `15_v2_output.json`'s `render.layer1`.

### Q1

```text
1. What did the study of active learning of neural population dynamics using two-photon holographic optogenetics find about data efficiency?
The available evidence does not establish an answer to this part.
The scoped search completed, but this obligation remains unresolved.
```

### Q3

```text
1. What evidence supports actively designing perturbation inputs to estimate neural dynamics more efficiently across the optogenetic active-learning and optimal perturbation-input studies?
The available evidence does not establish an answer to this part.
The scoped search completed, but this obligation remains unresolved.
```

### Q6

```text
1. What does the optogenetic active-learning paper report about prior work on limits of adaptive sensing?
The available evidence does not establish an answer to this part.
The scoped search completed, but this obligation remains unresolved.
```

Q2, Q4 and Q5 have **no selected answer**, not a missing report excerpt. Their exact
questions remain in `01_request_contract.json` and the frozen protocol. `RUN_FAILED.json`
preserves the stack trace and `evaluation_manifest.json` the failed disposition.

## Scientific assessment and demonstrated boundaries

### Q1 — useful evidence lost before the scientific ledger

Paper 83 is the first ordinary nominee; paper 82 is sixth. Initial retrieval reaches
the target abstract and recovery reaches the actual data-efficiency findings. The
source passage at 5591 explicitly states gains up to 2× in many cases, no substantial
gain in every case and worst-case baseline matching. The generated claim retains these
qualifications. Thus this is no longer the original paper-discovery failure.

The verifier requires all of: chunk similarity at least **0.7**, exact-quote confidence
**1.0**, and NLI support at least **0.55**. `stages.source_verified` excludes every status
other than `verified`. Illustrative actual records:

| Source / claim | Similarity | Quote | NLI support | Actual disposition |
|---|---:|---:|---:|---|
| 5215: in some cases up to twofold reduction | 0.223475 | 1.0 | 0.008645 | unverified |
| 5502: realistic-simulation stimulus design speeds estimation | 0.610472 | 1.0 | 0.905566 | weak |
| 5591: qualified up-to-2× gain / worst-case baseline | 0.657213 | 1.0 | 0.994068 | weak |

The last two are demonstrable similarity-gate exclusions despite high source-entailment
scores. The initial abstract result also has very low NLI support. The verifier scores
the **isolated exact quote** against the formed claim; it does not supply the surrounding
ownership/antecedent context used during claim formation. That difference is established
by the code/prompt pair, but the cause of the NLI score is **not** proven by this run.
No threshold or context repair was tested. Preserved minimal records are in
`Q1.verification_loss_examples.json`.

Nine claims were checked: two verified background statements, three unverified and four
weak. Only the two background statements reach the sealed ledger. Phi4 calls them
responsive; the subsequent Gemma rationale correctly says they do not state what the
study found. The scientific result role remains missing. This distinguishes permissive
coverage assessment from actual scientific goal satisfaction and final output.

Recovery retains target `s1-o1::2dc69aed8aff6365`, child `s1-o1`, retrieval owner `s1`.
It performs DEEPEN on the existing 25 candidates, obtains four hits and forms six more
claims, but adds zero verified evidence. Scoped state is
`completed / recovery_no_new_evidence`, with the obligation still unresolved.

Responsiveness and completeness fail: the answer supplies neither gains nor scope.
Scientific calibration is conservative relative to the sealed ledger, with no false
positive or false null. Attribution and final claim-citation fidelity are unexercised.
The limitation prose is readable but not useful as an answer to the researcher.

### Q2 / Q4 / Q5 — authored input accepted, mapping combination unsupported

All three fail with:

```text
ValueError: v4/v5 category observations apply only to all_requested_categories requirements
```

The actual stack reaches `e2e.execute`'s initial diagnostic map, then
`sufficiency_mapping._bind_role_candidates`. The guard explicitly includes **v8** despite
the older wording of its error. It deliberately rejects `explicit_category_terms` outside
the cardinality mapper. The frozen inputs instead pair those roles with `exists`:
Q2 excitation/error, Q4 human population, Q5 author-stated qualification.

The unchanged `load_reviewed_inputs` accepts all three reviewed input sets. A read-only
minimal call to the existing role binder with the exact authored role and **zero candidate
units** reproduces each exception. `authored_input_runtime_incompatibility.json` records
that mismatch independently of models or scientific content. This demonstrates a gap
between authoring/acceptance and executable semantics; it does not justify changing an
`exists` question into a cardinality question to make this battery pass. These are
the original Codex-authored experimental contracts: their review failed to catch
the runtime incompatibility. This is not evidence of a user's authoring mistake.

Q2's live prompts show two formed claims from paper 82: 4648's iterative design result
and 4461's exact excitation/error relationship. The subsequent coverage prompt contains
only the former as verified p1. No detailed per-claim verification artifact was dumped
before the exception, so the absent second claim's exact score/rejection reason is not
claimed. No relationship proof, recovery or final answer was produced.

Q4 reads real context from both primary studies but forms no claims. No final clinical
refusal exists to assess. It therefore cannot pass by absence of a false clinical answer,
nor establish correct handling of missing clinical evidence versus no effect.

Q5's first and second requested components run through initial context reading, but
form no claims. The inspected prompt contexts contain no GRU passage; the known 5315
performance/qualification passage was not surfaced there. The mapping exception then
prevents recovery and answer construction. This is an additional observed recall gap,
not proof of what recovery would have achieved. Both responsiveness and completeness
remain unassessed at final-answer level. Citation, attribution, calibration and readability
cannot be scored as successes for a nonexistent output.

These cases are classified **BLOCKED by authored input/runtime compatibility**, with
an observed execution failure. They are not global infrastructure failures and do not
erase the independently observed Q1/Q3/Q6 scientific failures. Their partial traces
remain preserved; nothing is reconstructed as if it had been emitted.

### Q3 — no two-study synthesis despite real evidence-bearing processing

Both primary papers are the first two nominees. Twenty claims undergo actual verification:
seven verification events succeed, one repeating existing evidence, leaving six unique
sealed propositions. Twelve events are weak and one unverified. Recovery DEEPEN obtains
six hits and adds three verified propositions; scoped state is
`completed / recovery_added_evidence` for `s1-o1::b8ea84ea79bf23da`.

Useful result exclusions recur. A paper-82 simulation result at 4616 receives NLI
support **0.990839** but similarity about
**0.617**, hence weak. Paper 83's low-rank efficacy statement at 5215 receives support
about **0.986** and similarity **0.693**, also weak. Its twofold-efficiency claim is
unverified with support about **0.005**. Exact observed values and pairs are retained
in `10_verification.jsonl` and `Q3.verification_loss_examples.json`.

The sealed propositions concern methods, motivation, possibilities and control-theory
recommendations; the required achieved-result bindings are missing. U1/U2 and Layer C
therefore emit no answer claims. This run does not establish a new defect in witness
selection or answer rendering: the upstream admissible result basis was not available.

The requested attributed synthesis, empirical/theoretical settings and limitations are
all absent. No cross-study citation borrowing or human-benefit inference appears in
the final answer. Calibration remains cautious, but responsiveness, completeness and
research usefulness fail. One intermediate p2 formulation drops the source's explicit
"If ... can be" construction; it was verified as source-supported but never rendered
as a scientific answer claim. That is an upstream qualification-preservation concern
for later inspection, not a fabricated final finding hidden by a passing score.

### Q6 — target paper eligible, requested prior-evidence passage missed

Paper 83 is nominated, but initial reading hits its reference material and general
active-learning passages rather than **5253**, the preserved prior-work result. The
full read packets confirm 5253 was never read. The context gates discard the initial
branches; zero propositions are formed throughout this case.

Gemma chooses NOMINATE. Generic recovery and the distinct scientific target
`s1-o1::9d83e51b6318369c` both resolve to `s1` and execute. Each nominates eight new
papers and retrieves three passages from paper 1, with no selected evidence. Their
query strings happen to be identical. The structured row is explicitly recorded,
not silently discarded; scoped state is `completed / recovery_no_new_evidence`.
Existing NOMINATE excludes already-nominated papers, so it does not re-search 83's
missed passage. This is an observed retrieval/recovery-choice limitation, not a reason
to inject source 5253 or modify the query in this evaluation.

The answer omits the logarithmic-gain/minimax result and all its qualifications.
There is no observed misattribution because there is no rendered substantive claim.
It does not claim adaptive sensing is ineffective. Its completed-search disclosure is
correct about the recorded bounded operation, not a certificate of exhaustive source
coverage. Responsiveness, completeness and researcher usefulness fail; correct prior
attribution remains unqualified.

## Source, citation, mapping and recovery integrity

All three completed outputs validate and match their selected render exactly. Their
scientific maps identify v8; all three requested requirements remain missing. All three
have **zero Layer C claims, zero relation units and zero final citations**. Parent
synthesis/plan-v5 execute over those empty claim sets, so useful scientific synthesis
and claim-to-citation rendering remain untested.

Independent physical-source checks validate **331 sealed candidate spans**: Q1 110,
Q3 103, Q6 118. Of these, 323 are same-paper direct substrings and eight are exact
joins of preserved physical anchors with established continuity. Another **141 packet
chunk occurrences** match their database paper/attachment/text exactly. These are
source-integrity checks, not 331 verified claims or final citations.

Every final citation record was inspected: there are none. Accordingly no source-level
claim-citation success is reported. Q1/Q3 generated and verified evidence was checked
against preserved quotations and original scientific expectations. Failed-run Q2
formed quotations match physical chunks 4648 and 4461. Q4/Q5 contain no formed claims.
`packet_source_checks.json`, per-question inspection files and the failed-boundary
evidence records retain the audit details.

The failed cases expose an observability limit: numbered retrieval, proposition,
verification and mapping artifacts are written at successful run finalization, so the
exception leaves only the already-streamed prompts, decisions and runtime/failure
manifests. The coverage prompt preserves Q2's admitted p1, but not its numerical
verification scores. No live replay, monkeypatch, invented score, replacement answer
or inferred complete candidate inventory was used to fill those gaps.

## Comparison, narrow next actions and stop

Original Q1: primary papers unreachable, zero verified propositions, structured target
silently skipped, 13 generation calls, 213.422 seconds, incomplete-search disclosure.
Attempt 2 Q1: primary source retrieved, nine real claim verifications, two background
propositions sealed, actual scoped DEEPEN recorded, 27 generation calls, 284.531 seconds,
completed-but-unresolved disclosure. **Both remain scientific failures**, with different
demonstrated causes. F1/F2 readiness progress is not an answer-quality pass.

The smallest justified next work is a separately authorized bounded investigation of:

1. **Verification false negatives:** reproduce the exact high-NLI / exact-quote
   exclusions and audit what chunk similarity is meant to certify. Separately diagnose
   low NLI scores on the actual quote/claim pairs and lost local antecedent context.
   Do not simply lower thresholds against this benchmark or assume a specific fix.
2. **Authored-input executable compatibility:** reject or otherwise resolve unsupported
   role-strategy/quantifier combinations before expensive live execution. Audit valid
   authoring for relational and descriptive/qualification roles without rewriting these
   frozen cases retroactively. A new authored condition requires explicit authorization.
3. **Targeted passage recall and recovery action:** inspect Q6's missed 5253 and Q5's
   missed 5315 from the exact retrieval/context trace. No evidence supports a broad
   architecture rewrite, source whitelist or blanket candidate-limit increase here.

Later qualification must also address evidence-bearing final citations, relationship
proofs, successful two-source synthesis, clinical-premise calibration, multipart answers
and faithful prior-work attribution. Statistical-null and genuinely conflicting-result
cases were not part of this preserved battery and remain outside qualification.

The raw root contains `readiness.json`, `starting_ci.json`, frozen working-library
fingerprint, six run directories, console logs, exact model prompts/responses, source
inspection receipts, minimal failure records, disposable drivers and final integrity
and artifact hash inventories. All attempts and the original failure remain distinct.
The working database, original database and indexed checkpoint remain byte-exact.
Ollama reports no resident models after cleanup; the task-owned SSH tunnel is closed.

Only this report and `CONTRIBUTION-LINEAGE.md` are tracked changes. No scientific code,
versions, contracts, D1/D2 identities, historical baselines, application endpoint or UI
changed. Commit/push only the documentation after applicable normal checks. The full
delivery HEAD and clean-worktree status are reported at delivery, avoiding a
self-referential commit hash in this file.

**LIVE E2E NOT QUALIFIED. Stop after reporting; no remediation or product integration.**
