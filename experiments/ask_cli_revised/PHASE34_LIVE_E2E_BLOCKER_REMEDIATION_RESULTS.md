# Phase 34 — Live E2E blocker remediation

Date: 2026-10-11. Bounded remediation of F1 discovery-index readiness and F2 flat
scientific-recovery routing. No live scientific-answer qualification in this increment.

## Starting checkpoint and scope

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
Starting HEAD: `1c18552fdd5481baa449616966237a74137747ce`, clean worktree, at
`C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum\.claude\worktrees\ask-060-hier11-recpm3-citefix-20260929T212442Z`.

Read the original live qualification, accepted E2 and I2-3 results, contribution lineage
and credit policy, and inspected indexing, discovery, request ownership and recovery.
The first Q1 attempt remains a failed qualification. Its protocol, all six questions,
reviewed inputs, independent expectations, sources, output and diagnostics are unchanged.
All 89 original files under `.local/phase34-live-e2e-20261011` match the inventory
recorded before this repair. No other five scientific questions were executed.

## F1 — cause and existing workflow

The exact demonstrated obstruction was absent discovery representations: papers 82 and
83 had neither paper embeddings nor axis membership. `discovery.nominate_papers` unions
paper-vector nearest neighbors with axis neighborhoods; chunk embeddings alone do not
make a paper available to that nomination path. Paper 82 had 843 indexed chunks;
paper 83 had 929 chunks but only 282 indexed. This was a source-library readiness
failure missed by the first evaluation preflight, not evidence that the papers lacked
relevant source passages.

The ordinary workflow already supplies the needed operations:

- `app/backend/embeddings/pipeline.py::embed_papers` embeds the existing paper metadata
  using the current model and `paper-metadata-v1` representation. Current-index checks
  make this idempotent. `embed_chunks` independently completes current chunk embeddings.
- Library scan/enrichment and import paths in `api/routers/library.py`, and the Zotero
  import path, call these indexing stages. PDF reprocessing can rebuild and index
  chunks separately from metadata indexing.
- `clustering/axis_scoring.py::ensure_candidate_embeddings_committing` completes
  missing live-paper embeddings using ordinary per-paper committed transactions.
  Axis scoring/clustering separately populates `cluster_node_papers`; it is not
  required when direct paper-vector nomination is available.
- `persistence/paper_lifecycle_repo.py::compute_processing_tier` bases `fully-chunked`
  on article chunk presence and `abstract-embedded` on metadata presence. These labels
  are not certificates that current embedding rows or vector payloads exist.

The preserved history establishes incomplete indexing, but **does not establish the
historical event that caused it**. Paper 82 records `doi-import` on September 11;
paper 83 records `crossref` on September 13. Other contemporary live papers also lack
paper embeddings. The parked QA log contains migration/ASGI failures, including an
unavailable `0078_imported_collection_axes` revision, but no receipt ties such a failure
to these particular missing embeddings. Neither an import interruption nor a universal
production indexing defect is proven. No speculative ingestion repair was made.

## New isolated evaluation condition

Artifacts are outside tracked code under
`.local/phase34-live-e2e-remediation-20261011/`. `index_copy.py` copies the entire original
frozen database and calls the existing workflow over **all live papers** and
**all document-role chunks**. It never filters indexing by expected paper IDs.

Configuration: cached `all-MiniLM-L6-v2`, version `all-MiniLM-L6-v2`, dimension 384,
normalization `whitespace-lower-v1`; `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`.
The real existing runtime is built with `want_verifier=False`, `want_qwen=False`.
There are no generation, claim-verification or external lookup calls. No axis rows
were manufactured or scoring limits changed. The application database was not used.

| Property | Original `library.sqlite` | New `library.indexed.sqlite` |
|---|---:|---:|
| Bytes | 72,482,816 | 74,424,320 |
| Papers / active / deleted | 86 / 69 / 17 | 86 / 69 / 17 |
| Attachments | 17 | 17 |
| Chunks | 6,610 | 6,610 |
| Embeddings | 5,700 | 6,863 |
| Axis memberships | 210 | 210 |
| Chunk-structure rows | 0 | 0 |
| WAL bytes at freeze | 0 | 0 |

Original SHA-256:
`6598c4798cc35a8364da48b9a0215c3777a9e25c31add09aaaa512a111e8c529`.

New SHA-256:
`0ba4b18364a532ab132dded173a93442ca75cc58d94f549eae3f9ac2b1809360`.

