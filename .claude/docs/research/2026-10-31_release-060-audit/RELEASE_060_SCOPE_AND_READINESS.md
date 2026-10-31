# Callosum 0.6.0: scope and readiness

> *Publication note (2026-10-31, inc 616 documentation commit): absolute local paths were rewritten to `%USERPROFILE%` form and a session-scratchpad path was replaced by a description before committing. No finding, number or status was changed.*

**Audit date:** 2026-10-31. **Revised 2026-10-31** for Cliff's two steering decisions ("Audit Decisions and
Modernization Implementation Direction" and "Final Model-Transition Policy"). Where they differ, the later one
governs; §5 separates what is now authorized from the qualification gates still outstanding.

**Nature:** read-only architectural audit. No code, migration, commit, push, merge, tag or release was made. No
adjudication, benchmark, model comparison or tuning was run.

**Code audited**
- `main` @ `c9ada5ff` (inc 608), at `%USERPROFILE%\Dropbox\Dropbox\01_Work\callosum`.
- Branch `integrate/inc607-608-ask` @ `af53b1d2` (incs 607, 609–612 on top of 608), at
  `%USERPROFILE%\callosum-worktrees\integrate-607-608`. This branch is 5 commits ahead of `main`, unpushed and
  unmerged.

**Also inspected**
- The installed desktop app.
- A read-only snapshot of the desktop database.
- The packaged Python runtime.

Companion documents in this folder:
- `RELEASE_060_BLOCKER_MATRIX.md`
- `BACKGROUND_MODERNIZATION_ARCHITECTURE.md`
- `BACKGROUND_MODERNIZATION_FAILURE_AND_RECOVERY_CONTRACT.md`
- `RELEASE_060_TEST_AND_PACKAGING_PLAN.md`
- `RELEASE_060_DEFERRED_BACKLOG.md`

---

## 1. What 0.6.0 is

| Delivers | Source on the integration branch |
|---|---|
| Arctic S retrieval for Ask, **automatically preferred** once its index is complete and verified | inc 608 profiles; inc 610 supervised index build; automatic preference not implemented (B3, B5, B6) |
| DeBERTa-v3 evidence verification (NLI) for synthesis, **automatically preferred** once its operating gates are satisfied | inc 608 `nli_profiles.py`; inc 609 fail-closed with no fallback; automatic preference not implemented, and its scientific gate is open (§6, B8) |
| Safe source-role versioning (`chunk-structure-v2`), plus narrow-path bibliography demotion and heading rescue | incs 607, 611, 612 |
| **Automatic background modernization of existing libraries** | **Not implemented** (§3) |
| Unchanged Qwen2.5 synthesis | Verified: `git diff 2f01feef..af53b1d2 -- app/backend/llm app/desktop-shell` is empty |

**MiniLM and MiniLM2 stay** as transitional compatibility infrastructure and for the functions that still depend on
them (§7). Their complete retirement is a deferred architectural workstream (`RELEASE_060_DEFERRED_BACKLOG.md`
§B), not a 0.6.0 blocker. No embedding migration is required merely to retire MiniLM in this release.

**Out of scope:**
- Complete MiniLM/MiniLM2 retirement and legacy-vector cleanup.
- Qwen3 and the 0.7 planner/decomposition work.
- Re-extraction or rechunking.
- Back-matter hygiene.
- Reference-region boundary repair.
- New Crossref fetching.

**Key finding on scope: 0.6.0 needs no re-extraction and no rechunking.** Since 0.5.16 (`2f01feef`) nothing changed
in extraction or chunking: no file in `pdf_processing/extraction.py`, the chunker or `ingest.py` changed. The only
`pdf_processing` changes are the derived classifier (`chunk_structure.py`) and the new `source_role.py`, and the
only migrations are 0085 and 0086, both additive. Modernization in 0.6.0 is therefore **additive-only**:
- new Arctic S vectors, beside the MiniLM ones, which stay;
- a re-derived `chunk_structure` (a derived table);
- a model download.

No chunk row, annotation, citation mapping or source component is rewritten.

---

## 2. Audit 1: what exists

Classification key:
- **Integrated:** implemented and on a user path.
- **Hidden:** implemented but not exposed.
- **Partial**, or **None** (not implemented).

