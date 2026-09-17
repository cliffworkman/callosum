# Callosum 0.7.0 non-semantic infrastructure implementation

Date: 2026-09-09. Experimental preparation only; no model inference, weight acquisition, production mutation, staging, or commit.

## 1. EXECUTIVE STATUS

The non-semantic runner, adapters, offline scorer, neutral preflight specification, corpus receipts, and pre-execution freeze are implemented in [experiments/ask_070](../../../experiments/ask_070/README.md). **55 synthetic tests passed**, **30 existing relevant tests passed**, six existing deterministic selfchecks passed, and Ruff passed. The final manifest verifies all **52** listed files and rebuilds byte-identically.

Three positive held-out questions are lexically qualified and their exact bytes are frozen. Their referents remain **HUMAN_REFERENT_REVIEW_REQUIRED**. The proposed Parkinson's/gut-microbiome negative control failed the declared absence rule and is **NEGATIVE_CONTROL_REPLACEMENT_REQUIRED**. No replacement was selected. This report uses the conservative partial-readiness status because that held-out slot remains unresolved, while the infrastructure itself is prepared.

R_0_6 remains **NOT_YET_AVAILABLE**, with an explicit hard-failure adapter. R_0_6 is not the only remaining human/final-freeze dependency; section 22 enumerates the others.

## 2. SCOPE

All new executable work is under `experiments/ask_070/`; production `app/` behavior is unchanged. Additional repository writes are this report and one appended SCRATCH handoff. Ignored task bytecode caches remain: automatic approval review blocked their optional deletion ("blocked by policy"); caches are excluded from all freeze identities. The package includes contracts, hashing, representation/runtime adapters, runner, append-only observation journal, receipt writer, schema validator, lexical audit, referent inventory builder, Stage-0 reconciler, offline scorer, freeze builder/verifier, selfcheck, guarded regression driver, specifications, frozen artifacts, and synthetic tests.

Private generated artifacts are in `C:/Users/cliff/AppData/Local/Temp/callosum-070-nonsemantic-infra-nv0h55dk/`: the corpus copy, complete lexical matches, Stage-0 snapshots, source/referent provenance, synthetic observation artifacts, test logs, and integrity receipts. No candidate weights or provider outputs from actual inference were generated.

The preregistration is preserved as an authored DESIGN document. The new manifest records the current human decisions and precision corrections without editing or retroactively recharacterizing that document.

## 3. GOVERNING EPISTEMIC CONSTRAINTS

- Schema-valid != semantically faithful.
- Anchor validity != interpretation validity.
- Quotation fidelity != proposition fidelity.
- Mechanical completion != semantic viability.
- Lexical presence != answerability, accepted referents, or complete ground truth.
- Procedural lexical absence != scientific absence from the corpus or world.

The sealed claim-arm key was not inspected; no hidden identities were inferred, no claim-arm adjudication occurred, and no mechanical result selected R_0_6. Its dependency remains human blinded adjudication -> candidate -> separately authorized revised-0.6 integration -> separately authorized bounded acceptance -> if READY, freeze R_0_6 -> final 0.7 freeze -> separately authorized semantic benchmark once.

## 4. STAGE-0 RECONCILIATION

[candidate_roster_v0.json](../../../experiments/ask_070/frozen/candidate_roster_v0.json) preserves all 12 exact model/artifact/runtime candidates and the completed dossier's dispositions: **1 ELIGIBLE, 4 UNKNOWN_REQUIRES_PREFLIGHT, 7 ELIGIBLE_WITH_CONSTRAINTS, 0 INELIGIBLE**. `reconcile.roster()` verifies the dossier's generated-file hashes and candidate/artifact agreement before producing this roster. No new model research was performed.

The roster preserves publisher/converter revisions, filenames, remote LFS SHA256 metadata, license constraints, context/cache facts, role assignments, hardware assumptions, and unexecuted runtime profiles. Every locally unverified weight hash is explicitly `HASH_REQUIRES_PREFLIGHT_DOWNLOAD`; remote metadata and historical incumbent provenance do not become a new local byte verification.

Special facts remain explicit: original hybrid Qwen3 variants and neutral thinking controls; Phi-4-mini LongRoPE above 4096; Gemma interleaved/window-aware cache allocation; Phi-4 native 16384 covering REALISTIC 12288; borderline JUNO 7–8B full-GPU fit; JUNO 14B host/offload requirements; separate weight/KV quantization; and converter/checkpoint provenance limitations. No paper disposition was upgraded or downgraded.

## 5. PRODUCT LATENCY FREEZE

