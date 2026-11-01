# Background modernization: architecture (proposal)

**Status:** proposal. Only step 1 is implemented: the packaged source-role derivation, inc 613 `829f35f4`.

**Revised 2026-10-31** for the model-transition policy:
- Arctic S and DeBERTa are automatically preferred when their gates are met;
- MiniLM and MiniLM2 stay as compatibility infrastructure;
- full MiniLM retirement is deferred.

See Scope §5 for authorized decisions A1–A10 and outstanding gates G1–G4.

**Design rule:** reuse inc 610 wherever it fits. Add only what 0.6.0 needs, and do no work a paper does not need.

---

## 1. The target, and what "outdated" means

A library is **modern for 0.6.0** when all three conditions below hold. Each check is computed from stored truth,
never from a counter.

| Component | "Current" test | Existing function |
|---|---|---|
| Arctic S retrieval generation | Every eligible article-fulltext chunk of a live paper has a vector with Arctic's full identity and `source_chunk_version == source_text_version == chunk.chunk_version` | `profiles.profile_coverage` (`app/backend/embeddings/profiles.py:137`); `profile_index.pending_chunk_ids` (`profile_index.py:45`) |
| Source-role classification | Every live paper with chunks has `chunk_structure` rows at `chunk-structure-v2`, with matching `raw_sha`/`chunk_version` | `chunk_structure_repo.papers_with_current_structure` (`:232`); staleness in `structure_role_states` (`:183`) |
| Models | Arctic S and DeBERTa snapshots present at the pinned revisions; DeBERTa contract verified | `PINNED_MODEL_REVISIONS`; `nli_profiles.verify_nli_checkpoint` (`:103`) |

