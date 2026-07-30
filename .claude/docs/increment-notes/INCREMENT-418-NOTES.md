# Increment 418 — speed up the flagship pipeline: batch model calls + concurrent batch-job fetches

## Implemented

Cliff was worried the app's "flagship functionality" was slow enough to risk user attrition, and asked whether
parallelizing work and/or GPU could help — explicitly without sacrificing quality, deferring the technical
judgment call. Three research passes + one design pass (all grounded against the real code, not just theory)
found the real lever: **nothing in the backend batches model calls or parallelizes independent work.** GPU
turned out to already be free wherever it exists — `SentenceTransformer(...)`/`CrossEncoder(...)` construct with
no `device=` argument anywhere in `app/backend`, so sentence-transformers' own cuda→mps→cpu auto-detection
already applies to anyone running the dev server on their own GPU machine, today, with zero code changes. The
CPU-only torch pin lives only in the three desktop-shell packaging scripts (bundle-size, not a code constraint)
— building GPU support into the shipped installer was explicitly scoped out as a separate, unmeasured trade-off,
not attempted here.

**Tier 1 — batch the verification + embedding model calls** (the real fix, since the NLI cross-encoder and the
embedding model both already batch internally; the app was just calling them with lists of length 1, over and
over):

- `app/backend/summarization/verification.py`: `NLISupportScorer` gained
  `support_and_contradiction_many(pairs)` — one `model.predict(pairs, apply_softmax=True)` call for the whole
  batch instead of one per pair; `support_and_contradiction()` is now a thin `[0]`-indexed wrapper around it.
  `LocalCitationVerifier` gained `verify_many(items, source_chunks)` — one batched `encode_texts()` call for
  every sentence and one batched NLI call for every `(passage, sentence)` pair, assembled back into
  per-item `VerificationResult`s in input order; `verify()` is now `verify_many(items=[one])[0]` — the key
  design choice, since **every existing test that calls `verify()` became a free regression test for the new
  code's n=1 case**, with zero test rewrites needed for that part. A genuine bonus find fell out of the
  restructuring: the embedding-existence check for the shared `source_chunks` pool used to redundantly re-run
  on every single citation even though it's the same list all call — now hoisted to run once per batch. Two
  functions were confirmed dead (zero callers anywhere, via grep) and deleted per rule #5:
  `_entailment_confidence` and, once `support_and_contradiction_many` called `_values_from_row` directly, the
  module-level `_support_and_contradiction` too; `_retrieval_confidence` (the old single-item method) was
  likewise deleted once `verify_many` stopped needing it, replaced by the reusable
  `_embedding_lookup`/`_retrieval_confidence_from_vector` pair.
- `app/backend/summarization/pipeline.py`, `summarize_scope`: flattens every `(candidate, citation)` across
  the whole summary into one list, calls `verify_many()` once, and unzips results back into per-candidate rows
  before `on_progress` fires — the reported progress sequence is unchanged (still exactly one call per
  candidate, in order), it just animates faster now, which is the intended outcome.
- `app/backend/summarization/reverify.py`: same restructuring for the imported-synthesis re-verify path —
  resolves each citation's local chunk first (unchanged, since that depends on paper/quote matching, not the
  model), then one `verify_many()` call for the whole flattened batch, redistributed back into per-sentence rows.
