# Increment 275 — Long-job incremental commits: A3 (axis-score embed-phase hoist)

Finishes the **auto-running offenders** grouped with the scan in the spec
(`.claude/docs/specs/2026-07-15-long-job-incremental-commits-design.md`). The axis-score job wrapped its whole run
— including embedding every candidate paper — in one `engine.begin()` transaction, holding the write lock for the
whole (multi-minute) embedding phase. A3 hoists that embedding out to per-paper commits, leaving only the fast
scoring inside a short transaction.

## Implemented
- **`ensure_candidate_embeddings_committing(engine, *, model, vector_store, parent_cluster_node_id=None,
  representation=None)`** (`clustering/axis_scoring.py`) — computes the candidate papers *lacking a current
  embedding* (candidate set, or all live papers when the run is unfiltered) and pre-embeds them **one committed
  transaction per paper** via `commit_each` (inc 273), releasing the write lock between papers. Idempotent papers
  are excluded up front (no wasted transactions); one paper's embed failure is skipped + logged (it's simply
  unscored), never aborting the pre-embed.
- **`_run_axis_score_job` rewired** (`routers/axes.py`): calls `ensure_candidate_embeddings_committing(engine, …)`
  **first** (the slow phase, lock released between papers), then runs `manual_assignment_paper_ids` + `score_axis`
  + `restore_manual_assignments` + the `scoring_gain` update in **one short `run_write` transaction**. `score_axis`
  is unchanged — its internal `ensure_embeddings` now finds every candidate already embedded (`embed_papers` is
  idempotent, `pipeline.py` L87–97) and is a fast no-op, so the scoring transaction holds the lock only for the
  axis embedding + the assignment replace.

## Key technical detail
The slow work in axis scoring is embedding the candidate papers, buried inside the monolithic `score_axis`
(`representation.ensure_embeddings`). Rather than thread `engine` + per-paper commits through the clustering
internals, A3 **pre-embeds** at the job boundary and relies on `embed_papers`'s existing idempotency to make
`score_axis`'s embedding step a no-op — so `score_axis` keeps its clean single-`conn` contract and the existing
`test_axis_scoring.py` suite is untouched/green. Atomicity of the *scoring* (assignment replace) stays a single
transaction, as it must (an axis's assignments are replaced atomically); only the *embedding* became per-item.

## Not in scope (still open)
Increments **B–D** per the spec: **B** = ingest family (citation import, bundle import, enrich-batch); **C** =
method batches (statcheck / retraction / transparency) + citation-counts; **D** = read-heavy (dedup, gap-finder,
my-publications refresh/decompose). The auto-running offenders (scan + rescan + axis-score) are now all per-item.

## Manual verification script
`uvicorn app.backend.api.app:app --port 8888`; on a library where papers are not yet embedded, create + score an
axis (`POST /axes/{id}/score`) and, while it runs, toggle a read marker / add a tag in another tab → succeeds (the
embedding phase releases the lock between papers) instead of 500ing. Re-scoring an already-embedded axis is fast
(the pre-embed is all no-ops) and assignments are unchanged.

## Pytest
`tests/test_axis_scoring.py` (incl. new `test_ensure_candidate_embeddings_commits_per_paper` +
`…_skips_a_failing_paper`) + `tests/test_axes.py` green (41). Full suite: **1221 passed, 1 skipped**.
