# Increment 608 — Selectable retrieval (Arctic S) and verification (DeBERTa) profiles; library identity guard

Numbering: main was at 606. Increment 607 (reference-eligibility repair, `e4d4f4e4`) lives on the unmerged
`codex/focused-discovery-tranche1` branch, so this increment takes 608 to avoid a collision.

## Implemented

**A. Development library identity and missing-database guard.** `CALLOSUM_DB_REQUIRE_EXISTING` makes startup raise
`MissingDatabaseError` before any engine connects when the configured SQLite file is absent (`api/startup.py`,
`api/app.py`). `CALLOSUM_LIBRARY_LABEL` adds `/health.library = {label, db_file, live_papers}` (`routers/health.py`;
`db_file` is parent folder + filename, never a full path) and a muted badge beside the Library eyebrow
(`js/03b_library_identity.jsx`, `js/10_pdf_layer.jsx`, `styles.css`). Both default off; the packaged app is unchanged.
The machine-local `run-callosum.ps1` launcher that sets them is gitignored and not committed.
Audit: `2026-10-29_library-identity-and-db-guard.md`.

**B. Arctic S retrieval profile.** `embeddings/profiles.py` defines revision-pinned profiles: `minilm` (default, legacy
stored identity unchanged) and `arctic-s` (`Snowflake/snowflake-arctic-embed-s@e596f507…`, CLS pooling, max_seq 512,
`whitespace-v1` case-preserving normalization, query prefix, no document prefix; all baked into `model_version`).
`embeddings/models.py` separates query and document encoding and refuses a checkpoint whose pooling or max sequence
length differs. Per-library selection lives in `library_settings` (migration 0085). `embeddings/profile_index.py`
builds a profile index per paper (resumable, cancellable, Status-tracked as `embedding_index_jobs`, Local AI).
`routers/embedding_profiles.py` exposes coverage, build, cancel and selection; selection of an incomplete index is
409. Only Ask retrieval follows the profile (`query_ranking.py`, split verbatim out of `pipeline.py` for the line cap;
`faceted_pipeline.py`); verification similarity stays on MiniLM and its 0.70 gate. A non-lazy profile is never
embedded on the fly: an incomplete index raises `IncompleteEmbeddingIndexError` and Ask fails with both remedies.
Critical Read (set) repair: `set_chunk_embedding_ids` now filters on the querying model's identity; before, it had no
identity filter.

