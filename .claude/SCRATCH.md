# SCRATCH - current Callosum Ask / evidence arc

Private operational handoff for Claude and Codex. Keep this file small.

## Ask 0.7 E2E lane - first two scored AIB runs COMPLETE; awaiting Cliff's review (2026-09-24)

**Read this first; the older lanes below are historical. No inference is pending. Do not start T1-T4, built-env, LLD, or Wave 2 without Cliff's go-ahead.**

* Worktree `.claude/worktrees/ask-e2e`, branch `experiment/ask-e2e`, local-only (no push). Tags: `e2e-substrate-v1` = `c58faff6` (harness ready), **`e2e-substrate-v2` = `6d863121`** (T5 -> T5*; the exact code both scored runs used). Docs in `experiments/ask_cli_revised/`: `E2E_RESULTS_AIB_T0_T5S.md` (results, aggregates only), `E2E_HARNESS.md`, `E2E_READINESS.md`, `E2E_TOPOLOGY_PLAN.md`.
* Done: **T0** (repaired Q2.5 baseline: W/R Qwen2.5, C det, P legacy) and **T5\*** (W qwen3.5:9b `think:false`, R off, C phi4:14b, P gemma3:12b; CLI key `T5`, manifest name `T5*`). T0 vs T5* is a system-level contrast (worker, R/C architecture, planner, recovery budget all differ), never a causal estimate for one model.
* Key facts: T0 = 0 source-verified claims (Q2.5 claims have exact quotes but ~0 NLI support; gate discards 82-95%). T5* = 14 source-verified claims (11 anchors, 5 papers); phi4 judged 6/6 items responsive, every claim attached to the item it was retrieved for (anchoring possible, unadjudicated); P/gemma recovery and C2 were never exercised (no unresolved items).
* Next decision (Cliff): review the results + the private 15-item blinded adjudication sheet (`ask-e2e/.local/e2e-runs/scored/adjudication/`, key file alongside), then decide whether/which of T3 or T4 to run (same Qwen3.5 worker, so they isolate R/C/P; they are the only arms likely to leave gaps for P to act on).
* Run one arm: `python -m experiments.ask_cli_revised.e2e --profile T0..T5 --question aib|lld|builtenv --db <library copy> --out <private dir under ask-e2e/.local/e2e-runs/> [--juno-sampler] [--smoke]`. Library copy `<ask-cli-staged-synthesis worktree>/.local/ask-060-fix-run/library_copy.sqlite` (frozen fingerprint beside it, read-only). Q2.5-bound arms (T0-T1) need `CALLOSUM_APP_DATA_DIR` = that worktree's `.local/dev-app-data-juno-tunnel` (never print `auth-token`); T2-T5 do not. A scored run refuses a dirty tree, drifted contracts, or a drifted library copy; retry only clearly transient infrastructure failures (fresh out dir, same SHA); library drift = STOP.
* JUNO: both tunnels and both Ollamas (isolated 0.34.3 :11435, shared 0.12.3 :11434) are up and idle - leave them. `juno.ps1` runs under `pwsh`.

## Governance

- Assume a fresh agent chat. Do not rely on inherited conversation context.
- Read SCRATCH once at task start and once at handoff.
- Prune stale entries immediately. Durable history belongs in committed reports / increment notes.
- Prefer targeted reads. Do not replay project history unless a named artifact is missing/stale.
- If scope expands materially, STOP and hand back.
- For long jobs, poll sparsely: about 33% / 66% / 99% of expected duration unless a better completion signal exists.
- Verify the final SCRATCH write persisted on disk.

## Current repo / release

- Main repo: `C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum`
- Published and installed Desktop: **v0.5.8**
- v0.5.8 target: `d6a85d5da5e3a4113ddf51bd9f7952fe1b0baba7`
- inc 581 Ask planner/hygiene is included in v0.5.8.
- Next planned public cut remains 0.6.0 after today's Ask work.

## Critical locations

- Demo DB: `C:\Users\cliff\callosum-data\library.sqlite`
- Demo launcher: repo-root `run-callosum.ps1` -> uvicorn `:8888`, no `--reload`.
- Rebuild frontend after UI changes: `python tools/build_frontend.py`.
- Demo H1a: **23,875/23,875 article chunks current, 0 stale**. Do not rerun backfill without a new reason.
- Codex Ask worktree: `C:\Users\cliff\AppData\Local\Temp\callosum-codex-ask-baseline-20260907`
- Codex branch: `codex/ask-preimplementation-baseline-20260907`
- Frozen baseline DB: `...\.local\ask-next-day-acceptance\baseline.sqlite` in that worktree. Keep frozen; use copies for new runs.

## Durable Ask artifacts

In the Codex Ask worktree unless noted:

- Frozen Gemini OLD-vs-NEW: `.claude/docs/research/2026-09-07_ask-old-new-acceptance.md`
- Frozen Local AI replication prereg: `.claude/docs/research/2026-09-07_ask-local-model-replication-preregistration.md`
- Local AI descriptor diagnosis: `.claude/docs/research/2026-09-07_local-ai-descriptor-provenance.md`
- Verification next-increment research (main repo): `.claude/docs/research/2026-09-07_ask-verification-next-increment.md`
- CLI staged-synthesis experiment scoping REV 2 (main repo): `.claude/docs/research/2026-09-07_ask-cli-experiment-scoping.md` — the architecture spec.
- CLI staged-synthesis experiment **BUILT + FIRST FROZEN RUN COMPLETE** — branch `experiment/ask-cli-staged-synthesis`, head `6b4b8d9` off main (NOT merged/pushed). `experiments/ask_cli/` (outside `app/`, zero production changes; runs on a DB copy). Invoke `python -m experiments.ask_cli --db <copy.sqlite> --out <dir>`; needs Qwen (`python tools/run_local_ai.py` + export `CALLOSUM_APP_DATA_DIR=<repo>/.local/dev-app-data`). `python -m experiments.ask_cli.selfcheck` green. Run artifacts were under `experiments/ask_cli/runs/` (gitignored, hold library text — inspected then left local). Qwen server + llama-server reaped; descriptor cleaned; demo `:8888` untouched.
  - **Postmortem (frozen run, ~42 min, 1 degraded subquestion, 4 props → 2 verified):** master failure = **Qwen Stage-1 decomposition** returned a JSON *object* not the required *array* → validator rejected → frozen fallback (0 obligations) → coverage trivially "unanswered", gap-recovery a no-op. **Deterministic S2/S4/S5 worked** (nominated paper 67 = Workman's own anomalous-is-bad paper; **evidence-anchor≠retrieval-anchor demonstrated**; context grew). **Qwen S6 extraction weak:** 3/7 dropped `quote_not_verbatim` (paraphrased); the 2 that verified are **front-matter noise** (a correspondence address + a keywords line — trivially self-entailing); the one real amygdala finding landed **weak** (ret=0.70 boundary — the retrieval-gate FN class again). **Terminal fork is the headline:** given the SAME impoverished sealed ledger, **Gemini honored it** ("evidence does not contain…" + honest gap list) while **Qwen fabricated** domain facts not in the ledger ("fear of the unknown", "evolutionary mechanisms"). Clean model-vs-pipeline separation, exactly as designed. **First-run freeze honored — no prompt/threshold tuning.** Pass-2 items (in the scoping report §23): tolerate a single-object decomposition response / decompose S1 further; strengthen S6 verbatim adherence; the retrieval-gate boundary recurs.

## Ask invariants

- inc 581 implementation commit: `5ddb321f5a9374d8258234562da4b0781c965d1a`.
- Broad Ask: breadth gate -> planner -> facets -> H1a hygiene/diversity -> facet-local generation -> one batched verifier -> verified-first assembly -> honest coverage.
- Narrow Ask stays on legacy path.
- Verifier unchanged: retrieval 0.70, exact quote 1.0, support 0.55, contradiction 0.55.
- Coverage/retrieval failure never means library absence.
- Do not rerun/tune the frozen Gemini acceptance.

## Closed verifier experiment - DO NOT IMPLEMENT

Proposal to remove `retrieval_confidence` from VERIFIED failed its preregistered gate.

- Complete flip universe: 12 rows -> SUPPORTED 10 / UNSUPPORTED 1 / UNRESOLVED 1.
- Counterexamples: mapping 285 / chunk 32651 and mapping 269 / chunk 32651.
- Conclusion: whole-chunk retrieval causes false negatives but also blocks a real NLI subject/scope false-positive class.
- `verification.py` remains unchanged.
- Do not revive wholesale removal without a new labeled validation design.

## Claude current lane - inc 582 responsiveness band → DONE (awaiting Cliff)

**Verified finding vs verified "study context" presentation layer — IMPLEMENTED, tests green, live-verified,
committed. NOT pushed. main untouched (still `d6a85d5`), so 0.5.8 is unaffected.**

- Branch `inc-582-responsiveness-band`, commit `f3dbb6c` (10 files: `summarization/responsiveness.py` +
  faceted/response/frontend threading + `20b_summary_groups.jsx` + tests + increment notes + research report).
  Merge to main is Cliff's call (branched deliberately to isolate from the in-flight 0.5.8 release).
- Presentation only: no verifier/status/threshold/prompt/schema/retrieval/provider change; rides
  `scope_ref_json`; narrow Ask unaffected. Classifier is pure, claim-semantics-only, fail-open.
- Ship gate CLEARED: 80 real verified claims across 3 disjoint artifacts → 0 false descriptive demotions
  (frozen SHA `339d11fc…`). Live broad Ask on an isolated demo-DB copy (`:8899`, torn down; `:8888` untouched):
  labels flow end-to-end, Findings/Study-context/Flagged grouping correct, 0 backend errors.
- Full narrative: `.claude/docs/increment-notes/INCREMENT-582-NOTES.md` (incl. a NEXT-ARC pointer:
  answer-obligations/contracts over topic facets — documentation only, not started).
- Responsiveness band was the approved slot; the retrieval-gate removal remains the CLOSED experiment above.

## Codex current lane - post-0.5.8 Local AI + frozen Qwen

0.5.8 is installed. Historical 2048 blocker was old v0.5.7 state, not a post-575 regression. **4096 remains required.**

**Qwen OLD-vs-NEW is still unrun.**

Next Codex task:
1. Validate supported Desktop 0.5.8 Local AI path:
   - installed 0.5.8
   - retained model assets reused
   - descriptor `max_output_tokens=4096`
   - llama-server `--n-predict 4096`
   - unmodified validator accepts
   - Local AI reachable from Desktop
2. If and only if validation passes, run frozen Qwen **OLD once -> NEW once**.
3. Reuse frozen query/corpus/protocol. No tuning. Retry only genuine technical failure.
4. Treat Qwen OLD-vs-NEW as primary. Gemini-vs-Qwen is descriptive because provider affects planning and generation.
5. Freeze metrics/failure inventory and STOP.

Do not hand-edit descriptor, delete model assets, bypass validation, rerun Gemini, or broaden into verifier research.

## Standing boundaries

- H1c-A2 packet remains sealed. Do not open.
- H1c-A3 worktrees/DBs are DO NOT TOUCH during Ask work:
  - `C:\Users\cliff\AppData\Local\Temp\callosum-codex-h1c-a3-census-20260906`
  - `C:\Users\cliff\AppData\Local\Temp\callosum-codex-h1c-a3-replication-20260907`
- No general adjacent-chunk merging.
- Assembled evidence is never one quote.
- A3 is validation/refinement, not a permission gate for Ask shipping.

## Ownership now

- Claude: finish inc 582 responsiveness work.
- Codex: validate 0.5.8 Local AI, then frozen Qwen OLD-vs-NEW.
- Do not duplicate the other agent's lane.
- When a lane finishes, move durable details to its report/increment notes and prune SCRATCH back to current operational state.

## Codex controlled verified-cap repeat — COMPLETE 2026-09-09

- Explicit user authorization allowed ONE Gemini repeat as an exception to the standing no-rerun rule; exhausted. No further rerun/tuning authorized. Other lanes above unchanged.
- Frozen acceptance NEW case (historical summary 9), exact question SHA256 `f399387564e6ab502bee4419f67026b9cecae06a31346fedfaf3f331f00cd6be`, saved six-facet plan. Gemini wire / `gemini-2.5-flash-lite` request and returned model_version; unchanged defaults. **6 generation calls**, no planner/overview/control/retry calls.
- Actual acceptance source `C:\Users\cliff\AppData\Local\Temp\ask_acceptance.sqlite` (226 total/216 live, schema `0081_source_representations`), NOT the earlier 229-paper baseline. Read-only SQLite backup; source before/after SHA256 `1838474db3b518551446cabdda81a689fcbaf313a0d8796cab57bb1779031746` unchanged. Baseline and H1c untouched.
- Private artifacts: `C:\Users\cliff\AppData\Local\Temp\callosum-cap-repeat-20260909-022214` (`repeat.sqlite`, harness, full pre-assembly/retrieval/provider captures, receipt, report, hashes). Copy initial SHA256 `5efff6a35e493cd7f9a94faa8dc0e50c4f1389e4c9e2ebc6cf72216378728dd5`.
- HEAD `6b4b8d9084da2131dc4cc8160c0bf6c37a486867`, branch `experiment/ask-cli-staged-synthesis`; frozen module hashes match. No source/test changes, migrations or commit.
- **VERIFIED CAP NOT EXERCISED**: generated 27 / verified 12 / flagged 15; all 12 verified retained, zero verified excluded. Per-facet verified 1/1/3/1/3/3. 29 local NLI rows, zero embedding fallback. No blinded semantic review because gate did not open.
- SHA256 pre-assembly `93e30ec339a2cbe5004ecdb4557229ee2208f06d004b47059b1602256e97ea8f`; receipt `66ff4a1391e40e3d950a601d4993db066f78266e0314f12d62470fa0a91a2ef6`; report `02e37a2f4eda88270997e6c0541ed0308d1df6d48498ebdc89a8870b699bb7dd`. Full safe manifest in `hashes.json`.
- Next unresolved decision: semantic loss conditional on verified overflow **remains untested**; this repeat supplies no affirmative evidence for further investigation. Stop; no implementation proposed.

## Claude A/B/C missing-A-cell — production plan_query on frozen questions — COMPLETE 2026-09-09

- **Task COMPLETE.** Filled the missing "A" cell: ran UNMODIFIED production `query_planner.plan_query` on the two byte-identical frozen questions (q_aib `6e037bab…`, q_builtenv `36e4623e…`; both raw==trimmed). Read-only repo; no source/test/experiment/descriptor edits. HEAD `6b4b8d9`.
- **Model identity (strong):** same JUNO Ollama tag `callosum-managed-local`, GGUF blob `sha256-6a1a2eb6…` == `EXPECTED_PREVIEW_MODEL_DIGEST` (byte-identical artifact Run 0.6 used), qwen2 / 1.8B-reported / Q4_K_M, ctx 12288 / seed 42 / temp 0, RTX 3050; reached via detached SSH forward to JUNO loopback ollama (tunnel reaped, port closed, scratch descriptor+token deleted). Runtime is Ollama (embeds llama.cpp), same as Run 0.6 — documented caveat, no identity conflict.
- **Call count (exact):** infra=1 (neutral preflight) + planner=2 (one per question). Bare production contract (no json_schema/response_format); prompts byte-identical to `_planner_prompt`.
- **HEADLINE:** production `plan_query` → **NARROW, 0 facets for BOTH** questions → broad faceted pipeline never engages; falls to single-vector `summarize_scope`. q_aib self-classified `"narrow"` + echoed the schema placeholder as its query; q_builtenv emitted 6 on-topic queries but a malformed envelope w/ no `scope` (+ a well-formed-but-empty broad block). Every source obligation STARVED (q_aib 13/13; q_builtenv 11/11), 0 invented. Matched A/B/C: A empty; B (q_aib) ~half + 1 invention; C preserved all units both. **A/C gap is confounded with structured-output enforcement (C added `response_format`, A sends none)** — not a clean source-anchoring causal estimate.
- **Decision:** evidence STRENGTHENS "production loses more request structure than source-anchored decomposition" for these 2 questions on this model (A produced *nothing* usable), but confounded by enforcement; whether the fix is enforcement, source-anchoring, or both is the next question — NOT designed here.
- **Artifacts (outside repo, no creds):** `…\claude\C--Users-cliff-…-callosum\0d92a5ec-6484-48fe-a016-5762ab44e412\scratchpad\askA\` — `REPORT_ask_A_cell.md` (`75a719f1…`), `plans.json` (`d5411423…`), `raw_calls.jsonl` (`48617249…`), `obligations.json` (`d969bae0…`), `frozen_inputs.json` (`b42b3711…`), `run_planner.py` (`2542ea86…`).

## Codex A1 response_format-only planner repeat — COMPLETE 2026-09-09

- Same A0 model confirmed: JUNO Ollama `callosum-managed-local`, tag `db5c42ae5c33…`, GGUF `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`; Qwen2.5-1.5B-Instruct / qwen2 / 1.8B-reported / Q4_K_M; ctx 12288/temp 0/seed 42. RTX 3050; /api/ps verified full model residency in VRAM. Unmodified descriptor loader accepted; same A0 placeholder-runtime-digest caveat.
- HEAD `6b4b8d9084da2131dc4cc8160c0bf6c37a486867`; planner SHA `2ceafab…`, query-planner-v1 unchanged. A0 artifact hashes, raw/trimmed question hashes, and byte-identical A0/current prompts verified before calls. Captured actual production wire body plus ONLY response_format field; no code/parameter/prompt changes.
- Schema preserves production's explicit narrow/broad choice (forcing broad would add semantic policy); label/query strings and JSON envelope enforced, 3..6 usable-facet validation left to unmodified parser. No repair/retry.
- Calls: infra **1**, experimental **2** (q_aib then q_builtenv). Both A1 whole-document JSON parseable, nontruncated, scope=narrow, thus final NARROW/0 facets. A0 q_aib parser-narrow + malformed trailing output → A1 parser-narrow with 3 rejected raw entries; A0 q_builtenv missing-scope validation failure → A1 explicit parser-narrow with 1 rejected raw entry. Narrow nonempty-facets still violates prompt wording. No broad semantic matrix: gate did not open.
- Headline causal result: shape enforcement succeeded in these two calls but recovered **0/2** broad plans. Remaining failure is scope selection/instruction fidelity; no proof Facet representation caused it. B/C remain descriptive only.
- Private directory `C:\Users\cliff\AppData\Local\Temp\callosum-planner-A1-20260909-033058`. Report SHA256 `7accdef739cc7b46c6eb3c464eae08ca1137670cd2ee456bcc131c7949497d50`; plans `1a0606ca86b067614b2f00762b695d805341f13bdd5e30db0668133295216104`; schema `dcf3a5ebc5bc7da52dab733891bb030619d900070f69ec278cf09e5f35480789`; full manifest `hashes.json`. Source A0 copies/referent unchanged.
- Cleanup complete: descriptor/token deleted, detached tunnel reaped, port 11434 closed. No DB/source/test modifications or commit. Next live question: **semantic request representation**, specifically scope-decision fidelity; valid-broad preservation remains unanswered. Stop; no implementation proposed.


## Codex A1 scope-only counterfactual audit — COMPLETE 2026-09-09

- Provider/model calls = **0** (infra/experimental/judge all 0); pure current _plan_from_payload only, no plan_query/provider access, JUNO/tunnel, retrieval or code/test changes. HEAD 6b4b8d9; planner SHA 2ceafab65133225e711fb23c49cfebdd711cb03a8e040a53e8658927755f079f unchanged. All 21 A1 manifest hashes, six A0 originals/copies and both C item hashes verified.
- Scope narrow -> broad was the ONLY payload change; canonical non-scope bytes and raw-whitespace-preserving substitution assertions passed. **q_aib VALID_BROAD / 3 unchanged accepted facets**; **q_builtenv NARROW / 0 accepted**, independently fails 1 usable facet < MIN_FACETS=3.
- Fidelity rescue is **PARTIAL for q_aib**: whole-facet semantic tally 2 preserved / 4 drifted / 7 starved (query-only sensitivity 1/5/7), 0 invented. **Fails for q_builtenv**: invalid plan; separate raw-content tally 2 preserved / 9 starved, 0 invented. Scope explains both original early returns but cannot fully explain failure to obtain faithful broad plans. C comparison descriptive only; source retention is not perfect rewrite fidelity.
- Private artifacts: C:/Users/cliff/AppData/Local/Temp/callosum-planner-A1-scope-audit-20260909-103118. REPORT_scope_counterfactual.md SHA256 61e76963163aac7fd7315591ad69e87fc85cc2e4e94a38eb20f3739fd916108b; results.json 3edfc2be6be62f5ee4922ea5945b47c0bac76d383426bca66655702475139cae; full safe hashes.json and replayable audit.py.
- Next decision: evidence supports a controlled deterministic-broad/model-only **3–6 facet** experiment, not run/designed. User's literal **36 facets** is not supported by this audit/current MAX_FACETS=6; report explicitly distinguishes the possible missing dash. No staging/commit. Other lanes and Claude notes preserved.


## Codex A2 deterministic-broad / facet-only — COMPLETE 2026-09-09

- User clarified **minimum 3 / maximum 6**, never literal 36. Both current breadth gates True; frozen raw==trimmed question hashes and 46 prior artifact hashes checked. Frozen 13/11 inventories unchanged (built-environment fine-grain provenance caveat retained). HEAD 6b4b8d9; planner 2ceafab65133225e711fb23c49cfebdd711cb03a8e040a53e8658927755f079f unchanged.
- Same JUNO Ollama 0.12.3 / callosum-managed-local / Qwen2.5-1.5B-Instruct Q4_K_M, GGUF 6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e; context 12288/temp 0/seed 42, RTX 3050, full VRAM residency. Unmodified descriptor loader accepted; historical placeholder runtime-digest caveat retained.
- Calls: **infra 1 + experimental 2**, q_aib then q_builtenv; no inference retries. Local setup failures before provider access disclosed in report. Three minimal prompt substitutions + response_format fixed broad/3–6; template frozen before calls. Both schema-valid, non-provider-truncated, **BROAD / 3 generated / 3 accepted**, three spare slots each.
- **q_aib: VALID BUT SEMANTICALLY LOSSY**. Accepted whole P/D/S **2/8/3**, query-only **0/10/3**. Exact bias identity survives only in labels; query F1 **312→200 characters** cuts personality/scales. Strict relationships **0/7 faithfully preserved** (3 explicit but drifted, 1 endpoints-only, 3 starved). Zero wholly unanchored facets; 3 queries have partial unsupported additions (one qualifier flag interpretive).
- **q_builtenv: VALID BUT SEMANTICALLY LOSSY**, much stronger topic fidelity: whole **10/1/0**, query **9/2/0**. All named interests and fMRI+EEG retained. Area→role mapping preserved only with charitable label credit; query-only drift. Open-ended scope lost. Operations faithful **4/5 whole, 3/5 query**. Zero inventions. No averaging with q_aib; C comparison descriptive, source retention distinguished from rewrite/query fidelity.
- Private artifacts: `C:/Users/cliff/AppData/Local/Temp/callosum-planner-A2-20260909-105909`. REPORT_A2.md SHA256 `9abb31b226addc954689aeb0d2e28360569bd4b5c965f498ac141475c9820c8e`; frozen-facets.json `29483fd8538ebe168cec7953102342dde51c0cbacbd92b5ae074119dfaf7a8cc`; semantic-matrices.json `cc5e22760052019ee40b025c53914f1a1a3a0b9f0a4fdfe0c53eadee6461c374`; full safe hashes.json. Includes exact prompts/diffs/schema/wire/raw/validation, both matrices, relationships, budget and C sensitivity.
- Descriptor/token removed, tunnel reaped, 11434 closed; 845 source files and git status unchanged before handoff. No retrieval/verifier/tests/DB/source changes/staging/commit. This entry is the only repository write. Claude notes preserved.
- Next unresolved decision: q_aib **strengthens** the case for higher-fidelity/source-anchored request representation; q_builtenv **leaves necessity unresolved** (named-topic case weakened; role/open-scope concern remains). Six-facet ceiling was not hit; intrinsic impossibility and causal necessity unproven. No implementation designed; stop after report/handoff.


## Codex A3 operation-aware facet generation — COMPLETE 2026-09-09

- Frozen A2 control not rerun; 87 prior hashes and both raw==trimmed question hashes verified, current breadth gates True. Same 13/11 referents/provenance caveat. HEAD 6b4b8d9 / planner 2ceafab65133225e711fb23c49cfebdd711cb03a8e040a53e8658927755f079f unchanged. Only generic facet-guidance replacement; same 3–6/schema/wire except prompt. A3 template SHA 00e28b3adebb5c0250b45629aed937ba67d225b097f6db8851d7ace832ea14f7.
- Same JUNO Ollama 0.12.3 / callosum-managed-local / Qwen2.5-1.5B-Instruct Q4_K_M, GGUF 6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e; ctx 12288/temp 0/seed 42, RTX 3050 full VRAM. Unmodified loader accepted; prior placeholder runtime-digest caveat retained. Calls **infra 1 / experimental 2**, q_aib then q_builtenv, no inference retry. Local pre-inference setup corrections and connection-helper logging deviation disclosed in report; no credentials in saved artifacts/handoff.
- **q_aib PARTIAL IMPROVEMENT; MATERIAL LOSS REMAINS**: A2→A3 whole P/D/S **2/8/3→4/7/2**, query **0/10/3→2/9/2**. Strict relationships whole **0/7→2/7**, query **0/7→0/7**; gains depend on intervention label. Exact query target **0/3→2/5**. Generated/accepted 5/5, spare 1, no cutoff. Scales/cultural measurement absent; unsupported neuroticism now accepted.
- **q_builtenv DEGRADED**: whole **10/1/0→5/5/1**, query **9/2/0→5/2/4**. Operations **4/5→0/5 whole, 3/5→0/5 query**; area-role **1/1→0/1 whole, 0/1→0/1 query**. Named-interest vocabulary retained but domain absent from all 4 queries (A2 3/3 domain targets); identity/role separated. Non-degradation FAIL: domain-specific topic fidelity and operations degraded, lexical interest coverage unchanged. Generated/accepted 4/4, spare 2, no cutoff.
- Unsupported-answer substitution diagnostic (existing obligations, retrospective A2 count distinguished from broader subcontent flags): AIB **3→1** accepted obligations / **2→1** queries with examples; built-environment **0→0**. Fewer substitutions does not rescue absent open requests. Zero wholly invented facets; qualifier/attachment flags separately retained.
- Private artifacts `C:/Users/cliff/AppData/Local/Temp/callosum-planner-A3-20260909-113329`. REPORT_A3.md SHA256 `a891980df05b9898597f3691eaaca180cc2e23cf7407c53c94f5e799fdafa75e`; frozen-facets.json `ff5f62a44bd991001450a65fe612099e1a8606ea8bfd83bf82e138cf4776052f`; semantic-matrices.json `108cecd41b189bd8ecf71a6a6ec2805d43cafbf27a40469753623b8202e72ff1`; full safe hashes.json. Includes exact diff/schema/raw/wire/validation, matrices and all requested audits. Output frozen before scoring.
- Higher-fidelity/source-anchored representation case **strengthened empirically**, necessity unresolved; limited AIB gain trades against built-environment domain/operation loss in these two draws. No global success or intrinsic impossibility claim. H1 multiplex decomposition + assembly/dedup and H2 corpus-relative specialist-term salience are **UNTESTED future hypotheses only**, neither endorsed nor tested; rarity != importance.
- Descriptor/token deleted, tunnel reaped, port closed; 845 source/test/experiment files and git status unchanged before handoff. No retrieval/verifier/tests/DB/code edits/staging/commit. Prior Claude/Codex notes preserved. Stop after report/handoff.


## Codex frozen A2+A3 multiplex union audit — COMPLETE 2026-09-09

- Provider/model calls **0**; local frozen-artifact inspection/manual semantic adjudication only. No JUNO/tunnel, parser/provider, retrieval/verifier/tests, code changes, dedup/assembly, staging or commit. Branch experiment/ask-cli-staged-synthesis / HEAD 6b4b8d9084da2131dc4cc8160c0bf6c37a486867. All 89 A2/A3 final-manifest hashes + 8 facet-freeze entries match; exact unchanged 13/11 referents. Accepted text/order/provenance retained; unions/rules hashed before scoring.
- **q_aib: LITTLE OR NO MULTIPLEX BENEFIT.** 3+5=8 facets; union whole/query P/D/S **4/7/2; 2/9/2**, exactly A3. Strict relationships **2/7 whole; 0/7 query**. Unique faithful obligations A2/A3: **0/2 whole, 0/2 query**. No gain beyond stronger packet; scales/cultural measurement still starved.
- **q_builtenv: LITTLE OR NO MULTIPLEX BENEFIT.** 3+4=7 facets; union whole/query **10/1/0; 9/2/0**, exactly A2. Frozen operations **4/5 whole; 3/5 query**, area-role **1/1 whole (prior charitable A2:F2 credit); 0/1 query**. Unique faithful A2/A3 **5/0 whole, 4/0 query**. Open scope remains drifted.
- Contamination accumulates without gain beyond stronger run: AIB **4 answer-substituted obligations / 3 queries** (A2 behavior/attitude examples + A3 neuroticism), plus qualifier/target corruption; built-environment adds **2 lexical corruptions / 4 domainless A3 queries**. Zero wholly invented facets. Coverage never erases unsafe subcontent.
- All **27 cross-run pairs** manually classified; overlap **10 AIB / 12 built-environment**, including different-binding **7 / 10**. No removal. Different drifted fragments do not reconstruct requested edges. Existential frozen scoring precludes two drifted facets synthesizing a preserved obligation; packet-level complementary faithful sets also absent here.
- Private artifacts: `C:/Users/cliff/AppData/Local/Temp/callosum-multiplex-union-audit-20260909-115414`. REPORT_UNION.md SHA256 `f830cb5f080a3c18b7cefe3775a2028e51a978bfec24df0e7f792a6a4961bc0b`; union q_aib `9d12cf94b28b53054ff80f258ccca223531c099bd2e21682891df519c3b74a99`; union q_builtenv `43d7959f51ee200693489ff778acb7fe9f9dd8d8e6dd6ebce8c82aea934fc9a1`; full safe hashes.json, all matrices/audits/report included.
- Multiplexing **did not gain empirical support** on within-question faithful preservation; case weakened for both frozen questions, broader usefulness unresolved. Across-question framing trade-off is not within-question complementarity. **Safe assembly/dedup is NOT established as the next live question** by these results. H1 multi-strategy and H2 corpus-relative specialist salience retained untested, not endorsed. Prior Claude/Codex notes preserved. Stop after report/handoff.


## Claude 0.7.0 local-orchestration feasibility study — COMPLETE 2026-09-09

- **COMPLETE.** Research + report only. No code/experiment/benchmark/download/migration/Ask-CLI change; no
  provider/model calls; read-only repo except the report file + this handoff. Nothing staged/committed.
  Report: `.claude/docs/research/2026-09-09_local-orchestration-feasibility-study.md` (18 sections + 10-Q
  appendix + sourced). Private working notes outside repo (scratchpad `orch07_notes.md`).
- **HEADLINE HARDWARE:** core population (research-active academics) baseline has moved to **16 GB** —
  institutional standard configs are 16 GB (Dell Pro Ultra 7 16/512; MacBook Air/Pro 16 GB) [PROCUREMENT
  PROXY]; new Apple Silicon is **16 GB-minimum at M4** [DIRECT DATA]; replacement cycle **4–5 yr**
  (established, not assumed) → institution machine in service = 2021–2025 purchase, far above the weak
  laptop that set 1.5B. Accessibility floor (8 GB / integrated-GPU / older) is real and kept as a fallback,
  not a cap. Population device *census* = [UNKNOWN] (no first-party telemetry).
- **JUNO CALIBRATION:** architecturally *different* per axis, not simply avg/better/worse. GPU-**above**
  the typical (integrated-graphics) research laptop but **below** M-Max/≥12 GB discrete; CPU (i7-8700, 2017)
  **below** modern Core Ultra/M-series; 8 GB VRAM = fast-but-capped vs Apple's larger unified memory
  (different, not better). ~28 tok/s on a quantized 7B. Envelope: 1.7–4B fully in VRAM w/ big ctx; 7–8B Q4
  w/ reduced ctx (+Q8 KV; Qwen GQA helps); 12–14B needs slow system-RAM offload. NOT a proxy for Apple
  Silicon → sweep needs an Apple-Silicon reference.
- **REOPEN 1.5B?** YES — as a *tested hypothesis*, not a diagnosis. The hardware constraint that set 1.5B
  has loosened. BUT A0–A3 failures are **confounded (model × prompt × representation)** — do NOT treat them
  as a capacity verdict; the sweep must **cross model × representation** to attribute cause. Structured
  decoding (GBNF/Ollama) fixes JSON *shape*, not *completion* or *scope/semantics* (A1: response_format
  recovered 0/2 broad plans) — the strongest in-repo reason a bigger model *might* help the part grammar
  can't, stated as hypothesis.
- **CANDIDATE SIZE CLASSES:** worker ~1.5–4B (Qwen2.5-1.5B control; Qwen3-1.7B/4B; Phi-4-mini-3.8B;
  Gemma3-4B; Llama-3.2-3B; Ministral-3-3B). Orchestrator ~7–14B run where tier allows (Qwen3-8B/14B;
  Ministral-3-8B; Gemma3-12B; Phi-4-14B). Cloud orchestrator refs bounded (Gemini ± Claude/OpenAI) over the
  same sealed ledger. License note: Apache (Qwen3/Ministral) + MIT (Phi-4) bundling-friendly; Gemma/Llama
  custom licenses = user-download / legal review before bundling. Qwen included, NOT assumed winner.
- **BENCHMARKING JUSTIFIED?** YES. **DECISION: HARDWARE EVIDENCE SUPPORTS LOCAL-ORCHESTRATOR BENCHMARKING**
  — a controlled JUNO sweep (+ Apple-Silicon reference + a CPU/integrated floor ref), crossing model ×
  representation, measuring total runtime memory at real context (weights+KV+overhead, not GGUF size) +
  low-frequency latency, scored on the Ask control-plane tasks, first-run-frozen, pre-registered fidelity
  threshold. It's a decision to *benchmark* (cheap/reversible), NOT to commit an architecture, and it
  **retains small-local + focal-cloud orchestration as the accessibility-tier design**. NEXT STEP is a
  separately-approved sweep; nothing built here.
- Prior Claude/Codex notes preserved; Codex 0.6.0 Ask lane untouched. Standing boundaries (H1c-A2 sealed,
  A3 worktrees DO NOT TOUCH, frozen Gemini/Qwen acceptance) unaffected by this research lane.


## Codex/shared revised Ask CLI 0.6.0 bounded baseline iteration — COMPLETE 2026-09-09

- **COMPLETE (task), milestone verdict: IMPROVED BUT ONE MORE BOUNDED ITERATION JUSTIFIED.** Main worktree `C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum`; branch `experiment/ask-cli-staged-synthesis`, HEAD `6b4b8d9084da2131dc4cc8160c0bf6c37a486867`. Revised package was already untracked. Four existing experimental files changed + six new code/test/helper files; production/DB/schema untouched; no staging/commit. Claude 0.7.0 notes preserved.
- Integrated literal Run06 units + raw question/hash/offsets/full parent context; exact-source recovery; original-unit non-certifying coverage; offered-span catalog; default verbatim ledger renderer with resolving IDs/spans. Optional model outputs are UNVALIDATED candidates. No graph/multiplex/rarity/supervisor work.
- Frozen textual retention: q_aib 6/6 units and 13/13 referent obligations; q_builtenv 8/8 and 11/11 (prior fine-grain provenance caveat retained); q_depr 8/8; controls 4/4. Operations/open requests/identity retained in context; no generated request additions. All 26 units remain completeness-unresolved. Retrieval/evidence utility NOT measured; single-field mapping remains routing, not semantic completion.
- Historical terminal replay: same verified p1 + frozen offered-span catalog; p27 nonexistent and seven unsupported scientific/mixed prose blocks before -> one verbatim p1, valid paper/chunk/e1 ancestry, zero added scientific claims/aggregates after. Upstream tangential-heading limitation remains. 13 new tests, five existing selfcheck suites, 15/15 adjudication checks PASS. All provider/infra/judge/embedding/retrieval/verifier calls **0**; tokenizer-only max 152/256, no truncation. No JUNO session.
- Private artifacts `C:/Users/cliff/AppData/Local/Temp/callosum-revised-060-20260909-123636`: `REPORT_060.md` SHA256 `0b39c27e5e187714ed86e73bd79b0870f794e40300f220428091fc2a52533877`; `code-hashes.json` `307f9cdb2923ca2168d67d2cb0e0bcab5bebcafd36bab5eb6f81842b0a23fdbe`; final `replay-v2/receipt-hashes.json` `45b5fd0bc19479f032ed1c5dce3c91a12ea41c729ab36ac81be8c8c66fa701d3`. Includes before snapshot, review diff, frozen receipts, test logs, final hashes and handoff receipt.
- Next bounded 0.6 iteration: isolate established structured-output enforcement on frozen extraction cases, then bounded same-model evidence-yield/coverage validation. Main Qwen gate/select/claim still use ungrammared caps; no capacity/architecture verdict. **0.7.0 must beat:** same frozen questions/referents, no request/operation/identity loss or invented substitutions, all final proposition/span references resolving and zero unverified scientific additions (explicit union ancestry for any aggregate), independently assessed evidence coverage and depression non-regression with honest gaps and measured calls/latency. No 0.7.0 design performed here.


## Claude 0.7.0 local-orchestrator benchmark PREREGISTRATION — COMPLETE 2026-09-09

- **COMPLETE.** Precommitment/readiness-audit document only. No inference, downloads, code/Ask/0.6.0 changes,
  benchmarking, or architecture decision; no provider/model calls; read-only repo except the report + this
  handoff + a plan backup (`.claude/backups/plans/2026-09-09_local-orchestrator-benchmark-prereg.md`). Nothing
  staged/committed. **Report: `.claude/docs/research/2026-09-09_local-orchestrator-benchmark-preregistration.md`**
  (23 sections). Converts the feasibility study (`…2026-09-09_local-orchestration-feasibility-study.md`) into an
  execution-ready, first-run-frozen protocol.
- **READINESS VERDICT: READY EXCEPT FOR R_0_6.** Fully specified + runnable NOW for the R_CONTROL column across
  the model axis; only the reserved R_0_6 representation awaits Codex (§18). No model/runtime or design blocker
  (candidates are at worst UNKNOWN_REQUIRES_PREFLIGHT / ELIGIBLE_WITH_CONSTRAINTS — a no-score preflight, not a
  design gap). The interaction test (the design's whole point) needs R_0_6, so the full run can't conclude
  until it lands — R_CONTROL runs standalone meanwhile.
- **FACTORIAL SHAPE: MODEL × REPRESENTATION PACKAGE**, all else fixed (structured decoding + output budget held
  CONSTANT — they fix FORMAT, not the SEMANTICS/SCOPE variable under study). **Representations = R_CONTROL**
  (frozen production Facet{label,query}; obligations are EXTERNAL evaluation referents, not part of it) **+
  R_0_6** (RESERVED, Codex's strongest 0.6.0 rep). Estimates model-conditional-on-package, package-across-model,
  and interaction — NOT isolated prompt-vs-representation (bundled in a package).
- **R_SOURCE AUDITED AND OMITTED** (don't re-propose without a frozen, unambiguous, executable package distinct
  from R_0_6): audit found A2/A3 operate on the production **Facet{label,query}** planner (R_CONTROL family),
  while the source-anchored line (`experiments/ask_cli_revised/calibration/` Runs 0.5/0.6/0.6a/0.6b) is an
  upstream-only, STOPPED-for-review, still-adjudicating selection policy and the **ancestor of R_0_6** — a
  provisional R_SOURCE would be factorial-padding.
- **STAGE-0 roster:** worker ~1.5–4B (Qwen2.5-1.5B **control=ELIGIBLE, pinned/proven**; Qwen3-1.7B/4B,
  Ministral-3-3B, Phi-4-mini = UNKNOWN_REQUIRES_PREFLIGHT; Gemma3-4B, Llama-3.2-3B = ELIGIBLE_WITH_CONSTRAINTS
  [custom license → user-download] + preflight); orchestrator ~7–14B (Qwen3-8B/Ministral-3-8B, Qwen3-14B/
  Gemma3-12B [offload], Phi-4-14B [16K ctx] = ELIGIBLE_WITH_CONSTRAINTS); cloud refs Gemini(±Claude/OpenAI) =
  reference, NOT a hardware cell. None INELIGIBLE. No leaderboard-based cuts.
- **STAGE-1 screen size:** a SMALL frozen subset of real Ask control-plane tasks (5 item types: scope
  classify / obligation preservation / ≥1 relationship-operation / exact-construct / structured-output
  completion). **Eliminates on representation-INDEPENDENT mechanical/runtime grounds by default** (load fail,
  no complete valid structured output, catastrophic latency, crash); any SEMANTIC floor is
  representation-COMPLETE, conservative multi-item (one miss ≠ cut), and **R_0_6-gated** (no semantic
  elimination before R_0_6 exists) — this is the fix for interaction-test selection bias. Survivors not ranked.
- **STAGE-2:** survivors × {R_CONTROL, R_0_6} on JUNO (primary) at SHORT/REALISTIC(/STRESS) context; frozen
  q_aib(13)/q_builtenv(11) + a small pre-frozen held-out set (q_depr/controls are candidates); one run/cell,
  NO retries; metrics grouped fidelity/mechanical/performance/contamination, correctness ≠ performance, cloud
  latency = service-level only, no cloud memory comparison. Apple/floor = finalist-only replication.
- **FROZEN SUCCESS CRITERIA (numeric proposals, locked at freeze; priority preservation/contamination →
  mechanical → context-fit → latency):** contamination = **0** (hard gate, both questions, never averaged);
  structured validity+completion **≥99% / 0 retries**; obligation-preservation floor with Wilson lower bounds
  per question; realistic-context memory fit on ≥16 GB Broad Baseline; low-frequency latency budgets
  (B_worker ~few s warm, B_orch ≤ ~15 s warm). **Success is NEVER "beats Gemini"** — a slower/weaker-than-cloud
  local orchestrator can still pass. First-run freeze; mechanically-failed cell recorded, never silently
  repaired/rerun; "loads" ≠ "passes."
- **STILL REQUIRED FROM CODEX for R_0_6 (§18):** representation spec (package), byte-exact prompts/templates,
  schema(s)+decoding mechanism, confirmation it runs on the SAME frozen inputs (hashes), source/request-ancestry
  artifacts, obligation/coverage emission (distinct from the external referents), a hash manifest, its passing
  tests, a frozen 0.6.0 acceptance report (unambiguous provenance — the bar that disqualified R_SOURCE), and any
  known defects. Latest SCRATCH shows Codex 0.6.0 at "one more bounded iteration justified" → **R_0_6 not yet
  frozen (expected).** I did NOT inspect/interfere with the Codex lane; R_0_6 arrives as a handoff.
- Five methodological corrections from Cliff applied: (#1) Stage-1 interaction-bias guard; (#2) reframed as
  MODEL × REPRESENTATION PACKAGE with explicit identifiability limits; (#3) R_SOURCE provenance-audited →
  omitted; (#4) obligations kept OUT of R_CONTROL (external referents); (#5) cloud = same inputs/contract/scoring
  but not a hardware cell (service-level latency, no memory comparison). Prior Claude/Codex notes preserved;
  standing boundaries (H1c-A2 sealed, A3 worktrees DO NOT TOUCH, frozen Gemini/Qwen acceptance) untouched.

## Codex final bounded revised Ask CLI 0.6.0 acceptance — COMPLETE 2026-09-09

- **COMPLETE (task); IMPROVED BUT NOT READY — RESPONSIVENESS LIMIT REMAINS.** HEAD 6b4b8d9084da2131dc4cc8160c0bf6c37a486867 unchanged. Only experimental qwen.py selection contract + one new test file; no production/DB/schema/threshold/representation/renderer changes, staging or commit.
- **Stage A PASS:** 50/50 frozen selection treatments complete/valid, zero truncation/parse failures; three empty. Three pre-frozen matched controls; only response_format differs. Historical trace is 46/50 selection truncations (prior 47/50 report count corrected), 99/140 overall; old hash unchanged. Same JUNO Qwen2.5-1.5B Q4_K_M / GGUF 6a1a2eb6… / Ollama 0.12.3 / ctx 12288 / temp 0 / seed 42 / full RTX 3050 VRAM. Historical runtime-attestation caveat retained.
- **Stage B ran once q_aib → q_builtenv → q_depr:** selection 256/256 clean. AIB: 96 hit occurrences/16 unique, 4 verified (2 repeated claim strings), only one partial 13-obligation component, no verified 7-operation support; EBQ subject corruption verifies. Built: 128/36, 2 identical unrelated caption records; all 11 obligations/5 operations unresponsive. User confirmed AFTER freeze that library has no built-environment material: valuable negative control, not an inferred library-absence claim; frozen positive-yield criterion caveat recorded, no abstention design. Depression: 128/39, 8 verified (4 repeated strings), some responsive amyloid/risk evidence; retrieved null/uncertain findings lost downstream.
- Request fidelity 22/22 live, 26/26 deterministic; all original context/offsets/IDs and 12 operations retained. **Terminal 14/14 IDs/paper/chunk/spans resolve, zero renderer-added scientific assertions/aggregates; all unresolved units visible.** Upstream unsupported/qualified-loss ledger copies remain separate contamination. Gate 246/354 and claim 152/328 truncate; no tuning/retry or model-capacity attribution.
- Stage B **938 Qwen calls / 916.437 s**, 37 nominations + 59 retrieval calls, 120 verifier batches/148 items, 3 recovery passes; 391290 input/62198 output tokens. Total provider calls including Stage A + neutral **992**, no retries. Recovery repeats all initial hits and 7 verified records. Source and private DB copies byte-unchanged; tunnel/descriptor/token cleaned. All 16 revised tests, original/revised main, calibration, Run06/06a/06b selfchecks, Cliff 15/15 PASS.
- **R_0_6 REPRESENTATION PACKAGE NOT FROZEN** (READY gate not met; not an accepted 0.7 factorial condition). Private report: C:\Users\cliff\AppData\Local\Temp\callosum-final-060-20260909-131923\REPORT_FINAL_060.md SHA256 d504b2442c2f4bb4dee1b2dad2b4072bfdadee13bd2fca1dda1bb256368224fb. Protocol SHA256 d123ea05d4d58b7bb8619076859f823ebcf6a0d3d0e67d57fa94326bbb448152; private changes.patch, semantic-audit.json, raw calls/matrices/hashes/test receipts. Prior Claude entries preserved byte-for-byte. Stop; no further iteration performed.

## Claude 0.6.0 semantic-loss postmortem — COMPLETE 2026-09-09

- **Analysis/report only.** No code/experiment/inference/download; no 0.7.0 edit; no R_0_6 freeze; read-only repo except the report + this handoff + a plan backup. Nothing staged/committed. Prior Claude/Codex entries preserved byte-for-byte. HEAD 6b4b8d9. Report: **`.claude/docs/research/2026-09-09_ask-060-semantic-loss-postmortem.md`** (23 sections; rev-2, Cliff's 10 methodological corrections applied). Steered by the final 0.6.0 receipt (`REPORT_FINAL_060.md`) + `experiments/ask_cli_revised/{qwen.py,synthesis.py,ledger_renderer.py}` + Runs 0.5/0.6/0.6a/0.6b.
- **Verdict:** 0.6.0 is COMPLETE and correct (IMPROVED BUT NOT READY). With request-preservation and selection-envelope failures removed *on this receipt*, remaining loss is now localizable. Headline: **all 148 candidate quotes are exact (quote-conf 1.0) yet the derived propositions are unsound → quotation fidelity ≠ proposition fidelity.**
- **Newly localized loss boundaries (un-bundled):** (1) **claim formation** = the destructive boundary — *mechanical* 152/328 ungrammared truncations→None (evidence deletion, same class grammar fixed for selection) **+** *representational* paraphrase meaning-mutation (subject/population/direction swaps, null reversal, neighbor import). (2) **context gate** = mostly *mechanical* — 246/354 truncations fail OPEN to `accept` (growth judgment never exercised; only ~108/354 produce a real action) **+** separate *semantic* discard of useful nulls (28044); report's "246/354=loss" bundles these. (3) **verification ≠ responsiveness** (policy) — verifies claim↔source, not claim↔request; accepts EBQ subject error 0.89 + generic caption 0.94 + 2 negative-control records. (4) **nodes survive, edges don't** (representational). (5) **null/mixed/uncertain smoothed away** (asked as prose, not typed). (6) **recovery = same-search no-op** (0 new hits, 7 duplicate verified records).
- **Stages judged unnecessary-in-current-form (findings to test/redesign, not deletions):** free-paraphrase claim formation (→ span-first/typed candidate annotation, quote stays canonical); recovery-by-same-search; the gate's model `discard` branch (→ deterministic H1a `evidence_role` + non-destructive retain-and-rank); the optional model-prose `synthesis.py` (superseded by the constrained renderer, which held its guarantees). Terminal renderer = keep.
- **Strongest worker/orchestrator implication:** the fragile task is **generative compression (paraphrase)**, NOT small-model/high-volume. Draw the boundary at **generative-compression vs source-preservation**; make claim formation source-preserving *before* escalating model size. No Qwen-capacity verdict is licensed (confounds unremoved).
- **Recommended next bounded experiment: CLAIM-REPRESENTATION ISOLATION** (context-gate isolation second). Model held fixed; unit = unique claim-formation input packet (recovery pseudoreplication removed); Arm 0 = contemporaneous current-form control, Arm 1 = same paraphrase + structured-output only (mechanical isolate), Arm 2 = quote canonical + typed source-anchored **candidate** annotation (no operative self-critique; fields anchored + allow NOT_STATED/NOT_APPLICABLE/UNCLEAR; null/mixed/uncertain kept distinct; not a universal ontology). Primary outcome = blinded/randomized human fidelity vs exact source (0.6a rubric, mutual-exclusivity checked). Built-env carried as a **responsiveness** negative-control packet only, never a source-fidelity criterion. First-run-frozen, no tuning. It yields a **candidate** representation, **NOT** R_0_6 (chain: isolation → candidate → integrate into revised 0.6 → bounded end-to-end acceptance → if READY freeze R_0_6).
- **0.7.0 preregistration: remains UNTOUCHED for now** (result refines, doesn't invalidate MODEL × REPRESENTATION PACKAGE; the isolation feeds the reserved R_0_6 slot rather than blocking on redesign). R_0_6 stays unfrozen. Standing boundaries (H1c-A2 sealed, A3 worktrees DO NOT TOUCH, frozen Gemini/Qwen acceptance) untouched. Codex 0.6.0 lane not interfered with.


## Codex claim-representation isolation — BLOCKED 2026-09-09

- **BLOCKED — PRE-INFERENCE INFRASTRUCTURE FAILURE.** Private task dir: `C:\Users\cliff\AppData\Local\Temp\callosum-claim-representation-isolation-20260909-184828`. Recovered **164 unique units** (AIB 39 / built-env 66 / depression 59) from 328 historical claim calls; every initial/recovery pair has exact matching source/context/request/prompt. Inventory SHA256 `cdcd76de16308cc8f66f1c11d2f69c2acdafc27a7f980952c3c4c55f749a6aef`. Planned 164 calls/arm (492); **actual Arm 0/1/2 = 0/0/0**, mechanical verdict each NOT_RUN.
- Established JUNO tunnel launched once, metadata preflight failed `ConnectError`; tunnel already exited at cleanup. Actual runtime/model identity UNVERIFIED. No predeclared neutral recovery, so **STOP before inference**, zero retries/cloud/retrieval/verifier calls. No credential artifact or managed descriptor/token created. All source quotes/DB hashes unchanged; no production code/DB change. 16 tests + 16 subtests and original/revised/calibration/06/06a/06b/Cliff selfchecks PASS. Nothing staged/committed.
- Protocol SHA256 `eef3dc9475e1978ff64345ac7342b665344dbfec3c52c8cb73df697ed1cc2ead`; freeze manifest SHA256 `0f3863fb4b44b18d6990b9abb6b17b3e7ea462b941a1f7e1cc3aeeffdda1db59`. **Inventory/blocked-preparation seal only, NOT_READY_FOR_INFERENCE**: final treatment schema/prompt/cap, runtime attestation, scoring operationalization, randomization and runner were not completed. Historical rubric already includes LOSS_AND_ADDITION; no new primary scoring performed.
- Arm-2 anchors: **NOT_ASSESSED, no outputs** (not vacuous success). Genuine human semantic labels: **NO**. Blinded packet/key: **NOT_CREATED**; separate status receipts `C:\Users\cliff\AppData\Local\Temp\callosum-claim-representation-isolation-20260909-184828\blinded_adjudication_packet.NOT_CREATED.json` SHA256 `1dcd0684c32ce66334d0c1eb518b116c4d5b7a81e5a940e23927d94def096625` and `C:\Users\cliff\AppData\Local\Temp\callosum-claim-representation-isolation-20260909-184828\SEALED_ARM_KEY.NOT_CREATED.json` SHA256 `b75f8f0262bafc005dfeeda42791ba74dde8969d0492c6432df0836d3d150042` are not adjudication deliverables. No semantic/architectural winner or awaiting-adjudication claim.
- Report: `C:\Users\cliff\AppData\Local\Temp\callosum-claim-representation-isolation-20260909-184828\REPORT_PRE_ADJUDICATION.md` SHA256 `ded10ec141f31b326c9519357ecd85c0bf3ab62632a57961b76419644b54228e`. Exact stop state **BLOCKED BEFORE FIRST MODEL OBSERVATION; no inference resumed**. **R_0_6 remains unfrozen; 0.7 preregistration untouched.** Prior SCRATCH content preserved byte-for-byte; one handoff appended and persistence verified.


## Codex claim-representation isolation RESUMED — COMPLETE 2026-09-09

- **EXPERIMENT RUN COMPLETE — AWAITING BLINDED HUMAN ADJUDICATION.** Resumed `C:\Users\cliff\AppData\Local\Temp\callosum-claim-representation-isolation-resume-20260909-190527` from blocked antecedent `C:\Users\cliff\AppData\Local\Temp\callosum-claim-representation-isolation-20260909-184828` (unchanged, zero prior observations). Reused exact **164-unit** inventory SHA256 `cdcd76de16308cc8f66f1c11d2f69c2acdafc27a7f980952c3c4c55f749a6aef`; no regeneration/re-deduplication; initial/recovery multiplicity lineage only. Actual **164/164 per arm,492 total**, retries0, neutral inference0; inference STOPPED.
- Infrastructure: established plink forward/Ollama reachable. Initial attestation assertion was parameter-line serialization order only; values unchanged. Actual JUNO/Ollama0.12.3, Qwen2.5-1.5B-Instruct Q4_K_M, managed tag callosum-managed-local, GGUF6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e, ctx12288/temp0/seed42; full GPU residency after first/final observations. First call cold; no warmup. Credentials never persisted/logged; descriptor/tunnel cleaned. Original failed tunnel root cause remains unproven.
- Execution-ready freeze **v2** SHA256 `55945c45fa1a95916260d7b9d610801d5cd74aad741cdd10e5f877fe22eed89e` (prefinal execution manifest preserved; before-observation correction prevents metadata recheck overwriting frozen snapshots; no treatment change). Arm0 10/164 complete, 68 truncated, 10 whole JSON, schema N/A; Arm1 163/164 complete, 0 truncated, 164 whole JSON, schema 164; Arm2 164/164 complete, 0 truncated, 164 whole JSON, schema 164. Caps192/192/823; Arm0/1 wire differs only response_format. All164 Arm2 canonical quotes preserved. Required anchors 196/1376 exact; all resolve=False; anchor existence != interpretation fidelity; no repairs.
- Blinded packet `C:\Users\cliff\AppData\Local\Temp\callosum-claim-representation-isolation-resume-20260909-190527\adjudication\blinded_adjudication_packet.json` SHA256 `c44e459da7049b18b2b8c635861e8e0ec287cbbf70cf46b0d937dd646de7caa8`; provide only `adjudication/` including instructions and blank492-label CSV. Sealed separate key `C:\Users\cliff\AppData\Local\Temp\callosum-claim-representation-isolation-resume-20260909-190527\sealed\SEALED_ARM_KEY.json` SHA256 `e62b3ea11b0fa5043ce5260d244178adc0c834b3b933a74cffe2f95601751fb2`; withhold key/aggregate report from adjudicator. Randomization reproducible; intrinsic output form remains a blinding limitation. Genuine human semantic labels **NO**; no primary semantic or architectural verdict. Built-env66 packets are responsiveness negative control only.
- Report `C:\Users\cliff\AppData\Local\Temp\callosum-claim-representation-isolation-resume-20260909-190527\REPORT_PRE_ADJUDICATION.md` SHA256 `4fc3ad00f619ee0b5438d231f61a803f0f5a1c209950e524fb40653e2e4971aa`. Source DB/all558 baseline code hashes unchanged; 16 tests+16 subtests and original/revised/calibration/06/06a/06b/Cliff selfchecks PASS; all frozen hashes and unit/wire/provenance invariants pass. Nothing staged/committed. Exact stop **492 FIRST OBSERVATIONS COMPLETE; AWAIT GENUINE BLINDED HUMAN LABELS**. **R_0_6 UNFROZEN; 0.7 preregistration UNTOUCHED.** Prior SCRATCH preserved byte-for-byte; one compact append verified.


## Claude 0.7.0 pre-execution readiness plan — COMPLETE 2026-09-09

- **Scoping/architecture only. No inference/downloads/scored cell; no prereg edit; no R_0_6 freeze; sealed arm key NOT opened; no adjudication substitute; read-only repo except the report + a plan backup + this handoff. Nothing staged/committed.** HEAD `6b4b8d9`. Report: **`.claude/docs/research/2026-09-09_070-preexecution-readiness-plan.md`** (23 sections). Plan backup `.claude/backups/plans/2026-09-09_070-preexecution-readiness-plan.md`. Cliff's 9 steering corrections applied (rev 2).
- **VERDICT: READY TO BUILD NON-SEMANTIC 0.7 INFRASTRUCTURE.** Nearly all 0.7 infra is R_0_6-independent + claim-arm-independent → buildable/freezable NOW; only the R_0_6 package slot, R_0_6-dependent (EQ3) cells, and any scored semantic inference wait. Human adjudication is the long pole and fully parallel. Terminal target = **READY_FOR_R_0_6**.
- **Completes before R_0_6 (as experimental code outside `app/`, NO model runs):** runner interface + R_CONTROL package adapter + model-adapter shim; `freeze_manifest_v0` builder (NEW artifact, all fields but R_0_6); per-cell artifact writer (generalizes `15_run_manifest.json`); offline scorer + rubric encoding (unit-tested on synthetic labels); held-out selection-procedure harness. Reuses `ask_cli`/calibration (`structured_output.py`, `run06/freeze.py`).
- **Blocked (C):** R_0_6 package (§18 handoff items) — chain = adjudication → candidate → revised-0.6 integration → bounded end-to-end acceptance → freeze R_0_6 → final 0.7 execution freeze → semantic benchmark once. EQ3 interaction cells. Output-budget-vs-package decision (needs R_0_6 shape). **Forbidden/not-now (D):** running ANY scored cell incl. R_CONTROL (own separate approval), any semantic Stage-1 item.
- **Held-out freeze rec:** freeze the SELECTION PROCEDURE now; items are **real scholar questions** exercising the 5 job-type coverage criteria (not surface tasks named after internals). Exclude **q_aib/q_builtenv/q_depr** from EVAL (all dev-exposed; q_depr in R_0_6 ancestry). Corpus presence/absence via **deterministic inspectable receipt** (no inference), Cliff supplies domain context but not sole criterion; negative-control recorded separately (built-env pattern). Author + freeze now, before R_0_6 integration.
- **Latency:** DO NOT invent numbers. Freeze framework + ordering + L_screen hard ceiling = LATENCY.md **600 s** (documented). **B_worker / B_orch / warm-L_screen = REQUIRES EXPLICIT PRODUCT DECISION** (smallest decision: max acceptable warm per-call latency for the high-volume worker vs the once/query orchestrator). **Context:** REALISTIC=**12,288** is the single primary-comparison context (freeze now); SHORT/STRESS are mechanical/sensitivity only, NOT a 3rd (CONTEXT) factor — shape stays MODEL × REPRESENTATION. **Quantization:** Q4_K_M primary where available; deviations only for a pre-declared mechanical reason (never a score); KV quant a separate recorded dimension; deviations exposed in interpretation; reconcile pins w/ Codex. Dropped incoherent "Q5 for borderline fit." **Cloud:** **Gemini-only** (service-level latency, not a hardware cell, no retries, never the pass bar).
- **Stage-1 semantic-screen rec: NEUTRAL-MECHANICAL-ONLY, NO semantic items at all** (not even "descriptively" — observed-but-unused semantic output is still observed outcome info). Only neutral probes: loadability, realistic-context allocation, neutral structured-output completion, crash/runtime, catastrophic-latency ceiling, cleanup. Removes the R_0_6-gated semantic-floor bar + its EQ3 bias vector. Within prereg §9.1 latitude → not a prereg edit. **Scorer rubric corrected:** five overall categories (FAITHFUL/LOSS/ADDITION/**LOSS_AND_ADDITION**/MALFORMED_OR_UNUSABLE) **plus independent co-occurring LOSS/ADDITION/MALFORMED flags**; overall category kept distinct from independent dimensions; never collapse to a mutually-exclusive four-way.
- **Recommended next implementation task:** reconcile Codex Stage-0, then freeze the outcome-independent decisions into `freeze_manifest_v0` + build the non-semantic scaffold (runner/R_CONTROL adapter/offline scorer/artifact writer/held-out harness), no scored inference; obtain B_worker/B_orch from Cliff + confirm held-out domain topics. Do NOT run the R_CONTROL column yet.
- **Concurrency:** **Codex Stage-0 audit still PENDING; must be reconciled before any implementation/preflight** (owns model eligibility/licensing/artifact identity/quant pins — did not touch/duplicate its lane). Prereg = design doc, NOT execution freeze; `freeze_manifest_v0` is a new artifact. Standing boundaries (H1c-A2 sealed, A3 worktrees DO NOT TOUCH, frozen Gemini/Qwen acceptance, blinded adjudication is the human's) untouched. Prior SCRATCH preserved byte-for-byte; one compact append verified.


## Codex 0.7 non-semantic infrastructure — COMPLETE 2026-09-09

- Built `experiments/ask_070/`: exact R_CONTROL adapter + independent FORMAT diagnostics, hard unavailable R_0_6, pure runtime serializers, synthetic-only one-observation runner/journal, private receipts, neutral Stage-1 specification, lexical audit, external referent drafts, offline human-label scorer, manifest builder/verifier. No live inference command.
- Stage-0 reconciled: all12 candidates, dispositions1 eligible/4 unknown/7 constrained unchanged. REALISTIC=12288 total; seed42/temp0; Q4_K_M primary, KV separate; Gemini-only. B_worker3s/B_orch15s are product budgets, NOT Stage-1 cull thresholds; L_screen600s only catastrophic latency ceiling. Cold/warm/padded are distinct predeclared trial IDs, not retries.
- Corpus procedure frozen before matching; source/copy SHA f2723b75…684d0 unchanged. Three positive questions PRESENCE_QUALIFIED (7/4/50 papers); exact question bytes frozen, all interpretive referents HUMAN_REFERENT_REVIEW_REQUIRED. Negative Parkinson/microbiome slot NEGATIVE_CONTROL_REPLACEMENT_REQUIRED (paper208, includes reference-region Parkinson match); no replacement invented. Lexical presence != semantic answerability/ground truth.
- freeze_manifest_v0 SHA256 753e3202b389997b39021c3f04e933ccc51d929a37f7bc32eb2b311f4747eb9f; 52 hashed files verify, byte-identical rebuild. Tests55/55, existing relevant tests30/30, six deterministic selfchecks, Ruff PASS. Protected baseline57473 files/index unchanged. ZERO candidate/Gemini/neutral/embedding/NLI inference, downloads, model loads, runtime/production mutations, sealed-key access, staging or commit.
- Status PARTIALLY_READY_FOR_R_0_6 — explicit negative-control domain blocker remains. Infrastructure prepared; parallel final-freeze dependencies include human referent review, fidelity/materiality floors, semantic output/thinking policies, acquired artifact/runtime/template hashes, hardware/task packets, cloud authorization, and accepted R_0_6 through adjudication -> integration -> bounded acceptance. Not "only R_0_6 left."
- Report `.claude/docs/research/2026-09-09_070-nonsemantic-infrastructure-implementation.md`; private receipts `C:/Users/cliff/AppData/Local/Temp/callosum-070-nonsemantic-infra-nv0h55dk/`. Next human decision: replacement negative-control domain; human referent review/adjudication can proceed independently. No further execution authorized.


## Claude worktree topology restore — COMPLETE 2026-09-17

- **Repo topology change, not a semantic decision.** The primary checkout
  (`C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum`) had been sitting on this branch
  (`experiment/ask-cli-staged-synthesis`) while ordinary product development continued
  independently on `main` via a temp-dir worktree. That froze Cliff out of his own primary
  folder for day-to-day product use. This entry documents where this branch's own state
  moved to, so a future session picking up SCRATCH here isn't confused about "the main repo."
- **This branch is no longer the primary checkout.** It now lives in its own dedicated
  worktree: `C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum\.claude\worktrees\ask-cli-staged-synthesis`.
  Same branch, same history — just relocated so the primary path could return to `main`.
  A checkpoint commit (`a0315503`) was made first to losslessly preserve everything that
  was dirty in the primary checkout at the time (this SCRATCH.md included), **except**:
  raw Playwright page-snapshot dumps (`broad-done.md`, `broad-result.md`, `reload-check.md`,
  `synth-pane.md`) and a UI screenshot (`axis-ask-interstitial-ax3.png`) that render live
  evidence text, and run-artifact directories that may hold retrieved library/paper text
  (`experiments/ask_070/frozen/`, `experiments/ask_cli_revised/runs/`,
  `experiments/ask_cli_revised/calibration/runs/` — same precedent as the already-gitignored
  `experiments/ask_cli/runs/`). Those were left untracked and manually relocated (not
  committed) into this same worktree, so they're still here on disk, just outside git history.
  `.claude/docs/legacy_engine/` (unrelated personal content, predates this research track)
  was deliberately excluded and left in the primary checkout for Cliff to handle himself.
- **Primary checkout is now `main`**, `origin/main` tip at the time of this restore
  (`1aa3973a`, inc 603 baseline), plus one small docs-only commit adding
  `.claude/docs/worktree-topology.md` (see that file for the live topology record —
  don't duplicate it here).
- **Frozen 0.6 baseline preserved separately and exactly**: branch `freeze/060` at commit
  `5ddb321f5a9374d8258234562da4b0781c965d1a` (the same commit this branch's own inc-581
  entry above references), attached at
  `C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum\.claude\worktrees\060`.
- **Zero semantic decisions made by this restore.** No H1a/H1b/H1c/Ask-CLI research
  conclusion changed; R_0_6 remains unfrozen; 0.6 human adjudication remains pending
  (Cliff is finishing a manuscript first); 0.7 remains subject to its existing dependency
  on an accepted 0.6. Every standing boundary above (H1c-A2 sealed, A3 worktrees DO NOT
  TOUCH, frozen Gemini/Qwen acceptance, no rerun/tuning) is unchanged and still binding.
  `browser-capture-research` (a separate, unrelated stranded worktree found during the
  audit) was deliberately left untouched, dirty, isolated — not this branch's concern.
- Audit trail (branch/worktree inventory before/after, ancestry checks, what was and
  wasn't reconciled into `main`) lives in the session transcript and the approved plan at
  `~\.claude\plans\we-are-changing-callosum-s-luminous-squirrel.md`, not duplicated here.
