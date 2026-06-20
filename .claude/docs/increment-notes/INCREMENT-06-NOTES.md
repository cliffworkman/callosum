# Increment 06 Notes

## Implemented

- Fixed `SQLiteVecVectorStore.search()` candidate-scoped retrieval.
- Kept the `VectorStore` protocol unchanged.
- Kept the unscoped sqlite-vec KNN cap at `max_knn_k = 4096`.
- Added behavioral regression tests for:
  - candidate subsets outside the global top-4096 result window;
  - sqlite-vec vs `InMemoryVectorStore` ranked-ID equivalence in small and large regimes;
  - unscoped `top_k > 4096` searches not crashing.

## Mechanism

- Installed sqlite-vec version: `0.1.9` (`vec_version()` reports `v0.1.9`).
- Chosen mechanism: write candidate embedding IDs into a per-connection temporary table and apply the candidate constraint inside the KNN query:

```sql
WHERE embedding MATCH ?
  AND rowid IN (SELECT id FROM callosum_vec_candidate_embedding_ids)
ORDER BY distance
LIMIT ?
```

- This avoids post-filtering a capped global KNN result set and avoids constructing very large `IN (?, ?, ...)` placeholder lists.
- Candidate-scoped `k` is now interpreted as `min(len(candidate_ids), top_k, max_knn_k)`.

## Why The Prior Test Was Insufficient

- The previous test only asserted that `_search_limit(...)` capped at `4096`.
- It did not assert that candidate-constrained retrieval returned the nearest hits within the candidate set.
- It therefore missed the correctness failure where candidates outside the global top-4096 were filtered out after sqlite-vec had already selected the wrong search universe.

## Deferred / Out Of Scope

- No clustering, summarization, NLI, OpenAlex/Semantic Scholar, FastAPI, frontend, model changes, schema changes, or protocol changes.
- No fallback vector-store backend changes were needed because sqlite-vec `0.1.9` supports the rowid-subquery constraint in the KNN predicate.

## Ambiguities / Questions

- None surfaced.

## Raw Pytest Output

Targeted embedding suite:

```text
.........                                                                [100%]
9 passed in 6.08s
```

Full suite:

```text
.....................                                                    [100%]
21 passed in 12.13s
```
