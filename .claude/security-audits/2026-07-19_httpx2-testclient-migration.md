# Security audit — httpx2 dev dependency (TestClient migration)

**Trigger:** CLAUDE.md audit gate #6 (a new third-party dependency). Follow-up to
`2026-07-19_web-stack-cve-migration.md` (inc 305), which bumped `starlette` to 1.3.1 and left this as a filed,
non-blocking follow-up: starlette 1.x's `TestClient` prefers `httpx2` and emits a `StarletteDeprecationWarning`
under plain `httpx` (a warning, not an error — the suite stayed green either way).

## What changed
- Added `httpx2>=2,<3` to `requirements-dev.txt` and to `pyproject.toml`'s `[project.optional-dependencies].test`
  group. **No source-code change** — `starlette.testclient` (imported via `fastapi.testclient.TestClient`, used
  by all ~73 API test files) does `try: import httpx2 as httpx / except ModuleNotFoundError: import httpx` +
  warn. Installing `httpx2` alongside is a superset install; nothing had to be re-pointed.
- Verified via `pip show httpx2`: v2.7.0, **BSD-3-Clause**, published by Tom Christie (httpx/starlette's original
  author) under the `pydantic` GitHub org — the same lineage as the existing `httpx`/`starlette` deps, not a
  new/unknown maintainer.

## Threat review
- **Supply chain:** same trust tier as the existing `httpx`/`starlette` dependencies (same author/org). Pinned to
  a version range (`>=2,<3`), consistent with the project's other dev-tool pins.
- **Egress / data handling:** none. `httpx2` here only powers `TestClient`'s in-process ASGI transport (no real
  socket, no network egress) — the exact same role `httpx` already played. It is **dev/test-only**: not in
  `requirements.txt` (the runtime dependency set), never imported by any `app/` or `integrations/` module, and
  confirmed absent from `THIRD-PARTY-NOTICES.md`'s scope (that file covers *shipped* runtime deps only — pytest/
  ruff/playwright/pip-audit/mcp aren't listed there either, and httpx2 follows the same convention).
- **Blast radius:** zero production impact. A broken or malicious dev dependency here could at most affect local
  test runs / CI, not the shipped app (which never installs `requirements-dev.txt`).
- **Negative-path check:** confirmed the deprecation warning reproduces without `httpx2` installed (`pip show
  httpx2` → not found; `pytest tests/test_health.py -q` → `StarletteDeprecationWarning` in the warnings summary)
  and disappears cleanly once installed, with the full suite still green (`tests/test_health.py` 6 passed before
  and after; see the increment notes for the full-suite re-run).

## Security Audit: PASS
