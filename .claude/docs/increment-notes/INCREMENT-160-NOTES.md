# Increment 160 — the library folder is watched by default

**The bug the user hit:** a PDF dropped into the library folder (a known-retracted paper) never appeared —
even after restart + hard refresh — so the Retraction Watch flow couldn't be tested.

**Root cause (systematic-debugging):** the auto-rescan (on launch / window-focus, inc 98/136) only re-scans
**registered watched folders**, and `watched_folders` was **empty**. The 82 existing library papers were ingested
by the validation harness (attachment `import_source='pdf-scaffold'`), **not** via a UI "Scan folder" (which sets
`'library-scan'` + registers the folder) — so the library folder was never watched, and nothing picked up the
drop. (Confirmed: `library/Whitehouse et al. - 2019 - Nature.pdf` is on disk but absent from the DB; 83 on disk,
82 in DB.)

**The fix (per the user's design):** the **library folder is now watched by default** — additional folders are
user-added, and the Watched Folders modal shows the library folder as a pinned **"default · always watched"**
entry. The canonical library folder already existed: `acquisition/fetch.py::library_dir()` (`CALLOSUM_LIBRARY_DIR`
env, else the project `library/`) — where OA-acquired PDFs land.

## Implemented

- **`app/backend/acquisition/fetch.py`** — promoted `_library_dir()` → public **`library_dir()`** (renamed the
  shadowing local var in `import_oa_pdf` to avoid `UnboundLocalError`).
- **`app/backend/api/routers/library.py`**:
  - `_run_watched_rescan_job` now **always scans `library_dir()` first** (if it exists), then the user-added
    folders (skipping the library folder if a user also added it — never scanned twice). So a drop into the
    library folder is picked up on launch/focus/Re-scan-all with **no prior "Scan folder"**.
  - `GET /library/watched` **pins the library folder first** as a non-removable default
    (`id=0, is_default=True`, even with zero registered rows); a user folder equal to it is folded into the pin.
    `WatchedFolder` gained `is_default`.
  - `DELETE /library/watched/0` → **422** ("the library folder is always watched and can't be removed").
  - `_path_key()` (resolve + casefold) compares folders robustly (Windows case-insensitive).
- **`app/frontend/js/27_scan.jsx`** (+ `styles.css`) — the watched list renders the default row with an accent
  border + a **"default"** pill + "your library folder · always watched" and **no remove button**; the modal note
  explains the library folder is watched by default. (`.watched-row.is-default` + `.watched-default-note`, tokens.)
- **`tests/conftest.py`** — the autouse fixture now isolates **`CALLOSUM_LIBRARY_DIR`** to a per-test temp dir, so
  the suite never scans/writes the real project `library/` (also fixes a latent hygiene issue where OA-acquire
  tests wrote into the real `library/`).

## Notes

- **No new endpoint** (`is_default` is additive on the existing `GET`; the `DELETE 0` guard reuses the route);
  no migration; **no new external fetch/dependency**. The rescan reading `library_dir()` server-side is the same
  posture as the existing watched folders (the deployment-gate note covers it). No Principles trigger (a watched-
  folder default, not a claim/signal). No audit gate.
- **Op note:** the existing 82 library papers stay `pdf-scaffold` (harness-ingested); the rescan content-dedups by
  `file_sha256`, so re-scanning the library folder each launch just re-hashes them + skips — only genuinely new
  files (e.g. Whitehouse) are added.

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc160_library_watched.py`, `CALLOSUM_LIBRARY_DIR` = a temp folder):
+ Add ▾ → Watched folders… → the library folder shows as the pinned **default · always watched** row with **no
remove button**; dropping a PDF into that folder + **Re-scan all** → **"1 added"**. 0 console/page/genai.

**For the user's real case:** restart uvicorn (autoScanWatched on, the default) → the on-launch rescan scans
`callosum/library/` → **Whitehouse is ingested + Crossref-enriched (DOI) + retraction-auto-checked** (inc 134),
so the Retraction Watch flow can finally be exercised. (The RW *database* source also needs the contact email —
now settable in Settings → Metadata access, inc 158.)

## Pytest

**581** (+3 `test_watched_folders.py`: the pinned default present + not-removable [422]; auto-rescan picks up a
drop with no prior scan; a user-scanned library folder isn't listed twice; the existing rescan test updated for
the pin). `ruff` clean; build + assembly green; surface **110/110 API + 577/577 FE, 0 uncovered**.

## Next

Back to **#30** — SP2 beyond-library discovery (design-led; its own plan-mode session).
