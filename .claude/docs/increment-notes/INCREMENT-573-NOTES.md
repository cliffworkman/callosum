# Increment 573 Notes — Synthesize → Ask crashed on a real user's library

## The report

Vasiliki Meletaki tried a synthesis and got:

```
OperationalError: (sqlite3.OperationalError) too many SQL variables
[SQL: SELECT chunks.id, chunks.paper_id, ... FROM chunks WHERE chunks.id IN (?, ?, ... )]
[parameters: (1, 2, 3, ... 629700 parameters truncated ... 716670)]
```

The parameters are `1, 2, 3, …, 716670` — **every chunk id in her library, sequentially**. Something was
fetching the whole corpus by id instead of a bounded set.

## Why this never happened here

`SQLITE_MAX_VARIABLE_NUMBER` is a **build-time property of whichever SQLite the interpreter was linked
against**, not a fixed constant:

| interpreter | limit |
|---|---|
| the development interpreter on this machine | **250,000** |
| the CPython runtime bundled in the packaged desktop app | **32,766** (upstream default) |

At roughly 100–200 chunks per paper, 32,766 is reached around **150–300 papers**. That is an ordinary
reference library, not an edge case. The largest test library here is 23,875 chunks *and* runs on a
250,000-parameter build — two independent reasons this could never reproduce locally. Vasiliki was
simply the first person with a real-sized library to press the button.

So the bug was never "an unusual user". It was a limit that development could not see.

## Root cause

`_rank_chunks_for_query` (`summarization/pipeline.py`) passes the whole candidate pool — for a **query**
scope, every article chunk in the library — into `embed_chunks`, which fans out to
`_chunk_rows`'s `chunks.id.in_(chunk_ids)`. Three call sites bound the same unbounded list.

## The fix

**1. Batching, not limit-detection.** New `app/backend/persistence/sql_batch.py`: id lists are chunked at
900 (below even the pre-3.32 SQLite default of 999), so no id list of any size can produce an invalid
statement on any build we could plausibly run on. Discovering the runtime limit was rejected — it makes
correctness depend on a value that differs per machine, which is exactly the failure mode here.

Note the vector store already had the right answer: `_search_candidates` binds candidates through a
**temp table**, not an `IN (...)`. The pattern existed; these two helpers just didn't use it.

**2. Classify in bulk, not per row.** Phase 1 of `embed_chunks` called `_current_embedding` once per row.
Its comment called this "a cheap per-row DB lookup" — true once, but at library scale it was the dominant
cost of the entire call. Replaced with one batched set query using the **identical** predicate
(`current_chunk_embedding_ids`).

**3. Classify first, embed only stragglers.** `_rank_chunks_for_query` now classifies using the
`chunk_version` each `SourceChunk` already carries, and calls `embed_chunks` only for chunks that
actually need work. In the overwhelmingly common case (everything already embedded) `embed_chunks` is
skipped entirely — it had been re-reading every row, *including `text`*, purely to decide "does this need
embedding?".

Measured, same DB, same connection:

| | 23,875 chunks | extrapolated to 716,670 |
|---|---|---|
| before | ~60s (10.5s fetch + ~49s per-row classify) | ~30 min — **and it crashed** |
| after | **3.2s** | ~96s |

**19× faster on the measured library, and the crash is gone.** The old per-row classification cost 2070µs
through SQLAlchemy — 12× my initial raw-`sqlite3` estimate of 167µs, which is why the first "fix" I
measured looked barely better than the original. Measuring the real path rather than a proxy is what
corrected that.

## A second bug, in what the user was told

The screenshot is arguably worse than the crash. Vasiliki was shown:

> **A cached draft citation could not be read.** Repair the local synthesis cache, then retry.
> *No source chunks matched this query.*

Both statements are false, and the offered button would have failed identically. `classifySynthesisFailure`
substring-matches the **whole** error text — and a SQLAlchemy error embeds the failing statement, which
contains `chunks.chunk_version`, which contains `chunk_`. Confirmed against her exact error string.

The same hazard hit `synthesisSourceDiagnostic`, whose `"chunk"` probe produced "No source chunks matched
this query" — asserting a fact about her library from an error that says nothing about it, to someone
holding 716,670 chunks.

Fixed by classifying on the message only (`synthesisFailureProbeText` splits at `[SQL:`), keeping the full
text under *Technical detail* so nothing is hidden, and adding an explicit branch that says plainly this is
a Callosum limitation, not a problem with her library or her PDFs.

## A latent correctness bug fixed on the way

`_chunk_embedding_ids_for_chunks` matched only on **model identity**, not the version columns. Since
`_insert_embedding_metadata` is a plain INSERT that keeps history (inc 438's "history left intact"), an
edited chunk holds *two* rows — and both were returned, putting the **superseded vector** into the
retrieval candidate set. A chunk could be retrieved into a synthesis on the strength of wording it no
longer contains. Its replacement requires version equality, so only current embeddings are candidates.
The dead helper was deleted (rule #5) and the behaviour is now pinned by a test.

## Verification

- **7 new tests** (`tests/test_sql_batch.py`), including a control test proving the lowered limit is
  load-bearing — without it a batching regression could pass silently, which is precisely how the original
  bug hid. Tests **lower the connection's parameter limit** rather than allocating a huge library, so they
  reproduce a real user's failure on any machine.
- End-to-end: a real query-scope retrieval against a real 23,782-chunk library **at the packaged runtime's
  actual 32,766 limit** — completes and returns 8 chunks. Before this change that path raised.
- Affected suites green (86 passed): summarization, summaries, summarize-selected, embeddings,
  document-scope, citations-suggest, frontend-assembly. Full suite result recorded below.
- `ruff check` + `ruff format --check` clean; line-budget gate passes.

## Honest limits

- **Not verified against Vasiliki's actual library** — I don't have it. The fix is verified against the
  largest real library available (23,875 chunks) plus a lowered-limit reproduction of her exact failure.
  Worth confirming with her before considering it closed.
- **It is fixed, not fast.** ~8.5 min for a query-scope synthesis at her size, because the query scope
  still materializes the whole library to pick 8 chunks. That is architectural and filed as **#79** with
  the per-phase measurements; it needs before/after retrieval comparisons, not a drive-by.
- Paper-scale `IN` clauses elsewhere (axis scoring, bundle export) were checked and left alone: they are
  bounded by paper count, not chunk count, so they are ~4,800 for her — far under any limit. Fixing them
  speculatively would be a drive-by refactor (rule #7).
