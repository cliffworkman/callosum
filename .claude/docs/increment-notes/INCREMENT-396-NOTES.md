# Increment 396 — Post-install feedback: scrollbars, stale Library/WIP cards, desktop icon

**Date:** 2026-07-27
**Status:** All three fixes implemented and verified — against the live dev server (Playwright) and
against a real rebuilt Windows Tauri package (the actual `callosum-shell.exe`, launched directly and
screenshotted).

## Context

Cliff launched the packaged Windows build for real (following incs 394–395) and reported three
issues from actual use, not a code read:

1. Chromium/WebView2 showed fat, unstyled default scrollbars, unlike Firefox's own subtle
   auto-hiding ones (invisible at rest, a hint on hovering the panel, full color on hovering the
   thumb) — wanted the same behavior reproduced cross-browser, theme-aware.
2. **Critical**: editing a paper's details (or a WIP manuscript's structure/tasks/references/
   checks) didn't update the corresponding card in the Library/WIP list; newly-ingested papers
   didn't appear either — both needed a manual page refresh, which isn't discoverable in the
   installed desktop app (no visible reload UI, and most users won't realize it's a website in a
   window that a right-click can refresh).
3. The desktop app's window/taskbar icon was still Tauri's default logo, which would confuse end
   users — wanted `.claude/media/logo_dm.png` (the transparent, "dark-mode" line-art treatment of
   callosum's brain/neuron mark, chosen over the plain `logo.png` because it should "pop more").

## Implemented

**Fix 1 — stale Library/WIP cards (the critical one).**
- `app/frontend/js/40_app.jsx`: added `onLibraryChanged: () => setLibRefresh(n => n + 1)` to
  `paneCtx`, next to the existing `onQueueChanged` — the same refresh-counter idiom already used
  for axis/tag/queue reactivity, just never wired to the Detail pane.
- `app/frontend/js/05_panes.jsx`: the "details" section's `render(ctx)` now passes
  `onLibraryChanged={ctx.onLibraryChanged}` into `DetailContent`.
- `app/frontend/js/25_detail.jsx`: `DetailContent` calls the new `onLibraryChanged` in the success
  branch of every mutation that changes what a paper's own Library card shows — `saveField`,
  `reresolve`, `fillMetadata`, `reprocessPdf`, `onAcquired`.
- `app/frontend/js/10f_wip.jsx`: `WipDetails`' internal `reload()` (used by the Structure/Tasks/
  References/Checks tabs and the file role/primary toggles) only bumped its own local `nonce` —
  never the outer WIP browser's card-list refresh (`onRelinked`, already wired to `wip.reload` for
  the overview form's `save()` and `WipRelink`). Now calls both: `setNonce(v => v + 1); if
  (onRelinked) onRelinked();` — every existing `onReload={reload}` call site inherits the fix.
- **New-paper ingest pagination gap**: the `setLibRefresh` wiring on every ingest path (Import/
  Scan/Bundle-import modals, Discover→Feed save) was already correct — a refetch does happen. The
  real gap: none of them also reset pagination. The default library sort ("added", ascending —
  `papers.c.id.asc()` in `persistence/paper_query_repo.py`, oldest-first/import order) puts a
  newly-added paper at the *tail* of the list, which lands on whatever the last page is, not
  page 1 — so on a library with enough papers to paginate, a fresh import can refresh silently
  off-screen, indistinguishable from nothing happening. Confirmed via the backend's own sort-order
  code (deterministic, no live repro needed) rather than the earlier hypothesis of a broken
  refresh callback. Fixed by calling `libraryBits.onPage(0)` (the same `setPage` already exposed
  for `LibraryFrame`'s pagination control) alongside `setLibRefresh` on `ScanModal.onScanned`,
  `ImportModal.onImported`, `BundleImportModal.onImported`, and `onDiscoverSaved` in
  `app/frontend/js/40_app.jsx` — mirroring the identical `setPage(0)` pattern every filter-change
  action in `03_library.jsx` already uses (`onSearchFieldChange`, `onItemTypeChange`,
  `onToggleMissingPdf`, `changeSort`).

**Fix 2 — cross-browser scrollbar styling.** New block in `app/frontend/styles.css` (recorded in
`.claude/DESIGN.md`'s "Scrollbars" recipe): standard `scrollbar-width`/`scrollbar-color`
properties for Firefox (and modern Chromium, which now also honors them) plus the
`::-webkit-scrollbar` pseudo-element family for older Chromium/WebView2. Thumb-at-rest → `--line-2`
(control-border weight); thumb-on-hover → `--ink-3` — never `--accent` (indigo stays
provenance/primary-only per DESIGN.md §4). Both tokens already flip light/dark through the
existing `:root`/`:root[data-theme="dark"]` mechanism.

**The bug found mid-verification:** the first version set the rest-state on `html` alone.
`scrollbar-color` is an *inherited* property, and `:hover` matches every ancestor of the actual
hover point (a child's box sits inside every ancestor's box), so `html:hover` is true almost
continuously — the pointer is always somewhere inside `html`'s box while the page is in view. That
meant `html`'s `:hover` reveal color inherited down through *every* descendant unconditionally,
regardless of which panel was actually under the pointer — every scrollbar everywhere showed the
hover-hint permanently, confirmed by two Playwright screenshots (page load vs. hovering an
unrelated heading) that looked identical. **Fix:** set the rest-state on `*` (universal) instead of
`html`, so every element gets its own explicit value and nothing depends on inheriting through the
always-hovering root; `*:hover` then only wins for the element the pointer is actually within (or a
descendant of).

**Fix 3 — desktop app icon.** `app/desktop-shell/packaging/logo_squared_1024.png` (new): a
1024×1024 RGBA transparent-canvas version of `.claude/media/logo_dm.png` (confirmed genuinely
transparent, not white, via pixel sampling — this determined the dm-vs-plain choice per Cliff's own
stated rule), centered with ~8% margin. `npx tauri icon packaging/logo_squared_1024.png` (run from
`app/desktop-shell`) regenerated the full `src-tauri/icons/` set (`32x32.png` through `icon.ico`/
`icon.icns`, the Windows `Square*.png`/`StoreLogo.png` tiles) from this source, replacing the
default Tauri logo everywhere `tauri.conf.json` already referenced it. The tool's own
auto-generated `android/`/`ios/` subdirectories were deleted (rule #5 — this project is
desktop-only, no mobile target).

## Key technical detail

The scrollbar bug is a general CSS lesson worth restating precisely: **an inherited property's
`:hover`-conditioned value is only safely scoped to "the element under the pointer" if the base
(non-hover) value is also set directly on every element that could receive it** — otherwise the
`:hover` reveal on a shared ancestor (which, for `html`/`body`, is essentially always true) wins
by inheritance on every descendant that doesn't have its own explicit override. This is why the fix
is `* { scrollbar-color: transparent transparent; }` rather than scoping the reveal itself to a
hand-enumerated list of scrollable container classes (which was considered and rejected — high
footprint, easy to miss a class, and contrary to the original "no per-surface differentiation"
design intent); giving every element its own explicit rest-state value is the one-rule fix that
preserves that intent while being correct.

## Manual verification script

1. Start the dev server (`uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8888`) against
   the real testing DB; open `http://127.0.0.1:8888/`.
