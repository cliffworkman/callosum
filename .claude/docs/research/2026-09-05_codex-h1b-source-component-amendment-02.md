# H1b Audit Protocol Amendment 02: Host-Crash Exclusion

**Date:** 2026-09-05  
**H1b target unchanged:** `a41266ba4850a17ce04af3480b7237197416574f`

During the first complete Callosum round-trip measurement, the host computer crashed. The audit
process exited without writing either its public summary or its private measurement artifact. No
partial result from that process is accepted as evidence.

After restart, no audit-owned Python process remained. The isolated study database reported
`PRAGMA integrity_check = ok`, migration head `0080_source_components`, 1,628 source pages,
1,089,546 source components, and 23,875 chunks. The previously completed invariant, coverage,
idempotence, and retrieval-identity receipts remained present. The unfinished Callosum round-trip
measurement will therefore restart from its first page against the same validated study copy.

Two earlier preparatory invocations of the round-trip command had terminated before measurement
because of harness-only import and deterministic tie-order defects. They likewise produced no
accepted result. The corrected harness keeps all production code and study data unchanged.

This amendment changes no hypothesis, metric, tolerance, corpus, sample rule, target commit, or
interpretation rule. It only records exclusion of interrupted or pre-measurement harness attempts
and preserves an auditable boundary around the clean rerun.
