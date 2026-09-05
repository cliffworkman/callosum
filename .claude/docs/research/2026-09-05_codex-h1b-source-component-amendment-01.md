# H1b Audit Protocol Amendment 01: Excluded Concurrent Preparatory Copy

**Date:** 2026-09-05  
**H1b target unchanged:** `a41266ba4850a17ce04af3480b7237197416574f`

Before any H1b outcome measurement, the command wrapper yielded while a long-running Python
backfill child remained alive. A follow-up command therefore unintentionally started a second
H1b backfill against the same copied SQLite database. At discovery, H1a had completed its expected
23,782 live rows, while the H1b tables contained only 10 pages and 8,348 components for one
attachment. Both exact audit-owned processes were stopped. SQLite still reported `integrity_check
= ok`, but concurrency made the copy methodologically ineligible.

The partial database and anything derived from it are excluded from evidence. No H1b fidelity,
coverage, idempotence, or invariant result had been recorded from it. The audit will recreate a
new study database from the unchanged frozen source snapshot SHA-256
`fc402464bfb9eb26b02f4b7bd12a844bbdc828413dcfc751b3cbf8252da93f70` and execute migrations and
backfills through one explicitly monitored process at a time.

This amendment changes no hypothesis, metric, tolerance, corpus, target commit, or interpretation
rule. It only corrects experiment-process isolation after a wrapper lifecycle defect.