| Quantity | Value | Role |
|---|---:|---|
| B_worker | 3.0 s warm | Product/interaction budget for a bounded high-volume worker call |
| B_orch | 15.0 s warm | Product/interaction budget for approximately once-per-query orchestration |
| L_screen | 600 s | Catastrophic Stage-1 mechanical infrastructure ceiling |

Provenance: **explicit human product decision, 2026-09-09**. These are not observed candidate-performance thresholds.

`preflight.assess()` records warm product-budget exceedance independently from mechanical admission. Synthetic tests prove that 4-second worker, 16-second orchestrator, and 599-second worker observations are not culled solely for exceeding those product budgets. The 600-second ceiling and declared representation-independent mechanical failures are separate. No latency was empirically benchmarked.

## 6. CONTEXT POLICY

REALISTIC is **12,288 total runtime context tokens**, the sole primary semantic context. Prompt, template/BOS/role tokens, and generated tokens share that envelope. A 4096 generation allowance implies at most 8192 rendered input tokens; it does not add 4096 beyond the context allocation.

SHORT/STRESS are mechanical/sensitivity conditions only and are not primary semantic levels. Semantic cells at another context hard-fail. Actual runtime allocation remains a future measured fact, not an assumed consequence of request serialization.

## 7. QUANTIZATION POLICY

Q4_K_M is the common primary weight quantization where available. Only exact artifact availability, runtime compatibility, memory fit, or a predeclared mechanical sensitivity can justify deviation; semantic scores cannot. Microsoft Phi-4's publisher `Q4_K` filename retains its documented alias status and required later header verification.

K and V cache precision are independent configuration fields. The dossier's f16 primary cache profiles and separate JUNO q8_0 K/V variants for the two 7–8B models are retained. Q5 files are documented alternatives, not automatic retries or memory-saving fallbacks. A changed configuration produces a different identity and is never silently normalized.

## 8. CLOUD POLICY

Gemini **gemini-2.5-flash-lite** is the sole calibration reference. Cloud is service-level calibration, not a hardware-equivalent cell, not a target to beat, and not part of Stage-1 local eligibility. Cloud memory metrics are not applicable. A future bounded call inventory and explicit egress/execution authorization remain required. Gemini was not run, and no other cloud reference was added.

## 9. STAGE-1 NEUTRAL-MECHANICAL POLICY

The fixture reuses the completed Stage-0 specification: tag `x`, a bounded list of four integer zeros, a boolean, and repeated `. 0 ~` padding. It contains no scholarly question, source-fidelity demand, obligation benchmark, relationship benchmark, or reasoning-quality task.

The interface includes fixed compact-cold, compact-warm, and padded observations, each with a stable distinct trial ID. They are predeclared observations, not retries. A failed observation remains data; no failure adds a trial. A later scheduled trial can run only if its own prerequisites hold, otherwise it must have an explicit not-run state. The inherited route-level schedule and count assumptions remain identifiable as the Stage-0 specification.

The pure padding builder follows the declared bounded tokenization-only adjustment algorithm, with a fake tokenizer in tests. The Stage-1-specific 4096 cap does not resolve the semantic cap. No tokenizer/runtime was loaded, no neutral smoke was executed, and no acquisition/load/unload process was launched.

## 10. HELD-OUT SELECTION PROCEDURE

The approved four scholar-question texts were recorded byte-exactly in `questions_v0.json`. The procedure and candidate bytes were hashed before corpus matching; the private `procedure-prefreeze.json` receipt records that ordering. No wording or term rule was adapted to observed matches.

The audit uses the verified frozen 0.6 database identified by its existing `database-source.json`, not the current production library. Its main-file SHA256 is `f2723b7506f8a387e4a0ba2394258bfea7bf059cf058653473f822ff574684d0`; the WAL was empty before copying. A byte-identical private copy was opened with SQLite read-only/immutable/query-only settings and a write/attachment/extension-denying authorizer.

Only live, unmerged papers' titles, abstracts, and source chunk text were searched. Normalization and finite regex term families are explicit in [heldout_selection_v0.json](../../../experiments/ask_070/specifications/heldout_selection_v0.json). Matching has raw character-offset provenance; no embeddings, model calls, semantic ranking, or generated summaries were used. Positive qualification requires all declared groups in the same paper, excluding reference/structural-only chunk support. Negative disqualification conservatively includes reference/structural matches. Unknown structure is retained.

## 11. HELD-OUT CORPUS-PRESENCE RESULTS

The two independent audit passes produced identical summary and match inventories: **217 live/unmerged papers, 434 metadata fields, 24,261 chunks, 15,898 lexical matches**. Of the chunks, 7,938 were excluded from positive qualification by the declared structural/reference rule. This is a scope/count receipt, not a semantic answerability assessment.