- `app/backend/embeddings/pipeline.py`, `embed_chunks`/`embed_papers`: restructured from "loop, encode 1,
  insert" into 3 phases — classify each row (existing embedding vs. needs one, a cheap per-row DB check, left
  as-is), one batched `encode_texts()` call for every row that needs one, then a second pass in original order
  to report progress (unconditionally, for every row — exactly preserving the existing per-row sequence tests
  assert on) and do the existing insert/vector-store bookkeeping. Benefits `pdf_processing/ingest.py` (a whole
  new paper's chunks) and `clustering/abstract_clustering.py` (every paper at once) automatically, with zero
  call-site changes; does **not** help axis scoring's pre-embed loop, which deliberately calls with one paper
  id at a time (an existing, documented "release the write lock between papers" trade-off) — left untouched.

**Tier 2 — bounded concurrency for the sequential I/O-bound batch jobs** (citation-count refresh, metadata
enrichment — both loop over papers making one external HTTP call each, one after another, with zero concurrency
anywhere in the codebase before this):

- `app/backend/api/routers/citation_counts.py` / `library_enrich.py`: both `_run_*_job` functions now submit
  the existing per-paper `run_write(engine, lambda conn: process(conn, row))` closure to a bounded
  `ThreadPoolExecutor` (4 workers — a courtesy-norm cap, not an OpenAlex-published limit) instead of a serial
  `for` loop, draining via `as_completed`. `process()`/`enrich_paper_metadata_multi()` themselves are completely
  unchanged; only the orchestration is concurrent. Progress is completion-count-based (inherently
  order-agnostic). Chose `ThreadPoolExecutor` over `asyncio`/`httpx.AsyncClient` deliberately: the whole codebase
  (DB layer, `OpenAlexClient`, adapters) is synchronous, and async-ifying everything down the call chain would
  be a large, invasive change against rule #7 — a thread pool lets every existing function stay byte-for-byte
  unchanged. Verified safe before writing any code: `make_engine()` uses no special `poolclass`, so SQLAlchemy's
  default `QueuePool` applies (built for exactly this — multiple threads each independently calling
  `engine.connect()`), and `run_write()` already opens a fresh connection per call with bounded retry on a
  transient `database is locked` error — the exact mechanism that makes concurrent calls safe; previously only
  ever exercised by accident, now doing its intended job for real.
- `tests/test_metadata_multi_enrich.py::test_enrich_commits_per_paper_partial_progress`: its docstring/comment
  claimed "papers processed id-ASC → the 2nd is paper B," which is no longer true under concurrent processing.
  On closer reading the test's actual assertions don't depend on that (they just check "one paper failed, one
  succeeded, the run still completed" — order-agnostic by construction) — confirmed stable across 5 repeated
  runs. Fixed the stale comment/docstring for accuracy; the test logic itself needed no change.

**Explicitly not built this pass** (documented as backlog, per the plan): CPU-bound batch-job concurrency
(statcheck-all — Python's `re` doesn't release the GIL, little real benefit; PDF scan/import and axis scoring's
pre-embed loop — both would need riskier restructuring of an existing fused fetch+write pattern). GPU packaging
for the desktop installer — noted as already-free for dev-server users, no code to write.

## Key technical detail

The single most consequential design choice was collapsing `verify()`/`support_and_contradiction()` into thin
wrappers around their own batched siblings (`verify_many`/`support_and_contradiction_many`) called with a
length-1 list, rather than writing a separate parallel batched implementation. This meant the entire existing
test suite — including tests asserting exact verification status/confidence values against real-shaped fakes —
became regression coverage for the new code's n=1 case for free, with zero test rewrites for that part. The
only genuinely new test surface needed was proving the batching *itself* happens (call **count**, not just
correct output) — nothing before this asserted that, since there was never anything to batch.

A real, non-faked verification was run against the maintainer's own ~200-paper testing DB
(`.local/validation-summarize/validation.sqlite`) using the actual `SentenceTransformer`/`CrossEncoder` models
(not test fakes): 8 real citations across 8 distinct real papers were verified both the old way (looped
`verify()`, one at a time) and the new way (one `verify_many()` call), and every single result matched — same
`status`, confidences agreeing to within 1e-6 (well inside expected floating-point noise from batched-matmul
reduction order, and nowhere near the app's coarse 0.55/0.7 thresholds). The batched path took **11.0s vs.
75.4s for the looped path — a 6.85x real speedup** on the verification stage for this sample, with byte-for-byte
equivalent verification outcomes. A parallel attempt to get a live network-timing number for the citation-count
concurrency change (Tier 2) using real OpenAlex calls against real DOIs from the same testing DB was
inconclusive: the DB's `external_api_cache` table was already warm from the database's own extensive prior use,
so both the sequential and concurrent passes hit near-instant cache reads rather than fresh network round
trips. Not pursued further — Tier 2's correctness is already thoroughly proven by the passing test suite, and
I/O-concurrency's wall-clock benefit is well-established, non-controversial behavior (unlike Tier 1's ML-batching
numerics, which had a genuine open question worth checking empirically).

## Housekeeping

- No security audit triggered — no new API endpoint, no new external integration, no new file-ingestion path, no
  new auth logic, no new third-party dependency (`concurrent.futures` is stdlib). The one net-new-feature-sized
  criterion (3+ files / ~300+ LOC) is arguably met by file count, but this is a pure internal
  restructuring/performance change with no change to inspectability, provenance, the fact/candidate distinction,
  or the egress posture — the Principles gate (rule #9) doesn't trigger either, for the same reason.
- `python tools/check_line_budget.py` — all 418 application-source files still within the 600-line cap (none of
  the touched files were close: verification.py 444→~500, pipeline.py 413→~425, embeddings/pipeline.py
  229→~260, citation_counts.py 115→~130, library_enrich.py 126→~150 — all comfortably under).
- `ruff format` / `ruff check` clean on every touched file.

## Manual verification script

1. Start the app, open a paper with a real PDF, run Synthesize > Ask against a scope with several source papers
   — the verification stage (the progress bar under "Verifying claim") should visibly complete faster than
   before, especially for a summary with many sentences/citations.
2. Settings → Library behavior → "Refresh cited-by counts" / the metadata-enrichment action on a library with
   several papers missing a citation count/metadata field — should complete faster for a library with more than
   a handful of papers, since fetches now overlap instead of running strictly one-at-a-time.
3. Import a large batch of new PDFs (library scan/import) — chunk embedding for a paper with many chunks should
   be visibly quicker (one batched encode instead of one per chunk).

## Pytest / build gates

- `pytest tests/test_summarization.py tests/test_nli_support.py tests/test_embeddings.py tests/test_reverify.py
  tests/test_summaries.py tests/test_citation_counts.py tests/test_metadata_multi_enrich.py -q` → **81 passed**
  (3 new: `test_verify_many_batches_encode_and_nli_calls_instead_of_looping`,
  `test_embed_papers_batches_encode_texts_into_one_call`, `test_embed_chunks_batches_encode_texts_into_one_call`
  — each proving the batching happens by call **count**, not just correct output).
- Broader call-site regression check: `pytest tests/test_pdf_processing.py tests/test_library_scan.py
  tests/test_abstract_clustering.py tests/test_axes.py tests/test_axis_scoring.py tests/test_curated_axis.py -q`
  → **82 passed**.
- Full suite: `pytest -n auto -q` → **1710 passed, 1 skipped** (up from 1707 post-inc-417; +3 new here), run in
  the foreground per this session's established workaround for backgrounded full-suite runs getting killed —
  completed cleanly in 17m26s with zero failures.
- Real-model equivalence + timing check (not a pytest gate, a one-off verification script against the real
  testing DB): 8/8 items matched between single-item and batched verification; 6.85x real speedup measured.