Existing indexing generated **10 paper embeddings and 1,153 chunk embeddings** in
about 50 seconds. The complete generated-record inventory, model configuration,
source-table hashes, before/after counts and probe outputs are in `indexing_result.json`.
`library.indexed.fingerprint.json` and `completion.json` freeze the new condition.
The completed database also has its filesystem read-only flag set.
Future evaluation must verify this fingerprint and use a separate working copy,
preserving this checkpoint and the original failed attempt.

The first disposable diagnostic stopped before indexing because a plain SQLite
table-hash query touched a virtual vector table without loading its extension. The
diagnostic was corrected to exclude vector implementation tables; the existing copy
was reused only after proving it still exactly matched the original fingerprint.
Both diagnostic logs are preserved. This was not an Ask or scientific-model attempt.

Readiness and integrity checks on the completed copy:

- All **69 live papers** satisfy the actual current paper-embedding predicate; all
  **6,610 chunks** have current embeddings. Paper 82 has paper embedding 5726;
  paper 83 has paper embedding 5727. Both retain their original identities and chunks.
- All referenced current paper/chunk embedding records resolve to vector payloads of
  the configured dimension. Foreign-key check is empty; SQLite integrity check is `ok`.
  Every chunk's paper ID agrees with its referenced attachment's paper ID.
- Papers, attachments, chunks, and every non-index application table compare exactly
  before/after. Existing embedding records remain unchanged. No deletion, source
  substitution, passage edit or attachment-provenance mutation occurred.
- Repeating both existing indexing operations is an exact inventory no-op.
- Ordinary nomination and within-paper retrieval consume the new index successfully.
  Probes use the unchanged first authored subquestion of Q1 and Q2; no expected paper
  list, extra hint, altered wording or candidate-limit change is supplied.

| Unchanged readiness query | Paper 82 nomination position | Paper 83 nomination position |
|---|---:|---:|
| Q1 | 6 | 1 |
| Q2 | 1 | 7 |

Q1 retrieval includes paper 82 chunks 4826/5202/5127 and paper 83 chunks 5206/5222/5215;
Q2 includes paper 82 chunks 4648/4411/4461. These IDs are observed results, not inputs
to discovery. Complete nominees, hits and source references remain in the local receipt.
All-live-paper **eligibility** is established; the observed rankings cover only these
two readiness probes and do not guarantee six-question scientific success.
No additional indexing prerequisite blocked the exercised ordinary path. Missing
optional structural/reference discovery capabilities were not added in this repair.

## F2 — ownership join and corrected dispatch

The request adapter's authoritative subquestion records contain an `obligations` list.
For the demonstrated flat request, obligation `field_id=s1-o1` belongs to retrieval
`subquestion_id=s1`. Structured recovery previously copied `search_child_id` into both
identities. `__main__._recover` could not find subquestion `s1-o1` and skipped that gap.

The integration now joins `target.search_child_id` to the unique declared obligation
owner before constructing the recovery gap:

| Identity | Correct value |
|---|---|
| Scientific target ID | `s1-o1::2dc69aed8aff6365` |
| Scientific search child / gap field ID | `s1-o1` |
| Retrieval subquestion ID | `s1` |

`recovery_routing.subquestion_id_for_obligation(subquestions, obligation_id)` performs
this pure lookup. It uses no string splitting, assumed naming convention or scientific
domain vocabulary. Missing ownership, duplicate obligation matches, missing owner ID,
and nonunique subquestion IDs raise named `ValueError` reasons before dispatch.
This is an explicit integration failure, not a scientific absence or completed search.
No new recovery status semantics were introduced. Invalid manually supplied generic
gaps are outside this structured-target change.

The target dictionary, role-aware hint, target selection, obligation ownership and
recovery query/search machinery remain intact. Generic gaps take their existing path.
Hierarchical requests use the same authoritative join and retain their established
IDs. The per-target identity remains independently recorded in `_recovery_target_id`.

Tracked runtime changes are limited to `experiments/ask_cli_revised/e2e.py` (import,
corrected ownership comment and lookup) and new `recovery_routing.py` (pure helper).
New `test_recovery_routing.py` supplies deterministic regression coverage. No
`app/`, frontend, discovery, indexing, mapper, verifier, guard, policy, version,
ParentClaim, AnswerPlan, producer authorization or product endpoint code changed.

## Regression and historical protection

The 13 new routing checks cover arbitrary and multi-child IDs, the actual preserved
hierarchy adapter, missing/ambiguous ownership, and the public reviewed runner through
the real recovery orchestration. Only worker boundaries are substituted. The exact
demonstrated scientific target reaches the existing query and retrieval calls with
`s1`; generic recovery also executes and records its own row.

