# Staged harness: performance / resource monitoring

**Checks:** query latency (library list/filter, retrieval, clustering) and storage growth (DB size, vector
index size, `.local/` bloat) over time, so a slowdown is caught by a number trending badly rather than by
Cliff noticing the app feels sluggish.

**Why deferred:** the maintainer's own library is ~200 papers today — well inside the range where SQLite +
`sqlite-vec` + agglomerative clustering are fast by construction. Building a monitoring harness now would be
tuning thresholds against a library size nobody actually has yet.

**Activation trigger:** a real library crosses **~1,000–2,000 PDFs**. That's the point where a linear scan or
an unindexed query starts to show up as real, user-noticeable latency rather than a rounding error, and where
the current architecture's assumptions (in-process `sqlite-vec`, no separate vector daemon) are worth
re-checking against actual numbers instead of intuition.

## Draft design (sketch — flesh out when the trigger fires)

- A lightweight timing wrapper (or `time.perf_counter()` around the key repository calls) logging
  library-list, retrieval, and clustering wall-clock time — behind a debug/verbose flag, not always-on
  overhead in the hot path.
- A `tools/measure_performance.py` harness (sibling to `tools/validation_harness.py`) that runs a fixed battery
  of queries against the real library and reports p50/p95 timings + DB/vector-index file sizes, so a
  before/after comparison is possible when tuning or when the library grows.
- No CI gate — this is a manual/periodic check against the real library, not something a hermetic test
  fixture can meaningfully exercise (test libraries are tiny by design).

## Activation steps
1. When the library approaches the trigger size, build `tools/measure_performance.py` per the sketch above.
2. Run it once to establish a baseline; re-run periodically (or before/after a schema or clustering change)
   to catch regressions.
3. Update this registry's status to `active` once the tool exists and has a recorded baseline.
