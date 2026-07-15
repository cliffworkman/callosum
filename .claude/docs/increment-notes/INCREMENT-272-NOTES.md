# Increment 272 — SQLite write-retry hardening (the "database is locked" short-write item)

Closes the **short request-path write** half of the long-standing `sqlite3.OperationalError: database is locked`
backlog item (the long-job-splitting half stays open). Two layers of defense (the user asked for both).

## Root cause
Short write endpoints get a plain `engine.connect()` via `Depends(get_connection)`, write, then `conn.commit()`.
They 500 on a lock in two collision cases: (1) a long background job (`_run_scan_job`/embed/enrich wraps a
multi-minute unit in one `engine.begin()`) holds SQLite's single WAL write slot → a foreground write waits out
`busy_timeout=5000ms` (inc 219) then gives up; (2) a snapshot-upgrade — a connection that read a snapshot then
tries to upgrade to a write after another connection committed → `SQLITE_BUSY` *immediately* (`busy_timeout`
deliberately doesn't apply). The inc-277 `_write` retry is at the wrong granularity: it retries a single
`conn.execute` on the *same still-open transaction*, which keeps its stale snapshot, so it can't clear the BUSY.

## Implemented

**Layer 1 — `run_write(engine, fn)` (`app/backend/persistence/sqlite_retry.py`).** Transaction-level retry: opens a
**fresh connection per attempt**, runs `fn(conn)`, commits, returns the result; on `database is locked` re-runs the
whole unit (fresh snapshot) with bounded backoff. Non-lock errors and any non-`OperationalError` (e.g. an
`HTTPException` a 404/422 check raised inside the closure) propagate immediately, un-retried. Explicitly scoped to
SHORT writes — a long job would restart on a late collision, so long jobs keep their own single `engine.begin()`.
Wired into the hot short-write endpoints (keeping `Depends(get_connection)` for the *response read* — WAL reads
never block): `papers.py` set_read/set_priority; `tags.py` color/add/lock/remove; `reading_queue.py`
add/reorder/remove; `axes.py` create.

**Layer 2 — `SqliteWriteRetryMiddleware` (`app/backend/api/sqlite_retry_middleware.py`).** A backstop ASGI
middleware (innermost user middleware in `app.py`) for the long tail of pure-DB write endpoints not individually
converted: if a handler raises an uncaught `OperationalError: database is locked` **before** producing any
response, it re-runs the whole request on a fresh connection (bounded attempts + backoff). Safe because: it retries
only when nothing was sent yet (a lock is raised mid-handler, before the response is built, so nothing committed);
only mutating methods; the request body is buffered once and replayed each attempt; and a **replay-unsafe
denylist** (`REPLAY_UNSAFE_PREFIXES`/`_SUBSTRINGS` → `is_replay_safe`) excludes families that do more than a pure
DB write — `/library`, `/settings`, `/access`, `/sync`, `/discovery`, `/acquire`, `/enrich`, `/gaps`,
`/summaries`, `/critical-read`, `/reference-integrity`, `/methods`, `/workbench`, `/citations/render`, and the
`/score`, `/generate`, `/reprocess-pdf`, `/fill-metadata`, `/reresolve`, `/acquire`, `/refresh` substrings — so a
replay can never double-spawn a job, re-issue a fetch, or re-write a secret. (No file-upload/multipart endpoints
exist — imports are server-side path reads — so buffering every replay-safe body is cheap and safe.)

## Key technical detail
The two layers are complementary, not redundant: `run_write` is the **precise, in-request** retry (no full-request
replay, safe for any side effect, fast) on the known-hot paths; the middleware is the **blanket backstop** for the
rest, correct only because a lock error precedes any commit/send (so a re-run is side-effect-free) and because the
denylist keeps replay away from anything that isn't a pure DB write.

## Not in scope (still open)
The long-job half: `_run_scan_job` / embed / enrich / the axis-**score** job wrap a multi-minute unit in one
`engine.begin()` write transaction. A foreground write colliding with one of those can still exceed the retry
window (the lock is held for minutes, not milliseconds). The fix there is to split those jobs into incremental
commits so they don't hold the write lock for minutes (then `BEGIN IMMEDIATE` also becomes safe). Left as its own
increment; recorded in the backlog.

## Manual verification script
1. `uvicorn app.backend.api.app:app --port 8888`. 2. Start a library scan/enrich (holds the write lock), then in
another tab rapidly toggle a paper's read marker / add a tag / add to the reading queue → they now succeed (retry)
instead of 500ing. 3. Confirm a genuinely bad write (e.g. a 404 on an unknown paper) still returns 404/422, not a
retry-masked 500.

## Pytest
`tests/test_sqlite_retry.py` (9: retry_sqlite_locked + run_write) + `tests/test_sqlite_retry_middleware.py` (7) all
pass; the converted endpoints' suites (papers/tags/reading_queue/axes) unchanged-green. Full suite: **1214 passed,
1 skipped** (through the wired middleware, which touches every mutating request).