**Per-paper minimality**
- A paper whose chunks all have current Arctic vectors gets no embedding work.
- A paper already current at v2 gets no classification.
- Metadata-only papers are reported, not counted as gaps (`profile_coverage`'s `papers_without_passage_text`).
- **No paper is re-extracted or rechunked**, because extraction has not changed since 0.5.16.
- MiniLM vectors are never regenerated.

**Ingest-time interaction.** New and re-extracted papers enter the same pending sets automatically, because both
tests are computed rather than stored. No separate trigger list is needed.

## 2. Can the schema hold old and new generations at once?

This was checked against the code, not assumed.

| Layer | Holds old and new simultaneously? | Why | Consequence for 0.6.0 |
|---|---|---|---|
| **Embeddings** | **Yes** | `embeddings` rows carry `(model_name, model_version, normalization, dimension, source_chunk_version)`. The same-dimension profiles share `callosum_vec_embeddings_384`, and every search is restricted by `candidate_embedding_ids` (an AST-tested invariant) | MiniLM stays complete and authoritative for Ask while Arctic builds. **No dual-schema work is needed** |
| **`chunk_structure`** | **No.** One row per `chunk_id` (PK, `schema_chunk_structure.py:59`) | v2 replaces v1 per paper inside one transaction (`replace_paper_structure`, `:50`). Stale rows are recorded but never obeyed, so a not-yet-reclassified paper behaves as unclassified (eligible) | **Safe mixed state.** During reclassification a paper is either fully v1 (ignored, so fail-open, as in 0.5.16) or fully v2. A half-classified paper is impossible |
| **Chunks** | **No.** A single generation; `chunk_version` is a content version, not a generation key | Re-extraction replaces rows. `citation_mappings.chunk_id` and `registration_*.chunk_id` are `ON DELETE SET NULL`; `chunk_structure` cascades. Annotations are anchored by `attachment_id` + `page` + bbox, not by chunk | **Not exercised in 0.6.0.** A future extraction change would need a real side-by-side generation design (deferred backlog D7). 0.6.0 must not change extraction |
| **Settings** | One active value per key | `library_settings` (0085) | The flip is one row write (§6) |

**Conclusion:** 0.6.0 needs no generation tables, no shadow chunk sets and no remapping, only additive vectors and
per-paper derived-row replacement. This is the smallest sound architecture, and it exists because the release
scope excludes extraction changes.

## 3. Components

The proposal adds one coordinator and two stage adapters. Everything else is existing code.

```
lifespan startup (api/app.py ~:228)
  └─ ModernizationCoordinator.reconcile()          NEW   app/backend/modernization/coordinator.py
       ├─ detect()  -> {models, structure_pending_papers, arctic_pending_chunks}
       ├─ stage 1: ensure_models()                  NEW   (B2) snapshot_download(pinned) -> verify -> local-only
       ├─ stage 2: classify_pending()               MOVED (B4) app/backend/pdf_processing/structure_backfill.py
       │                                                  (pure move of tools/backfill_chunk_structure.backfill core)
       ├─ stage 3: arctic index                     REUSE  IndexSupervisor.start / intent=run (inc 610)
       └─ activate_if_complete()                    NEW   (B6) one run_write: re-check coverage -> set_active_*
  monitor tick (index_supervisor._monitor, 2 s)    REUSE  + coordinator.tick() every N s: catch-up, disk, network
Ask (_retrieval_model, routers/summaries.py:439)   CHANGED (B5) effective profile = target if complete else MiniLM
Status (embedding_index_jobs mirror)               REUSE  relabel "Library modernization", carries stage
```

**Ordering**
1. Models, then classification, then Arctic indexing.
2. Classification runs before indexing because it takes minutes and delivers the scientific change to the narrow
   path immediately. Indexing takes hours.
3. Classification does not depend on Arctic, and Arctic does not depend on classification, so a failure in one never
   blocks the other: the coordinator advances each independently.

### 3.1 The coordinator
- **State it owns.** Nothing new on disk except two `library_settings` keys:
  - `modernization_intent`: `run` or `pause`; a user's Pause persists here.
  - `retrieval_embedding_profile_source`: `modernization` or `user` (§6).

  Arctic progress lives in `embedding_index_runs` (migration 0086, unchanged). Classification progress *is* the set
  of v2-current papers, so it needs no checkpoint table. **No migration is required.**
- **`reconcile()`** runs once at startup, after `reconcile_index_builds`. **`tick()`** runs from the existing monitor
  thread at low frequency (≈30 s). Both are idempotent.
- **Concurrency.** It runs in-process on the existing monitor thread. Classification runs on one low-priority
  daemon thread, one paper per transaction, through `run_write` (`persistence/sqlite_retry.py`), which already opens
  a fresh connection with retry-on-lock.
- **Ownership.** The existing `index_lock.py` OS lock guarantees one Arctic worker per library across processes.
  Classification is safe to run twice concurrently: per-paper replacement is idempotent and deterministic. A second
  library-scoped OS lock, the same `index_lock` primitive with a different lock file, avoids the wasted duplicate
  effort.

### 3.2 Stage 1: models (B2)
- Use `huggingface_hub.snapshot_download(repo_id, revision=pinned)` into the default HF cache. That cache is already
  where MiniLM and MiniLM2 live in the packaged app. It carries **no library content** and is the same class of
  egress as the existing first-run MiniLM download.
- **Results:**
  - `waiting_network`: retry with backoff 30 s → 10 min, then indefinitely at 10 min;
  - `verified`;
  - `model_invalid`: terminal; the user sees an exact message, and MiniLM Ask is unaffected.
- After verification the supervisor is configured with `local_files_only=True` (`SupervisorConfig.local_files_only`,
  `index_supervisor.py:55`), so a worker never reaches the network.
- **Two independent model tracks** (A6):
  - Arctic S (≈133 MB) is provisioned first and unconditionally, because the retrieval target needs it.
  - DeBERTa (≈369 MB) has its own track and state. It never blocks Arctic, classification or library use.
  - **DeBERTa's automatic download is armed only when `DEBERTA_AUTOMATIC_PREFERENCE_QUALIFIED` is true** (G1/G2;
    Scope §5.2). Before that it is provisioned only on an explicit user selection, the existing route. This avoids
    downloading an unusable model to every machine.
- **No repeated work.** A verified snapshot is recorded as `(repo, revision, verified_at)` in `library_settings` and
  re-verified only when the files' sizes or mtimes change. Nothing is downloaded on launches after the first success.

### 3.3 Stage 2: source-role v2 (B4)
- **Done in inc 613:** the derivation lives in `app/backend/pdf_processing/structure_backfill.py`, byte-identical
  to the tool, with `tools/backfill_chunk_structure.py` as a CLI.
- **Before the coordinator uses it:** restrict `papers_with_current_structure` to article-role chunks
  (`ARTICLE_DOCUMENT_ROLES`). Otherwise papers with preregistration attachments never become current and are
  re-derived on every tick (found in inc 613).
