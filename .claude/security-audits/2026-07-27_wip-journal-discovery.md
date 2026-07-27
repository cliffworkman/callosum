# Security audit — Discover > Journals wired to WIP manuscripts

**Date:** 2026-07-27
**Status:** complete — PASS

## Scope

Increment 404: `POST /methods/publishers/run` gains an optional `manuscript_id` field. When set, the run's
outcome is persisted as a compact receipt (`wip_journal_runs`: `topic_id`, `weighting`, `considered`, `shown`,
`created_at` — never the ranked profile list itself) in a new table, migration `0058_wip_journal_runs`. A new
endpoint `GET /wip/manuscripts/{manuscript_id}/journal-runs` reads that receipt list back, scoped to the
manuscript, for display in its own workspace tab.

## Threat review

- **Input validation:** `manuscript_id` is an optional int; `publishers_run` rejects `paper_id` +
  `manuscript_id` together (422) and 404s if the manuscript doesn't exist (`get_manuscript`, the same check
  every other WIP mutation route uses). It never substitutes for the existing `abstract`+`subject` requirement
  — a `manuscript_id` alone still 422s exactly as before (unchanged validation order; the manuscript path reuses
  the existing `abstract`+`subject` resolution in `_resolve_topic_and_abstract`, untouched).
- **Output encoding / injection:** parameterized SQLAlchemy Core throughout (rule #3); `list_journal_runs` uses
  a bound `.where()` filter, not string interpolation. `record_journal_run` inserts only numeric/short-string
  fields already validated/derived server-side (topic_id from OpenAlex, weighting/considered/shown from the
  deterministic `build_profiles` computation) — no raw user text is stored in this table at all.
- **Authorization scoping:** the new endpoint is mounted on the existing `/wip` router
  (`dependencies=[Depends(require_local_wip)]`), inheriting the same loopback-only gate as every other WIP
  route — verified: `GET /wip/manuscripts/1/journal-runs` with a non-loopback `Host` header 403s
  (`test_wip_journal_runs_route_remains_local_only`). Scoping correctness is verified directly:
  `test_journal_runs_list_404s_for_a_missing_manuscript_and_is_scoped`.
- **SSRF / external calls / data egress:** none new. Journals' existing external calls (OpenAlex `/sources`,
  DOAJ) are unchanged and already audited; a manuscript-tagged run exercises the identical fetch path as a
  paper-tagged or pasted-abstract run. The abstract is still only ever embedded locally (unchanged
  `_abstract_never_transmitted` invariant, re-verified by the existing `test_abstract_never_transmitted` — the
  new manuscript path reuses the same `_resolve_topic_and_abstract` code, so this guarantee automatically
  extends to it without a new test needed to prove it separately).
- **Resource caps:** `list_journal_runs` caps at 25 rows (`max(1, min(int(limit), 25))`, matching the
  `funding_run_summaries` precedent from inc 403).
- **Supply chain:** no new dependency. New table `wip_journal_runs` (additive migration `0058`, FK CASCADE to
  `wip_manuscripts`) — no changes to any existing table. Deliberately does NOT reverse `publishers.py`'s
  documented "ephemeral job result; no table/migration" design for the paper/abstract paths: only a
  manuscript-tagged run ever writes a row, and only a small receipt (never the full ranked profile list) is
  stored.

## Negative-path checks

All verified by new tests in `tests/test_publishers.py` (5 passed):
- `paper_id` + `manuscript_id` together → 422.
- A `manuscript_id` for a nonexistent manuscript → 404 (both the run and the list endpoints).
- The list endpoint scopes correctly across two manuscripts (one with a run, one without).
- A successful manuscript-tagged run's receipt matches the computed report's `topic_id`/`considered`/`shown`/
  `weighting` exactly.
- The list route stays loopback-only.

## Result

No exploitable issue or new sensitive boundary was found. The change adds a small, correctly-scoped receipt
table and reuses Journals' existing, already-audited provider/embedding path; the paper/abstract paths are
completely untouched.

**Security Audit: PASS**
