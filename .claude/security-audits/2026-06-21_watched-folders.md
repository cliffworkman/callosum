# Security audit — watched library folders (inc 98)

**Date:** 2026-06-21
**Feature:** persist the folders the user scans (`watched_folders`) + auto re-scan them on launch + a manual
"Re-scan all" + un-watch. Builds on the inc-87 scan (reused unchanged).
**Trigger(s):** new endpoints (`GET /library/watched`, `DELETE /library/watched/{id}`,
`POST/GET /library/watched/rescan`), a new ingestion trigger (auto on launch), a new table + migration (0014).
(No new dependency; the double-click fix is unrelated frontend.)

## Surface
- `app/backend/persistence/schema.py` + `alembic/versions/0014_watched_folders.py` — the `watched_folders` table.
- `app/backend/persistence/watched_repo.py` (NEW) — add/list/remove/touch.
- `app/backend/api/routers/library.py` — register-on-scan + the watched endpoints + the rescan worker.
- Frontend `27_scan.jsx` (Watched-folders modal), `40_app.jsx` (auto-rescan on launch), `35_settings.jsx` (toggle).

## Threat review
- **Server-side folder read (the load-bearing one).** Watched folders **persist user-supplied folder paths** and
  **auto-read them on launch**, amplifying the inc-87 note: `POST /library/scan` already reads a server-side
  folder, fine on **127.0.0.1** (the server *is* the user's machine) but a remote caller could enumerate/read
  server files. The auto-rescan reads the *persisted* paths automatically. Same local single-user threat model;
  **must be gated before any hosted deployment** — recorded in the CLAUDE "before public deployment" checklist
  (this row extends the existing `/library/scan` one). No path is built from request data beyond the folder the
  user supplies; the scan globs `*.pdf` only, caps per-file size, and links in place (nothing copied).
- **SQL injection (rule #3).** `watched_repo` uses bound params throughout — `INSERT OR IGNORE` on the UNIQUE
  `path`, bound `delete`/`update`/`select`. No interpolation. `path` is stored data, never an SQL identifier.
- **Resource exhaustion.** The rescan is an **async job** (doesn't block the loop), bounded by the watched-folder
  count × the inc-87 scan caps (per-file 80 MiB, per-file savepoint isolation, content-dedup so a no-change
  rescan adds nothing). Auto-on-launch fires **once** per load (a ref guard) and is opt-out (Settings toggle,
  default on). A vanished watched folder is skipped + counted, never fatal.
- **EGRESS.** Only the Crossref DOI lookup for newly-imported papers (metadata egress, **not** the Gemini gate),
  exactly as the inc-87 scan. No new egress.
- **Destructive safety.** Un-watching (`DELETE /library/watched/{id}`) drops only the `watched_folders` row — the
  papers it imported are kept (tested). No file is ever deleted or moved.
- **Migration.** 0014 is additive + idempotent (guarded `create_table`; fresh DBs get it from 0001's
  `create_all`), matching 0002–0013. No data migration, no down-migration.
- **Principles (rule #9).** Ingestion / fact-gathering (like the inc-87 scan + the Zotero importer) — not a
  claim/signal about the literature; the gate is light, no misalignment.

## Negative-path checks (run)
- `add_watched_folder` idempotent on the UNIQUE path (no duplicate); remove keeps the papers (tests). ✓
- Scan registers + stamps a watched folder; rescan picks up a new file; an unchanged rescan adds nothing
  (content-dedup); rescan over a now-missing folder → counted, not fatal (tests + the worker guard). ✓
- `GET /library/watched/rescan/{bad}` → 404. ✓ Auto-rescan no-ops when there are no watched folders. ✓

## Result
**Security Audit: PASS.** The one material exposure (server-side folder read, now persisted + auto-read) is the
inc-87 surface extended — acceptable on 127.0.0.1, **flagged to gate before any hosted deploy**. Otherwise:
bound-param SQL, async + bounded + content-deduped, non-destructive un-watch, no new dependency, additive
migration.