- It is cache-only. Papers without Crossref references get no anchored region. They are still classified by the
  other rules, and this is the existing, gated behavior.
- **Ordering:** papers with the most recent `updated_at` first, so newly imported papers are covered quickly. Order
  has no effect on output.

### 3.4 Stage 3: Arctic S index (reuse inc 610)
- The coordinator sets intent `run` through `index_runs.upsert_requested` (`index_runs.py:57`) and calls
  `IndexSupervisor.start`.
- Everything else is inc 610 as shipped:
  - batches of ≤8, each committing vectors, identity rows and checkpoint in one transaction;
  - memory floors, with halving on resource exits;
  - the circuit breaker;
  - reconciliation from vectors.

  These are `profile_index.index_chunk_batch` (`:49`), `index_supervisor._maybe_launch` (`:370`) and `_on_exit`
  (`:442`).
- **Catch-up:** when coverage drops (an import), `tick()` re-requests intent `run`, unless paused.

## 4. Resource bounding
| Resource | Mechanism | Status |
|---|---|---|
| CPU | Worker at below-normal priority, or `nice 5` (`index_supervisor.py:126-137`); threads `min(4, cpu/2)` (`:56`); classification on one thread | Existing; classification thread new |
| Memory | `resources.py` commit/available measurement; reserve/stop/pause floors; batch halving; the `insufficient_memory` breaker | Existing |
| Disk | Preflight estimate plus the runtime floor through `shutil.disk_usage`; `waiting_disk`; the `SQLITE_FULL` exit code | **New (B7)** |
| Network | Model stage only; `waiting_network` | **New (B2)** |
| SQLite contention | Short per-batch and per-paper transactions; `run_write` retry; worker exit 69 (DB busy) is classified retryable | Existing |
| Battery or metered network | Not handled | Deferred (D9) |

## 5. Retrieval while modernization is unfinished or failed (B5)
**Rule: never retrieve from a partial index, and never present one as complete.**

For each Ask, `_retrieval_model` resolves the **effective** profile:
1. If the user explicitly chose a profile (`source=user`), it is honored and never overwritten.
   - A user-chosen MiniLM stays MiniLM.
   - A user-forced Arctic S with an incomplete index keeps the 608 fail-closed behavior: `IncompleteEmbeddingIndexError`
     with both remedies, including a one-click "Use automatic selection" or MiniLM. It is never converted silently.
2. Otherwise (`source=modernization`, or unset):
   - the target profile (Arctic S) if its model is verified **and** `profile_coverage` is complete (identity and
     source-chunk versions included);
   - **else MiniLM**, which is always complete because every ingest path embeds it.
3. Provenance (`scope_ref_json.retrieval_embedding`, inc 609) records:
   - the effective profile that ran;
   - `target_profile` (`arctic-s`);
   - `fallback_reason`: `model_unavailable`, `modernizing`, `catching_up`, `failed` or `paused`.
4. The UI shows the existing provenance line plus one muted note.

**The scientific semantics of each profile are untouched:**
- the same candidate pools;
- the same `order_for_budget`;
- the same `candidate_embedding_ids` isolation;
- verification similarity stays on MiniLM with its 0.70 gate.

**Classification state** never gates Ask. Unclassified papers are eligible (fail-open), exactly as in 0.5.16, and the
heading rescue is text-only.

**Faceted path:** the same resolution, applied to `faceted_pipeline.py:231`.

**As implemented (inc 618).** The policy lives in `embeddings/retrieval_resolution.py::resolve`, reached through
`routers/modernization.py::resolve_retrieval` and called once per operation by `_retrieval_model`. The faceted path
needed no separate change: `_run_summarize_job` resolves before `summarize_faceted`, which receives the model.
Differences from the proposal above:
- Automatic selection applies only when the coordinator is enabled (packaged app or `CALLOSUM_MODERNIZATION=1`). A
  source checkout keeps MiniLM unless the user chooses otherwise.
- Provenance field names: `intended_profile` (not `target_profile`), plus `preference`, `preference_source`,
  `index_verified_complete` and `index_contract`. Reasons: `model_unavailable`, `indexing` (not `modernizing`),
  `catching_up`, `paused`, `cancelled`, `failed`.
- MiniLM is complete because its contract is lazy (the ranking step embeds missing candidates), not because every
  ingest path embeds it; the record says `index_contract: baseline_embeds_missing`.
