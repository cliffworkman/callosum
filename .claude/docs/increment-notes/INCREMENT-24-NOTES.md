# Increment 24 Notes

## Implemented

- Added `POST /summarize` to start a background summarization job and return `202 Accepted` with a `job_id`.
- Added `GET /summarize/{job_id}` to poll job state: `pending`, `running`, `done`, or `error`.
- Reused `summarize_scope` unchanged for retrieval, generation, local verification, and persistence to the trust-spine tables.
- Added injectable summarization dependencies to `create_app()` so tests use `FakeSummaryGenerator`, a fake embedding model, an in-memory vector store, and a deterministic support scorer.
- Production default generator is `GeminiSummaryGenerator`, gated by `CALLOSUM_ALLOW_DATA_EGRESS=true` and a configured Gemini API key. If either is missing, the job ends with a clear `error` status instead of crashing.
- Kept the increment-20 verifier defaults: NLI support scorer by default inside the pipeline, with embedding fallback and support threshold `0.55`.

## Job Pattern

Jobs are stored in an in-process registry keyed by a UUID-like `job_id`. This is sufficient for the local single-user tool, but jobs do not survive a server restart. Completed summaries are still persisted in the database by `summarize_scope`.

`GET /summaries/{summary_id}` was deferred. The persisted tables contain the summary trust chain, but adding a read-back endpoint would require a separate serializer path. The current frontend-facing result is available through the completed job response.

## Result Shape

Completed job response:

```json
{
  "job_id": "...",
  "status": "done",
  "summary_id": 1,
  "summary_status": "verified",
  "sentences": [
    {
      "sentence_id": 1,
      "ordinal": 0,
      "text": "...",
      "flagged": false,
      "citations": [
        {
          "mapping_id": 1,
          "evidence_quote_id": 1,
          "chunk_id": 1,
          "paper_id": 1,
          "paper_title": "...",
          "page_start": 1,
          "page_end": 1,
          "quote": "...",
          "retrieval_confidence": 1.0,
          "quote_confidence": 1.0,
          "support_confidence": 1.0,
          "status": "verified",
          "coordinate_precision": "exact",
          "bbox_json": []
        }
      ]
    }
  ]
}
```

`coordinate_precision` is serialized as `"exact"` or `"region"` when available. This lets the frontend distinguish exact quote rectangles from chunk-region fallback coordinates.

## Scope Request Shape

`POST /summarize` accepts:

- `{"scope_type": "papers", "paper_ids": [1, 2], "top_k": 8}`
- `{"scope_type": "cluster_node", "cluster_node_id": 10, "top_k": 8}`
- `{"scope_type": "query", "query": "facial anomalies", "top_k": 8}`

Invalid `scope_type` returns Pydantic validation failure; a missing required scope field returns `400`.

## Route Surface

The only new non-GET route is:

- `POST /summarize`

No existing JSON response models were changed, and no pipeline, verifier, extraction, embedding, or schema logic was changed.

## Raw Pytest Output

```text
$ pytest tests/test_api.py -q
..............                                                           [100%]
14 passed in 13.02s

$ pytest -q
........................................................................ [ 77%]
.....................                                                    [100%]
93 passed in 52.40s
```
