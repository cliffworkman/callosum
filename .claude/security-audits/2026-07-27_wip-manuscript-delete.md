# Security audit — WIP manuscript delete

**Date:** 2026-07-27
**Status:** complete — PASS

## Scope

A new endpoint, `DELETE /wip/manuscripts/{manuscript_id}`, added to the existing `/wip` router
(`app/backend/api/routers/wip.py`) so it inherits the router's existing `require_local_wip` gate
(loopback-only, blocked entirely under `CALLOSUM_READ_ONLY=1`) with no new authorization logic. It
backs a new "Remove manuscript" action in `WipContextMenu`, and pairs with a watch-root list UI that
surfaces the already-existing `DELETE /wip/watch-roots/{root_id}` endpoint (no backend change needed
there — only new frontend wiring).

This closes a real, confirmed gap: deleting a watch-root already correctly preserves its manuscripts
(`ON DELETE SET NULL` on `wip_manuscripts.watch_root_id`), but with no manuscript-level delete, an
orphaned manuscript (once its watch-root is gone) could never again be synced, marked missing, or
removed — a permanent "ghost" row. This endpoint is the only way to clear one.

## Threat review

- **Input validation:** `manuscript_id` is a path int; the row's existence is checked via the delete's
  own `rowcount` (mirrors `roots_delete`'s exact existing pattern) — 404 on a missing/already-deleted id,
  never a 500.
- **Cascade completeness:** every one of the 8 tables referencing `wip_manuscripts.id` (files, findings/
  checks, sections, tasks, references, provenance/checkpoints, across `schema_wip.py`/
  `schema_wip_provenance.py`/`schema_wip_workflow.py`) is `ForeignKey(..., ondelete="CASCADE")`, and
  SQLite FK enforcement is on (`PRAGMA foreign_keys=ON`, confirmed in `persistence/database.py`). A
  single `DELETE FROM wip_manuscripts` is complete — no manual per-table cleanup, no orphaned child rows.
- **Output encoding / injection:** parameterized SQLAlchemy Core throughout (rule #3); no raw SQL.
- **File-path safety:** this endpoint never touches the filesystem — it only deletes database rows. The
  manuscript's own files/folder on disk are completely untouched (the frontend's confirm dialog says so
  explicitly, so the user isn't misled into thinking this deletes their actual manuscript files).
- **Destructive-action confirmation:** gated behind `window.confirm` client-side (the established pattern
  used by 10+ other files in this codebase) before the request is even sent — not a server-side
  protection, but consistent with how every other destructive action in this app is guarded, and this is
  a single-user local app (rule: the threat model here is accidental self-harm, not a malicious actor).
- **Data egress:** none — pure local DB operation.
- **Supply chain:** no new dependency, no migration (existing schema/FKs already support this).

## Negative-path checks

All verified by `tests/test_wip_api.py`:
- Deleting an orphaned (watch-root-deleted) manuscript with a child task succeeds (204), the task is
  gone with it (cascade), and the manuscript is subsequently 404 on both GET and a second DELETE.
- `DELETE /wip/manuscripts/{id}` with a forwarded-header/non-loopback host → 403 (extended
  `test_wip_routes_deny_remote_forwarded_and_read_only_access`).
- Frontend: `window.confirm` cancel leaves the manuscript/root untouched (manually verified — see
  increment notes); the selected-manuscript state clears if the deleted manuscript was selected
  (`deleteManuscript`'s `setSelectedId` guard).

## Result

No exploitable issue or new sensitive boundary was found. The endpoint inherits the existing
`require_local_wip` gate, relies entirely on already-declared FK cascades (no new manual delete logic
to get wrong), and never touches the filesystem.

**Security Audit: PASS**