| Slot | Result | Lexical witness scope |
|---|---|---|
| Serotonin / 5-HT2A | PRESENCE_QUALIFIED | 7 papers |
| Expert vs lay face viewing | PRESENCE_QUALIFIED | 4 papers |
| Aesthetics / truthiness | PRESENCE_QUALIFIED | 50 papers |
| Parkinson's / gut microbiome negative control | NEGATIVE_CONTROL_REPLACEMENT_REQUIRED | Paper 208 disqualifies procedural absence |

The negative-control witness is especially important to interpret conservatively: `microbiome` occurs in chunk 42234 at raw offsets [365,375); `Parkinson` occurs in bibliographic/reference material in chunk 42339 at [24,33). The rule intentionally operates at paper level and includes reference material for negative disqualification. These observations prevent the declared absence receipt; they do not establish that this paper substantively answers the question. No scientific relevance adjudication or replacement-domain selection was performed.

[corpus_presence_v0.json](../../../experiments/ask_070/frozen/corpus_presence_v0.json) contains counts and outcomes; `corpus_witnesses_v0.json` contains bounded source-ID/offset witnesses. The complete private `corpus-matches.json` has canonical content hash `b3720f4cfa4c82e91eabc9626bf33419c0444750448ba7b982bbc778963ef376`. No absent-corpus claim was frozen for the failed slot.

## 12. HELD-OUT REFERENT STATUS

The three qualified question byte hashes and deterministic source spans/offsets are frozen. Their inventories preserve the full original request, plus draft exact-phrase categorizations for constructs, operations, requested relationships, explicit populations, output fields, qualifications, and open elements.

Every interpretive annotation is explicitly a **Codex draft**, **HUMAN_REFERENT_REVIEW_REQUIRED**, and **not accepted ground truth**. Scientific answer targets were not authored. No lexical pass promotes a referent. Genuine approval must identify the reviewed inventory hash, human reviewer, decision, and unresolved issues. The scorer rejects missing/unapproved referent provenance.

These records are external evaluation referents and are excluded from package preparation and wire prompts. q_aib, q_builtenv, and q_depr remain DEV with original hashes. Historical source-unit/obligation/operation records were retained, including the built-environment 8-literal-unit/11-fine-grained-obligation provenance caveat.

## 13. RUNNER ARCHITECTURE

`CellSpec` hashes exact model/runtime configuration × representation package × hardware configuration × context × frozen task hash, with output policy included. Original input bytes, package hashes, hardware identity, and stable trial identity determine the cell. Ordering is deterministic; duplicate planned cells are rejected.

The runner accepts only an explicit deterministic `FakeRuntimeAdapter` and synthetic tasks in this delivery. There is no live inference command or transport implementation. It provides the preparation/observation/receipt seam without dispatching to production. No artifact/model/quant/context/prompt/template/package/provider substitution or automatic repair exists.

An exclusive cell directory claims the observation. A durable hash-linked append-only journal records submission before invocation and records failures/finalization. A crash or partial receipt is indeterminate and cannot be automatically reclaimed or resubmitted. Per-cell attempt counts remain one even when the same fake adapter serves separately predeclared trials.

## 14. REPRESENTATION-PACKAGE INTERFACE

The protocol exposes identity manifest, supported task preparation, output schema, interpretation, and deterministic transformation decisions. It consumes frozen tasks, not evaluation referent inventories. Unsupported package/task combinations fail explicitly; future package-specific tasks can use the same interface without inventing production semantics now.

R_CONTROL currently supports the existing request-planning task. Downstream context/source-fidelity/coverage/terminal packet contracts remain enumerated final-freeze work where the governing documents have not supplied an executable R_CONTROL counterpart. No claim-formation representation was reconstructed from the isolation experiment.

## 15. R_CONTROL IMPLEMENTATION

The adapter loads the exact unchanged production `query_planner.py` source directly, bypassing parent-package initialization that otherwise imports model-runtime definitions. It hashes source identity, adapter identity, prompt version/template, A1 schema, and relevant constants. A source change after loading fails visibly.

Its effective representation is produced by the production breadth gate, `_planner_prompt`, `_extract_json_object`, and `_plan_from_payload`, including tolerant prose/fence handling, narrow fallback, trimming, character caps, deduplication, and facet bounds. Diagnostics record strict whole-response/schema validity, parser result, fallback, and transformations separately. **Strict diagnostics never select or rewrite the effective plan.**