- The way back from a forced incomplete Arctic S is the Settings "Automatic" option or
  `PUT /embedding-profiles/active {"key": "automatic"}`; the error text names both.
- Pause stops background work, not use: a complete, verified Arctic index is used while modernization is paused.

## 5a. Verifier resolution (B8)
Before each synthesis or re-verification operation, resolve the **effective verifier** once:
1. **An explicit user choice** of MiniLM2 or DeBERTa is honored. A forced DeBERTa that is unavailable fails with a
   clear path back to automatic selection. It is never converted silently.
2. **Otherwise DeBERTa**, when all of these hold:
   - the pinned snapshot is present and verified (`verify_nli_checkpoint`, `nli_profiles.py:103`);
   - `DEBERTA_AUTOMATIC_PREFERENCE_QUALIFIED` is true (G1, G2);
   - the `resources.py` free-memory check covers the measured DeBERTa peak plus the reserve.
3. **Otherwise MiniLM2**, with `verifier_fallback_reason` recorded.
4. **Once an operation has started, the verifier is fixed.** A DeBERTa inference failure fails the operation (inc 609
   `NLIInferenceError`; no row written). MiniLM2 never finishes a DeBERTa operation.
5. **Provenance** records `verification_nli` (actual), `preferred_verifier` and `verifier_fallback_reason`. The
   thresholds and the `thresholds_calibrated_on` field are unchanged.

**Scope.** This covers synthesis verification only, the inc 608 scope. Stance features, Suggest-citation, Critical
Read, citation context and imported re-verification keep MiniLM2 (§7 of the Scope document; pinned by test).

**As implemented (inc 619).** `summarization/verifier_resolution.py::decide`, called once per synthesis by
`summaries._verifier` (before retrieval). Differences from the text above:
- The gate is `DEBERTA_RELEASE_GATES` / `deberta_auto_provisioning_armed` (inc 615); field names are
  `preferred_profile` and `fallback_reason` inside `verification_nli`.
- Memory: free = min(available physical, available commit) from `resources.measure()`; need = 1,500 MB when DeBERTa
  is not resident (G2: 540 → 2,016 MB peak), 512 MB when it is, plus a running Arctic worker's recorded peak (or the
  1,200 MB estimate); `ResourcePolicy.can_start` adds the reserve. Unmeasurable → `memory_unmeasured`.
- A load or contract failure before scoring is `not_verified` (automatic → MiniLM2; explicit → refused).
- Imported re-verification still uses MiniLM2 (the stated scope), so §5a's "or re-verification" does not apply yet.

## 6. Atomic activation (B6)
`activate_if_complete()` runs in **one** `run_write` transaction:
1. Re-compute `profile_coverage(conn, arctic)`. If it is not complete, abort.
2. If `retrieval_embedding_profile_source == "user"`, never override.
3. Otherwise call `set_active_retrieval_profile(conn, "arctic-s")` (`profiles.py:112`) and set the source to
   `modernization`.
4. NLI is **not** flipped by writing a setting. The verifier is resolved per operation (§5a), so DeBERTa becomes
   effective as soon as its conditions hold, and stops being effective if they stop holding.

**Consistency.** SQLite serializes the write against concurrent imports. An import committed after the flip makes
coverage incomplete, and §5 resolves that to MiniLM until catch-up. An Ask in flight keeps the model it resolved at
start.

**As implemented (inc 618).** `activate_arctic` in `embeddings/retrieval_resolution.py`. It takes SQLite's writer lock
first (no-op UPDATE) so its reads cannot be overtaken, then checks the preference, the model's verified state and
coverage, in that order. Resolution does not wait for activation: a complete, verified index is used from the first
operation, and activation records that modernization made the choice. "An Ask in flight keeps the model it resolved"
holds; if the library changed under it, the ranking-time check fails the operation closed (nothing saved) rather than
searching a partial Arctic index.

## 7. Annotations, anchors and citations
**Preserved by construction.** 0.6.0 writes only:
- `embeddings` and vec rows (added);
- `chunk_structure` rows (derived, replaced per paper);
- `library_settings` and `embedding_index_runs`.

**It never touches:**
- `chunks`;
- `annotations` (anchored by `attachment_id`/page/bbox, `schema_annotations.py:28-29`);
- `citation_mappings`;
- `source_representations` / `source_components` (SourceLocator identity, inc 579);
- `papers`.

