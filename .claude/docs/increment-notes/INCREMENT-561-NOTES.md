# Increment 561 Notes — primary-synthesis DB-transaction/CAS redesign (Wave 3 item, LLM provider audit)

## Outcome

Closes the last open item from the combined LLM-provider-integration audit
(`.claude/docs/research/2026-09-01_llm-provider-integration-audit.md`) — the one both the original
audit and an independent Codex pass explicitly flagged as needing real snapshot/CAS design, not a
mechanical patch, because a naive fix risked a stale-write correctness bug in the citation-
verification trust spine. Designed properly in Plan Mode (research + a dedicated Plan-agent pass +
direct reading of every touched file) before any code changed; see
`.claude/docs/2026-09-01_codex-local-ai-audit-handoff.md` for how this fits the overall audit.

## The problem

`_run_summarize_job` (`app/backend/api/routers/summaries.py`) used to run the **entire** primary-
synthesis pipeline — retrieval, a generation-cache check, the real remote/local-AI provider call (up
to ~600s per `.claude/LATENCY.md`), a cache write, local citation verification, and persisting the
full evidence graph (`summaries` → `summary_sentences` → `citation_mappings` → `evidence_quotes`) —
inside one `with engine.begin() as conn:` block. Two concrete, confirmed bugs followed:

1. **Reliability.** A query-scoped synthesis writes fresh embeddings during retrieval
   (`_rank_chunks_for_query` → `embed_chunks`) *before* generation starts, so SQLite's writer lock was
   often already held for the whole slow provider call. Two concurrent synthesis jobs — even for
   unrelated scopes — could fail each other via the 5s `busy_timeout`.
2. **Correctness/staleness.** Citation verification had an internal inconsistency masked only by the
   single-transaction shape: a citation whose chunk was in the original retrieved set used the
   **retrieval-time in-memory snapshot** for both quote-matching and the persisted
   `chunk_version_verified_against`, while the *same* verification pass's embedding step did a
   **fresh** DB read for any chunk missing an embedding. A naive multi-transaction split would have let
   these silently diverge if a chunk changed in the gap (e.g. a concurrent re-extraction).

## Implemented

Three-phase restructure of `summarize_scope` (`app/backend/summarization/pipeline.py`), now taking a
bare `Engine` instead of a `Connection` and managing its own connections internally — mirroring the
already-proven Overview lifecycle pattern (`overview_lifecycle.py`, inc 494), but simpler: primary
synthesis has no multi-caller race to defend against (each job creates a brand-new `summaries` row),
so no CAS claim/schema change was needed — a failed attempt just leaves no row, exactly as before.

- **Phase 1 — Prepare** (short transaction): retrieval (`_source_chunks_for_scope`), unchanged.
- **Phase 2 — Generate** (zero DB connection held): `generator.generate(..., engine=engine)`. The
  connection-vs-engine split lives *inside* `CachedSummaryGenerator.generate`
  (`app/backend/llm/cache.py`), not in `pipeline.py` — confirmed by reading `egress.py` that the call
  chain is `EgressGatedSummaryGenerator` (checks egress **first**) → `CachedSummaryGenerator` (checks
  cache **second**) → the real provider (network call, **third**), a deliberate existing order
  ("a cache hit can never bypass the gate"). Hoisting the cache-check to `pipeline.py` would have
  silently inverted that. `CachedSummaryGenerator.generate` now opens a short `engine.connect()` for
  the cache read (closes before any network call), calls the real provider with zero connection open
  on a miss, then a short `engine.begin()` for the cache write.
- **Phase 3 — Verify + Persist** (fresh short transaction): a new `_refresh_source_chunks(conn,
  source_chunks)` re-reads every chunk fresh (same live-paper + article-role filter as retrieval)
  immediately before `verify_many` runs — closing the staleness bug with zero changes to
  `verification.py`/`_insert_summary`/`_persist_verification`, since `chunk_version_verified_against`
  was always sourced from whatever `cited_chunk` object verification was handed; making that object
  fresh makes the recorded provenance correct by construction. A chunk that no longer qualifies
  (deleted, or its paper trashed, in the interim) is simply dropped — any citation pointing at it falls
  through to `verify_many`'s existing out-of-pool fallback (`_source_chunk_for_id`), which fails the
  whole attempt honestly (clean rollback, job error) rather than fabricating a result.

