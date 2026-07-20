# Increment 310 — Sync UI (SP3c), Increment A: list + resolve conflicts (backend)

## Context
Backlog #15's last open item is SP3c: the Settings → Sync UI (setup/enable/run + a conflict-review screen). A
planning pass this session (3 parallel research agents covering the `/sync/*` API surface, existing Settings UI
conventions, and the full 194–202 increment/spec history) found the backend wasn't quite ready for a UI to build
against: `sync_conflicts` is written by the engine but **nothing reads or resolves it** — no repo, no endpoint.
This increment closes that gap (**Increment A** of the approved 2-increment plan); Increment B (the frontend) rides
on top of it next.

## Implemented

- **`app/backend/sync/engine.py` — `apply_conflict_resolution(conn, collection, record_id, payload)`.** The "keep
  mine" write: builds a synthetic `RemoteRecord` from the conflict's stored `losing_payload` and hands it to the
  *same* `_apply_record`/`_apply_link` dispatch a real remote winner already goes through — same FK-translation,
  same `_coerce_for_write` column allowlist (rule #4), same link-table handling. Deliberately does **not** touch
  `sync_state` — leaving it alone means the next ordinary `run_sync`'s hash-diff sees the restored value differs
  from what's recorded and pushes it as a ordinary local change, naturally out-versioning the remote side. No
  separate versioning path to get wrong.
- **`app/backend/persistence/sync_conflicts_repo.py` (new).** `list_unresolved_conflicts`, `get_conflict`,
  `resolve_conflict(conn, id, side)` — `"theirs"` is a pure bookkeeping flip (the remote value already won and is
  live); `"mine"` calls `apply_conflict_resolution` then flips `resolved=1`, only on success.
- **`app/backend/api/routers/sync.py` — two new endpoints.** `GET /sync/conflicts` (list unresolved rows, each
  paired with the *live* domain value via `changeset.collect_local` for a mine-vs-current diff) and
  `POST /sync/conflicts/{conflict_id}/resolve {side: "mine"|"theirs"}` (fails closed → 409 on an unknown/
  already-resolved id, or an unresolved FK dependency). Neither endpoint is gated on enabled/signed-in/configured
  — a conflict is local data from a past run, reviewable regardless of current sync state. The resolve endpoint's
  request body accepts only `side` (a 2-value enum) — there is no field through which a client could supply data
  to write; the only content ever written is what the engine itself already captured in `losing_payload`.
- **`.claude/qa-routes/route_46_sync.md`** extended (was API-only for setup/settings/run; now also covers
  list/resolve, with a new standing assertion: conflicts are surfaced, never silently resolved, and the resolve
  endpoint fails closed rather than no-op-as-success).
- **`.claude/security-audits/2026-07-19_sync-conflict-resolution.md`** — PASS (new endpoint + new write path
  triggers). Key finding worth restating: the resolve endpoint literally cannot accept a data payload from the
  client — only a choice between two already-server-held values — which closes off the obvious injection concern
  before it can arise.

## Key technical detail
Found mid-implementation: the full pytest suite's `test_short_write_sweep.py` (inc 281's machine-enforced
"every short write goes through `run_write`, never a raw `conn.commit()`" gate) caught my first draft of
`resolve_sync_conflict` — it used `Depends(get_connection)` + a manual `conn.commit()`, exactly the pattern inc
281 retired. Fixed by switching to the `request.app.state.engine` + `run_write(engine, op)` closure pattern
(mirroring `routers/reading_queue.py`): an `HTTPException` raised inside the closure propagates immediately,
un-retried, and `resolve_conflict`'s failure paths are read-only checks (no `execute()` before them), so nothing
partial is ever left mid-write. This is exactly the kind of drift the machine gate exists to catch — worth noting
since it's a good example of the gate doing its job on a brand-new endpoint, not just legacy code.

## Manual verification (automated, no browser — this is a backend-only slice)
`tests/test_sync_endpoints.py`'s new tests build a genuine two-device conflict (mirroring
`test_sync_engine.py`'s recipe, via direct `engine.run_sync` calls against two separate SQLite files — the
existing API-level test harness shares one `app_settings` store per test process, which can't represent two
independent "devices"), then hit the new endpoints against the device holding the conflict:
1. `GET /sync/conflicts` → one row, `losing_payload["title"] == "B-edit"` (mine), `current["title"] == "A-edit"`
   (theirs, already live).
2. Resolve `"theirs"` → 200, conflict no longer listed, domain value **unchanged** (still "A-edit").
3. (Fresh conflict) Resolve `"mine"` → 200, conflict no longer listed, domain value **restored** to "B-edit".
4. Resolving an unknown id, or the same id twice → **409** both times.

## Pytest
`tests/test_sync_endpoints.py` **13 passed** (7 existing + 5 new + the short-write-sweep regression this
surfaced); `tests/test_sync_engine.py` + `test_sync_server.py` unaffected (29 passed together). Full suite:
`pytest -n auto -q` → **1288 passed, 1 skipped** (1283 baseline + 5 new). `ruff check .` + `ruff format --check .`
+ `python tools/check_line_budget.py` (346 files) clean. `python tools/qa/build_surface_map.py check` →
250/250 API, 0 uncovered.

## Next
**Increment B** (the frontend): a new `app/frontend/js/35c_sync.jsx` chunk — `35_settings.jsx` is at 552/600, no
room for a full setup/enable/run/conflict-review section — implementing the Settings → Sync UI against these four
existing + two new endpoints. See the approved plan (`.claude/backups/plans/2026-07-19_sync-ui-sp3c-plan.md`).
