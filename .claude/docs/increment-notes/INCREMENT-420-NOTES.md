# Increment 420 — relocate "Check for updates" into Account & sync

## Implemented

A small Settings reorganization, at Cliff's request: "Check for updates" (inc 417) no longer lives in its
own standalone "Desktop app" card at the bottom of Settings. It now lives as a subsection nested inside
"Account & sync," positioned right after the existing "Appearance" subsection — matching the pattern already
used by "My Publications" and "Appearance" (a `settings-subsection` div with an `eyebrow`-classed label).

`app/frontend/js/35_settings.jsx`:
- `DesktopUpdateSettings`'s returned JSX gained its own `<p className="eyebrow">Desktop app</p>` label and
  switched its wrapper from `settings-section` to `settings-subsection`, matching its new siblings. Internal
  logic (the `!("__TAURI__" in window)` early-return, the `check()` handler, the live-vs-one-shot `statusText`
  derivation) is completely untouched.
- The standalone `<SettingsCard title="Desktop app">...</SettingsCard>` block at the end of `SettingsView` is
  gone; `<DesktopUpdateSettings desktopUpdate={desktopUpdate} />` now renders inside "Account & sync"'s second
  `settings-section` column, right after the Appearance subsection.
- Net effect outside the desktop shell (a plain browser/dev-server): unchanged — `DesktopUpdateSettings`
  already returned `null` there, so there's still no orphaned "Desktop app" label with nothing under it.

## Housekeeping

- `tests/test_frontend_assembly.py`'s `test_desktop_update_progress_surfaces_in_status_popover_and_settings`
  updated: asserts the old standalone-card string is now **absent**, and the new
  `<DesktopUpdateSettings desktopUpdate={desktopUpdate} />` call site is present — a real regression guard
  for the new placement, not just a removed assertion.
- `python tools/build_frontend.py` re-run; `check_line_budget.py` clean.
- No security audit triggered — pure UI relocation, no new surface, no behavior change to what the control
  does, only where it's shown.

## Manual verification

Confirmed via the assembled frontend source: Settings → Account & sync now shows Appearance's Dark-mode
toggle immediately followed by a "Desktop app" eyebrow + the Check-for-updates button (desktop-shell only —
a plain browser render correctly shows nothing there, same as before).

## Pytest / build gates

- `pytest tests/test_frontend_assembly.py -q` → **57 passed**.
- Full suite: `pytest -n auto -q` → **1712 passed, 1 skipped** — unchanged count from before this increment
  (a pure assertion update, no tests added or removed), zero failures.