2. **Stale-card fix:** open a paper's Detail pane, edit the Journal field, save — confirm the
   Library card updates immediately with no reload. Open a WIP manuscript's Tasks tab, add a task —
   confirm the WIP browser card's "N open tasks" count updates immediately. (Both verified live via
   Playwright this increment; test edits reverted afterward.)
3. **Scrollbar fix:** hover a paper row in the Library list — confirm only the Library pane's own
   scrollbar (not the Axes sidebar's, not the Detail pane's) shows the hint color. Toggle
   light/dark theme — confirm the thumb color changes. (Verified via `getComputedStyle` inspection
   of `scrollbar-color` on the hovered element's full ancestor chain vs. its siblings, plus a
   direct `--line-2` light/dark value check — more precise than a screenshot comparison for
   confirming CSS scoping.)
4. **Icon fix:** rebuild the Windows installer (`python app/desktop-shell/packaging/
   stage_source.py` then `npx tauri build` from `app/desktop-shell`), install, and check the
   taskbar/title-bar icon shows the callosum brain/neuron mark, not the Tauri default. **Done**:
   rebuilt (release build, ~10 min compile), launched the real `target/release/callosum-shell.exe`
   directly (no full system install needed — its `bundle.resources` land alongside the exe in
   `target/release/` too), confirmed via screenshot that both the window title-bar icon and the
   Windows taskbar running-instance icon show the new brain/neuron mark, and confirmed the real app
   loads its persisted per-user library (`%APPDATA%\com.callosum.desktop\callosum.sqlite`, from
   earlier inc-394/395 testing) end-to-end through the same rebuilt frontend. Killing the process
   left no orphaned bundled-Python child (the Job Object cleanup held) — confirmed via
   `Get-CimInstance Win32_Process` before/after.

## Pytest

`pytest tests/test_frontend_assembly.py -q` — 53 passed (targeted, during dev). Full suite before
merge: `pytest -n auto -q` — **1636 passed, 1 skipped** (no backend logic changed this increment;
all edits are frontend JSX/CSS + the desktop-shell icon assets, so the full-suite green is a
regression check, not new coverage).

## Files changed

- `app/frontend/js/{40_app.jsx,05_panes.jsx,25_detail.jsx,10f_wip.jsx}`
- `app/frontend/styles.css`
- `.claude/DESIGN.md` (new "Scrollbars" recipe + the inheritance-leak gotcha)
- `app/desktop-shell/packaging/logo_squared_1024.png` (new)
- `app/desktop-shell/src-tauri/icons/*` (regenerated)
- `callosum-app.html` (rebuilt)
