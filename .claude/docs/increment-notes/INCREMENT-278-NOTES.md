# Increment 278 — Long-job incremental commits: D (read-heavy jobs) — the long-job half COMPLETE

Increment D (the final group) of the `database is locked` long-job half (spec:
`.claude/docs/specs/2026-07-15-long-job-incremental-commits-design.md`). The read-heavy jobs — dedup, gap-finder,
and my-publications refresh/decompose — which (unlike A–C) are **not** per-paper loops. With D landed, **every
long background job now releases the SQLite write lock** during its slow work.

## Implemented

**Task 1 — dedup (read-only).** `_run_dedup_job` (`routers/duplicates.py`): `engine.begin()` → `engine.connect()`.
`find_duplicate_groups` only SELECTs + compares existing embeddings (no writes), so a read-only scan must never open
a write transaction.

**Task 2 — the self-committing cache path (the enabler for 3–4).** `put_cached_committing(engine, …)`
(`integrations/api_cache.py`) writes a cache entry in its OWN short `run_write` transaction; the OpenAlex
`OpenAlexClient` **and** author `OpenAlexAuthorClient` each gain an opt-in `cache_engine` (+ `with_cache_engine`) so
their `_store`/`_put` dispatch to the committing path when set. **Default off → every per-item B/C caller is
untouched** (a universal self-committing cache would deadlock/degrade a caller that fetches inside a held per-paper
`run_write` — the reason the fix is opt-in, not global).

**Task 3 — gap-finder (clean).** `_run_gap_refresh` (`routers/gaps.py`): `compute_gaps` does no conn writes (only the
cache), so it runs on a **read connection** with the client in self-committing-cache mode (lock-free fetches), then
the single atomic `replace_gap_candidates` is a short `run_write`.

**Task 4 — my-publications (deepest).** `resolve_my_publications` + `decompose_domains` interleave external fetches
with membership/domain writes. Each split into a **fetch phase** (`_resolve_fetch` / `_decompose_compute` — no conn
writes; author-client caches self-committingly) and a **persist phase**; the public functions stay all-in-one
**wrappers** so every direct caller/test is unchanged (avoided a ~19-call-site signature-change blast radius). The
two jobs (`routers/my_publications.py`) run the fetch on a read connection then persist (set-dismissed + membership
rewrite / `set_research_domains`) in a short `run_write` — a **fresh snapshot**, which avoids a snapshot-upgrade
BUSY on the persist. Domain decomposition extracted to a sibling `clustering/my_publications_domains.py` (the
600-line cap; the inc-226 pattern).

## Key technical detail
The A–C jobs were per-paper loops, so each paper's fetch+write ran in its own short `run_write`. The D jobs are
monolithic single computes whose fetches cache to the DB — so the fix is **fetch-outside-lock**, not per-item: run
the reads + external fetches on a *read* connection (the response cache self-commits on a separate connection, so it
doesn't need the caller's write lock), then apply the one final persist in a fresh short write transaction. The
opt-in `cache_engine` is what makes the fetch phase writeless from the caller's connection, and the fresh persist
transaction is what dodges the snapshot-upgrade hazard (an early read snapshot can't be upgraded to a write after
the self-committing cache modified the DB).

## The long-job half is complete
Every long job (scan/rescan/axis-score [A–A3], ingest family [B], method batches [C], read-heavy [D]) now releases
the write lock during its slow work; combined with inc-272's foreground `run_write` + retry middleware, a
background job no longer 500s the tag/read-marker/queue writes a user makes while it runs.

## Manual verification script
`uvicorn app.backend.api.app:app --port 8888`; run a **duplicates scan** / **gap refresh** / **my-publications
refresh** / **decompose** and, while it runs, toggle a read marker / add a tag in another tab → the foreground write
succeeds instead of 500ing.

## Pytest
`tests/test_api_cache.py`, `tests/test_duplicate_detection.py`, `tests/test_gapfinder.py`,
`tests/test_openalex_adapter.py`, `tests/test_my_publications.py`, `tests/test_health.py`,
`tests/test_citation_counts.py`, `tests/test_metadata_multi_enrich.py` green (the last two prove the B/C per-item
cache path is untouched — no deadlock). Full suite: **1225 passed, 1 skipped**.
