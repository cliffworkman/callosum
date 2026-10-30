# Security audit — active-library identity on /health + fail-closed missing-DB guard (2026-10-29)

**Scope.** Uncommitted on `main`: `app/backend/api/startup.py` (`require_existing_database`, `MissingDatabaseError`),
`app/backend/api/app.py` (one call in `create_app`), `app/backend/api/routers/health.py` (`HealthResponse.library`),
`app/frontend/js/03b_library_identity.jsx` (`LibraryIdentityBadge`), one CSS rule, rebuilt `callosum-app.html`.
Trigger: audit-gate item 1 (request/response-schema change) — `/health` gains an additive field. No new endpoint, no new
external fetch, no new file-write path, no dependency.

## Threat review

| Area | Finding |
|---|---|
| Information disclosure | `/health` is token-exempt (it answers even when Remote access is on). `library` is `null` unless the operator sets `CALLOSUM_LIBRARY_LABEL`; the packaged app never sets it (`backend.rs` spawn env checked). When set, it exposes the operator's own label, the DB file's parent-folder + file name (never the full path or drive/user directories), and one integer (live paper count). No titles, ids, or content. Accepted for a dev/operator surface. |
| Output encoding / XSS | Label is truncated to 80 chars server-side and rendered as React text (no `dangerouslySetInnerHTML`); the `title` attribute is set through React props. A `<img onerror>` label round-trips as inert text. |
| Injection | Count uses a constant SQL string; no request input reaches SQL. The guard parses only the operator's own `CALLOSUM_DB_URL`. |
| File-path safety | The guard only calls `Path.is_file()` on the configured path and raises before any engine connects or `_ensure_sqlite_parent_dir` runs, so it creates nothing. Non-`sqlite:///` URLs and in-memory databases are skipped. |
| Availability | The guard is opt-in (`1/true/yes`); default behavior (packaged first-launch DB creation, dev self-heal) is unchanged. |
| Egress / secrets | None involved. |

## Negative-path checks (run 2026-10-29)

- Label `<img src=x onerror=alert(1)>` + 200×`A` → returned label length 80, verbatim text; `db_file` = `tmp…/t.sqlite`; `live_papers` = 0.
- Label unset → `library: null`.
- `CALLOSUM_DB_REQUIRE_EXISTING=1` with a nonexistent `…/nope/x.sqlite` → `MissingDatabaseError`; directory `nope` not created.
  A real `uvicorn` start against a missing path was also refused earlier the same day (`DEV_LAUNCHER_AND_GUI_VALIDATION.md`).
- Tests: `tests/test_startup_migration.py` + `tests/test_health.py` + `tests/test_frontend_assembly.py` → 122 passed; ruff
  format/check clean; line budget OK; QA surface map OK.

## Residual notes

- The badge reads `/health` once on mount, so its count is current as of page load (a reload refreshes it).
- `tools/run_dev.py` does not set the guard; only the machine-local `run-callosum.ps1` does. Not changed here (scope).

**Security Audit: PASS**
