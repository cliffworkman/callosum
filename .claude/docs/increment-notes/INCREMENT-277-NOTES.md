# Increment 277 — Long-job incremental commits: C (method batches)

Increment C of the long-job half (spec: `.claude/docs/specs/2026-07-15-long-job-incremental-commits-design.md`):
per-item commits for the four **method-batch** jobs — statcheck, retraction, transparency, and citation-counts —
so each releases the SQLite write lock between papers instead of holding it for the whole run.

## Implemented (all four in the same shape)
Each job read its paper list inside one `engine.begin()` and looped, holding the write lock the whole time. Now
each reads the id/row list first on a plain read connection, then processes **every paper in its own `run_write`
transaction** (lock released between papers), skipping + logging one bad paper rather than aborting the batch:
- **statcheck** (`_run_statcheck_all_job`, `routers/methods.py`): per paper — `run_statcheck` (local compute) →
  `store_statcheck` + `upsert_findings` (the inc-133 candidate for the review queue).
- **retraction** (`_run_retraction_all_job`, `routers/methods_retraction.py`): per paper — `detect_retraction`
  (**external DOI lookups**) → `apply_retraction`. The per-paper network check no longer holds a batch-wide lock.
- **transparency** (`_run_transparency_all_job`, `routers/transparency.py`): per paper — `persist_transparency`
  (local detect + write); progress preserved.
- **citation-counts** (`_run_citation_counts_job`, `routers/citation_counts.py`): per paper — the **external
  OpenAlex `fetch_cited_by_count`** + `upsert_citation_count`; progress preserved.

Each router gained a module logger + the `run_write` import.

## Key technical detail
All four were already per-paper loops, so the conversion is the cleanest form of the pattern: hoist the id/row
read to a read connection, then `run_write(engine, lambda conn, x=item: process(conn, x))` per item, accumulating
the summary counters from each item's result and skipping on a per-item exception. The retraction + citation-counts
jobs benefit most (their per-paper work is an external HTTP call that previously ran *inside* the batch-wide write
lock). Atomicity is per-paper (intended, consistent with A/B): a mid-run failure leaves earlier papers' signals
committed; every batch is a re-runnable overwrite, so partial progress is safe + resumable.

## Not in scope (still open)
Increment **D** (read-heavy): dedup, gap-finder, my-publications refresh/decompose — the last group; their exact
per-item boundary gets pinned when converted (they are read-mostly with some writes).

## Manual verification script
`uvicorn app.backend.api.app:app --port 8888`; run a library-wide statcheck / retraction / transparency /
citation-count batch (`POST /methods/statcheck/run`, `/methods/retractions/run`, `/methods/transparency/run`,
`/papers/citation-counts/refresh`) and while it runs toggle a read marker / add a tag in another tab → succeeds
(the lock is released between papers) instead of 500ing. A mid-run failure leaves earlier papers' signals
committed and the job completes.

## Pytest
The four batch-covering suites green (statcheck / retraction / retraction_watch / transparency /
transparency_findings / citation_counts / findings_review — 74) + new
`test_statcheck_batch_commits_per_paper_partial_progress`. Full suite: **1224 passed, 1 skipped**.