**Mechanical fallout** (the `conn`→`engine` passthrough-parameter rename, since it's part of the
`SummaryGenerator` Protocol): `app/backend/summarization/generators.py` (Protocol +
`FakeSummaryGenerator`), `app/backend/llm/egress.py` (`EgressGatedSummaryGenerator`),
`integrations/gemini/generator.py` (`GeminiSummaryGenerator` — the parameter was always unused by the
real provider, confirmed by direct read), and every direct caller of `summarize_scope`/
`CachedSummaryGenerator.generate` across ~20 call sites in `tests/test_summarization.py`,
`tests/test_nli_support.py`, `tests/test_summary_overview.py`, `tests/test_summary_overview_
lifecycle.py`, `tests/test_llm_cache.py`, `tests/test_egress_gate.py`, `tests/test_providers.py`,
`tests/test_summarize_selected.py`, `tests/test_validation_harness.py`, and
`tools/validation_harness.py`.

**A real bug found and fixed along the way, not by inspection**: `tools/validation_harness.py`'s
`run_validation` wrapped PDF ingestion *and* the summarization probe in one still-open transaction —
`summarize_scope`'s new Phase 1 opens its own fresh connection and can't see uncommitted ingestion on
a different connection. Split into two: ingestion/axis-calibration commits first, summarization runs
afterward in its own short `with engine.connect()`.

## Key technical detail

`Connection.engine` is a real, public SQLAlchemy attribute — `run_summarization_probe` (which still
takes its own `conn` for other reads) passes `conn.engine` to `summarize_scope` at the one call site
that needed it, rather than restructuring its own signature.

Two new regression tests in `tests/test_summary_overview_lifecycle.py` prove both fixes directly:
- `test_no_connection_held_during_generation_call`: a query-scoped request (forcing Phase 1 to write
  embeddings) with a generator that blocks on a `threading.Event`; while blocked, an independent write
  on the *same* engine (`papers.priority`) must complete within 2s, proving Phase 1's connection isn't
  still held.
- `test_verification_uses_fresh_chunk_data_when_mutated_during_generation`: a generator that mutates
  a cited chunk's `chunk_version`/text via its own connection *during* its `.generate()` call
  (simulating a concurrent re-extraction), then cites a quote that only exists in the fresh text.
  Verified to actually discriminate: reverting `_refresh_source_chunks`'s call site locally and
  re-running this test fails it (`quote_confidence` drops from 1.0 to 0.0, status `weak` not
  `verified`) — confirmed live before restoring the fix.

**Explicit scope boundary** (per the approved plan): Critical Review (single-paper and Set Tier-2),
Workbench extraction, and analytic-flexibility (Library + WIP) were surveyed this session and
deliberately deferred — confirmed lower risk under WAL semantics (most don't actually hold the writer
lock during their provider call, only an open connection/snapshot; only Critical Review single-paper
Tier-2 with `triage=true` has a real write-then-second-call exposure), and the WIP analytic-
flexibility site already demonstrates the right shape in-repo as a reference for that future pass.

## Manual verification script

1. Start the app against the real testing DB, confirm `GET /health` is reachable.
2. `POST /summarize {"scope_type":"papers","paper_ids":[<id>]}`, poll `GET /summarize/{job_id}` to
   completion.
3. Confirm the response shape is unchanged: verified/weak/flagged sentences, exact bbox coordinate
   precision on verified citations, an Overview narrating the verified claims.
4. Done live against the real ~200-paper testing DB with a real Gemini call (the DB's default
   `managed_local` provider has no runtime outside the packaged Tauri app, so the active provider was
   temporarily switched to `gemini` for this check, then restored, and the test synthesis deleted
   afterward) — summary id 8, 7 verified + 2 weak sentences, exact coordinates throughout, Overview
   generated. Byte-for-byte the same response shape as before this redesign.

## Pytest

- Targeted (every touched-file test): 203 passed
  (`test_summarization.py`, `test_nli_support.py`, `test_summaries.py`, `test_summary_overview.py`,
  `test_summary_overview_lifecycle.py` [15, incl. the 2 new regression tests], `test_llm_cache.py`,
  `test_managed_local_ai.py`, `test_egress_gate.py`, `test_validation_harness.py`,
  `test_summarize_selected.py`, `test_providers.py`, `test_document_scope.py`, `test_settings.py`).
- Full suite (`pytest -n 4 -q` — `-n auto`/`-n 4` both hit this machine's known xdist worker-crash
  flakiness on the first few attempts, resolved once AnyDesk/Dropbox were quit to free resources):
  **2713 passed, 3 skipped**, 0 failures, in 35m10s.
- `ruff format` + `ruff check` clean on all touched files.
- `python tools/check_line_budget.py` — clean (578 files; none of the touched files are close to cap).
- `python -m tach check` — clean.
- Confirmed `app/backend/llm/providers.py` untouched by this change — the qualification-battery
  freeze (`.claude/qualification/synthesis-overview-v1/freeze.json` + its two dependents) did not
  need re-freezing this time.

## Revert

Revert this increment's commit. No database migration — the redesign is purely a transaction-boundary
and parameter-naming change; no schema or data was touched.
