# Increment 98 — Double-click-to-open fix + watched library folders

Two things the user surfaced: a double-click regression and a request for Zotero/Mendeley-style folder watching.

## Part A — double-click always opens (the bug)
The user couldn't open papers by double-clicking. Root cause: the inc-82 guard
`if (!sel || sel.isCollapsed)` — double-clicking the **title** auto-selects the word (browser default), so
`isCollapsed` was false and the open was suppressed (working as inc-82 designed, but the title is the natural
target). Independent of the scan (the `openPdf` wiring was intact; the timing was coincidental). **Fix
(`10_pdf_layer.jsx`):** `onDoubleClick={() => onOpenPdf && onOpenPdf(p)}` — always open; titles stay copyable in
the editable Details pane. Frontend-only.

## Part B — watched library folders
callosum didn't "watch" folders — the inc-87 scan was a one-shot reconcile. Now folders you scan are **watched**
and re-scanned automatically, so new PDFs appear without re-adding (and the library folder is clearly already
tracked, answering the user's "no need to re-add" concern).
- **Schema + migration:** new `watched_folders` table (`id`, `path` UNIQUE, `created_at`, `last_scanned_at`) in
  `schema.py` + guarded migration **0014** (fresh DBs get it from 0001's `create_all`; existing DBs here).
- **`persistence/watched_repo.py`** (NEW): `add_watched_folder` (`INSERT OR IGNORE` on the UNIQUE path, idempotent),
  `list_watched_folders`, `remove_watched_folder` (drops the watch only — papers kept), `touch_last_scanned`.
- **`routers/library.py`:** the scan worker now **registers** the scanned folder as watched + stamps
  `last_scanned`; extracted a shared `_process_scan_result` (enrich + embed) reused by scan **and** the new
  rescan. New endpoints: `GET /library/watched`, `DELETE /library/watched/{id}` (un-watch), `POST
  /library/watched/rescan` + `GET …/{job_id}` (async, re-scan **all** watched folders, aggregating one
  `ScanSummary`; a vanished folder is counted not fatal; reuses the `library_scan_jobs` JobStore).
- **Frontend:** `27_scan.jsx` reframed as a **"Watched folders"** modal (the watched list with last-scanned +
  **remove**, an "Add + scan" field, a **"Re-scan all"** button); the inc-96 "+ Add ▾" menu item renamed to
  **"Watched folders…"**. `40_app.jsx` auto-rescans on launch (once-guarded effect; `autoScanWatched` default-on,
  bumps `libRefresh`/`tagRefresh` when new papers land). `35_settings.jsx` gains an **"Auto-scan watched folders
  on launch"** toggle (Library section, `localStorage["callosum.autoScanWatched"]`). Rebuilt `callosum-app.html`.

## Key technical detail
"Watching" = persisted folders + auto-rescan-on-launch + a manual "Re-scan all" — **not** a live OS file-watcher
(no `watchdog`/inotify; no continuous polling). It's safe to re-scan because `scan_library_folder` content-dedups
by `file_sha256` (and the Zotero importer stores that same hash), so re-scanning the library folder is a no-op
("all unchanged"), never a duplicate. Un-watch is non-destructive (drops the row, keeps the papers). The rescan
reuses the inc-87 scan body via `_process_scan_result`. The auto-rescan endpoint is the same `ScanJobResponse`
shape over the `library_scan_jobs` store.

## Security
`POST /library/scan` already reads a server-side folder (fine on 127.0.0.1); watched folders **persist** those
paths + **auto-read** them on launch, so the CLAUDE "before public deployment" checklist line is extended.
Audit `.claude/security-audits/2026-06-21_watched-folders.md` **PASS** (bound-param SQL, async + bounded +
content-deduped, non-destructive, additive migration, no new dependency).

## Manual verification script
1. Double-click any paper (on the title or anywhere) → it opens.
2. **+ Add ▾ → Watched folders…** → it lists the folder you scanned (with a last-scanned date). Drop a new PDF
   into that folder → relaunch (or **Re-scan all**) → the new paper appears. **Remove** a watched folder → it's
   no longer auto-scanned, but its papers stay. Settings shows the **Auto-scan watched folders on launch** toggle.
   _(Visual check delegated to the user.)_

## Pytest
**410 passed, 1 skipped** (+2 `test_watched_folders.py`: the repo add-idempotent/list/touch/remove; the
endpoint scan-registers → rescan-picks-up-new → unchanged-adds-nothing → un-watch-keeps-papers → 404. The
migration-head test now asserts `0014`; `watched_folders` added to the expected-tables set). `ruff` clean; audit
PASS. The double-click fix is frontend-only (verified manually).