**C. DeBERTa verification NLI profile.** `summarization/nli_profiles.py`: `minilm2` (default; legacy load path
untouched) and `deberta-v3-base` (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli@6f5cf0a2…`). Before use the loaded
checkpoint must match label order `{0: entailment, 1: neutral, 2: contradiction}`, `model_type deberta-v2` and a
`DebertaV2*` tokenizer; a mismatch is refused (409 on selection). Pairs stay `(passage, claim)`. Thresholds are
unchanged and labelled as calibrated on MiniLM2. The DeBERTa scorer is built with **no embedding fallback**: an
inference failure fails the Ask job (`status=error`, exception text in `detail`) instead of persisting cosine scores
under an NLI label. Synthesis records `scope_ref_json.retrieval_embedding` / `verification_nli` for non-baseline
runs. Scope: synthesis verification only; Suggest-citation, Critical Read, citation context and imported-synthesis
re-verification deliberately keep MiniLM2 (pinned by `test_stance_features_and_reverify_keep_the_baseline_nli`).

UI: Settings → Library behavior → Retrieval model (`js/35i_retrieval_profiles.jsx`), including the verification-model
radio group. Help corpus updated. QA route 97. Audit `2026-10-29_retrieval-and-nli-profiles.md` (+ addendum).

## Key technical detail

Same-dimension profiles share one sqlite-vec table, so isolation is a hard invariant at the search seam: every
`vector_store.search` passes `candidate_embedding_ids` built from `(model_name, model_version, dimension,
normalization)` of the querying model. An AST test fails if a store search omits it (and asserts ≥6 call sites so it
cannot pass vacuously); a behavioral test with reversed vectors in one shared store proves no mixing. Currentness is
`source_text_version == source_chunk_version == chunk.chunk_version`. Coverage counts article-fulltext chunks of live
papers; metadata-only papers are reported separately, never as gaps, and no abstract is synthesized.

The DeBERTa contract check matters because `stance._label_index` falls back to positional MiniLM2 order when label
names are missing; DeBERTa's order differs, so a silent positional read would swap entailment and contradiction.

## Manual verification script

1. Start DEV (`run-callosum.ps1`). The Library eyebrow shows the label badge; `/health` shows `library`.
2. Settings → Library behavior → Retrieval model: MiniLM active; Arctic S row shows model@revision, "Experimental",
   coverage `indexed of eligible`, Build index; radio disabled until coverage is complete.
3. Build, stop after a paper, reload: partial coverage, "Resume index build". Status shows one Local AI row.
4. Verification model: select DeBERTa → Status shows "Verifying NLI model checkpoint"; copy states MiniLM2-calibrated
   thresholds. Run Ask; inspect the summary row's `scope_ref_json.verification_nli`. Switch back to MiniLM2.
**Not yet performed in a browser** (Playwright unavailable this session; the DEV server also stopped for an
undetermined reason during the memory-pressure episode and was not restarted).

## Validation

- Historical serial full suite (before the fallback fix and scope test): 3,514 passed, 6 failed, 12 skipped
  (27 min 41 s; peak tree RSS 1.0 GB). The 6 failures were Overview freeze checks caused solely by
  `app/backend/llm/providers.py` having CRLF bytes in this checkout (`core.autocrlf=true`; working sha `abc53adb…`,
  blob and frozen hash `67065f72…`, identical after stripping CR). Restored the exact blob bytes; working tree, index
  and HEAD now share object `b301fdc3`; all six pass. No manifest or test changed.
- An earlier interrupted xdist run printed 4 `F` markers without names; they did not reproduce serially (first 200
  tests pass).
- Targeted serial run after the final changes (18 files: profiles, NLI, Critical Read set, health, startup/migrations,
  status, summaries/summarization/faceted/overview, model runtime, frontend assembly, help, both freeze suites):
  **327 passed** in 3 min 4 s, peak 305 MB. The full suite was not re-run (workstation memory reserved for other work).
- Gates: ruff format/check, tach, 600-line budget, bandit, QA coverage (459/459), changelog drift: pass. Demo and
  website showcase gates: pass after Cliff-authorized deferral through 608 and a reasoned exclusion of QA route 97
  (experimental model selection is not a showcase claim).
- Real-checkpoint checks (offline, earlier in the session): Arctic profile encoding bit-identical to the qualified
  research recipe (max abs diff 0.0); DeBERTa entailment 0.997 / contradiction 1.0 / neutral ~0 on three sanity
  pairs, wrong expected label order refused. These are sanity checks, not scientific validation.

## Known limitations (release qualification outstanding)

1. Arctic S is ready for controlled use only once a library's index is complete.
2. The disposable-copy index is paused at 25,453 / 42,044 chunks (integrity ok, 0 stale/orphan, MiniLM digest
   unchanged); completion, app recognition of completeness and re-run idempotence at full scale are unverified.
3. No LLM-free MiniLM vs Arctic S retrieval comparison has been run in the application.
4. DeBERTa is experimental and **not scientifically qualified**; it needs evaluation on independently labelled
   claim/passage pairs.
5. MiniLM (retrieval) and MiniLM2 (verification) remain the defaults.
6. Model provenance is stored but **not user-visible**: the summary API and result screen do not show it.
7. The MiniLM2 baseline still silently falls back to embedding similarity on NLI failure (pre-existing; follow-up).
8. Settings UI visual review incomplete; desktop release qualification outstanding.
9. DEV library database was at alembic 0083 when last inspected; 0084/0085 apply on next upgrade.

## Lineage and preservation

No production, installed-desktop, historical research or frozen experiment database was modified. Index building ran
only on a backup-API copy under `C:\Users\cliff\callosum-data\experiments\arctic-index-20261029\`. No push.
