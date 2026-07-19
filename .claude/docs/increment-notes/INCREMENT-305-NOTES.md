# Increment 305 — web-stack CVE migration (FastAPI 0.115→0.139, Starlette 0.45→1.3.1)

## Implemented
Cleared **all 14 open Dependabot advisories** (6 high / 6 moderate / 2 low), every one on `starlette`, by bumping
the pinned web stack. A high-severity advisory covers the whole `starlette >=0.4.1,<1.3.1` range, so **1.3.1 is
the floor**; `fastapi 0.115` caps `starlette <0.46`, so FastAPI had to move to **0.139.2** in lockstep.

- **`requirements.txt`** — `fastapi==0.115.8 → 0.139.2`, `starlette==0.45.3 → 1.3.1` (exact pins; comment rewritten
  to record the why + the `_IncludedRouter` gotcha). `requirements-dev.txt` needs no edit (it `-r requirements.txt`).
  `pyproject.toml`'s runtime range (`fastapi>=0.115,<1`) already permitted 0.139 — untouched.
- **`tests/test_health.py`** — new `_iter_api_routes(app)` recursive walker + the mutation-surface lockdown test
  points at it (see the technical detail below).
- **`app/backend/api/routers/my_publications.py`** — the one **shipped-code** touch: two `HTTPException` raises
  used `HTTP_422_UNPROCESSABLE_ENTITY`, which starlette 1.x renamed to `HTTP_422_UNPROCESSABLE_CONTENT` (identical
  value 422). Renamed both (surfaced as a runtime `StarletteDeprecationWarning` by the suite).
- **`.claude/security-audits/2026-07-19_web-stack-cve-migration.md`** — the dep-bump audit (PASS).

New transitive dep pulled by fastapi 0.139: **`annotated-doc 0.0.4`** (fastapi-ecosystem typing helper; recorded
in the audit).

## Key technical detail
**FastAPI 0.139 restructured route inclusion into a lazy `_IncludedRouter`.** Previously `app.include_router(r)`
copied `r`'s routes flat onto `app.routes`, so the security test could do `for route in app.routes if
isinstance(route, APIRoute)`. Under 0.139 each `include_router` leaves a single `_IncludedRouter` container on
`app.routes` (49 of them) and the `APIRoute` leaves live in `_IncludedRouter.original_router.routes`, computed
lazily. The flat iteration collapsed to just the top-level `/` shell → the mutation-surface assertion failed
(`{'/'} == {full set}`). Fix: a recursive `_iter_api_routes` that descends `original_router.routes` (callosum
includes every router **bare, no `prefix`**, so nested routes already carry full paths) — recovering all **252
APIRoutes / 231 distinct paths**. The lockdown assertion (`write_routes == allowed_mutation_routes`) is unchanged
and still passes, which is the proof the bump added/dropped/re-methoded **no** mutation route.

No **runtime** app code introspects `app.routes` (verified by grep); the access-control middleware keys off the
stable `request.url.path` / `request.method`, so the restructure is a test-only concern.

## Gates
- **Security audit (gate #6, dep bump + new transitive dep):** PASS — `2026-07-19_web-stack-cve-migration.md`.
  The mutation surface (the one invariant at risk) is explicitly re-verified unchanged.
- **QA (rule #10):** surface map **248 API / 1157 FE, 0 uncovered** — unaffected (it reads router sources).
- **Not a claim/signal change** (rule #9 not triggered); no CSS (rule #8); no user-facing surface (rule #11) —
  behavior-preserving infra bump.

## Known follow-up (non-blocking)
starlette 1.x deprecates `httpx` under `starlette.testclient` (`StarletteDeprecationWarning: install httpx2
instead`). **Dev/test-only** (the `TestClient`; the shipped server never imports it), a warning not an error, so
the suite is green. Filed to migrate the test client to `httpx2` before the deprecation becomes a removal. The
app's **runtime** `httpx` (external-metadata client, `httpx>=0.27,<1`) is a separate, unaffected dependency.

## Manual verification script
1. Fresh env: `pip install -r requirements-dev.txt` → resolves to fastapi 0.139.2 + starlette 1.3.1 (+ annotated-doc).
2. `pytest tests/test_health.py -q` → 6 passed (the mutation-surface lockdown holds under the new stack).
3. Start the app (`uvicorn app.backend.api.app:app --port 8888`); confirm `/` serves the shell, `GET /papers`
   works, and `POST /papers` → 405 (a read route rejects a write — the surface is unchanged).

## Pytest
`pytest -n auto -q` → **1265 passed, 1 skipped** under the new stack (unchanged count — one existing test
modified, two shipped constant renames, none added/removed). `tests/test_my_publications.py` 41 passed with
`-W error::DeprecationWarning` (confirms the 422 rename cleared the runtime deprecation).
