# Increment 564 Notes — embedding/NLI integration audit, Wave 1 remediation

## Outcome

Follows the read-only audit at `.claude/docs/research/2026-09-02_embedding-nli-integration-audit.md`
(mirroring the LLM-provider audit's own Wave 1/2/3 split). This closes the mechanical, low-risk
subset of findings — crash hardening, three batching-invariant fixes, a model-identity filter gap,
and pinning consistency — while explicitly deferring the harder DB-transaction-across-model-call
bugs, the `commit_each` systemic-failure blind spot, and the Status/cold-cache UX gaps to a future
pass (each needs either a real design pass like increment 561's, or new UI work).

## Implemented

**A. Batched three previously-unbatched NLI stance loops** (LATENCY.md's batching invariant), each
restructured as "filter → one batched `classify_stances(scorer, pairs)` call → scatter results back
by original position/index":
- `app/backend/citations/suggest.py::suggest_citations` — up to `MAX_SUGGESTIONS=20` per-candidate
  calls collapsed to one.
- `app/backend/citations/beyond_library.py::suggest_beyond_library` — up to 20 per-candidate calls
  collapsed to one; combined with the above, closes the `POST /citations/suggest` endpoint's worst
  case (was up to 40 sequential NLI calls per request, directly blocking the interactive
  cite-while-you-write UI).
- `app/backend/methods/citation_context.py::classify_citation_contexts` — the trickiest of the
  three (each item's hypothesis is per-item, `getattr(ctx, "claim", None) or claim`, not a shared
  query, and only items with a truthy `sentence` get scored) — up to 500 per-citation calls
  collapsed to one.

**B. Crash-hardened three unguarded synchronous embedding/NLI endpoints**, matching increment 557's
established style for `resolve_llm_config()` sites: a narrow `try/except Exception` around just the
model-touching call, converted to `HTTPException(503, "<feature> could not complete: <ExceptionType>:
<message>")` — an honest, inspectable error (invariant #4: the real exception stays visible in the
detail) rather than a raw, opaque 500:
- `app/backend/api/routers/citation_suggest.py::suggest_citations_endpoint`
- `app/backend/api/routers/discovery.py::discovery_relevance`
- `app/backend/api/routers/registration_retrieval.py::retrieve_registration_publication_evidence`

**C. Fixed the model-identity filter gap** — `other_paper_chunk_embedding_ids`
(`app/backend/methods/critical_review.py`) had no `model_name`/`model_version`/`normalization`
filter, unlike its sibling `library_article_chunk_embedding_ids` three call sites away. Added the
same three-column filter, threading `embed_model.name`/`.version`/`.normalization` from its one
caller, `_run_critical_read_job` (`app/backend/api/routers/critical_review.py`), which already had
the resolved model in scope.

**D. Closed `PINNED_MODEL_REVISIONS` bypass gaps**:
- `default_support_scorer` (`verification.py`) and `default_stance_scorer` (`stance.py`) now pass
  `revision=PINNED_MODEL_REVISIONS.get(DEFAULT_NLI_MODEL)` — both were dead in production (every
  real router already passes an explicit, pinned scorer) but were a live trap for a future caller
  that omits the argument.
- `adapters/libreoffice/run_roundtrip.py` and `tools/demo/generate_demo_library_state.py` (2 sites)
  — direct `SentenceTransformerEmbeddingModel(...)` construction now pins its revision too. The
  latter closes a real, if narrow, reproducibility gap: this script's output (a SPECTER-scored axis)
  ships in the public static demo, so its similarity scores previously depended on an untracked,
  undated model revision.

**E. Corrected a stale documentation claim** — `INCREMENT-560-NOTES.md` claimed
`wip_critical_review.py`'s cold-cache failure "will still raise whatever raw exception
sentence-transformers produces." Spot-checked during the audit: it already gracefully degrades to a
`"local-model-unavailable"` report (lines 170-185, unrelated to this increment's own changes — this
was already true). Added a dated correction note rather than rewriting the original entry.

## Key technical detail

The "filter → batch → scatter" restructure had to preserve an existing, tested invariant at every
site: not every candidate gets scored today (some lack the field being classified, or fall outside
the selected/ranked slice) — `tests/test_beyond_library_preslice_nli.py`'s own name records this as
a previously-fixed performance property (only scoring the *returned* slice, not every raw
candidate). All three restructures keep that exact selection logic unchanged; only the mechanism
for the *scoreable* subset changed from N calls to 1.

Existing test doubles across the affected test files (`RecordingScorer`, `FakeStanceScorer`,
`_FakeStance`) only implement the single-item `classify_stance` method, not the batch
`classify_stances` method — so `classify_stances(scorer, pairs)`'s duck-typed fallback
(`app/backend/summarization/stance.py`) transparently loops through them exactly as before. This is
*why* every pre-existing test kept passing unmodified: the batching change is only observable
against a scorer that actually implements the batch method, which is exactly what the real
`NLIStanceScorer` does and what the new regression tests (below) specifically probe for.

## Manual verification script

1. Start the app against the real testing DB (`CALLOSUM_DB_URL` pointed at
   `.local/validation-summarize/validation.sqlite`).
2. `POST /citations/suggest {"text": "...", "top_k": 3, "evaluate": true}` — confirmed distinct,
   correct per-candidate stance/confidence values in the real response (batching didn't collapse or
   misalign results across candidates).
3. `POST /papers/{id}/critical-read` (Tier 1), poll `GET /critical-read/{job_id}` — confirmed a real
   contested claim was retrieved from another paper in the corpus, proving the
   `other_paper_chunk_embedding_ids` model-identity fix still returns correct matches in production
   (not just an empty-but-non-crashing result).

## Pytest

- Targeted (every touched-file test, incl. 6 new regression tests — 3 proving batching via a
  call-counting scorer that asserts `single_calls == 0` / `batch_calls == 1`, 3 proving the
  crash-hardened endpoints return a clean 503 with the real exception still inspectable rather than
  a raw 500): **144 passed**
  (`test_citations_suggest.py`, `test_beyond_library_preslice_nli.py`, `test_beyond_library_saved.py`,
  `test_citation_context.py`, `test_critical_review.py`, `test_discovery.py`,
  `test_discovery_relevance.py`, `test_registration_retrieval.py`, `test_model_runtime.py`,
  `test_summarization.py`).
- `ruff format` + `ruff check` clean on all touched files.
- `python tools/check_line_budget.py` — clean (579 files).
- `python -m tach check` — clean.
- Confirmed no touched file overlaps the `synthesis-overview-v1` qualification freeze manifest.
- Demo-experience and website-coverage drift gates both fired (touched files fall in their watched
  globs — several `app/backend/api/routers/*.py` files, `tools/demo/generate_demo_library_state.py`,
  and `adapters/libreoffice/run_roundtrip.py`) and were refreshed with notes explaining no
  user-visible behavior, copy, or capability claim changed.

## Note on this session's shared working tree

This increment landed while Codex was concurrently active in the same local working directory
(2 of its own commits, `c2881f2`/`7ef0350`, were already on local `main` when this work started;
its own further in-progress, uncommitted edits to unrelated files — `citation_equity.py`,
`publishers.py`, `wip_citation_equity.py`, `followed_author_feed_source.py`, `funding/providers.py`,
the `integrations/openalex/*` module, and their test files — were present in the working tree
throughout and were never staged, touched, or read as part of this increment's own commit).

## Revert

Revert this increment's commit. No database migration or data mutation involved.
