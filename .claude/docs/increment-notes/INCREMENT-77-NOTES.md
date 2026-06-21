# Increment 77 — Hide uncertain axis papers by default (a Settings option)

## Implemented
A backlog quick-win: the inc-51 per-axis **👁 hide-uncertain** view can now be the **default** via a Settings
toggle, so axis cards start in the assigned/manual-only view and surface uncertain papers only on demand.

- `app/frontend/js/35_settings.jsx` — a new **Axes → "Hide uncertain papers by default"** toggle row (mirrors
  the Appearance/Dark-mode switch), with a sub-label explaining it.
- `app/frontend/js/40_app.jsx` — `hideUncertainDefault` state persisted to `localStorage["callosum.hideUncertainDefault"]`
  (mirrors the `theme` pattern: `_loadLayout`/`_saveLayout`); passed to `SettingsModal` (toggle) and down to the
  sidebar.
- Threaded App → `Sidebar` (`10_pdf_layer.jsx`) → `AxesPanel` (`15_axes.jsx`) → `AxisItem`.
- `15_axes.jsx` — `AxisItem`'s `hideUncertain` state now **initializes from `hideUncertainDefault`** (was
  hardcoded `false`); `AxesPanel` includes the default in each `AxisItem` **key** (`axis.id + "-h"/"-s"`) so
  flipping the Settings toggle **remounts** the axis cards and they pick up the new default live. The per-axis
  👁 still overrides for that axis until the next remount.
- `styles.css` — a small `.settings-sub` rule (the toggle's explanatory sub-line).
- Rebuilt `callosum-app.html`.

## Key technical detail
The default is a starting value, not a binding: `AxisItem` reads it as initial `useState`, and the per-axis 👁
remains a local override. To make a Settings change apply **immediately** to already-rendered axes (React
`useState` initializers don't re-run on prop change), `AxesPanel` keys each `AxisItem` on the default — flipping
it changes every key → the cards remount → re-init from the new default. Local per-axis overrides reset on that
remount, which is the right semantics for changing a *global default*.

## Manual verification script
1. Hard-refresh the app (Ctrl+Shift+R) to load the rebuilt frontend.
2. Settings (⚙) → **Axes → Hide uncertain papers by default** → toggle **on**.
3. Confirm expanded axis cards now show only assigned/manual papers, with the "N uncertain hidden — show" hint;
   the per-axis 👁 still toggles an individual axis; the choice persists across reload.
   _(Visual check delegated to the user — no in-repo browser automation this session.)_

## Pytest
**347 passed, 1 skipped** — unchanged (frontend-only; no Python touched). `ruff` not applicable to JSX. No
migration, no endpoint, no egress. Backlog item "Hide uncertain axis papers BY DEFAULT" → done.
