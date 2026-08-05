# Security audit: local usage instrumentation (backlog #38A)

Date: 2026-08-05

## Scope

A new local-only, zero-egress instrumentation seam + a "Your usage" Settings dashboard (backlog #38A, the
buildable-now half of the "Research-impact analytics" future track:
`.claude/docs/future-tracks/opus4.8_future-tracks_researchimpactanalytics.md`). Triggers the audit gate via
CLAUDE.md's #1 (new API endpoints) and #5 (net-new feature spanning 3+ files); #2 (a new external fetch) does
**not** apply — this is the one feature in the audit-gate checklist with no external call anywhere in it.

New surfaces:

- `app/backend/persistence/schema_usage.py` (new table `usage_events`), `alembic/versions/0067_usage_events.py`
- `app/backend/persistence/usage_repo.py` (pure repo)
- `app/backend/usage.py` (the `record_event()` seam: gating + allowlist)
- `app/backend/api/routers/usage.py` — `POST /usage/events`, `GET /usage/summary`, `GET /usage/export`,
  `POST /usage/clear`
- `app/backend/app_settings.py` (`usage_events_enabled`, default **True**), `app/backend/api/routers/settings.py`
  (4-point wiring)
- 6 call sites instrumented: `papers.py::export_citations`, `citations.py::render_citations`,
  `duplicates.py::dismiss_duplicates`/`merge_papers_endpoint`, `paper_enrich.py::reresolve_paper`/`fill_metadata`,
  `reference_integrity.py::reference_integrity_review`, `wip_reference_integrity.py::wip_reference_integrity_review`
- `app/frontend/js/35f_usage.jsx` (new Settings card), `app/frontend/js/37_cite.jsx` (`quote_located` fire)

## Data egress

**Zero.** Grepped every new/touched file for `httpx`/`requests`/`fetch(` beyond the app's own same-origin
`apiPost`/`api`/`downloadAsset` helpers — none found; no new import of any HTTP client. `usage.py`,
`usage_repo.py`, and `routers/usage.py` do not import `httpx` or any integrations client at all. The four
`/usage/*` endpoints only ever read/write the local SQLite DB. This is the one feature in this project's audit
checklist that is trivially clean on this axis — confirmed by inspection, not merely asserted.

## Content-leak boundary (the load-bearing check for this feature)

The `usage_events` table (`schema_usage.py`) has exactly five columns: `id`, `event_type` (a `String(40)` from a
closed 5-value set), `count`, `duration_ms` (always `NULL` this increment), `created_at`. **No JSON/text/payload
column exists, and no FK to `papers` or any other table exists.** This forecloses a content leak or a
paper-identifying reconstruction structurally, not just by policy: even a bug at a call site could not leak a
title, DOI, or PDF excerpt into this table, because the schema has nowhere to put one. `usage_repo.py`'s
`list_usage_events()`/`GET /usage/export` return exactly `{event_type, count, duration_ms, created_at}` per row —
pinned by `test_list_events_never_carries_a_payload_field`/`test_usage_export_endpoint_returns_json_download_with_
no_payload_fields` in `tests/test_usage_events.py`, which assert the exact key set rather than just checking a
few expected fields are present (a set-equality assertion catches an accidental future addition too).

## Input validation

