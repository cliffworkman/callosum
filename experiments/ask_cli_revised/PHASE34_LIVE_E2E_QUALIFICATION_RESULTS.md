# Phase 34 — Live end-to-end scientific qualification

**Disposition: LIVE E2E NOT QUALIFIED.** The ordinary-question smoke executed real
retrieval and generation through the actual selected v8 / Layer C v2 / plan-v5 answer,
but did not retrieve independently verified findings available in the selected library.
The answer safely abstained. That is not successful scientific question answering.

Two boundaries are demonstrated: the selected evaluation library lacks the discovery
index entries for both primary papers, and flat reviewed requests silently lose their
structured scientific recovery target at a child/subquestion ID join. The first prevents
meaningful completion of this predeclared battery; the second is a distinct runtime
integration defect. Neither establishes a defect in scientific adjudication given real
evidence, because no proposition reached that stage. No fabricated claim, relationship,
false citation, or null-to-positive conversion was observed.

The remaining five cases were **not run**. The brief requires stopping for a blocker
that invalidates the whole evaluation and forbids changing the corpus after poor answers.
The required meaningful ordinary, relational, incomplete-evidence and multi-source
qualification has therefore **not been obtained**. This report preserves the failure,
not a passing score inferred from empty-output structural validation.

## Checkpoint and authority

- Canonical worktree: `C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum\.claude\worktrees\ask-060-hier11-recpm3-citefix-20260929T212442Z`.
- Branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
- Starting HEAD: `d5e10c3fd15f43bef3328b130b15fc980ba25fe7`; clean before evaluation.
- Read actual runner, authoring, discovery, retrieval, verification, recovery and consumer
  code; accepted E2, E1B, I2-3 reports; contribution lineage; and
  `.claude/CREDIT-THE-LINEAGE.md`.
