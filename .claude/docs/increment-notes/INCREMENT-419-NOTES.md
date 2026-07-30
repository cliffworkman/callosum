# Increment 419 — dev-mode fallback for the connection-tooltip version

## Implemented

A real bug report from live use, caught within minutes of shipping inc 417's fix: Cliff checked the
connection tooltip via the browser dev server (`uvicorn`, launched directly from PowerShell — not the
packaged desktop app) and found the old `(local-verifier-v1)` text correctly gone, but nothing replaced
it — no `(v#.#.#)` either, just a bare "Connected." His ask: "that way, I can easily confirm which
version I am running."

This traced cleanly, not to a bug in inc 417's logic, but to a real gap in its scope: `app_version`
(`app/backend/api/routers/health.py`) is only ever populated via `CALLOSUM_APP_VERSION`, an env var the
Tauri desktop shell's `backend.rs` sets when it spawns the backend as a child process. A plain `uvicorn`
run has no such env var — by design, per inc 417's own notes ("no version invented for a non-packaged
run"). That design correctly avoided fabricating a fake packaged-release version for a dev context, but
it left dev-server users with literally nothing to check against, which defeats the actual point Cliff
was after. The packaged builds Cliff has installed (v0.3.1, and the v0.3.2 he's mid-installing) also
don't even carry inc 417's code at all — it landed on `main` only after v0.3.2 was tagged — so this fix
was tested and observed purely via the dev server, the exact context that exposed the gap.

**Fix:** `health.py` gains `_dev_git_version()` — a small, `functools.lru_cache`d helper that shells out
to `git rev-parse --short HEAD` (falling back to `None` on any failure — no git installed, not a git
checkout at all, e.g. a from-scratch source tarball) and appends a trailing `+` if `git status
--porcelain` shows uncommitted changes. The result is deliberately prefixed `dev-` (e.g. `dev-4ed3196`,
or `dev-4ed3196+` if dirty) so it can never be mistaken for a real packaged semver release — the same
honesty concern inc 417 already cared about, just extended to cover the dev case too. `health()`'s
`app_version` field is now `os.getenv("CALLOSUM_APP_VERSION") or _dev_git_version()` — the packaged-shell
env var still wins when present; the git identifier only ever fills the gap it was actually missing.

## Key technical detail

`_dev_git_version()` is cached via `functools.lru_cache(maxsize=1)` — it's cheap enough to not strictly
need this, but the health endpoint is the one App() unconditionally fetches at every launch, and a
process's own git SHA/dirty-state never changes without a restart, so recomputing on every call would be
pure waste. Tests must call `health_module._dev_git_version.cache_clear()` before exercising a different
scenario in the same pytest process (a monkeypatched git failure, then a real git success afterward) — a
handful of module-level caches share this need across the codebase, not a new pattern.

## Housekeeping

- `tests/test_health.py`: replaced the single inc-417 test that asserted `app_version is None` outside
  the shell (no longer true) with three: the env-var-wins case, a real-git-checkout case (asserts the
  `dev-[0-9a-f]+\+?` shape against this actual repo, not a fake), and a mocked-git-unavailable case
  (still falls back to `None`, never crashes).
- No security audit triggered: `subprocess.run(["git", ...])` takes no user/request input at all — the
  command and its arguments are fully hardcoded, `cwd` is the fixed `PROJECT_ROOT` constant already used
  elsewhere in this same module. Not a new external-process-spawning *pattern* either — `app_settings.py`
  and other backend modules already shell out to git-adjacent tooling in a few places.
- `ruff format`/`ruff check` clean; `check_line_budget.py` clean (no file near the cap).

## Manual verification

Confirmed directly against the live dev server this session: hit `GET /health` before the fix
(`"app_version": null`) and traced why; after the fix and a server restart (plain `uvicorn`, no
`--reload`, so the running process needed a manual restart to pick up the change — noted to Cliff), the
same endpoint should return `"app_version": "dev-<short-sha>"` matching the current checkout, and the
brand-logo tooltip should show `Connected (dev-<sha>)`.

## Pytest / build gates

- `pytest tests/test_health.py tests/test_frontend_assembly.py -q` → **67 passed** (1 test replaced with 3 new
  in `test_health.py`, net +2 — 1712 total collected across the whole suite; `test_frontend_assembly.py`
  unaffected — this is a backend-only change).
- `pytest tests/test_sync_server.py tests/test_mobile_ingress.py tests/test_access_control.py -q` →
  **59 passed** (the other suites that touch `/health`, confirmed unaffected by the additive field
  change).