- `POST /usage/events`'s `event_type` is validated against `USAGE_EVENT_TYPES` (a closed, hardcoded 5-value
  tuple) at the router layer (422 on anything else) **and again** inside `record_event()` itself (`ValueError` —
  a call-site bug for the 5 hardcoded backend callers, since only the frontend can send an arbitrary string).
  Double-checked deliberately: the endpoint is the untrusted-input boundary (rule #4), `record_event()` is the
  internal invariant every caller — trusted or not — must satisfy.
- `count` is `Field(ge=1, le=1000)` — rejects 0, negative, and unbounded values; a compromised or buggy frontend
  cannot make the table grow unboundedly per call or record a nonsensical negative count.
- `GET /usage/export` takes no path or query parameters — no traversal surface. The response filename
  (`callosum-usage-log.json`) is a constant, never built from request data.
- `POST /usage/clear` is an unconditional `DELETE FROM usage_events` with no `WHERE` clause and, per the
  content-leak boundary above, no FK from any other table points at `usage_events` — clearing it can never
  cascade into library/paper data. Confirmed structurally (no `ForeignKey(...)` anywhere referencing this table)
  and by test (`test_usage_clear_endpoint_zeroes_counts_and_works_regardless_of_toggle`).

## Concurrency / correctness boundary

`record_event()` deliberately takes the caller's **already-open** `Connection` rather than opening its own. The
DB runs SQLite in WAL mode with a 5s `busy_timeout` (`persistence/database.py`) — WAL still allows only one
writer. Four of the six instrumented call sites already run inside an open write transaction (`run_write`'s
`_do(conn)` closure, or `with engine.begin() as conn:`); a `record_event()` that opened a second connection
nested inside one of those would contend for the same single-writer lock the outer transaction hasn't released
yet — a real deadlock, only resolved by the `busy_timeout` expiring into `database is locked`. This is not a
theoretical concern flagged during review and left unresolved — it shaped the actual function signature
(`record_event(conn: Connection, ...)`) before any code was written. See `INCREMENT-450-NOTES.md`'s Key
technical detail for the full reasoning; a future edit that "simplifies" this into owning its own transaction
would reintroduce the deadlock risk, so the module docstring states this explicitly as a guardrail.

## Gating boundary

The enabled/disabled toggle (`app_settings.stored_usage_events_enabled()`, default **True** — the one flag in
`app_settings.py` defaulting on, since nothing here egresses) is checked in exactly one place
(`app/backend/usage.py::record_event()`), so no call site can forget it — pinned by
`test_record_event_no_ops_when_disabled` and the endpoint-level
`test_usage_events_endpoint_disabled_records_nothing`. Read (`GET /usage/summary`), export
(`GET /usage/export`), and clear (`POST /usage/clear`) are **never** gated by this toggle, by design — the local
log must be inspectable/exportable/deletable at any time regardless of on/off state (the design doc's
non-negotiable constraint) — pinned by `test_usage_clear_endpoint_zeroes_counts_and_works_regardless_of_toggle`.

## Principles / A-A alignment (rule #9)

None of `PRINCIPLES.md`'s four worked examples apply directly (all four concern claims *over the literature*;
this produces a claim about the user's own usage) — but Principles #6 (silence isn't a certificate — the
never-empty summary + the honestly-stated `duration_ms`-always-null limitation), #7 (no opaque scores — five
separate labeled counts, never a blended "flourishing score"), and #8 (inspectability — export/clear work
unconditionally) apply directly. A-A is additionally consulted per CLAUDE.md's future-track trigger: **A5**
(local-first — trivially satisfied here), **A4** (the local log is inspectable/exportable/deletable, non-
negotiable), **A1 + the standalone no-opaque-composite-score veto**, and **A3** (the dashboard's copy states
"a count of actions, not a score — for tedious operations, doing them less is the win," directly naming the
Goodhart trap the design doc warns against, rather than silently risking engagement-reads-as-flourishing). The
doc's elaborate research-grade consent form is Stage-4-only (opt-in *contribution*, N>1) — out of scope here,
confirmed by re-reading the doc's own staging language before building.

## Checks

- `pytest tests/test_usage_events.py tests/test_migrations.py -k usage_events -q` — 15 passed (repo, migration,
  gating, allowlist, settings round-trip, all 4 endpoints, the 30-day-cutoff, and the no-payload structural
  checks).
- `pytest tests/test_papers.py tests/test_paper_merge.py tests/test_citations.py tests/test_metadata_multi_enrich.py
  tests/test_reference_integrity.py tests/test_wip_reference_integrity.py -q` — 204 passed, including the new
  single-line instrumentation assertion added to each of the 5 real endpoints' own existing test files (so a
  future edit to one of those endpoints is checked against instrumentation in the same place it's already
  reviewed, not only in the dedicated `test_usage_events.py`).
- `python tools/check_line_budget.py` — clean.
- `ruff format` + `ruff check` on every touched file — clean.
- `python tools/build_frontend.py` — clean; `pytest tests/test_frontend_assembly.py -q` — 64 passed.
- `python tools/qa/build_surface_map.py check` — the 4 new endpoints extend `route_35_settings.md` +
  `route_42_cite.md`'s existing `qa-coverage` blocks (mandatory per `QA-POLICY.md`, no complexity exemption).
- `alembic upgrade head` + `alembic check` on a scratch DB — clean, zero drift.

Result: **PASS.**
