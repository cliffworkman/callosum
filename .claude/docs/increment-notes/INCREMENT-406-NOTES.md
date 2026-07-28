# Increment 406 — "Status" menu: a cross-feature popover of active/recent async jobs

## Implemented

Backlog #50, Phase 1 (scoped 2026-07-28, built the same day). ~30 independent features already
keep their own `JobStore` on `api.state` (Ask, axis scoring, dedup scan, library scan/import,
statcheck-all, meta-analysis batches, ...) but there was no single place to see what's running
across the whole app. This adds a "Status" item after Help/Settings on the menu bar: click to
open a popover listing every active/recently-finished job, each with a progress bar + ETA where
the underlying job reports real progress, or an honest indeterminate spinner where it doesn't.

**Backend:**
- `app/backend/api/job_store.py` — `Job` gains `finished_at`. `mark_done(job_id, result,
  progress=None)` now carries the job's last known progress forward (previously discarded on
  completion) and stamps `finished_at`; `mark_error` stamps `finished_at` too. `JobStore` gains
  `list_all()`, `dismiss(job_id)`, and `prune_finished_older_than(seconds)`.
- `app/backend/api/routers/status.py` (new) — `discover_stores()` reflects over `api.state` for
  every `JobStore`-typed attribute (auto-discovery, not a hand-maintained list — a future 31st
  `JobStore` shows up automatically). `JOB_LABELS` gives friendly names to the known stores;
  anything unregistered falls back to an auto-prettified attribute name (`_prettify`), never
  silently omitted. `GET /status/jobs` aggregates + sorts (running/pending first, then
  most-recent-finished) + prunes on read. `POST /status/jobs/{store}/{job_id}/dismiss` and
  `POST /status/jobs/clear-finished` remove acknowledged rows. Mounted in `app.py`.
- `tests/test_status.py` (new, 11 tests) + `tests/test_job_store.py` updated (the pre-existing
  `test_done_and_error_carry_no_progress` asserted the OLD discard-on-done behavior — replaced
  with three tests covering the new carry-forward/override/error-still-clears-progress behavior).

**Frontend:**
- `app/frontend/js/04c_status.jsx` (new) — `StatusMenu`, a click-to-toggle popover mirroring
  `AddMenu`/`SavedSearchMenu`'s existing pattern (`10b_libmenus.jsx`), rendered directly into
  `MenuBar`'s `.menubar-utils` (`04b_workspaces.jsx`) after Help/Settings — **not** a registered
  `registerWorkspace` (those are click-to-navigate full panes, the wrong shape for a popover).
  Polls `GET /status/jobs` every 2s while open, 12s in the background. Running/pending rows reuse
  the existing `ProgressBar` component unmodified; `done` rows deliberately do NOT use
  `ProgressBar` (its animated sweep would misleadingly read as still-working) — a static summary
  line instead. Badge = `jobs.length` from the same response. Per-row dismiss on finished rows +
  a "clear all finished" bulk action.
- `app/frontend/styles.css` + `.claude/DESIGN.md` — new `.status-menu`/`.status-badge`/
  `.status-row*` recipe: badge reuses `.finding-badge`'s `--accent`/`--accent-soft` tokens
  (provenance/primary, never the citation-verification colors); popover is right-anchored
  (`.add-menu-pop` anchors left, which would overflow past the viewport at the far-right menu
  position); error rows get a `--danger` left border (the retraction-chip precedent — red for a
  negative fact, not only destructive actions).

**Not built (explicitly out of scope for Phase 1):** individual pipelines (Ask, statcheck-all,
meta-analysis refresh, axis scoring/suggest, dedup scan) still don't report real progress — they
show the honest indeterminate spinner. Instrumenting them is Phase 2, deferred. Also not built:
a mobile/phone-width rendering of Status (the phone menu bar is a `<select>`; Status doesn't fit
that shape and isn't shown there yet — noted in `DESIGN.md`, not silently dropped).

## Key technical detail — `api.state` isn't a plain object

The first implementation of `discover_stores()` used `vars(state).items()`, and every
data-bearing test failed silently (empty job lists). `api.state` is Starlette's `State`, which
proxies `state.foo = x` into a private `_state` dict via `__setattr__` rather than the instance
`__dict__` — so `vars(state)` only ever sees the one wrapper attribute, never the real entries.
`State` is iterable/subscriptable over its real keys (`__iter__`/`__getitem__`), which is what
the fixed version actually walks: `{name: state[name] for name in state if isinstance(...)}`.

## Manual verification script

1. Start the app, open the browser.
2. Confirm "Status" appears on the menu bar after Help/Settings, with no badge when nothing's
   running.
3. Trigger a real job with progress (e.g. the library-header "Citations ↻" cited-by refresh, or
   a library scan). Open Status: confirm a badge appears, the row shows a real fill bar +
   "current / total" + label.
4. Trigger Synthesize > Ask (or any job kind without progress instrumentation). Confirm its row
   shows the indeterminate pulse, not a fake percentage.
5. Let a job finish. Confirm it stays listed (a static "Done" / final-count line, no animated
   sweep), then dismiss it with the row's `×` — confirm it disappears and the badge count drops.
6. Start two jobs of different kinds at once; confirm both rows appear independently.
7. Force a job to error (e.g. malformed input to a batch endpoint you control); confirm the row
   shows the red-bordered error detail, and "Clear all finished" removes it alongside any done
   rows but leaves a still-running job alone.
8. Click outside the open popover; confirm it closes (the existing `AddMenu` outside-click
   pattern).

**Not run this session:** the Playwright MCP disconnected mid-session (server-side), so no live
browser drive-through was possible. In its place: the full backend flow was verified directly
against a disposable second callosum instance (port 8899, isolated from the user's own running
dev server on 8888) — a real citation-count-refresh job was started, polled mid-run, confirmed
done with its final progress preserved (`178/178`), dismissed, and the store-name allowlist
negative path (`store=engine`) confirmed 404. The frontend popover/CSS/badge itself is unverified
visually this session — flagged as a follow-up for whenever a live browser check is available.

## Pytest

`pytest tests/test_status.py tests/test_job_store.py -q` → **17 passed**.
`pytest tests/test_frontend_assembly.py -q` → **53 passed** (after `python tools/build_frontend.py`).
`python tools/check_line_budget.py` → all files within the 600-line cap.
`ruff format --check .` + `ruff check .` → clean.
