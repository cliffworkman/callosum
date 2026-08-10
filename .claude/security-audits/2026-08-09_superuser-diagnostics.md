# Security audit — superuser gate (`require_superuser`) + `GET /diagnostics`

**Date:** 2026-08-09
**Status:** complete — PASS

## Scope

A new reusable FastAPI dependency, `require_superuser` (`app/backend/api/dependencies.py`), and its first
application: `GET /diagnostics` (`app/backend/api/routers/diagnostics.py`). This is new authorization logic
(audit-gate trigger #4) — the first endpoint in the codebase gated on the `is_superuser` flag that has existed
since inc 195 but previously gated nothing.

## Principles-gate note (rule #9)

This is a general access-control **pattern**, not a one-off: any future feature not yet proven safe for general
release gets the option to sit behind this same gate (Cliff's explicit ask). Its first application here is
read-only operational visibility — plain counts and config booleans, never a composite score (Principles #7),
never paper content/titles, never secrets or tokens. Recorded explicitly with Cliff: the gate is for "not yet
proven safe, eventually meant for everyone" — it has **no exception** to `APPROACH-AVOIDANCE.md`'s standalone
veto-level boundary ("no paywall circumvention... a line it will not cross"). Nothing in this increment touches
that boundary; the note is here so it's on record before any future feature actually gets designed behind this
gate.

## Threat review

- **Input validation:** `GET /diagnostics` takes no request parameters at all — nothing to validate or inject.
- **Authorization — the core question.** `require_superuser` reads only the **server-stored** session
  (`app_settings.oauth_account_status()["is_superuser"]`, itself derived from `stored_oauth_session()`, a
  single server-side secret written only by the real `/oauth/callback` flow). No request header, query
  param, or body field is ever consulted — a caller cannot claim superuser status via anything they send. This
  is the identical posture the existing `is_superuser` flag already has (inc 195); the new code adds an
  enforcement point, not a new trust decision.
- **Output encoding / injection:** N/A — the response is five plain integers/booleans plus an optional short
  version string already served by `/health`.
- **Data exposure:** `DiagnosticsResponse` was deliberately scoped to counts and config-enablement booleans
  only (paper/chunk/embedding counts, remote-access-enabled, sync-enabled/configured, app version, DB
  reachability). No paper titles, no library content, no tokens, no secrets, no file paths, no sync-server
  credentials. Verified against the actual Pydantic model — every field is `int`/`bool`/`str|None` (a version
  label, already public via `/health`).
- **SSRF / external calls / data egress:** none — pure local DB read (`diagnostics_repo.py`) + local settings
  read (`app_settings`). No new dependency, no new external call.
- **Resource caps:** three `COUNT(*)` queries, already-indexed tables (`papers`, `chunks`, `embeddings`) — same
  cost class as existing count queries elsewhere in the codebase (`gapfinder.py`, `wanted_repo.py`).
- **Bypass surface:** confirmed the dependency is applied via `dependencies=[Depends(require_superuser)]` on
  the route decorator itself (not conditionally inside the handler body, which would be easy to accidentally
  skip on a future edit) — FastAPI evaluates route-level dependencies before the handler runs, so there is no
  code path that reaches `diagnostics()`'s body without passing the gate first.

## Negative-path checks

All verified by `tests/test_diagnostics.py` (4 passed) + confirmed live:
- Signed-out caller → `GET /diagnostics` → **403** (`tools`/curl-verified against a live server too, not just
  the test client).
- Signed-in but **non-allowlisted** ORCID → **403** (both the hermetic test and, live, a real signed-in
  "authentik Default Admin" session on the maintainer's own platform correctly shows no "· superuser" suffix
  and no Diagnostics section in Settings — a stronger real-world negative-case proof than planned).
- Signed-in **allowlisted** ORCID → **200** with correct live counts (verified against a freshly-created paper
  in a hermetic test, not just a canned fixture).
- The frontend `DiagnosticsSettings` component renders nothing (not even a placeholder) until
  `acct.is_superuser` is confirmed true — no flash of hidden content, confirmed by code review of the two
  sequential `useEffect`s (the second is gated on `isSuperuser`, and the component returns `null` unless both
  `isSuperuser` and `stats` are set).

## Result

No exploitable issue or new sensitive boundary was found. The gate cannot be bypassed via client-supplied data,
the first application leaks nothing sensitive, and both the negative and positive paths were verified against
real (not just mocked) code — including a live check against the maintainer's own running platform.

**Security Audit: PASS**
