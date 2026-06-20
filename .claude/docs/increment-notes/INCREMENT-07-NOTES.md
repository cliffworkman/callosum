# Increment 07 Notes

## Implemented

- Added supervised user-defined axis scoring under `app/backend/clustering/`.
- Added helpers to create/update axes and score an axis into `cluster_nodes` plus `cluster_node_papers`.
- Added nested-axis scoring by passing a parent cluster node; child scoring is restricted to papers already recorded under the parent.
- Added the metric-alignment preamble fix for sqlite-vec.
- Added hermetic tests for axis scoring, uncertainty preservation, nested candidate scoping, re-scoring isolation, and unnormalized-vector ranking parity.

## Paper Representation

- Chosen representation: paper-level embeddings from `embed_papers()`.
- Rationale: user axes are library-organization concepts, so title/abstract/metadata embeddings are the right first-pass granularity. Chunk aggregation or max-over-chunks remains swappable later through the `PaperRepresentationStrategy` interface.
- Papers without usable paper text are not scored in this increment because `embed_papers()` intentionally skips empty text.

## Metric Alignment

- Chosen mechanism: declare new sqlite-vec tables with cosine distance:

```sql
USING vec0(embedding float[N] distance_metric=cosine)
```

- Rationale: this keeps stored vectors faithful to model output and makes `SQLiteVecVectorStore` match `InMemoryVectorStore` by metric, even when inputs are not normalized.
- Existing sqlite-vec tables already created with the older L2 declaration are not migrated in this increment; no schema migration was requested, and tests create fresh stores.

## Nested Scoring And Candidate Retrieval

- Nested axes use `cluster_nodes.parent_id`.
- Child scoring reads the parent node's `cluster_node_papers` rows, maps those papers to paper embedding IDs, and calls `vector_store.search(..., candidate_embedding_ids=...)`.
- Candidate searches are batched under the vector store's `max_knn_k` when present, preserving the increment-6 candidate-scoped retrieval behavior without changing the protocol.

## Threshold And Uncertainty Handling

- `assignment_threshold` controls normal assignment.
- `uncertainty_threshold` controls borderline preservation.
- Scores between the uncertainty and assignment thresholds are still written to `cluster_node_papers.confidence`; the current schema has no separate status column, so low confidence is the preserved uncertainty signal.
- Re-scoring deletes and rewrites only the scored node's paper rows, leaving unrelated axis nodes intact.

## Deferred / Out Of Scope

- No automatic abstract-first clustering, BERTopic, summarization, NLI, OpenAlex/Semantic Scholar, FastAPI, frontend, schema changes, or embedding model changes.
- No LLM-assisted label cleanup.

## Ambiguities / Questions

- None surfaced.

## Raw Pytest Output

Axis suite:

```text
....                                                                     [100%]
4 passed in 5.99s
```

Embedding plus axis suites:

```text
.............                                                            [100%]
13 passed in 11.56s
```

Full suite:

```text
.........................                                                [100%]
25 passed in 21.05s
```