The three dispatch outcomes independently establish:

- Scoped recovery contributes evidence: `completed / recovery_added_evidence`.
- Search executes with no new evidence: `completed / recovery_no_new_evidence`.
- Recovery query produces no usable answer: `not_completed / recovery_query_no_answer`.

The found-evidence fixture leaves generic recovery empty, so the scoped target itself
must contribute the recorded evidence. Tests do not require any expected scientific
finding, external artifact or q_aib-specific runtime branch.

Focused qualification: **106 passed in 79.18s**, covering routing, reviewed fresh
requests, scientific recovery targets, production embeddings and axis scoring.
The optional mocked psutil gate module independently passed **7 tests in 9.29s**.
All 26 D1 producer-code input hashes match the installed normalized-text manifest;
the repair does not touch that producer surface or reinterpret a historical source pin.
Original evidence hashes and the new frozen database hash were independently rechecked.

Broad offline qualification: **5,509 passed, exactly 5 known failures, 12 skipped,
9 xfailed and 276 passing subtests in 323.21s**. The failure inventory is exactly equal
to the independently rerun known-five inventory (**5 failed in 13.47s**).
There are **zero unexplained new failures**. Historical replay, D1/D2 identity and
recorded-qualification protections execute within this broad suite; no fixture or
expected output was edited.

The unchanged failures are:

1. `ask_070/tests/test_corpus_and_referents.py::test_dev_eval_separation`: absent
   frozen `dev_inputs_v0.json`.
2. `ask_070/tests/test_schema_validation.py::test_real_frozen_nonsemantic_artifact_schemas`:
   absent frozen `corpus_presence_v0.json`.
3. `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`:
   the existing offline Ollama tags probe is denied.
4. `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`:
   pre-existing legacy `hierarchy_contract.py` pin drift.
5. `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`:
   the same legacy pin drift returns code 3.

Reproduction: use `.venv/Scripts/python.exe .local/i4-4c/run_offline.py` with
`experiments -q --tb=short`, excluding only
`experiments/ask_cli_revised/contract_directed/tools/test_run_gate_integration_live.py`.
That fully mocked optional module runs separately with the existing Anaconda Python
providing psutil. The offline plugin denies network access. Focused paths are
`test_recovery_routing.py`, `test_reviewed_fresh.py`, `test_sufficiency_recovery_targets.py`
under this experiment, plus `tests/test_embeddings.py` and `tests/test_axis_scoring.py`.

Local evidence: `focused.xml/.log`, `full.xml/.log`, `known-five.xml/.log`,
`optional.xml/.log`, `regression_comparison.json`, `integrity_verification.json`,
`source_reference_check.json`, `source_snapshot_history.json`, `original_evidence_hashes.json`,
`indexing_result.json`, `completion.json`, and both indexing logs. Ruff check and format
check pass for all three changed/new Python files.

Commit hooks: the first invocation selected the system Python without Bandit/Tach.
Rerunning with the existing project virtual environment on PATH passes whitespace,
EOF, merge-conflict, large-file, Ruff formatting/lint, Bandit and Tach checks. The
**sole remaining hook failure** is the pre-existing 615-line
`app/frontend/js/20_synthesis.jsx`. Its worktree and starting-HEAD Git blob are both
`03f9d3dfee3763533a78d5da601a99cb81bb37f1`. The user explicitly authorizes this exact
unchanged frontend exception when substantive gates pass. Use `SKIP=line-budget`
for this commit only; do not disable any other hook or alter the frontend/cap.
The normal hook evidence is retained in `commit-hooks.log`.

## Limits and decision

The repaired index is a new evaluation condition. No original failure was relabeled.
Current reviewed v8, Layer C v2, parent synthesis v2, plan-v5, disclosure behavior,
scientific mapping, U1/U2, sealing and recovery meaning remain closed. The routing fix
changes whether the already-authored target reaches its intended retrieval owner.

There was no live Qwen/Gemma/Phi4 scientific run, live NLI qualification, live answer
inspection, new question authoring, expected-answer injection, retrieval tuning,
source mutation, product integration or UI work. Real local embedding/indexing and
the two permitted retrieval-readiness probes are the only live library operations.
Scientific answer fidelity, completeness, evidence verification and the remaining
five questions still require the separately authorized requalification.

**LIVE E2E PREREQUISITES RESTORED - READY FOR REQUALIFICATION.**

Commit and push the bounded five-file change set, preserving both local library
checkpoints. Stop here; do not automatically begin the six-question live evaluation.
