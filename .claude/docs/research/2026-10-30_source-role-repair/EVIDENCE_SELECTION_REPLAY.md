# Evidence-selection replay (inc 611): controlled, in-sample

**This is not a new blinded experiment.** It replays five named development cases through the real
`pipeline._source_chunks_for_scope`, then records mechanistic before/after lineage:
- no adequacy re-scoring;
- no reviewers;
- no generation.

Artifacts live in `C:\Users\cliff\callosum-data\experiments\source-role-repair-20261030\` (not in Git).

## Database identity (fresh disposable copy)

| | Path | Bytes | SHA-256 |
|---|---|---|---|
| Source (protected, unchanged) | `…\reference-backfill-20261030\classified.sqlite` | 715,993,088 | `d2c82be56b49c448d72c8c5eaabd2ea00bf7468503af85f8b60ffe9bfc4881a0` (before = after) |
| Destination | `…\source-role-repair-20261030\replay.sqlite` | 715,993,088 | `b40b6cbfde5187acee2710346e44da9d3caf8feb3af3eee44cf570c0ccc6f84f` (at copy) |

**How the copy was made.** `sqlite3.Connection.backup` (the online backup API) from a `mode=ro&immutable=1`
source. The source WAL was 0 bytes, which `make_copy.py` checks before using `immutable`.

**Integrity.** Counts match: 265 papers, 68,086 chunks, 110,401 embeddings, 42,044 chunk_structure rows.
`integrity_check` returned ok. Receipt: `COPY_RECEIPT.json`.

## Procedure

| Step | Code / data | Result |
|---|---|---|
| Before | `code-before\` (`git archive` of `9d9417f9`), copy holding v1 rows, read-only | Reproduces the frozen four-condition B (MiniLM) and D (Arctic S) selections **exactly, 10/10 units** |
| Reclassify | Repaired `tools/backfill_chunk_structure.py` on the copy | See the migration document |
| After | Repaired worktree code, copy holding v2 rows, read-only | Run twice (before and after the latency changes): identical selections, hits and fates |

**Guards (both runs):**
- network, generation, NLI construction and lazy embedding refused;
- 0 attempts recorded;
- serial and model-major: MiniLM, then Arctic S.

## Table fingerprints

124 tables were digested row by row (`fingerprint.py`).

| Event | Tables changed |
|---|---|
| Backfill | `chunk_structure` only |
| Replays | None |

**Vectors are preserved.** `embeddings` and every `callosum_vec_embeddings_384*` shadow table are identical
before and after.

## Selection changes (8 slots)

| Case | Profile | Added | Removed (now just outside budget) | Mechanism |
|---|---|---|---|---|
| WL15 | MiniLM | 5399 @7 | 5161 (raw 9) | 607 had demoted 5399 from raw rank 7; now scientific |
| WL15 | Arctic S | 5399 @4 | 5121 (raw 9) | Same |
| WL18 | MiniLM | 58052 @7, 56894 @8 | 58415 (raw 9), 1060 (raw 10) | 58052: heading filter had removed it; 56894: 607 demotion from raw 7 |
| WL18 | Arctic S | none | none | 58052 is now retrieved (raw 11) but stays outside the budget |
| SP18 | both | none | none | Unchanged; the earlier 607 benefit (a promoted passage) is preserved |
| D_q2 | MiniLM | 56618 @1 | 42181 (raw 10) | 56618 (raw 1) was demoted; now `unknown`, so not demoted |
| D_q2 | Arctic S | 56618 @7 | 57316 (raw 9) | Same (raw 7) |
| D_p2 | MiniLM | 56618 @1 | 56508 (raw 11) | Same (raw 1) |
| D_p2 | Arctic S | 56618 @4 | 56514 (raw 10) | Same (raw 4) |

**The two other tracked chunks:**
- **58043** was retrieved in neither run, for any case.
- **67832** moved from `excluded_heading_reference_filter` to `not_retrieved` for every whole-library case. It
  is now reachable, but these queries do not rank it.

**Essential chunks of these cases are unchanged:** 56795 is selected in WL18 under both profiles, and 23819 in
SP18. Every pre-existing essential fate is identical, apart from 56888's raw rank moving 19 → 20 under Arctic S
WL18, caused by 58052 entering the candidate set.

**Pool size (whole library):** 26,083 → 26,293 after boilerplate. Chunks excluded by the heading filter in scope:
11,877 → 11,664.

## Bibliography control (10 runs, 80 slots)

| Metric | Before | After |
|---|---|---|
| Current `bibliographic` chunks among vector hits | 182 | 175 (still demoted) |
| Current `bibliographic` chunks selected | 0 | 0 |
| `references`-labelled chunks selected | 0 | 1 (58052, a genuine conclusion) |
| Slots filled | 80 | 80 |

## Latency

Measured on the whole-library candidate fetch, 68,086 chunks, n=7 interleaved (`latency_receipt.txt`):

| Path | Time |
|---|---|
| Old SQL exclusion | median 5.29 s |
| inc-611 two-phase | median 5.62 s |
| Rescue phase alone | median 0.21 s |
| First call per process | about 0.6–1.3 s more (reads undecided texts once) |

**This deviation is intentional and measured.** About 0.3 s per warm whole-library Ask buys reachability of
genuine prose mislabelled `references`.

The first implementation fetched every labelled row and re-assessed it on each query. It cost about 1.2 s (fetch)
plus about 1.5 s (assessment). It was replaced by the two-phase fetch, cheapest-first conjunction order and a
per-process `(chunk id, chunk_version)` memo; the replay confirmed identical selections afterwards.

Selected-papers scope is unaffected: 0.26–0.52 s before and after.

## Interpretation limits

**These are the failures the repair was designed against,** so it recovering them is expected. That shows the
defect is fixed in these instances; it is not evidence of a general improvement.

**Adequacy was not re-scored.** The pilot tied WL15's adequacy loss to 5399's demotion, and 5399 is selected
again. Whether WL15 is now adequate, or whether any displaced passage (5161, 5121, 58415, 1060, 42181, 57316,
56508, 56514) mattered, would need a fresh, blinded, source-verified evaluation on held-out questions.