Shared A1 structured-output enforcement preserves narrow/broad choice and does not add obligations or force scope. Parity tests cover malformed, narrow, too-short, duplicate, capped, coerced, fenced, and prose-wrapped results. An end-to-end synthetic receipt proves a strict-format failure can retain a historical tolerant BROAD result. Actual enforcement transfer remains untested; any demonstrated contract incompatibility must stop final freeze.

## 16. R_0_6 EMPTY-SLOT BEHAVIOR

The adapter is explicitly unavailable and raises `REPRESENTATION_PACKAGE_NOT_AVAILABLE` before dispatch. The manifest records `R_0_6 = NOT_YET_AVAILABLE` and a null implementation. Tests prove zero fake-provider calls and no R_CONTROL replacement when this slot is requested. No R_0_6 implementation, acceptance, or freeze occurred.

## 17. MODEL/RUNTIME ADAPTER

Pure deterministic serializers distinguish Ollama/OpenAI `response_format`, llama.cpp top-level `json_schema`, and the separately identified Ollama-native `format` compatibility path. They emit request bodies and explicit server/Modelfile/template prerequisites; unsupported policies fail rather than disappearing from the request.

Model artifacts, runtime binary identity/status, templates, thinking controls, total context, output cap, seed, temperature, weight quantization, K/V precision, threads, batch/microbatch, GPU layers, and placement are represented independently. Qwen3 neutral control fields remain route-specific and require later enforcement receipts. No production descriptor spoofing, target mutation, managed-local resolution, download, or model load is implemented.

## 18. PER-CELL RECEIPTS

Private correctness artifacts preserve package input, wire bytes without credentials, raw provider bytes and text, finish reason, truncation/error state, observed configuration/context identity, parser/schema results, effective representation, and transformations. Synthetic data alone exercised this writer.

Performance-only receipts use allowlisted numeric/enumerated fields and opaque hashes. Scholarly text, prompts, titles, authors, quotes, and paths are rejected. Unmeasured tokens/memory/context remain null with explicit measurement state, never zero by omission. Future cloud memory is not applicable. Every failure/prune includes decision, reason code, inputs, and kept/discarded state. Missing, corrupt, failed, and successful artifacts remain distinguishable; success requires a final journal entry and verified artifact hashes.

## 19. OFFLINE SCORER

The scorer performs arithmetic on external labels, never model-based adjudication. It retains all five overall categories and independent co-occurring LOSS/ADDITION/MALFORMED flags, with mechanical validity, semantic fidelity, responsiveness, completeness, and contamination separate. Request dimensions retain preserved/drifted/starved/unresolved counts and distinct null/mixed/uncertain fields.

Reports are per question and task. Matched contrasts cover model conditional on package, package within model across models, and MODEL × REPRESENTATION PACKAGE difference-in-differences. Missing counterparts are not estimable. No prompt-effect output, pure-capacity claim, cross-question average, or automatic materiality verdict is produced.

Rates include numerator/denominator and the lower endpoint of a two-sided 95% Wilson interval; zero denominators are not estimable. Minimum-context outcomes retain acceptable sets and separate under/over-expansion distances. Contamination is a separate hard outcome. Semantic fidelity floors, numeric promotion floors requiring approval, and materiality criteria remain `REQUIRED_FINAL_FREEZE_VALUE`. The new scorer was run only on synthetic labels.

## 20. FREEZE_MANIFEST_V0

[freeze_manifest_v0.json](../../../experiments/ask_070/frozen/freeze_manifest_v0.json) is the new pre-execution artifact; its detached SHA256 is `753e3202b389997b39021c3f04e933ccc51d929a37f7bc32eb2b311f4747eb9f`.

It includes governing document hashes, Stage-0 provenance and roster, product/context/quantization/cloud/Stage-1 decisions, DEV/EVAL identities and states, receipts and referents, seeds/temperature, FORMAT routes, scorer/rubric identity, schema/privacy policy, hardware plan, runner/scorer hashes, validation evidence, unavailable R_0_6, and 13 explicit final-freeze dependency records.

The builder/verifier checks schema, detached manifest hash, all 52 listed file hashes, governing sources, and nested path/hash links. Two builds produced identical bytes. The detached hash avoids self-reference. `execution_authorized` is false. Verification is not permission to run either a neutral smoke or scored cell.

## 21. TEST RESULTS

The final new suite passed **55/55**, with no skipped tests. Existing planner/experimental contract tests passed **30/30**. Original Ask CLI, revised Ask CLI, calibration, Run06, Run06a, and Run06b deterministic selfchecks passed. Run06a's data-backed checks were also run explicitly with isolated argv after the initial regression driver's `--out` argument had caused those optional checks to skip; that driver was corrected. Ruff check and formatting check passed.