- Starting-HEAD [GitHub workflow](https://github.com/cliffworkman/callosum/actions/runs/38171299759)
  completed successfully. That CI result is separate from this live failure. The previously
  accepted 5,496-pass offline result and seven optional checks were not rerun or relabeled
  as live qualification.
- User supplied qualification framing and permission. Codex selected the corpus, inspected
  sources, authored and reviewed the experimental inputs, executed and assessed the run.
  **This is not independent human scientific review or approval.**

No production code, producer material, source pins, versions, frozen baselines, contracts
from earlier phases, application endpoint or frontend changed. The only tracked changes
are this report and the experiment lineage append. Disposable drivers and raw artifacts
are outside tracked production code.

## Execution surface and actual components

Entry: `reviewed_ask.run_reviewed_request`, called by disposable `run_live.py` using
`reviewed_ask_inputs.load_reviewed_inputs` with five explicit paths per question.
Each input set contains a literal request, frozen scientific role definitions, reporting
ownership, empty flat parent map and content-bound joint review. No benchmark loader,
seeded ledger, fake client, patched stage, supplied expected claim or preferred citation
enters execution. Assessment expectations remain in a separate protocol that the runner
never reads. No claim is made about `/summarize`, product UI or unattended raw-text authoring.

| Boundary | Implementation and observed execution |
|---|---|
| Request authority | Actual immutable reviewed snapshots and fresh invocation authority |
| Discovery | Real local embedding inference, SQLite vector search, paper kNN and axis nomination |
| Reading/extraction | Real Qwen context gates and evidence selection; no claims selected |
| Responsiveness | T5 assigns coverage authority to model C; separate R is intentionally off |
| Verification/sealing | Real verifier provisioned; zero actual claim-NLI verifications because extraction produced no propositions; empty proposition ledger sealed |
| U1 | Actual deterministic v8 mapping; one missing requirement |
| Recovery | Actual Gemma planner, Qwen query, new-paper retrieval and evidence selection; structured target skipped as detailed below |
| U2 | Actual deterministic remap, still missing; C2 skipped for no new verified evidence |
| Layer C | Actual authenticated projection, claims v2, relation units and parent synthesis v2; no scientific claims or relation units to adjudicate |
| Plan/render | Actual plan-v5 and I2-3 disclosure; selected answer exactly equals returned answer and v2 Layer 1 |

The public fresh route explicitly refuses model-assisted scientific nomination. Its
deterministic mapping was used unchanged. No alternative nomination capability was
invented. For the same reason, inputs use declared deterministic strategies. Q3's open
list does not mechanically enforce independent source count; that is an independent
assessment obligation. These are authoring/qualification scope limits, not hidden changes.

### Models and configuration

Existing T5 profile: W `qwen3.5:9b`, thinking off; C `phi4:14b`; P `gemma3:12b`;
R off; legacy S off. Fresh Layer C is deterministic. Native Ollama 0.34.3 on JUNO
(`brain`, NVIDIA RTX 3050, 8 GB), reached through a task-owned hidden SSH forward to
`127.0.0.1:11435`. No cloud model or mock was used.

| Installed binding | Digest |
|---|---|
| qwen3.5:9b | `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` |
| phi4:14b | `ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba` |
| gemma3:12b | `f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a` |

Shared options: context 12,288; base prediction allowance 4,096; temperature 0;
seed 42; six threads; batch 512; keep-alive 30 minutes; per-call watchdog 1,200 seconds.
Existing task-specific worker caps remain unchanged and are recorded per call.
Installed/bound Phi4 is **not** claimed as physically invoked: C1 took the empty-ledger
shortcut and C2 was skipped.

Local embedding: `all-MiniLM-L6-v2`, pinned revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Local NLI:
`cross-encoder/nli-MiniLM2-L6-H768`, pinned revision
`b95119ce93d3e065de6214e38cd4a97b0f2f2c6d`. Cached weights loaded with
`HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`; those flags did not disable live
Ollama calls. An actual CrossEncoder identity-pair preflight returned support
0.993228 and contradiction 0.000992, proving NLI availability without accepting the
runtime's embedding fallback. **That preflight is not scientific claim verification.**

## Library and independent source inspection

The current application database was empty. A separate preserved QA library was copied
using SQLite's read-only-source backup operation from
`C:\Users\cliff\Callosum-Windows-QA-0516-20260930\parked\roaming-data\callosum.sqlite`.
The entire library was retained: no source selection/deletion, reindexing, synthetic
publication or expected-evidence insertion. This is a separate library snapshot, not
a newly ingested, fully indexed corpus. It includes older overlapping papers, but the
two primary scientific works below are absent from the preserved q_aib inventory and
were not used in that scientific rebuild.

Frozen evaluation copy: `.local/phase34-live-e2e-20261011/library.sqlite`.
SHA-256: `6598c4798cc35a8364da48b9a0215c3777a9e25c31add09aaaa512a111e8c529`.
86 paper rows, 69 active, 17 deleted; 17 attachments; 6,610 chunks; 5,700 embedding
rows; 210 axis-membership rows; zero `chunk_structure` rows. Full active metadata
inventory is retained in `source_inventory.json`; missing structural metadata is an
additional corpus limitation, not fabricated by the runner.

| Primary source | Preserved material independently inspected before answers |
|---|---|
| Ogino et al., *Designing optimal perturbation inputs for system identification in neuroscience*, [eLife reviewed preprint](https://doi.org/10.7554/eLife.110030.2), paper 82 | 843 chunks, all with chunk embedding rows. Preserved PDF text identifies revised v2, September 9, 2026. Abstract 4392; methods 4424/4438; Results 4461; covariance/error derivation and illustrations 4478/4482/4494. Theory and simulations, not clinical recovery evidence. |
| Wagenmaker et al., *Active learning of neural population dynamics using two-photon holographic optogenetics*, [arXiv:2412.02529](https://arxiv.org/abs/2412.02529), paper 83 | 929 chunks, 282 with chunk embedding rows. Metadata year 2024; preserved text identifies v4, May 8, 2025. Abstract 5215; summary 5223; mouse dataset 5255; model comparison 5313/5315; evaluation 5440/5504/5591; limitations 5593; related-work qualification 5253. |

Full preserved chunk text and source IDs are in `source_82_chunks.json`,
`source_83_chunks.json`, and their readable text exports. Expectations came from these
passages independently of Ask's retrieval/output. No external search or scientific
content intuition supplied ownership or findings. Recorded attachment checksums remain
available in the library diagnosis; this evaluation used preserved source passages,
not a fresh PDF acquisition or PDF-checksum certification.

The initial preparation checked chunk availability and embedding counts but failed to
check **paper-level discovery eligibility** before starting the smoke. That is a
qualification-harness preflight omission attributable to this evaluation, not evidence
that all production libraries are unindexed. The subsequent read-only diagnosis proves
that papers 82/83 have **zero paper embeddings and zero axis membership**. Neither can
enter `discovery.nominate_papers`, regardless of query. Recovery NOMINATE uses the same
discovery function; DEEPEN remains restricted to existing nominees. Citation-graph
rescue is explicitly disabled by the existing implementation. No repair was made.

## Frozen question matrix and expectations

All six questions and all reviewed input bodies were materialized before Q1 generated
an answer. `predeclared_protocol.json` preserves wording, roles, expectations, source
chunk references, model profile, failure rules and authorship. Expected claims and
source IDs are not passed to model-facing inputs.

| Case | Exact question | Independent success criteria | Result |
|---|---|---|---|
| Q1 / A ordinary | What did the study of active learning of neural population dynamics using two-photon holographic optogenetics find about data efficiency? | Report gains that vary by setting, in some cases up to twofold fewer samples; distinguish offline mouse data and simulations from online or human validation. Sources 5215, 5223, 5440, 5504, 5591, 5593. | **FAIL**, retrieval/integration; mechanically completed |
| Q2 / B relationship | What relationship between excitation of neural states and estimation error is reported in the study of optimal perturbation inputs for neural system identification? | Explain linked excitation/covariance and reduced estimation error under stated model assumptions; no clinical extrapolation. Sources 4424, 4438, 4461. | Not run: shared corpus blocker |
| Q3 / C multi-source | What evidence supports actively designing perturbation inputs to estimate neural dynamics more efficiently across the optogenetic active-learning and optimal perturbation-input studies? | Attribute both studies separately, distinguishing theoretical/simulated and offline experimental settings; no borrowed citations or patient-benefit inference. Sources 4392, 4438, 4461, 5215, 5440, 5504, 5593. | Not run: shared corpus blocker |
| Q4 / E sparse, I unsupported premise | Do these active-learning and optimal perturbation-input studies establish improved motor recovery in human patients? | Do not establish that clinical outcome; explain evidence scope without claiming proof of no effect. Sources 4392, 5215, 5255, 5504, 5593. | Not run: shared corpus blocker |
| Q5 / J multipart | In the optogenetic active-learning study, how did GRU models compare with linear autoregressive models? What limitation did the authors give for that comparison? | Report worse evaluated GRU performance and possible hyperparameter-tuning explanation; not intrinsic nonlinear-model inferiority or a proven explanation. Address both obligations. Sources 5313, 5315, 5593, 6023. | Not run: shared corpus blocker |
| Q6 / G attributed | What does the optogenetic active-learning paper report about prior work on limits of adaptive sensing? | Attribute the cited sparse/minimax limitation to prior work; retain hard-problem and non-matrix-recovery qualifications. Source 5253. | Not run: shared corpus blocker |

H (recovery) was enabled without withholding evidence to force success; Q1 exercised
generic recovery and exposed the skipped structured target. D (statistical null) and F
(directly conflicting empirical findings) were not manufactured: no independently
verified suitable pair/result was selected. A worst-case baseline match is not a
statistical null, and different theoretical settings are not a contradiction. Those
cells, as well as substantive B/C/E/G/I/J results, remain unqualified.

## Q1 actual selected answer and assessment

One attempt only: `runs/Q1/attempt-01` under the evaluation root. Started
2026-10-11 20:44:30 UTC; finished 20:48:04 UTC; runtime **213.422 seconds**, including
runtime preflight, model loading and cleanup. No retries, crashes, watchdog failures,
schema failures or evidence injections. All 13 generation-call records were usable.

Actual `14_final_answer.md`, equal to returned `selected_answer` and v2 `render.layer1`:

> 1. What did the study of active learning of neural population dynamics using two-photon holographic optogenetics find about data efficiency?
> The available evidence does not establish an answer to this part.
> Recovery has not completed the scoped search for this obligation.

| Dimension | Assessment |
|---|---|
| Responsiveness | Fails to supply the requested finding despite independently inspected relevant text in the library. |
| Scientific correctness | No false substantive claim; the abstention is consistent with the empty retrieved proposition ledger. This does not demonstrate correctness of the scientific adjudication machinery. |
| Attribution/citations | No substantive citations in the selected answer, so citation fidelity is unexercised rather than passed. |
| Completeness | Material retrieval omission: the target paper is never nominated. Not evidence that the source lacks the answer. |
| Calibration | Appropriately does not establish an answer or certify completed search; no fabricated negative conclusion. |
| Readability | Concise and understandable limitation statement, but scientifically unhelpful for this answerable library question. |
| Recovery | Generic search ran without evidence gain. Independently required scientific target was silently skipped by the flat-ID mismatch. |

### Trace counts and physical provenance

Initial discovery nominated 25 papers; neither 82 nor 83 appeared. Eight initial hits
were rejected by eight real Qwen context gates. Gemma generated NOMINATE; Qwen generated
one query. Recovery nominated 10 new papers, retrieved three hits and made three real
evidence-selection calls, all returning no selected spans. Totals: 12 Qwen calls and
one Gemma call. Actual claim formation, claim NLI and Phi4 coverage calls: **zero**.

The sealed ledger contains zero verified propositions and 31 candidate source spans
from an irrelevant recovery paper. Read-only source checking verifies all 31 against
their correct paper and physical chunks. One span is an established two-chunk
continuation (2141 + 2142), not a direct substring of its first anchor alone. The initial
single-chunk diagnostic flag is retained in `smoke_assessment.json`; the complete anchor
and seam check in `span_continuity_assessment.json` resolves it. No authority/provenance
corruption was found, and no raw run artifact was rewritten.

U1 and U2 both leave the one evidence role/requirement missing. Layer C has zero claims
and zero relation units; plan reports `not_established`. Fresh output validation and
exact selected-render checks pass. The library fingerprint is unchanged after execution.
These checks verify integrity of this empty-evidence result, not a successful answer.

## Demonstrated failure boundaries and smallest corrections

### F1 — selected corpus lacks discovery prerequisites

**Boundary:** evaluation-library readiness / retrieval. Preserved chunks are insufficient
for this paper-first entry: a paper must enter the nomination set before within-paper
chunk retrieval. Both primary papers have neither paper embeddings nor axis membership.
The condition is established by exact SQL in `library_readiness_diagnosis.json` and the
unchanged discovery/recovery code, not guessed from an empty answer.

**Consequence:** all six predeclared questions depend on inaccessible primary papers.
Continuing would not produce the requested meaningful scientific battery. This blocks
qualification; it does not prove a scientific mapping defect or universal library failure.

**Smallest next action, not performed:** separately authorize completing the existing
indexing workflow in a new isolated evaluation copy, checking paper and chunk eligibility
before running. Preserve this original copy, attempt and unchanged question expectations;
identify any later indexed-copy run as a new attempt with a new corpus fingerprint.
No retrieval redesign or source-specific workaround is justified by this result.

### F2 — flat structured recovery target uses the wrong identity

**Boundary:** current reviewed flat-request recovery integration. The actual request has
subquestion `s1` and scientific child/obligation `s1-o1`. In `e2e.execute`, structured
recovery appends both `field_id` and `subquestion_id` from `target.search_child_id`, hence
`subquestion_id=s1-o1`. In `__main__._recover`, `sq_by_id` is keyed by `s1`; a missing
lookup immediately continues without a recovery record. The generic coverage gap has
the correct `s1`, which explains why one generic search ran while the scientific target
`s1-o1::2dc69aed8aff6365` remained `not_attempted`, with no reason code.

**Consequence:** scoped scientific recovery can be silently dropped for legitimate flat
reviewed inputs. The renderer faithfully discloses incomplete search; it does not cause
or repair the lost target. This integration defect exists independently of whether an
indexed paper could have supplied evidence. It prevents claiming reliable fresh flat
recovery and is a material reason for **NOT QUALIFIED**.

**Smallest plausible correction, not implemented:** resolve the obligation/child's actual
subquestion identity at this boundary while retaining its existing target/obligation ID,
and explicitly account for any unresolved lookup. A separately authorized bounded fix
should validate flat scoped recovery and preserve hierarchical identity behavior. No
scientific semantic change is inferred to be necessary from this identity mismatch alone.

There is no evidence here warranting changes to attribution, guards, support policy,
relationship proofs, ParentClaims, AnswerPlan or scientific versions. No severe
fabrication/citation/null-conversion failure was observed; the empty-evidence result
cannot be used to assert their absence in evidence-bearing runs.

## Artifacts, comparison and stop

All raw material is under the canonical worktree's
`.local/phase34-live-e2e-20261011/`:

- `predeclared_protocol.json`, `inputs/Q1` through `inputs/Q6`: frozen experimental design
  and five reviewed bodies per question.
- `library.sqlite`, `library.fingerprint.json`, `source_inventory.json`, `source_82*`,
  `source_83*`: preserved source corpus and independent reading evidence.
- `runs/Q1/attempt-01/`: numbered discovery, retrieval, reading, evidence, verification,
  coverage, recovery, U1/U2, ownership, ledger, plan/render and fresh output artifacts;
  exact prompts/responses in `qwen_calls.jsonl`; started/runtime/final evaluation manifests;
  returned public result in `evaluation_return.json`.
- `Q1.console.log`, `starting_ci.json`, `library_readiness_diagnosis.json`,
  `smoke_assessment.json`, `span_continuity_assessment.json`: operational and independent
  assessment records. Disposable Python scripts preserve how inputs, execution and
  diagnostics were produced. No pytest mocks or offline replay supplied an answer.
- `artifact_hashes.json`: final inventory hashes, excluding itself and later delivery logs.

Historical q_aib runs use a different library/question and earlier execution surfaces;
their answer quality is not a matched comparator. They helped identify existing runtime
wiring, but no historical claims or outputs were injected, rerun or scored here. The
accepted offline and CI evidence remains valid within its original scope and does not
close this live gate.

Remaining uncertainties include all evidence-bearing claim NLI, substantive coverage,
candidate/relationship adjudication, attribution, multi-source synthesis, null/conflict
handling and useful final scientific prose. Sparse/unsupported-premise success cannot
be inferred from accidentally missing evidence in an ordinary positive case. Fulltexts
were inspected as preserved chunks; fresh PDF acquisition/ingestion was not qualified.

The run released its models; Ollama reported no resident models afterward. The task-owned
SSH tunnel was closed. No remote service was modified and no production behavior was
changed. Stop after the documentation-only report/lineage checkpoint; no index repair,
recovery fix, product integration or additional scientific implementation begins here.

Final delivery commit is identified by `git log -1 --format=%H --
experiments/ask_cli_revised/PHASE34_LIVE_E2E_QUALIFICATION_RESULTS.md` and the final user
delivery, avoiding a self-referential hash. Normal documentation hooks and final worktree
status are checked at delivery. This is **LIVE E2E NOT QUALIFIED**, not complete product
release readiness and not a claim that the live runtime was unavailable.
