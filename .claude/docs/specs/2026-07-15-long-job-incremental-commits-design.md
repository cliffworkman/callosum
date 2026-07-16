# Long-job incremental commits — design spec

**Status:** approved (brainstorm, 2026-07-15). The second half of the `database is locked` concurrency item; the
first half (short request-path retry — `run_write` + `SqliteWriteRetryMiddleware`) shipped in **inc 272 / PR #11**
and is the complementary foreground mechanism this design leans on.

## Problem

The long-running background jobs each wrap their **entire** multi-minute unit of work in **one**
`engine.begin()` transaction. `_run_scan_job` (`routers/library.py`) is the exemplar: a single transaction spans
the file scan + per-paper **Crossref HTTP calls** + embedding inference for every chunk + the retraction check +
the watched-folder bookkeeping. Because SQLite has a single writer, that one transaction holds the write lock for
the whole duration — including during network calls and model inference. A foreground write (add a tag, toggle a
read marker, reorder the queue) that collides with a running job waits out `busy_timeout=5000ms` (inc 219) and
then 500s. Inc-272's foreground retry (`run_write`) helps a *transient* collision, but it can't outlast a lock
held for **minutes** — that requires the job to stop holding it for minutes.

Confirmed structure (inc-272 investigation): `_run_scan_job` → `with app.state.engine.begin() as conn:` wrapping
`scan_library_folder(conn, …)` + `_process_scan_result(conn, …)` (the enrich + embed loop) + `add_watched_folder`
+ `touch_last_scanned`. Every other long job (axis-score, citation/bundle import, enrich-batch, dedup, gap-finder,
the statcheck/retraction/transparency batches, my-publications refresh/decompose, citation-counts) follows the same
one-big-transaction shape. **No job spawns work synchronously** — all use FastAPI `BackgroundTasks` and iterate a
list of items inside the single transaction.

## Goal

Make each long job release the write lock **between units of work** by committing per item instead of once at the
end, so foreground writes (retrying via inc-272) slip in between a job's item-commits. Uniform across all ~12 jobs.

## Non-goals

- Moving the slow work itself (Crossref HTTP, embedding inference) **outside** the transaction (the "compute
  outside the lock" option). Explicitly declined for this pass: per-item commits keep each item's HTTP/embed inside
  a *short* per-item transaction (~a second), released between items — enough that the foreground retry succeeds.
  A future pass can pull HTTP/embed-compute out of the per-item write if the residual per-item hold is a problem.
- `BEGIN IMMEDIATE` for foreground writes. Orthogonal; the inc-272 retry already covers the snapshot-upgrade case.

## Design

### The reusable primitive — `commit_each`

Add to `app/backend/persistence/` (beside `sqlite_retry.py`):

```python
def commit_each(engine, items, process, *, on_item_error="skip", logger=None):
    """Process each item in its OWN short transaction, releasing the SQLite write lock between items.

    Runs `process(conn, item)` for each item via `run_write` (inc 272 — fresh connection → run → commit, with a
    bounded retry if that item's own commit hits a transient lock). `on_item_error="skip"` logs and continues (the
    resilient-batch behaviour these jobs already want — one bad paper never aborts the run); `"raise"` propagates.
    Returns the per-item results in order (None for a skipped item).
    """
```

This unifies both concurrency layers on one primitive: `run_write` is a foreground short write *and* a long-job
per-item unit. The jobs' loops change from `with engine.begin() as conn: for item in items: process(conn, item)`
to `commit_each(engine, items, lambda conn, item: process(conn, item))` (or a hand-rolled per-item `run_write`
where a job's shape doesn't fit a plain iterate — e.g. a scan's insert-phase-then-loop).

### Deliberate consequence — atomicity moves from per-job to per-item

Today a mid-job failure rolls back the whole job (all-or-nothing). With per-item commits, items processed before a
failure stay committed. For these jobs that is **intended and better**:
- **Partial progress is usable + resumable.** A scan interrupted at paper 40 of 77 leaves 40 usable papers; the
  scan is idempotent (content-hash dedup, inc 45), so a re-run continues from where it stopped rather than redoing
  everything.
- **It fixes a latent bug.** In the current shared-transaction loop, a caught per-item exception can leave the
  transaction in a poisoned state that fails *subsequent* items' writes. A fresh per-item transaction isolates each
  item, so one bad item can't corrupt the rest of the batch.

The spec records this as an accepted behaviour change; each job's "done" summary already reports per-item error
counts, so partial completion stays observable.

### Per-job item boundary

Uniform "per-paper / per-unit". The mechanism is identical; the item differs:

| Job | Item boundary |
|---|---|
| `_run_scan_job`, `_run_watched_rescan_job` | commit the fast local **scan-insert** phase, then enrich + embed **per paper** (+ a final short txn for the watched-folder bookkeeping) |
| axis-score job | per paper (embed + score one paper's membership) |
| citation import, bundle import | per imported entry |
| enrich-batch (`library_enrich`) | per paper |
| statcheck / retraction / transparency batches, citation-counts | per paper |
| my-publications refresh / decompose | per publication / per domain |
| dedup, gap-finder | per candidate-group / per axis (read-heavy; exact boundary pinned in the plan) |

## Testing

- **`commit_each` unit tests:** each item commits independently (inject a failure at item K → assert items 1..K-1
  persisted, which the old all-or-nothing rollback would lose); `on_item_error="skip"` logs+continues vs `"raise"`
  propagates; a transient per-item lock retries (via `run_write`); results returned in order.
- **Per-job behavioural test (load-bearing):** for each converted job, inject a mid-list item failure and assert
  the earlier items are persisted — the direct proof the transaction boundary moved from per-job to per-item.
  "Lock released between items" is not directly unit-testable; this partial-progress assertion is the honest proxy.
- **Regression:** every existing job test (`test_library_scan`, `test_axes`, import/bundle, the method batches,
  my-publications…) stays green — the happy path is behaviour-preserving.

## Sequencing (one spec → ~4 grouped increments, each its own green PR)

- **A — pattern + auto-running offenders:** `commit_each` + tests, then scan / watched-rescan / axis-score. Proves
  the pattern end-to-end where it matters most (these auto-run on launch + focus).
- **B — ingest family:** citation import, bundle import, enrich-batch.
- **C — method batches:** statcheck / retraction / transparency + citation-counts.
- **D — read-heavy + my-pubs:** dedup, gap-finder, my-publications refresh/decompose (pin their item boundaries).

Each increment converts its jobs, adds the partial-progress test(s), keeps existing tests green, and ships as its
own PR so the sequence can be paused or re-ordered between groups.

## Invariants / gates

- No egress-posture change (jobs already make the same external calls; only the transaction boundary moves).
- No new endpoint / schema / external fetch / ingestion path / auth → **no security-audit gate trigger**; note the
  atomicity-becomes-per-item change in each increment's notes. No new user-facing surface → no new QA route (the
  jobs' endpoints are already covered); the honesty invariants are untouched.
- Parameterized SQL (rule #3), 600-line cap, `ruff`, full `pytest` per increment.