| Capability | Status | Tested | Release status | Evidence |
|---|---|---|---|---|
| Arctic S profile definition (revision-pinned, CLS, 512, query prefix, identity baked into `model_version`) | Integrated (Settings, opt-in, "Experimental") | Yes (`tests/test_embedding_profiles.py`, including the AST search-isolation test) | Done | `app/backend/embeddings/profiles.py:36-84`; `embeddings/models.py:159` |
| Vector isolation by model identity in a shared `callosum_vec_embeddings_384` table | Integrated | Yes (AST ≥6 call sites; reversed-vector behavioral test) | Done | `query_ranking.py:38-66` passes `candidate_embedding_ids` |
| Fail-closed incomplete index (`IncompleteEmbeddingIndexError`) | Integrated | Yes | Done; becomes a UX hazard once activated (B5) | `profiles.py:91,189`; `query_ranking.py:42-47`; `faceted_pipeline.py:231`; `routers/summaries.py:411,439-458` |
| Supervised, resumable, memory-aware Arctic index build (OS-lock liveness, parent watch, exit-code contract, circuit breaker, startup reconciliation) | Integrated, **manual start only** | Yes (inc 610 failure/retry tests; real 42k-passage continuation) | Reusable core of modernization | `embeddings/index_supervisor.py`, `index_worker.py`, `index_runs.py`, `index_lock.py`, `resources.py`; migration 0086; lifespan `api/app.py:228,232` |
| DeBERTa NLI profile (label/arch/tokenizer contract; no embedding fallback) | Integrated (Settings, opt-in) | Yes (contract and fail-closed tests) | Default status needs a decision (B8) | `summarization/nli_profiles.py:25-140`; `routers/embedding_profiles.py:180-197`; `model_runtime.py` |
| Fail-closed NLI for every profile, with model provenance on every run | Integrated | Yes | Done | inc 609; `routers/summaries_provenance.py`; `js/20e_model_provenance.jsx` |
| `chunk-structure-v2` classifier and eligibility seam (demotion only, stale ignored) | Hidden: the classifier is consumed. The derivation is now packaged (inc 613), but **nothing runs it automatically** | Yes (in-sample, plus the held-out v2 gate PASS, AI-adjudicated); inc 613 byte-identity on three copies | **Blocker B4** (packaging done; automatic run and currentness defect open) | Writer: `pdf_processing/structure_backfill.py::backfill()` (inc 613), with `tools/backfill_chunk_structure.py` as its CLI. Readers: `evidence_eligibility.py`, `evidence_selection.py:69`, `chunk_structure_repo.py:183` |
| Heading rescue (M1), memo keyed by text | Integrated (text-only, needs no classification) | Yes | Done | `summarization/reference_rescue.py:57,78`; inc 612 |
| Per-library settings | Integrated | Yes | Done | `persistence/schema_library_settings.py`; migration 0085 |
| Automatic detection of outdated processing | **None** | — | **Blocker B3** | No startup path calls `IndexSupervisor.start`; only `POST /embedding-profiles/{key}/index` does (`routers/embedding_index.py:246`) |
| Automatic activation of a completed generation | **None** (manual select, 409 if incomplete) | Partly (409 path) | **Blocker B6** | `routers/embedding_profiles.py:121` |
| Keeping the active profile complete after new imports | **None** | — | **Blocker B5** | `pdf_processing/ingest.py:219,291` and `embeddings/admission.py:68` embed MiniLM only |
| Model provisioning (Arctic, DeBERTa) | Partial: Hugging Face download on first load (`local_files_only=False` default; `SupervisorConfig.local_files_only=False`) | No offline test | **Blocker B2** | `model_runtime.py:57,342-362`; `index_supervisor.py:55`; no `HF_HOME` handling in `src-tauri` |
| Disk-space guard | **None** | — | **Blocker B7** | No `disk_usage`/`statvfs`/`GetDiskFreeSpace` anywhere in `app/backend` |
| ↳ *Update 2026-10-31, inc 616* | **Implemented** (`embeddings/disk_guard.py`, `waiting_disk`, exit 74) | Focused + process-tested (simulated) | B7 implemented; **not release-validated** | Original row above kept as found |
| Status row | Integrated (`embedding_index_jobs`, "Retrieval index build", Local AI, navigates to Settings) | Yes (QA route 97) | Reuse; relabel | `routers/status.py:53,110,180`; `api/app.py:268` |
| Pause/Resume/Cancel | Integrated **in Settings only**; Status rows have navigate and dismiss only | Yes | Acceptable through navigation (B9) | `js/04c_status.jsx:173-178`; `js/35i_retrieval_profiles.jsx` |
| First-run notice | Mechanism exists (version-keyed `whatsnew.json` plus a typed `actionKind`) | Yes (coverage gate) | Needs a 0.6.0 entry (B9) | `app/frontend/whatsnew.json`; `js/04e_whatsnew.jsx`; `tools/check_whatsnew_coverage.py` |
| Re-extraction/rechunking generation swap | **None** (chunks are single-generation) | — | **Not needed for 0.6.0**; deferred | See Architecture §2 |

