# Source-role repair (inc 611): prose protection and heading-filter rescue

**Date:** 2026-10-30.

**Trigger:** audit gate item 5 (a net-new behaviour spanning 3+ files). No other trigger applies:
- no new API endpoint or request schema;
- no external fetch;
- no file-ingestion or file-write path;
- no auth;
- no new dependency.

## Threat review

**Input handling.** All inputs are chunk text and labels already stored in the local database.
- `source_role.py` is pure: regular expressions over a single chunk's text, with no I/O.
- Every regex was checked for catastrophic backtracking. All are bounded, with no nested unbounded quantifiers
  over the same class.
- Measured worst case: 13,404 texts in about 0.8 s, roughly 60 µs each.

**Injection.** Every query is SQLAlchemy Core with bound parameters. Id lists go through `sql_batch.in_batches`
(900 per batch), so no unbounded `IN (...)` is ever built. Table and column names are constants.

**Data egress.** None. No model, provider or network is used. Both replay runs recorded 0 guard attempts.

**Resource caps.**
- The rescue memo is bounded at 500,000 entries and cleared on overflow. Each entry is a key of an int and a short
  string.
- The text phase reads only undecided chunks, in batches.

**Integrity and safety (the scientific-safety analogue).**
- A v1 classification cannot be read as current: the version string is compared by every consumer.
- Reclassification writes only `chunk_structure`. This was verified by fingerprinting 124 tables.
- Genuine references stay excluded or demoted:
  - in the replay, 0 current-bibliographic chunks were selected, before and after;
  - 0 rescued chunks carry a v2 bibliographic label.
- An ambiguous chunk becomes `unknown`, never a confident label.

**File paths.** None are touched. The developer backfill accepts a DB URL, as before.

## Negative-path checks (recorded results)

| Check | Result |
|---|---|
| A stale v1 row on a chunk later labelled scientific | Ignored; never demotes (test) |
| Interrupted backfill (`--limit 1`) | One paper committed; the next run resumes the other only; a third run does nothing (test) |
| Rows outside `chunk_structure` after backfill | Byte-identical: chunks, embeddings, papers (test); 123 other tables in the replay copy |
| Same chunk id with changed text (new `chunk_version`) | Re-decided, never served from the memo (test) |
| Incomplete Arctic S index | Still raises `IncompleteEmbeddingIndexError`, embeds nothing (test) |
| Publisher or licence notice labelled `references` that reads as prose | Not rescued (test; 117 in the library) |
| `"body"` / empty text labelled `references` | Excluded (test) |

**Security Audit: PASS**