Coverage includes stable cell hashes, exact R_CONTROL parity plus independent diagnostics, hard unavailable R_0_6, failures/no retries, no substitution/context reduction, distinct trials, deterministic transports, thinking/KV identity, receipt incompleteness/tampering/privacy, fidelity co-occurrence, matched per-question contrasts, Wilson edge cases, DEV/EVAL separation, read-only DB enforcement, reproducible lexical receipts, and freeze hash/link validation.

Zero-inference evidence is structural and process-local: no live delivery path; network/DNS/subprocess denial within guarded workloads; model-library import and production inference-entrypoint traps; synthetic-only runtime/scorer fixtures; and command/source review. Four deliberate new-suite guard probes were blocked. Existing regressions recorded four blocked subprocess attempts and zero network/model-entrypoint denials; command details for those subprocess probes were not captured, and none executed. The initial import guard caught transitive model-runtime definitions, prompting the direct-source planner loader; no weights or models were loaded.

The final protected-input check found **zero changes among 57,473 baseline files**, including production source, governing documents, project configuration, and the git index. Frozen source DB and private corpus-copy hashes remained unchanged. This does not claim host-wide network surveillance or make assertions about unrelated processes. Test and integrity evidence is in `frozen/validation_receipt_v0.json` and the private bundle.

## 22. REMAINING OPEN FREEZE VALUES

1. Accepted R_0_6 and its full specification/prompt/schema/code/test/acceptance handoff through the authorized dependency chain.
2. Human replacement decision for the failed negative-control domain, followed by a newly declared deterministic qualification procedure; no automatic replacement.
3. Genuine human referent review, including draft interpretive categories and any scientific expectations.
4. Per-question fidelity/relationship/operation/construct floors and explicit approval of numeric validity/completion promotion thresholds; historical proposals are not silently promoted.
5. Material-interaction/equivalence criteria before semantic outcomes.
6. Semantic output-budget policy after R_0_6 exists: common sufficient cap preferred; package-specific mechanically necessary envelopes belong to the package estimand.
7. Exact locally acquired weight SHA256/header verification.
8. Runtime executable, tokenizer/template, allocation, cache, placement, and neutral-mechanical receipts.
9. Semantic Qwen3 thinking policy; only the neutral path is currently fixed disabled.
10. Finalist hardware availability and actual configuration receipts.
11. Frozen downstream task packets and compatible package contracts for context, source-fidelity, coverage, and terminal work.
12. Gemini bounded call inventory and separate egress/execution authorization.
13. Final execution freeze and separate authorization to execute the semantic benchmark once.

These dependencies are explicit; non-semantic readiness must never be paraphrased as “the only thing left is R_0_6.”

## 23. WHAT WAS NOT RUN

Zero candidate model calls, zero scored semantic inference, zero neutral Stage-1 inference, zero Gemini calls, zero embedding/NLI model inference, zero candidate weight downloads, zero model loads, and zero empirical candidate latency benchmarks. No Stage 2, production Ask change, managed-local configuration mutation, migration, claim-arm adjudication, sealed-key inspection, R_0_6 implementation/freeze, preregistration edit, staging, or commit occurred.

All provider-shaped observations and new scorer outputs were synthetic. The real-data operation was the deterministic read-only lexical audit, not inference or semantic evaluation. Existing regression selfchecks reused their historical fixtures without running models.

## 24. EXACT READY_FOR_R_0_6 STATUS

The runner/adapters/scorer/receipt infrastructure is prepared for eventual R_0_6 integration, and outcome-independent choices are frozen or explicitly represented as final-freeze dependencies. The infrastructure does not certify model mechanical admission, semantic answerability, product viability, or release readiness.

The final status is **partial readiness** because the approved absent-corpus negative-control slot could not be frozen under the declared procedure. This is an explicit held-out content blocker, not a failure of the runner or a model-capability verdict. Positive referent review and the other parallel final-freeze dependencies remain enumerated and enforced. No replacement is fabricated to obtain a stronger status.

## 25. NEXT AUTHORIZED DECISION REQUIRED

The next held-out decision is a human replacement domain for the failed negative control. Genuine human referent review and the blinded claim-representation adjudication can proceed independently. None of those decisions alone authorizes acquisition, Stage-1 inference, R_0_6 integration/acceptance, or semantic execution; the previously specified separate gates still apply.

The current task's authorized infrastructure implementation is complete, with the explicit domain blocker preserved and no semantic result observed.

PARTIALLY_READY_FOR_R_0_6  EXPLICIT BLOCKERS REMAIN