### Four separate processes

| Process | Needed in 0.6.0? | Per-paper cost | Model? | Writes |
|---|---|---|---|---|
| Extraction/rechunking | **No.** Unchanged since 0.5.16 | — | — | — |
| Embedding regeneration (Arctic S) | **Yes**, for every article-fulltext chunk | Dominant (≈12–13 passages/s, measured in inc 610) | Arctic S, in the worker | `embeddings` rows plus vec rows (additive) |
| Source-role v2 reclassification | **Yes**, for every paper with chunks. Derivation packaged in inc 613 (`829f35f4`) | Small, pure CPU; reads `external_api_cache` (Crossref) and `reference_instances` | None | `chunk_structure` (replaces derived rows) |
| NLI verification (DeBERTa) | **No per-paper work.** Runs at Ask time | None at upgrade; a load once per process | DeBERTa, in the main process | Nothing at upgrade |

---

## 3. What the installed app does today

**Installed version.** Callosum **0.5.16** (registry `DisplayVersion`). It runs the packaged runtime
`win-x86_64-py3.11-s1-2094b5a287a1dd54` with transformers 5.14.1, sentence-transformers 5.6.1 and torch 2.13.0+cpu.
The stale `%USERPROFILE%\AppData\Local\Programs\callosum-shell` (July) is a leftover folder, not the live install.

**0.5.16 predates incs 607–612 and 608.** It therefore has:
- no profiles and no DeBERTa;
- no `chunk_structure` consumer;
- no `library_settings`.

**Desktop library**, from the read-only snapshot
`%USERPROFILE%\callosum-data\snapshots\desktop-20261029T193838Z\callosum.sqlite`; the live database
was not opened:

| Property | Value |
|---|---|
| Alembic revision | `0084_provisional_artifacts`. 0.6.0 adds 0085 and 0086, both additive |
| Live papers | 151 |
| Chunks | 68,086 (≈451 per paper), all `pymupdf-block-v2` |
| Embeddings | MiniLM only (68,086 chunk vectors; 165 paper; 6 axis) |
| `chunk_structure` rows | **0**. The 607/611 demotion would be inert here until reclassification runs |
| `source_representations` | 159 `complete` |
| Annotations | 0 |
| Summaries | 0 |
| DOIs | 151 papers; 154 Crossref cache rows, so reference-region anchoring is possible offline |
| Database size | 614 MB (live file) |

**Research master** (`%USERPROFILE%\callosum-data\library.sqlite`, read-only):
- 256 papers and 55,287 chunks;
- mixed `pymupdf-block-v1/v2` and `document-text-block-v1` chunks;
- 23,875 `chunk_structure` rows at **v1**, all stale under v2 and therefore ignored until reclassified;
- 15 annotations and 10 summaries.

### Arctic S and DeBERTa availability on this machine
- **Models.** Both pinned snapshots are in `%USERPROFILE%\.cache\huggingface\hub`:
  - Arctic S: `e596f507467533e48a2e17c007f0e1dacc837b33`;
  - DeBERTa: `6f5cf0a2b59cabb106aca4c287eed12e357e90eb`.

  They are there because of development work. **A clean user machine has neither.**
- **Packaged-runtime compatibility.** The packaged runtime has no `sentencepiece` or `protobuf` (and no `psutil`).
  It still loads the DeBERTa tokenizer (`DebertaV2Tokenizer`, from `tokenizer.json`) and config (`id2label` order
  and `deberta-v2` match the contract), offline at the pinned revision.
- **Packaged vs development output.** A three-text / two-pair probe, run offline and from the scratchpad:
  - Arctic: cosine ≥ 0.99999987, max |Δ| 7.5e-8.
  - DeBERTa: probabilities equal to 4 dp (0.99607 vs 0.99609 entailment).
  - This is a **compatibility smoke check, not a benchmark**. It shows the packaged environment can run both
    pinned checkpoints. It says nothing about quality or latency.

