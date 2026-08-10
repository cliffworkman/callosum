# Increment 468 — Superuser capabilities: a reusable gate + Diagnostics (item #1 of round 2)

## Implemented

Item #1 of the round-2 post-P2 backlog sequence (memory `callosum-next5-backlog-roadmap-round2`). The
`is_superuser` flag has existed since inc 195 (a verified-ORCID allowlist, `CALLOSUM_SUPERUSER_ORCIDS`) but
gated nothing — deliberately deferred at the time. Asked Cliff what it should gate; his answer reframed the
task from "pick one capability" to a genuine access-control **pattern**: any feature that could stand in
tension with `PRINCIPLES.md`/`APPROACH-AVOIDANCE.md` guidance should have the *option* to sit behind the
superuser gate until it's proven safe for general release (his example: a future, more permissive
literature-acquisition mode he could dogfood before it's "bulletproof" for others). Explicitly recorded and
confirmed with Cliff: the gate has no exception to `APPROACH-AVOIDANCE.md`'s standalone veto ("no paywall
circumvention... a line it will not cross") — nothing in this increment touches that boundary; the note is on
record for whenever a future feature is actually designed behind this gate.

**Architecture finding that shaped the design:** `app_settings.stored_oauth_session()` is a single stored
secret, not a per-request multi-user session table (consistent with callosum's local-first/single-user
design). So "superuser" doesn't distinguish concurrently-signed-in users — it means "is the *currently*
signed-in identity Cliff's own verified ORCID," meaningful when the instance is reached by someone else (the
remote-access tunnel, a shared/hosted deploy) while Cliff isn't the one currently signed in.

### 1. The reusable gate

`app/backend/api/dependencies.py::require_superuser()` — 403s unless
`app_settings.oauth_account_status()["is_superuser"]` is true. Reads only the server-stored session; no
request header/body/query param is ever consulted. Applied via `Depends(require_superuser)`, the same FastAPI
dependency pattern already used everywhere else in this file.

### 2. First application: `GET /diagnostics`

New router `app/backend/api/routers/diagnostics.py`, gated via `dependencies=[Depends(require_superuser)]` on
the route decorator (not inside the handler body — the gate can't be accidentally skipped by a future edit).
Returns local operational state not shown anywhere else: live paper/chunk/embedding counts (new
`diagnostics_repo.py::library_stats`, mirroring the established `select(func.count()).select_from(...)`
pattern), remote-access/sync config state (`app_settings.stored_remote_access()`/`stored_sync_settings()`),
and app/DB identity (reusing `health.py`'s existing `reported_app_version()`/`_database_status()` helpers).
Deliberately excluded from v1: DB file size (no existing URL→path helper, not every deploy is file-based
SQLite) and sync run-history (lives in the `sync_state` table, a real future addition). Doesn't duplicate the
existing Status popover (active-job visibility) — this is config/exposure state, not job activity.

### 3. Frontend

`app/frontend/js/35_settings.jsx` — a new `DiagnosticsSettings` component in the "Account & sync" card, right
after `AccountSettings`. Self-contained (its own `/settings` check for `is_superuser`, then its own
`/diagnostics` fetch), returning `null` until both are confirmed — no flash of hidden content before the gate
resolves. 481→513 lines, comfortably under the 600-line cap.

## Key technical detail

The gate is enforced at the FastAPI route-decorator level (`dependencies=[...]`), which runs before the
handler body executes — structurally impossible to reach `diagnostics()`'s body without passing
`require_superuser` first, unlike an inline `if not is_superuser: raise` inside the handler (which a future
edit could accidentally move below other logic).

## Manual verification script

1. Sign out (or on a fresh instance) — Settings shows no Diagnostics section; `GET /diagnostics` → 403.
2. Sign in as a non-allowlisted identity — same: no section, 403 (the "· superuser" suffix on the Account line
   is also absent).
3. Sign in as an ORCID in `CALLOSUM_SUPERUSER_ORCIDS` — the Account line shows "· superuser"; a new
   "Diagnostics (superuser only)" block appears showing library counts, remote-access/sync state, and DB/app
   version; `GET /diagnostics` → 200 with matching data.

## Verification

- `pytest tests/test_diagnostics.py tests/test_auth_oidc.py tests/test_health.py -q` → all passing (4 new + 24
  existing, no regressions).
- `python tools/build_frontend.py` — clean build; `pytest tests/test_frontend_assembly.py -q` → 64 passed.
- `python tools/check_line_budget.py` (run as the **last** step, per inc 467's own lesson) → clean.
- `python tools/qa/build_surface_map.py check` → 0 uncovered (extended `route_45_account.md` to cover
  `/diagnostics`, since a real superuser sign-in shares the same "needs the live Authentik platform" limitation
  that route already documents for ORCID sign-in generally).
- Live-verified against the maintainer's real running platform (not just the hermetic test client): confirmed
  `GET /diagnostics` → 403 by default, and — more informatively than planned — confirmed live that a **real,
  currently signed-in identity** ("authentik Default Admin," not Cliff's own allowlisted ORCID) correctly shows
  no "· superuser" suffix and no Diagnostics section, a stronger real-world negative-case proof than the
  originally-planned signed-out-only check. The positive (superuser sees real data) case is proven by the
  hermetic suite using real code paths (`create_app`, a real DB, the real `require_superuser` dependency, a
  real sign-in flow via the existing `FakeOidcClient` test double) — a live positive check needs Cliff's own
  real ORCID sign-in through the real Authentik platform, the same manual-only limitation this codebase already
  documents for ORCID sign-in generally (`route_45_account.md`).
- `.claude/security-audits/2026-08-09_superuser-diagnostics.md` — PASS.

## Housekeeping

- Closed this item in `INCREMENT-BACKLOG.md` §3 → one line in `INCREMENT-BACKLOG-DONE.md`.
- Memory `callosum-next5-backlog-roadmap-round2` updated: item 1 closed, item 2 (statcheck signal/work-state
  duality) next.
- `.claude/CLAUDE.md`: counter bumped to 468; pytest count updated.
