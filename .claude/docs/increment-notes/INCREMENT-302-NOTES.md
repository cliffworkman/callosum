# Increment 302 Notes — Mobile workspace switcher

Date: 2026-07-18

## Backlog Pick
- Picked the top autonomous backlog item: **Workspaces nav mobile treatment**.
- Verified it was still open: mobile already had the B5 bottom region nav, but `MenuBar` still rendered as the desktop horizontal workspace tab strip inside the center region.
- Marked the item closed in `INCREMENT-BACKLOG.md` and added the DONE breadcrumb.

## What Changed
- `MenuBar` now accepts the existing `mobile` flag.
- Desktop behavior is unchanged: primary workspaces render as tab buttons and Help/Settings render as right-aligned utilities.
- Mobile behavior now renders a compact **Workspace** `<select>`:
  - Workspaces: My Publications, Library, Synthesize, Discover, Work, Extract.
  - Utilities: Help, Settings.
- The bottom mobile nav remains separate: **Library / Panels / Details** chooses the visible region, not the active workspace.
- Updated help, DESIGN, QA routes, frontend assembly tests, and the opt-in e2e smoke.

## Design Notes
- Reuses the existing `.menubar` container and `.lib-sort` select recipe.
- Uses only existing tokens; no new color or typography semantics.
- Read-only filtering still flows through `workspaces(readOnly)`, so mobile sees the same allowed workspace set as desktop.

## Security
- Added `.claude/security-audits/2026-07-18_mobile-workspace-switcher.md`.
- Result: PASS. Frontend-only, no new endpoint, egress, file path, dependency, or user-input HTML path.

## Experience Pass
- Persona: returning user on a phone-width screen trying to re-find moved tools.
- Finding: the desktop tab strip is too wide/noisy in the single-column layout and competes conceptually with the bottom region nav.
- Fix: the compact **Workspace** dropdown makes "what am I doing?" distinct from **Library / Panels / Details** ("which region am I viewing?").

## Verification
- `python tools/build_frontend.py` — passed; rebuilt `callosum-app.html`.
- `pytest tests/test_frontend_assembly.py tests/test_help.py -q` — 48 passed.
- `CALLOSUM_RUN_E2E=1 pytest tests/e2e/test_smoke.py -q` — 3 passed.
- `ruff check .` — passed.
- `ruff format --check .` — passed after formatting the two edited test files.
- `python tools/check_line_budget.py` — passed.
- `python tools/qa/build_surface_map.py check` — 248 API / 1157 FE, 0 uncovered.
- `pytest -n auto -q` — 1264 passed, 1 skipped.

## Manual QA To Eyeball
- At mobile width, confirm the **Workspace** dropdown is usable with real content and does not overlap the read-only badge.
- Confirm desktop still shows the horizontal menu bar and Help/Settings at the right.

## Revert
Restore the files listed in `.claude/changes.md` for increment 302 and rebuild `callosum-app.html`.