### Defaults
| Default | Current | After upgrading to the integration branch as-is |
|---|---|---|
| Retrieval | MiniLM | Unchanged. `active_retrieval_profile` falls back to `minilm` when `library_settings` has no row |
| NLI | MiniLM2 | Unchanged |
| Classification | Absent | Absent: no writer runs |

**An upgrade to the current branch therefore changes no default and delivers none of the 0.6.0 behavior** unless
the user opens Settings, builds the index, selects Arctic S and selects DeBERTa. Only that manual route works
today. **0.6.0 as scoped requires the automatic path.**

---

## 4. A 4,000-paper library

These are estimates from existing measurements, not new benchmarks.

| Quantity | Low (research master: 216 chunks/paper) | High (desktop: 451 chunks/paper) |
|---|---|---|
| Article chunks | ≈0.86 M | ≈1.8 M |
| Arctic S compute at 12–13 passages/s (inc 610, `LOW_MEMORY_RESOURCE_MEASUREMENTS.md`) | ≈18–20 h | ≈38–42 h |
| Added storage at ≈1.5 KB float32 vector plus ≈0.3–0.5 KB metadata/index | ≈1.6–1.8 GB | ≈3.4–3.7 GB |
| v2 reclassification | Minutes | Minutes |
| Model download | Arctic S ≈133 MB; DeBERTa ≈369 MB (`model.safetensors` at the pinned revisions; one-time). DeBERTa resident memory is ≈1.1–1.5 GB (Phase 34 bakeoff) | Same |

**Consequences**
- **Modernization of a large library spans several sessions.** Pause, close and reopen are the normal case, not an
  edge case.
- **MiniLM remains the retrieval model for one to two days of active use**, and must stay complete and correct the
  whole time. The current per-identity isolation already guarantees this.
- **Disk is a real constraint.** Several GB, plus WAL growth, on laptops.

---

## 5. Decisions authorized, gates outstanding, verdict

### 5.1 Authorized (Cliff, 2026-10-31)
| # | Decision |
|---|---|
| A1 | Development base: `integrate/inc607-608-ask` @ `af53b1d2`, worked in its isolated worktree. **No merge into the dirty main checkout now.** A reviewed, clean-tree integration into `main` before a release candidate needs separate explicit authorization. No push, merge, tag, deployment or release |
| A2 | Arctic S is the **automatically preferred** retrieval model. It is used whenever the pinned model is verified and its index is complete and current for the eligible corpus. Otherwise the complete MiniLM index serves Ask. A partial Arctic index is never served |
| A3 | Automatic activation of Arctic S on completion, and automatic restoration after import catch-up, unless the user has made an explicit choice. A manual preference is never overwritten. An explicitly forced incomplete profile keeps the 608 fail-closed behavior, with a clear path to MiniLM; it is never silently converted |
| A4 | Provenance records the effective retrieval model, the target model and the fallback reason. The UI shows a concise explanation |
| A5 | DeBERTa is the **automatically preferred** NLI verifier once its operating gates are satisfied (§5.2). The effective verifier is resolved before each operation and recorded. MiniLM2 is the compatibility verifier until then. **Never** substitute MiniLM2 after a DeBERTa operation has started and failed (inc 609 fail-closed stays) |
| A6 | Models are provisioned automatically, at pinned revisions, with verification, bounded retries, automatic continuation when connectivity returns, and no library content sent. Arctic indexing is independent of DeBERTa provisioning; failing to obtain DeBERTa blocks nothing else |
| A7 | Modernization is additive-only: Arctic S vectors beside MiniLM, source-role v2 derived from existing chunks, model provisioning. No re-extraction, no rechunking; chunks, annotations, citations, paper metadata and MiniLM vectors are untouched. Not to be described publicly as rechunking |
| A8 | MiniLM/MiniLM2 remain wherever still needed (§7). Their full retirement is deferred and is not a release blocker |
| A9 | Scientific rules, thresholds and contracts stay frozen. The 0.6.0 adjudication program is closed. No new adjudication or model comparison without explicit authorization |
| A10 | Implementation in small, separately testable increments, each committed locally only after focused tests pass. The first increment (source-role v2 packaged, output unchanged) is in progress as inc 613 |

*Superseded:* the first steering's "do not automatically download DeBERTa for users who have not enabled it". The
later policy makes DeBERTa automatically preferred and automatically provisioned. See G2 for a sequencing consequence.

