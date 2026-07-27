# Increment 398 — WIP folder-picker: universal in-app folder browser

**Date:** 2026-07-27
**Status:** Implemented and verified live (Playwright, light + dark theme); full backend test suite
green including 6 new endpoint tests; security audit PASS.

## Context

Under WIP, adding a manuscript location ("+ Add location") and relinking a moved manuscript
("Relink folder") both required pasting a raw absolute folder path into a text input. The user
wanted a folder-picker dialog instead.

callosum runs both as a plain browser tab (the primary dev/testing workflow) and as the packaged
Tauri desktop app. Only Tauri can offer a true native OS folder dialog that returns a real filesystem
path — a plain browser tab has no way to get one (the File System Access API only returns an opaque
directory handle, never a path). **Confirmed with the user**: build a universal, server-driven in-app
folder browser instead of a native-Tauri-only dialog, so the feature works identically in both
contexts without a new Tauri dependency/capability.

## Implemented

**Backend** — new read-only endpoint `GET /wip/browse-dirs?path=<optional>` added to the existing
`/wip` router (`app/backend/api/routers/wip.py`), so it automatically inherits
`dependencies=[Depends(require_local_wip)]` — no new security boundary to design. Lists a folder's
immediate subdirectories (default `Path.home()` when `path` is omitted): resolves the path, 422s on a
missing/non-directory target, skips symlinks and the existing `SKIP_DIRECTORY_NAMES` set
(`discovery.py` — the same exclusions the real recursive scan already uses), caps at 1000 entries
(`truncated: true` beyond that), and — the one deliberate design choice worth flagging — a
permission-denied read on the *requested* folder itself returns **200** with `entries: []` and an
`error` string rather than a crash, so "Up one level" always stays usable and the user is never
stranded.

**Frontend** — one new shared component, `FolderBrowserModal`
(`app/frontend/js/10j_wip_folder_browser.jsx`, ~55 lines): a themed modal (current-path readout,
scrollable subfolder list, "Up one level," "Select this folder"/"Cancel") modeled directly on
`ScanModal`'s existing chrome (`.axis-modal-overlay`/`.axis-modal-head`/`.axis-link`/`.axis-err`/
`.axis-hint`/`.axis-form-actions`/`.btn.btn-primary` — zero new classes needed for the shell). Wired
to both call sites with a one-line diff each: `WipRootSetup` (`10f_wip.jsx`) and `WipRelink`
(`10g_wip_relink.jsx`) each gained a `browsing` state flag, a "Browse…" button next to the existing
path `<input>`, and a conditional `<FolderBrowserModal onSelect={chosen => setPath(chosen)} />` —
neither component's `submit`/API-call logic changed at all. `WipRelink`'s modal defaults to the
manuscript's current (possibly-now-missing) `root_path` when the input is still empty, a small
navigation head-start specific to that flow.

**CSS**: reused `.lockout-path`'s existing mono/bordered recipe for the path readout (extended its
selector rather than retyping it), added one small new block for the scrollable folder list/rows
(neutral `--hover`/`--accent` row styling — deliberately not WIP's teal, since this modal is generic
utility chrome, not WIP-context chrome), and widened two existing grid layouts
(`.wip-root-form`/`.wip-location form`) by one column so the new button doesn't fall into an implicit
extra row.

## Key technical detail

`require_local_wip` (`app/backend/api/wip_security.py`) blocks **every** method — GET included — once
`CALLOSUM_READ_ONLY=1`/`app_settings.read_only_mode()` is set, unlike the general
`AccessControlMiddleware`'s mutating-methods-only rule. This is deliberate: the whole WIP feature area
is authoring/editing unpublished work, not meant for the read-only mobile-reading companion instance,
so even a read-only *listing* endpoint like this one is correctly blocked wholesale. Verified directly
(`test_wip_routes_deny_remote_forwarded_and_read_only_access` now asserts `/wip/browse-dirs` → 403
under read-only, not 200) rather than assumed.

## Manual verification script

1. Start the dev server; open WIP → "+ Add location" → "Browse…" — confirm the modal opens on
   `Path.home()`'s subfolders with the current path shown in mono above the list.
2. Click a subfolder to descend (path + list update); "Up one level" to return to the parent.
3. "Select this folder" — confirm the modal closes and the path input is populated with the chosen
   absolute path.
4. Cancel at any point — confirm the underlying input is untouched.
5. Toggle dark theme — confirm the modal's folder rows/path readout re-theme correctly (no
   unstyled/native chrome).
6. Zero console errors throughout. (All verified live via Playwright this increment; "Relink folder"'s
   identical wiring was reviewed but not separately live-tested, since it reuses the exact same
   component/pattern already proven working for "Add location.")

## Pytest

`pytest tests/test_wip_api.py -q` — **11 passed** (5 pre-existing + 6 new: default/explicit-path
listing + `SKIP_DIRECTORY_NAMES`/file exclusion, filesystem-root `parent: null`, symlink exclusion,
1000-entry cap + `truncated`, a monkeypatched permission-denied folder → 200/`error`/empty entries, and
missing/non-directory path → 422). Extended the existing security-gate test with one assertion
(`/wip/browse-dirs` → 403 under read-only). `pytest tests/test_frontend_assembly.py -q` — 53 passed.
Full suite before merge: `pytest -n auto -q` — **1642 passed, 1 skipped**.

## Files changed

- `app/backend/api/routers/wip.py` (new `GET /browse-dirs` endpoint + 2 Pydantic models)
- `app/frontend/js/10j_wip_folder_browser.jsx` (new — `FolderBrowserModal`)
- `app/frontend/js/10f_wip.jsx`, `app/frontend/js/10g_wip_relink.jsx` (wired "Browse…")
- `app/frontend/styles.css` (new folder-browser-list/row block; 2 grid-column widenings)
- `tests/test_wip_api.py` (6 new tests + 1 extended assertion)
- `.claude/qa-routes/route_75_wip_workspace.md` (extended: new endpoint + a browse-flow step)
- `.claude/security-audits/2026-07-27_wip-folder-browser.md` (new — PASS)
- `callosum-app.html` (rebuilt)
