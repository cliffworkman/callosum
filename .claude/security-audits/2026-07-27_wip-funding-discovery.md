# Security audit — Discover > Funding wired to WIP manuscripts

**Date:** 2026-07-27
**Status:** complete — PASS

## Scope

Increment 403: `POST /funding-discovery/run` gains an optional `manuscript_id` field (tags the resulting
`research_funding_profiles` row's `source_kind`/`source_id` instead of `"manual"`, so the run is attributable to a
specific WIP manuscript) and a new endpoint `GET /wip/manuscripts/{manuscript_id}/funding-runs` (reads that same
table back, scoped to the manuscript, for display in the manuscript's own workspace tab).

## Threat review

- **Input validation:** `manuscript_id` is an optional int; `funding_run` rejects `paper_id` + `manuscript_id`
  together (422) and 404s if the manuscript doesn't exist (`get_manuscript`, the same check every other WIP
  mutation route already uses). It never substitutes for the existing `description` requirement — a
  `manuscript_id` with no `description` still 422s exactly as before (unchanged validation order).
- **Output encoding / injection:** parameterized SQLAlchemy Core throughout (rule #3); `funding_run_summaries`'s
  new `source_kind`/`source_id` filter uses bound `.where()` clauses, not string interpolation.
- **Authorization scoping:** the new endpoint is mounted on the existing `/wip` router
  (`dependencies=[Depends(require_local_wip)]`, `wip_checks.py`), so it inherits the same loopback-only gate as
  every other WIP route — verified: `GET /wip/manuscripts/1/funding-runs` with a non-loopback `Host` header 403s
  (`test_wip_funding_runs_route_remains_local_only`). Scoping correctness (a manuscript's list never includes
  another manuscript's or a paper's runs) is verified directly:
  `test_funding_runs_list_404s_for_a_missing_manuscript_and_is_scoped`.
- **SSRF / external calls / data egress:** none new — Funding Discovery's existing external providers
  (OpenAlex/Crossref/Grants.gov) are unchanged; a WIP-tagged run exercises the identical, already-audited fetch
  path as a paper-tagged or manual run. No LLM/egress-gate interaction (LLM triage remains a separate, already
  opt-in toggle, untouched by this change).
- **Resource caps:** `funding_run_summaries`'s new filter doesn't change its existing `limit` clamp
  (`max(1, min(int(limit), 25))`); the new endpoint caps at 25.
- **Supply chain:** no new dependency. No schema change — `research_funding_profiles.source_kind`/`source_id`
  were already generic, unconstrained strings (used today for `"paper"`/`"manual"`/`"saved_<kind>"`); `"wip-
  manuscript"` is simply a new value in that same free-text field, not a new column or table.

## Negative-path checks

All verified by `tests/test_wip_funding.py` (5 passed):
- `paper_id` + `manuscript_id` together → 422.
- A `manuscript_id` for a nonexistent manuscript → 404 (both on the run endpoint and the list endpoint).
- The list endpoint scopes correctly across two manuscripts (one with a run, one without).
- The list/run routes are gate-exempt from nothing — both stay behind `require_local_wip`.

## Result

No exploitable issue or new sensitive boundary was found. The change reuses Funding Discovery's existing,
already-audited provider/persistence path; the only new surface is a small, correctly-scoped read endpoint and a
provenance tag on an already-generic column.

**Security Audit: PASS**