### 5.2 Qualification gates still outstanding (not authorized by the decisions above)
| Gate | What is open | Blocks |
|---|---|---|
| **G1, DeBERTa scientific qualification at the shipped thresholds** | **Closed by product decision (§5.2a): CONDITIONAL result accepted, not retroactively a PASS.** Receipt `G1_DEBERTA_EXACT_THRESHOLD_RECEIPT.md` | Nothing further; activation waits on the implementation safeguards in §5.2a |
| **G2, DeBERTa CPU latency and memory acceptance** | **Conditional runtime acceptance (§5.2a).** Receipt `G2_DEBERTA_CPU_RESOURCE_RECEIPT.md`: ≈ +3 s per 21-pair verification, ≈ +1.06 GB peak working set, fits the inc-610 policy on 16 GB. Packaged-runtime recheck still owed | Release arming only (packaged-runtime recheck) |
| **G3, merge authorization** | A clean-tree reviewed integration into `main` | The release candidate |
| **G4, three-platform packaging and upgrade validation** | B10 | Release |

### 5.2a Accepted G1/G2 decision (2026-10-31, increment 615 instruction)
- **DeBERTa is the intended automatically preferred synthesis NLI verifier for 0.6.0.** This explicitly accepts the
  G1 **CONDITIONAL** result; it does not claim that G1's original strict GO rule passed (it failed by one net false
  `contradicted` on SciFact, 7 against 6).
- **Accepted tradeoff:** fewer incorrectly verified claims on the Phase 34 set (1 vs 5); no increase on SciFact (1 vs
  1); substantially more genuine contradictions recognized; one additional net false `contradicted` on SciFact.
- **Remaining uncertainty, preserved in documentation and provenance:** the 0.55/0.55 thresholds are MiniLM2-
  calibrated and not independently optimized for DeBERTa (`thresholds_calibrated_on` already records this).
