# Increment 609 — 607 + 608 integration; NLI failure fails closed for every profile; visible model provenance

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), based on inc 608
`c9ada5ff`. Not pushed, not merged into main.

## Implemented

**A. Integration of inc 607 onto inc 608.** `git cherry-pick -x e4d4f4e4` became `d85556b6`, with the original
author and the `(cherry picked from commit e4d4f4e4…)` line. Four files conflicted:
- `app/backend/summarization/pipeline.py`: inc 608 had moved `_rank_chunks_for_query` and
  `_select_ranked_with_paper_coverage` verbatim into `query_ranking.py`, while 607 edited them in their old place.
  608's layout is kept, and 607's three ranking edits are applied in `query_ranking.py`: over-fetch
  `top_k * ELIGIBILITY_OVERFETCH`, `order_for_budget` over the hits, then `ranked[:top_k]`. `pipeline.py` keeps 607's
  `evidence_selection` import for the no-query path. 608's fail-closed check and `encode_query` are unchanged.
- `demo/experience-coverage-v1.json` and `www/showcase-coverage.json`: the later 608 deferral, which covers 607, is
  kept; this increment extends it to 609.
- `.claude/CLAUDE.md`: the increment counter is reconciled.

Every other 607 file is byte-identical to `e4d4f4e4`. No eligibility rule, threshold or expected outcome changed.

**B. MiniLM2 silent fallback removed.** `ModelRuntimeRegistry.get_support_scorer` no longer attaches
`EmbeddingSupportScorer` as a fallback, so the dead `embedding_model` parameter is removed from it and from
`resolve_support_scorer`. `NLISupportScorer` without a fallback raises `NLIInferenceError`, which carries the model
name and cause. The Ask job (narrow and faceted) catches it and fails with "Citation verification failed, so no
synthesis was saved." The verify+persist transaction rolls back, so no row is written. Re-verify returns **503**
before any write, and the imported synthesis stays imported. `default_support_scorer` keeps its fallback because no
app route reaches it; only `tools/validation_harness.py` and fake-model tests do, and that boundary is pinned by a test.
`StanceScorer` was already fail-closed per pair (Suggest-citation, Critical Read, citation context) and is unchanged.

**C. Provenance recorded on every run and returned.** `_retrieval_model` now records the baseline too
(`embeddings/profiles.baseline_retrieval_provenance`, read from the encoder that ran). `verification_nli_provenance`
records the baseline too and adds `embedding_fallback: false`. Re-verification writes the baseline identities it
used. `SummarizeJobResponse.model_provenance` (`routers/summaries_provenance.py`) is derived only from
`scope_ref_json`:
- `recorded=false` with no model names for rows that never recorded provenance;
- `None` for an imported synthesis;
- never filled in from the current Settings.

UI: `js/20e_model_provenance.jsx` renders the provenance line on Synthesize → Ask and on the reader/axis scoped Ask,
using the existing `synth-coverage` recipe (no CSS change). Help corpus: one bullet. QA route 97 extended.
`tools/backfill_chunk_structure.py` docstring corrected: it said nothing on the retrieval path reads its output,
which has been false since 607.

## Key technical detail — the integrated Legacy Ask call graph (verified against code)

```
POST /summarize -> _run_summarize_job (routers/summaries.py)
  model = baseline MiniLM (verification similarity, 0.70 gate)
  retrieval_model, provenance = _retrieval_model()        # 608: active profile; non-baseline needs a complete index
  support_scorer = resolve_support_scorer(nli_profile)    # 608/609: MiniLM2 or DeBERTa, no embedding fallback
  query scope, no sections -> plan_query()                # egress-gated LLM planner
    broad  -> summarize_faceted(...)                      # 608 profile YES; 607 eligibility NO (narrow-only by design)
    narrow -> summarize_scope -> _source_chunks_for_scope
                scope SQL (papers | cluster | query)
                sections allow-list | heading-based reference exclusion (#82, query scope)
                repeated-boilerplate removal
                query:    query_ranking._rank_chunks_for_query
                            current vectors for THIS model identity; non-lazy gap -> IncompleteEmbeddingIndexError
                            vector_store.search(candidate_embedding_ids = this identity, top_k*3)   # 608
                            order_for_budget (chunk_structure demotion) -> [:top_k]                  # 607
                no query: _select_no_query(top_k*3) -> order_for_budget -> [:top_k]                # 607
  generator.generate (LLM) -> LocalCitationVerifier(model=MiniLM, support_scorer) -> verify_many -> persist
  scope_ref_json += retrieval_embedding + verification_nli -> response.model_provenance
```

