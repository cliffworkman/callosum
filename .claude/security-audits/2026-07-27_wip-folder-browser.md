# Security audit — WIP folder-browser endpoint

**Date:** 2026-07-27
**Status:** complete — PASS

## Scope

A new read-only endpoint, `GET /wip/browse-dirs`, added to the existing `/wip` router
(`app/backend/api/routers/wip.py`) so it inherits the router's existing `require_local_wip` gate
(loopback-only, blocked under `CALLOSUM_READ_ONLY=1`) with no new dependency wiring. It backs a new
in-app folder-browser modal (`FolderBrowserModal`, `app/frontend/js/10j_wip_folder_browser.jsx`) that
lets a user click down through subfolders and select one, replacing raw path-paste for WIP's
"Add location" and "Relink folder" controls.

This is a **read-only extension of an already-accepted local-disk-read surface**, not a new exposure
class: `POST /library/scan`, `POST /wip/watch-roots`, and `POST /wip/manuscripts/{id}/relink` already
accept an arbitrary absolute local path from the user with no containment/allowlist, a threat class
CLAUDE.md already flags under "before public deployment." This endpoint only *lists* a folder's
immediate subdirectories so the user can look before pasting — it never reads file contents, never
writes, and returns strictly less information than the three endpoints above already accept as input.

## Threat review

- **Input validation:** `path` is an optional query string, `max_length=4096`, matching the existing
  `WatchRootCreate.path`/`ManuscriptRelink.path` cap. Resolved via `Path(...).expanduser().resolve(strict=False)`;
  a resolution failure or non-directory result returns 422, never a raw exception/traceback.
- **Output encoding / injection:** the response is a typed Pydantic model (`BrowseDirsResponse`) —
  plain strings (path/name), no HTML, no template interpolation. The frontend renders entry names as
  React text content (auto-escaped), never `dangerouslySetInnerHTML`.
- **SSRF / external calls:** none — pure local filesystem read via `pathlib`, no network call of any
  kind.
- **Secret handling:** no credentials, tokens, or environment values touched.
- **Data egress:** none — this endpoint runs entirely local-to-local (browser tab or Tauri WebView to
  the same-machine uvicorn process). No library text, PDF content, or metadata leaves the machine;
  invariant #3 (egress gate) is untouched — this feature has no LLM/external-API involvement at all.
- **Resource caps:** listing is capped at `MAX_BROWSE_ENTRIES = 1000` (alphabetically-deterministic
  truncation, `truncated: true` returned) to bound response size against a folder with an enormous
  number of children. No recursion — only the immediate children of the requested folder are read
  (`Path.iterdir()`, not a walk), so there is no risk of the unbounded-depth cost `discovery.py`'s own
  recursive scan already caps separately (`MAX_SCAN_DEPTH`).
- **File-path safety:** the endpoint only *reads directory entry names* — it never opens, writes, or
  deletes a file. Symlinks are always skipped (`child.is_symlink()`) so the listing cannot be used to
  escape outside the filesystem's real directory structure via a symlink to an unexpected location.
  `SKIP_DIRECTORY_NAMES` (`.git`/`.hg`/`.svn`/`__pycache__`/`node_modules`) reuses the exact set the
  real recursive scan already excludes — no new exclusion policy invented.
- **Supply chain:** no new dependency (backend or frontend). No DB migration — this endpoint is
  stateless, touches no table.
- **Authorization boundary:** inherits `require_local_wip` from the router (`app/backend/api/wip_security.py`)
  automatically, since it's declared on the existing `router` object rather than a new one — the same
  loopback-only / read-write-instance check every other `/wip/*` endpoint already enforces. No new
  gate to design, audit, or forget.

## Negative-path checks

All verified by `tests/test_wip_api.py` (11 passed):

- [x] `GET /wip/browse-dirs` with a forwarded-header/non-loopback host → 403 (extended the existing
      `test_wip_routes_deny_remote_forwarded_and_read_only_access`).
- [x] `GET /wip/browse-dirs` under `CALLOSUM_READ_ONLY=1` → **403**, not 200. Correction from the
      original plan's assumption: `require_local_wip` (`app/backend/api/wip_security.py`) blocks
      *every* method, GET included, once `app_settings.read_only_mode()` is true — a stricter,
      WIP-specific gate than the general `AccessControlMiddleware`'s mutating-methods-only rule, since
      the whole WIP feature area is authoring/editing, not meant for the read-only mobile-reading
      companion instance. This new endpoint correctly inherits that same blanket block.
- [x] `path` pointing at a file (not a directory) → 422, no traceback
      (`test_browse_dirs_rejects_missing_or_non_directory_path`).
- [x] `path` pointing at a nonexistent location → 422, no traceback (same test).
- [x] `path` pointing at a folder the process cannot read → 200 with `error` set and `entries: []`,
      never a 500; `parent` still populated so "Up one level" remains usable
      (`test_browse_dirs_reports_unreadable_folder_without_crashing`, monkeypatched `Path.iterdir`).
- [x] A folder containing a symlinked subdirectory → the symlink is excluded from `entries`
      (`test_browse_dirs_skips_symlinks`; skips itself if the test environment can't create symlinks,
      e.g. unprivileged Windows).
- [x] A folder with 1000+ subdirectories → `entries` capped at `MAX_BROWSE_ENTRIES`, `truncated: true`
      (`test_browse_dirs_caps_entries_and_flags_truncated`).
- [x] A file (not a folder) and `SKIP_DIRECTORY_NAMES` entries (`__pycache__`) never appear in listings
      (`test_browse_dirs_lists_subfolders_and_supports_navigation`).
- [x] A filesystem root's `parent` is `None`, proven against the real OS filesystem anchor (not a
      simulated path) via `test_browse_dirs_root_has_no_parent`.
- [x] Frontend: manually verified live (see below) — Cancel at any point leaves the underlying path
      `<input>` untouched; zero console errors through the full browse→descend→select flow in both
      light and dark theme, for both "Add location" and "Relink folder."

## Result

No exploitable issue or new sensitive boundary was found. The endpoint inherits the existing
`require_local_wip` gate with no new authorization logic to review, reuses the existing
`SKIP_DIRECTORY_NAMES` exclusion set rather than inventing a new policy, and every failure mode
(missing path, unreadable folder, oversized folder) degrades to a typed response or a bounded 422 —
never an unhandled exception.

**Security Audit: PASS**