- **G2:** conditional runtime acceptance.
- **Required before DeBERTa is used automatically** (later increments; none needs new adjudication):
  1. per-operation memory precheck, with MiniLM2 as the allowed compatibility verifier and the actual model identity
     and fallback reason recorded;
  2. once an operation starts on DeBERTa, no MiniLM2 substitution (fail closed, inc 609);
  3. verifier-specific ETA/progress accounting (invariant #5);
  4. cautious wording for DeBERTa `contradicted` findings ("the model judges this source to disagree; check the quote");
  5. packaged-runtime recheck (cold + warm 21-pair) before release.
- The MiniLM cosine retrieval-verification gate (0.70) stays operational; G1 showed it is what keeps some
  unsupported claims out.
- **Provisioning (inc 615) is not qualification.** A verified checkpoint proves bytes and static contract only.

**G1/G2 sequencing consequence.** Automatic DeBERTa *provisioning* (A6) without activation would download ≈369 MB
to every machine for a model that cannot yet be used. The directive also says not to download unnecessary models.
The recommendation:
- implement provisioning now;
- **arm DeBERTa's automatic download only when the release configuration marks G1 and G2 satisfied**: one constant,
  pinned by a test;
- until then, provision it only when the user selects it, the existing route.

This is reported here as a conflict between two directive requirements, not resolved silently.

### 5.3 Verdict
**CONDITIONAL GO** to continue modernization implementation (increments 1–5 of the sequence). Retrieval-side
modernization (A2–A4, A6–A7) is fully authorized and has no open scientific gate. **NO-GO for release** until
B1–B10 are accepted and G1–G4 are resolved, or until Cliff decides to ship with DeBERTa automatic preference
disarmed (MiniLM2 as the effective verifier, DeBERTa selectable).

## 6. DeBERTa thresholds: investigation for automatic deployment

**The app configuration** (`app/backend/summarization/nli_profiles.py:6-7,51,62`; `verification.py:70-77`):
- DeBERTa reads the same two probabilities with the MiniLM2-calibrated thresholds: support ≥ 0.55, and
  `contradicted` at contradiction ≥ 0.55 with contradiction greater than support.
- The profile is labelled "Experimental and uncalibrated".
- Provenance records `thresholds_calibrated_on = cross-encoder/nli-MiniLM2-L6-H768`.

**The only existing evidence** is the Phase 34 scientific NLI bakeoff,
`%USERPROFILE%\callosum-worktrees\c1-child-retrieval\experiments\ask_cli_revised\PHASE34_SCIENTIFIC_NLI_MODEL_BAKEOFF_RESULTS.md`:
- both pinned checkpoints;
- 99 pairs, single AI adjudicator, synthetic negatives derived from MiniLM-verified claims, previously inspected.

| Finding | Value | Bearing on 0.55/0.55 |
|---|---|---|
| Main set, supported / negatives admitted | DeBERTa 45/59, 2/27 at both *t* = 0.50 and 0.70 (flat 0.50–0.80); MiniLM2 42/59, 8/27 at 0.50 and 40/59, 6/27 at 0.70 | 0.55 lies in DeBERTa's flat band. On this set DeBERTa at 0.55 admits **fewer** negatives than the current production default (MiniLM2 at 0.55) and more supported claims |
| Held-out split, dev-selected *t* | DeBERTa at 0.50: 30/40 supported, 2/16 negatives; MiniLM reference 0.90: 24/40, 3/16 | Supports "not worse than the status quo", at a neighbouring threshold |
| Supplementary human-labelled SciFact pairs (post hoc) | At 0.50: DeBERTa admits 64/138 supported but 5/71 contradictions; MiniLM 35/138 and 3/71. At 0.70: 56 and 4 vs 28 and 2 | **At a fixed threshold DeBERTa lets through more natural contradictions.** The bakeoff concludes a threshold "cannot be carried across" |
| `contradicted` status | Not evaluated: the bakeoff used a single support knob | Unknown |
| Bakeoff's own disposition | "CHALLENGER PROMISING"; "replacement is not justified without a separate qualification"; "0.50 here is not a recommendation" | Automatic activation is beyond what that evidence was designed to support |

**The precise unresolved release decision.** Is DeBERTa accepted as the automatic verifier **at the unchanged
MiniLM2-calibrated thresholds**? The evidence argues both ways:
- for: on the 99-pair set it is non-inferior to the current default at the current thresholds;
- against: on natural contradictions it admits more, the contradiction rule is untested, and the bakeoff disclaims
  a qualification.

Recalibrating is excluded by the directive. Only acceptance at the frozen thresholds, or deferral, is available.

**Smallest defensible validation** (needs separate authorization; not started):
1. **Offline re-score at the shipped thresholds, with no new labels.** Run the already frozen, already labelled
   Phase 34 pairs (the 99 main pairs plus the 209 SciFact development pairs) through the **app's** verification
   code path (`verification.py` statuses: verified / contradicted / flagged) with MiniLM2 and DeBERTa at exactly
   0.55/0.55.
   - Report the status confusion against the existing labels, including how often `contradicted` fires on true
     contradictions and on supported claims.
   - This is a re-measurement of the shipped configuration on existing data, not an adjudication or a model
     comparison for selection.
   - Decision rule, to be fixed before running: DeBERTa may be armed if, on both sets, it admits no more
     contradicted/negative pairs as `verified` than MiniLM2 does at the same thresholds, and its `contradicted`
     status does not fire on more supported pairs than MiniLM2's.
2. **G2 latency and memory receipt** on the app path.

If item 1 fails, or Cliff judges the bakeoff's §7 qualification (fresh natural negatives, human adjudication)
necessary, ship with automatic DeBERTa disarmed: MiniLM2 effective, DeBERTa selectable, everything else unchanged.

## 7. MiniLM dependencies retained in 0.6.0
These remain on MiniLM or MiniLM2 in 0.6.0. None blocks automatic Arctic S retrieval or a DeBERTa synthesis
verifier, because each is an independent role. The full inventory and retirement plan is in
`RELEASE_060_DEFERRED_BACKLOG.md` §B.
- **Ask verification similarity** (retrieval ≥ 0.70 gate) and quote extraction: MiniLM, by design (inc 608).
- **The MiniLM chunk index:** the complete fallback generation, embedded by every ingest path.
- **Paper and axis embeddings, axis scoring** (assignment 0.7 / uncertainty 0.5), clustering, duplicates,
  discovery/acquisition similarity and capture: MiniLM.
- **Stance/NLI outside synthesis:** Suggest-citation, Critical Read (single, set, WIP), citation context,
  classify-stance, and imported-synthesis re-verification stay on MiniLM2 (pinned by
  `test_stance_features_and_reverify_keep_the_baseline_nli`).
- **Historical provenance:** stored `scope_ref_json` identities and `embedding_version_verified_against`.