Eligibility reads `chunk_structure` by chunk id only, so for the same candidates it decides identically whichever
model ranked them. Which candidates reach it does depend on the model, which is the point of the comparison.

## Manual verification script

1. Start the integration worktree's server against a disposable library copy at alembic 0085.
2. Run Ask on the baseline. Under "Retrieved N source chunks" the screen shows "Retrieval: MiniLM (baseline) ·
   Verification: MiniLM2 NLI (baseline)"; hover shows the exact ids.
3. Open a synthesis saved before 609: "Models: not recorded for this synthesis".
4. Select DeBERTa, run Ask: "Verification: DeBERTa-v3 base NLI (experimental; thresholds calibrated on MiniLM2)".
   Switch back to MiniLM2 and reopen it: the line is unchanged.
5. With the NLI model unavailable (e.g. `HF_HUB_OFFLINE=1` and an uncached model), Ask ends in "Citation
   verification failed, so no synthesis was saved."

**Not performed:** no browser was available (Playwright MCP failed to connect), and no server was started (resource
limits). The UI is verified by static and bundle tests only.

## Pytest (new runs on this branch, serial)

- After the cherry-pick: 607 + 608 targeted set **130 passed, 15 skipped**. The skips were 607's frozen q_lld tests,
  whose artifacts live only in Codex's worktree `.local\`. Run against them through temporary read-only junctions
  (opened `mode=ro&immutable=1`, junctions removed afterwards): **11 passed, 4 xfailed (strict)**, the same 4
  expected failures as 607's receipt. This run also confirms the junctions were removed.
- Final targeted run (25 files: 607 eligibility/selection/DOI-owner/frozen, 608 profiles/NLI, the two new 609 files,
  Critical Read set, summaries/summarization/selected/faceted, reverify, NLI support, model runtime, migrations,
  startup, health, status, overview + lifecycle, help, both Overview freeze suites): **289 passed, 15 skipped**
  (the frozen set, covered by the junction run above) in 3 min 26 s, peak 295 MB, lowest available memory 4.5 GB.
  `tests/test_frontend_assembly.py`: **88 passed** after the bundle rebuild. New 609 tests: 8 + 3.
- Gates: ruff format/check, tach, 600-line budget (665 files), bandit, QA coverage 459/459, changelog drift, and the
  demo/website gates (after extending the deferral to 609): all pass.
- Not re-run: the full suite. The previously recorded individual receipts stand separately: 607 had 148 passed and
  4 xfailed; 608 had 327 targeted passes and a full suite of 3,514 passed, 6 failed (CRLF artifact) and 12 skipped.

## Known limitations

1. **607 false exclusions remain.** Three native-morphology withholds of real prose (chunks 23431, 35671, 38379) and a
   mislabelled span that flags Methods quotes are recorded as strict xfails and are not fixed. No paper-specific
   exception or threshold change was made.
2. **607 covers only the narrow path.** Broad questions (LLM planner → faceted path) apply 608's profile but not
   607's demotion.
3. **607 has no effect on the candidate corpora today.** The DEV library
   (`C:\Users\cliff\callosum-data\dev-postimport-20261029\dev.sqlite`, alembic 0084) and the Arctic disposable copy
   (`...\experiments\arctic-index-20261029\copy.sqlite`, 0085) both hold **0** `chunk_structure` rows, so the seam
   is an exact no-op on them. Running `tools/backfill_chunk_structure.py --db-url sqlite:///<evaluation copy>`
   (cache-only, no network, resumable) is a prerequisite for any evaluation meant to include 607.
4. The Arctic index on the disposable copy is still paused at 25,453 / 42,044 and was not touched.
5. DeBERTa is not scientifically qualified. MiniLM and MiniLM2 remain the defaults, with thresholds unchanged.
6. Rows written before 609 cannot rule out a past silent cosine fallback; they report `recorded=false` rather than
   claiming MiniLM2.
7. No visual review. Desktop release qualification is outstanding. The DEV server stopped earlier for an
   undetermined reason and was not restarted.

## Lineage and preservation

No library, snapshot, frozen experiment, adjudication or launcher was modified. The Codex branch and worktree were
not modified: only temporary read-only junctions pointed into its `.local\`. No model was loaded or downloaded, no
LLM was called, there was no inference beyond fakes, and nothing was pushed.
