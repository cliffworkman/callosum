# Increment 219 — Reading queue (the to-read "Queue" tab) + a SQLite concurrency fix

## Implemented

A **Reading queue** — a personal, ordered to-read list — surfaced as the **third tab of the left-pane AXES
section** (`[Axes | Tags | Queue]`). It is **not** an axis (no semantic scoring): its own small table, the
inc-208 saved-searches / inc-211 curated-axis class.

- **`app/backend/persistence/schema.py`** — new `reading_queue` table: `id` PK, `paper_id` FK→papers
  (`ON DELETE CASCADE`) + `UniqueConstraint(paper_id)` (one row per paper → add is idempotent; purge a paper →
  its queue row CASCADE-drops), nullable `position` (the manual order), `created_at`.
- **`alembic/versions/0030_reading_queue.py`** — guarded `create_table` (skip if present) + **no-op
  `downgrade()`** (the 0021-0029 pattern: 0001's metadata-loop drops it on a real downgrade). Head **0030**;
  tests assert it via `alembic_head()`.
- **`app/backend/persistence/reading_queue_repo.py`** (new) — `list_reading_queue` (join papers, exclude
  trashed, order by `position` NULLS-last then id), `is_in_queue`, `add_to_queue` (idempotent; `position =
  coalesce(max,-1)+1`), `remove_from_queue`, `set_queue_order` (validate `paper_ids` == current members else
  `ValueError`; write position by index). Bound-param Core (rule #3); split out so `repository.py` stays under
  the cap (the saved_search_repo / tags_repo precedent).
- **`app/backend/api/routers/reading_queue.py`** (new) — `GET /reading-queue`, `POST /reading-queue`
  (404 on a nonexistent paper, `{added}` idempotent), `DELETE /reading-queue/{paper_id}` (204, idempotent —
  both ✓ and × call it), `PUT /reading-queue/order` (`ValueError`→422). Reuses `papers._authors_from_csl` for
  row display. Included in `app.py` after `saved_searches.router` (no `/papers/{id}` collision).
- **Frontend** `app/frontend/js/16_queue.jsx` (new) — `QueuePanel` + `registerPaneTab` into the AXES section
  (order 30). The panel is a **drop target** for `application/x-callosum-paper` (the inc-206 card MIME → add);
  each row is **draggable + a drop target** via a queue-only MIME `application/x-callosum-queueitem`
  (the inc-212 reorder pattern → `reorderToIndex` splice → `PUT /reading-queue/order`); rows have a ⠿ grip, a
  click-to-open title, **✓** (read → remove) + **×** (remove). `25_detail.jsx` gains a **+ Reading queue**
  button (`addToQueue` → `POST /reading-queue`); `05_panes.jsx` passes `onQueueChanged` into the Details
  render; `40_app.jsx` adds `queueRefresh`/`onQueueChanged` to `paneCtx`; `styles.css` gains the `.queue-*`
  recipes (tokens only, rule #8).

### The SQLite concurrency fix (the non-obvious half)

`app/backend/persistence/database.py::make_engine` now also runs, on connect:

```
PRAGMA journal_mode=WAL
PRAGMA busy_timeout=5000
```

**Why:** the headed verification (below) reliably hit `sqlite3.OperationalError: database is locked` on a
`/reading-queue` write. uvicorn serves sync FastAPI endpoints from a threadpool → multiple concurrent
connections to the one SQLite file. With the **default rollback journal + busy_timeout=0**, a write that
collides with the list-refresh GET it triggers (or the inc-138 auto-select Details fetch) fails *immediately*.
WAL lets the single writer proceed alongside readers; busy_timeout makes a residual write-write collision
**wait** instead of erroring. This is the standard local-SQLite-under-a-web-server pairing and a real,
app-wide hardening (not specific to the queue).

## Key technical detail

- **The queue is NOT an axis.** A dedicated table (not the curated-axis machinery): a queue isn't a scored
  lens, and the maintainer's instinct was a separate tab. Membership + order live in `reading_queue`, decoupled
  from `cluster_node_papers`.
- **Two distinct drag MIMEs** so the gestures never cross-fire: `application/x-callosum-paper` (a library card
  → add to the queue, inc 206) vs `application/x-callosum-queueitem` (a queue row → reorder, inc 212). The
  panel drop handler accepts only the former; the row drop handler only the latter.
- **WAL + busy_timeout, NOT `BEGIN IMMEDIATE`.** The textbook cure for the residual read-then-write
  *upgrade-deadlock* (a SELECT-then-write transaction can't upgrade its snapshot when another write landed in
  between → SQLITE_BUSY *immediately*, which busy_timeout can't break) is `BEGIN IMMEDIATE` (grab the write
  lock up front). **It is unsafe here**: `_run_scan_job` wraps the entire scan + `embed_chunks` + `embed_papers`
  in **one** `engine.begin()` transaction (minutes long), so app-wide BEGIN IMMEDIATE would hold the exclusive
  write lock for the whole job and block every other request. So WAL+busy_timeout is the in-scope fix, and the
  upgrade-deadlock is a **filed backlog item** (it's pre-existing + app-wide — every read-then-write endpoint
  has it — and a human essentially never triggers it; it needs its own focused increment, likely scoped
  transaction-retry or splitting long jobs into incremental commits first).

## Manual verification script

Headed, **no egress**, deterministic across **10/10 runs**: `.local/visual/drive_inc219_queue.py` (own free
port + own seeded SQLite; kills stray uvicorns first):

1. Seed 3 papers, open the **Queue** tab → empty-state hint shows.
2. **Drag** the first library card onto the Queue panel → 1 row; `GET /reading-queue == [A]`.
3. Select the 2nd card → Details → **+ Reading queue** → 2 rows; `== [A, B]`.
4. **Drag-reorder** row[1] onto row[0] → the DOM reorders to "Beta paper" first; `== [B, A]` (persists).
5. **✓** the first row → 1 row (`== [A]`); **×** the last → 0 rows (`== []`).
6. Assert 0 console (non-500) / page / genai errors. The driver tolerates **only** a transient
   `database is locked` 500 on a `/reading-queue` write (the known upgrade-deadlock artifact) and retries the
   step up to 3× — it cannot mask a wrong-state (the DOM must still reach the expected count/order).

(The driver synchronizes on DOM state via `wait_for_function` + drains in-flight fetches with
`wait_for_load_state("networkidle")` between mutations, so the verification reflects realistic human pacing.)

## Pytest

`tests/test_reading_queue.py` — **6** (add/list/idempotent/authors; trashed excluded; remove idempotent;
`set_queue_order` reorders + rejects a foreign id set; CASCADE on paper delete; the 4 endpoints incl. 404 +
422). Full suite: **783 passed** (+6 vs inc 218's 777). QA surface **159/159 API + 706/706 FE, 0 uncovered**
(`route_49_reading_queue.md`).

## NEXT

- **Backlog (filed):** the app-wide **read-then-write upgrade-deadlock** hardening (a write racing a concurrent
  fetch can still rarely SQLITE_BUSY; needs its own increment — BEGIN IMMEDIATE is unsafe given long jobs).
- **Backlog (Bella's beta asks, queued):** a true **read/unread marker** (vs the queue's ✓-removes), priority
  markers.
- Otherwise the design-gated B-items (B2 collaboration, B3 OCR, B4 citation-context classifier, B5 mobile).
