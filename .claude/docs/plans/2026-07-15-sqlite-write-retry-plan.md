# SQLite write-retry hardening — plan (backlog: "database is locked")

**Goal:** Stop short request-path write endpoints from returning 500 `sqlite3.OperationalError: database is locked`
when a write collides with a concurrent read/write (a long background job holding the WAL write slot, or a
snapshot-upgrade BUSY). Two layers of defense (user asked for **both**).

**Root cause (verified):** endpoints get `engine.connect()` via `Depends(get_connection)`, write, then `conn.commit()`.
On a lock they 500. The inc-277 `_write` retry is at the wrong granularity (a single `conn.execute` on the *same*
still-open transaction, which keeps its stale snapshot) — clearing a BUSY needs rolling back and re-running the
**whole unit of work** on a fresh connection.

**Non-goals:** the long-job half (splitting `_run_scan_job`/embed/enrich `engine.begin()` into incremental commits,
and the axis-**score** job's embedding insert) — a separate, riskier increment. This one is the short-write retry.

## Layer 1 — `run_write(engine, fn)` helper (the fast in-request path)

`app/backend/persistence/sqlite_retry.py` (extend):
```python
def run_write(engine, operation, *, attempts=5, delay_seconds=0.05, sleeper=time.sleep):
    """Run a SHORT read+write unit with transaction-level retry on a transient SQLite writer lock.
    Opens a FRESH connection per attempt, runs operation(conn), commits, returns the result. On
    'database is locked' the whole unit is retried (fresh snapshot) with bounded backoff — the granularity a
    snapshot-upgrade BUSY needs. Non-lock errors and the final attempt re-raise. Do NOT wrap a long job in this."""
    remaining = max(1, attempts)
    while True:
        try:
            with engine.connect() as conn:
                result = operation(conn)
                conn.commit()
                return result
        except OperationalError as exc:
            remaining -= 1
            if remaining <= 0 or not is_sqlite_locked(exc):
                raise
            sleeper(delay_seconds)
```
Tests (`tests/test_sqlite_retry.py`): retries-then-succeeds; re-raises non-lock immediately; exhausts attempts →
re-raises; a fresh connection per attempt (spy engine); commits on success; returns operation's result;
a non-OperationalError (e.g. HTTPException raised inside the closure for a 404) propagates WITHOUT retry.

**Convert the hot short pure-DB write endpoints** (keep `Depends(get_connection)` for the *response read* — WAL
reads never block; use `run_write` for the *mutation*):
- `papers.py`: `set_read_endpoint`, `set_priority_endpoint`
- `tags.py`: `set_paper_tag_color`, `add_paper_tag`, `set_paper_tag_lock`, `remove_paper_tag`
- `reading_queue.py`: add / reorder / remove
- `axes.py`: `create_axis_endpoint`
Each: move the write closure into `run_write(request.app.state.engine, lambda c: <repo write>)`, then build the
response from the `Depends` connection (a fresh read snapshot sees the committed write). 404/422 checks that read
first stay as-is; the write closure returns the found/notfound bool.

## Layer 2 — `SqliteWriteRetryMiddleware` (the backstop)

`app/backend/api/sqlite_retry_middleware.py` — catch an **uncaught** `OperationalError: database is locked` from a
**mutating** request (POST/PUT/PATCH/DELETE), replay with bounded backoff. Replay-safety: an uncaught lock error
means the request's transaction rolled back (nothing committed) → safe to re-run a pure-DB handler. **Denylist**
replay-unsafe paths (external fetch / job spawn / keychain / egress): `/library/scan`, `/library/watched`,
`/enrich`, `/acquire`, `/discovery`, `/settings`, `/sync`, `/citations/render` … (prefix match). GET/HEAD never
retried; non-lock errors never retried. Buffer the request body once (`await request.body()` caches on the
Request) so `call_next` can re-run with the same body. Cap attempts (e.g. 4) + small backoff.
Register in `app.py` (`app.add_middleware`).
Tests (`tests/test_sqlite_retry_middleware.py`, a tiny FastAPI app): a mutating route that raises lock-once →
200 after retry; a denylisted route → not retried (raises through); a GET → not retried; a non-lock error → not
retried; attempts capped.

## Verification + docs
- `pytest` (full) green; `ruff check`/`format`; `check_line_budget.py`; no new frontend surface (no build needed).
- No audit-gate trigger (no new endpoint / external fetch / ingestion / auth; the middleware only re-runs existing
  handlers, adds no data path). Note the replay-safety denylist as the key correctness guard in the increment notes.
- `changes.md` + `INCREMENT-272-NOTES.md` + backlog: mark the short-write retry half done, leave the long-job half open.
- Branch `feature/sqlite-write-retry` → PR.