The test plan asserts this with table fingerprints, using the existing fingerprint technique from the held-out work.

## 8. Unreadable or missing PDFs
- Neither stage reads PDFs. Arctic indexes stored chunk text, and classification reads stored chunks plus cache.
- **Missing or unavailable attachments do not block modernization**:
  - their existing chunks are indexed and classified;
  - a paper with no chunks is metadata-only and reported, not counted as a gap.
- A chunk with empty text is embedded as stored, the existing behavior.

## 9. Offline operation
- Fully offline after stage 1. Stages 2 and 3 make no network call:
  - classification is cache-only;
  - the worker runs with `local_files_only=True`.
- If the models are absent and the machine is offline:
  - `waiting_network`;
  - classification still proceeds;
  - Ask keeps working on MiniLM, with MiniLM2 verification.

## 10. Progress accuracy
- **Truth comes from storage:**
  - Arctic: `indexed_chunks / eligible_chunks` from `profile_coverage`;
  - classification: `v2-current papers / papers with chunks`.
- **ETA** comes only from measured recent throughput: the existing checkpoint timestamps in `embedding_index_runs`.
  Until one batch has completed, it is indeterminate, per invariant #5.
- **No combined percentage across stages.** The stages report separately within one Status row, with the stage name
  first. This follows principle 7: no opaque composite.

## 10a. Visibility as implemented (inc 620)
- **One derived entry.** `modernization_status_job(app)` builds the "Library modernization" Status row from
  `coordinator.status()` plus the Arctic run row on every `/status/jobs` read. It holds no state of its own, so it
  is identical after a restart and in every window. It is omitted when modernization is disabled or complete. While
  modernization is enabled, the `embedding_index_jobs` mirror row is hidden so the build is not shown twice.
- **Summary mapping** (`modernization/presentation.py`, pure). Precedence: paused intent → indexing actively running
  → classification running (or owned by another window) → model downloading → indexing starting → any wait (disk,
  memory, network, database busy, retry, waiting for the model) → attention only → complete. Terminal conditions
  (model `invalid`, run `failed` / `cancelled`) are listed in `attention` alongside whatever is still working; they
  become the state only when nothing else is. When the model is invalid or not installable, an index that is
  "waiting for the model" is reported as blocked, not waiting.
- **Progress.** One grounded `progress` block for the current activity only: passages indexed / eligible passages,
  or papers current / papers with classifiable passages. No combined percentage, no download percentage (the
  provisioner has no reliable downloaded-byte count) and `eta_seconds` is always null.
- **Non-blocking reads.** `status()` try-acquires the coordinator lock for 0.2 s. During a classification pass it
  returns the counts cached at `checked_at` and reads the run row, intent, model state and preference directly.
- **Effective retrieval** is the inc-618 `resolve()` itself (an `IncompleteEmbeddingIndexError` becomes
  `ask_blocked`), cached for up to 60 s keyed on the counts, run state, model state, intent and preference, so a
  poll does not repeat the coverage count. **Effective verifier** is `dependencies.preview_verifier()`, the same
  no-load preview the NLI settings panel uses.
- **Frontend.** One refresh loop (`LibraryModelsSection`) reads `/modernization` and `/embedding-profiles` together;
  `modernizationPollDelay` returns 2 s (build busy), 5 s (build waiting, incl. `waiting_disk`), 3 s / 10 s (other
  working / waiting) or stops. The Status popover keeps its own existing cadence.

## 11. What is deliberately *not* proposed
- No generation-swap tables, no chunk remapping, no re-extraction.
- No automatic Crossref fetching to improve anchoring: that would be new egress, and it is a separate, consented
  enrichment action.
- No partial-index retrieval, ever.
- No deletion of MiniLM vectors or paper/axis embeddings. MiniLM is the verification-similarity model, the fallback
  generation and the clustering/axis model in 0.6.0. Its retirement is a deferred workstream
  (`RELEASE_060_DEFERRED_BACKLOG.md` §B).
- No transplanting of MiniLM-specific similarity thresholds to Arctic S, and no NLI threshold recalibration.
- No deletion of shared Hugging Face caches.
- No change to classifier rules, thresholds, `DERIVATION_VERSION`, NLI thresholds or Qwen2.5 synthesis.
