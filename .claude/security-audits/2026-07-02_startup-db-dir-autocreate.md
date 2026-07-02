# Security audit — startup SQLite parent-dir auto-create + collapsed failure log

**Date:** 2026-07-02
**Change:** `app/backend/api/startup.py` — new `_ensure_sqlite_parent_dir(db_url)`, called at the top of
`_upgrade_database_to_head(db_url)`; the connect/migration failure log collapsed from a full traceback
(`exc_info=True`) to one actionable ERROR line (full trace demoted to DEBUG).
**Trigger:** audit gate #3 — *a new file-write path* (a `mkdir` at startup).

## What it does
For a `sqlite:///<path>` URL whose parent directory does not yet exist, create that directory
(`Path(parent).mkdir(parents=True, exist_ok=True)`) before Alembic runs, so a no-config `uvicorn ...`
launch boots a fresh empty DB (dir → file → migrate → stamp) instead of crashing every DB request with
`unable to open database file`. No-op for in-memory (`sqlite://`, `sqlite:///:memory:`, `mode=memory`)
and non-SQLite URLs.

## Threat review
- **Input source / trust boundary.** The path is **not request-derived**. It comes only from the process
  environment (`CALLOSUM_DB_URL`) or the hardcoded `DEFAULT_DB_URL` constant, both set by the operator who
  launched the server — the same principal that owns the working directory. No privilege boundary is
  crossed and no untrusted/remote input reaches the mkdir (rule #4 boundary is upstream of this code).
- **Path traversal / arbitrary write.** The directory created is exactly the parent of the DB file the
  process was already going to open and write. `mkdir` cannot write file *contents*; it only materializes
  the directory the operator's own config named. There is no attacker-controlled path component. Relative
  paths resolve against CWD — the same base SQLAlchemy uses for the URL — so the dir created matches the
  file opened (no divergence to a surprise location).
- **Symlink / TOCTOU.** `exist_ok=True` + `parents=True` is idempotent; a pre-existing dir short-circuits
  before the `mkdir`. No follow-the-symlink-then-write on untrusted input (single-user local machine).
- **Failure handling / fail-closed.** A `mkdir` OSError (e.g. permissions, read-only volume) is caught and
  logged at WARNING; the subsequent connect then fails and is reported by the collapsed ERROR line naming
  the DB and the `CALLOSUM_DB_URL` fix. The server continues serving (reads/`/health` honest) — no crash,
  no silent state change (the dir-created + migration lines are logged loudly, INCREMENT-style).
- **Info disclosure in logs.** The new ERROR line logs the DB URL (a local path) + the first line of the
  exception string only — no traceback, no secrets (the DB URL is not a secret; `GOOGLE_API_KEY` etc. are
  never touched here). Full traceback is DEBUG-only (hidden at the default INFO level).
- **Egress / external calls.** None. Purely local filesystem + SQLite. Invariant #3 untouched.
- **Supply chain.** No new dependency (`pathlib`, `logging` — stdlib; `alembic`/SQLAlchemy already present).

## Negative-path checks (run)
- `sqlite:///:memory:`, `sqlite://`, `postgresql://...` → `_ensure_sqlite_parent_dir` is a silent no-op,
  creates nothing, never raises (`test_ensure_sqlite_parent_dir_noop_for_memory_and_nonsqlite`).
- DB URL under a non-existent directory → dir auto-created, fresh DB migrated to head, **no ERROR logged**
  (`test_startup_creates_missing_sqlite_parent_dir`).
- Simulated migration failure → single ERROR line, no `exc_info` on the visible record, message names
  `CALLOSUM_DB_URL`, DB left unchanged, no crash (`test_startup_migration_failure_is_non_fatal`).
- Full suite green; `ruff format`/`ruff check` clean.

## Note for the pre-public pass
This is single-user/local behavior. If callosum is ever hosted, `CALLOSUM_DB_URL` remains operator-set
(not request-set), so this path does not become remotely reachable — but re-confirm that the DB URL is
never populated from request data at that time.

**Security Audit: PASS**
