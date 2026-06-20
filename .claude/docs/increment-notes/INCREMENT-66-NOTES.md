# Increment 66 Notes — Exclude trashed papers from synthesis retrieval

Closes the last soft-delete leak (the inc-65 deferred item): a paper sitting in **Trash** (soft-deleted,
not yet purged) still had its chunks/embeddings available to retrieval, so it could be cited in a **new**
synthesis. Now a trashed paper is excluded from retrieval until it's restored.

## Where the leak actually was (a correction)
The inc-65 note pointed at `retrieval._candidate_embedding_ids`, but the summarization pipeline does **not**
use `search_similar` — `summarization/pipeline.py::_source_chunks_for_scope` builds the candidate chunks with
its **own** SQL and ranks within them. For the **query** scope that SQL was `select(chunks)` with **no paper
filter** → it pulled chunks from every paper, trashed included. That was the real user-facing leak.

## Implemented
- **`summarization/pipeline.py::_source_chunks_for_scope`** (the real fix): the base statement now filters to
  **live papers** — `select(chunks).where(chunks.c.paper_id.in_(select(papers.id).where(deleted_at IS NULL)))`.
  This covers the **query** scope (its only guard) and is defense-in-depth for the **papers**/**cluster_node**
  scopes (a trashed id passed explicitly, or one lingering in a cluster node, no longer leaks). `papers` added
  to the module imports.
- **`embeddings/retrieval.py::_candidate_embedding_ids`** (defense-in-depth for the general primitive, used
  by the validation harness + `search_similar`): excludes embeddings belonging to a trashed paper — a
  `paper`-target embedding whose paper is trashed, or a `chunk`-target embedding whose chunk's paper is
  trashed (`not_(belongs_to_trashed)`, bound-param subqueries). Keeps "retrieval excludes trashed" true at
  both layers so a future `search_similar` consumer can't reintroduce the leak.

**Backend-only.** No migration, no new endpoint, no egress, no frontend change, no new dependency. The change
is behavior-preserving when nothing is trashed (the filter matches all papers), so existing behavior + the
validation harness (which has no trashed papers) are unaffected.

## Verification
- **pytest 234** (+2):
  - `test_query_scope_retrieval_excludes_trashed_papers` (`test_summaries.py`) — a query-scope
    `_source_chunks_for_scope` returns the banana paper while live, then **not** after it's trashed (the
    facial paper still returns).
  - `test_trashed_paper_excluded_from_retrieval` (`test_papers.py`) — `search_similar` returns both papers,
    then drops the trashed one after `soft_delete_paper` (the live one stays).
- Full suite green; no audit gate (2-function correctness fix, no new surface).

## Manual verification script
1. Start the app; have ≥2 papers with extracted text. Run a **query**-scope synthesis whose answer cites
   paper X — confirm X appears.
2. Trash paper X (check box → delete). Re-run the same query synthesis.
3. Confirm X's chunks are no longer retrieved/cited. Restore X → it's retrievable again. Previously-saved
   syntheses are unchanged.

## Notes
- A **permanently deleted** (purged, inc 65) paper is fully gone; this increment is specifically about the
  **trashed-but-not-purged** window.
- Still deferred (unrelated): purge doesn't delete the on-disk PDF file (inc 65).
