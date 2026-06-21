# Increment 105 — two chores: default axis cutoff in Settings + a tag source filter

The "2 chores" half of a fresh patter (carrot = the literature gap-finder, next, in its own plan-mode
increment). Both **frontend-only**, reusing already-tested endpoints/data.

## Implemented

### Chore 1 — Default axis cutoff → Settings
The per-axis assignment cutoff (inc 45, `axes.scoring_gain`; NULL → backend `DEFAULT_AXIS_CUTOFF` 0.35) can now
have a **user default** so a new/unscored axis's re-score flipper starts where you like instead of always 0.35.
- **`40_app.jsx`** — `axisCutoffDefault` state (persisted to `localStorage["callosum.axisCutoffDefault"]`, clamped
  to [0.2, 0.6], default 0.35), mirroring the inc-77 `hideUncertainDefault` pattern; threaded App → Sidebar →
  AxesPanel → AxisItem, and to `SettingsModal`.
- **`15_axes.jsx`** — `AxisItem` takes `axisCutoffDefault` (defaulted 0.35); the cutoff `useState` falls back to it
  when `axis.scoring_gain == null`. `AxesPanel` keys each card on the default (`…-c{value}`) so changing it
  re-initializes unscored cards live.
- **`35_settings.jsx`** — a "Default axis cutoff" range slider (0.20–0.60) in the **Axes** section.
- **Scope note (v1):** the default sets what the *flipper proposes*; a stored per-axis gain still wins, and an
  unscored axis's read-time tiering uses the backend 0.35 until it's actually scored (then the chosen value
  persists). No backend change.

### Chore 2 — "Show only author keywords" tag filter
Builds on the inc-100 tag-provenance work (the `/tags` response already carries `source`).
- **`10_pdf_layer.jsx`** — the sidebar `TagsPanel` gained a small **All / Yours / Keywords** segmented control
  (`src` state) that filters the list by provenance via `tagIsImported(t.source)` (composes with the existing
  text filter). It only renders when the library has **both** imported keyword tags and tags you added (otherwise
  it'd be pointless). Purely client-side — no new query/endpoint.
- **`styles.css`** — `.tags-srcfilter` / `.tags-srcfilter-btn` (token-based; accent = active) + the
  `.settings-cutoff` slider styles for Chore 1.

## Key technical detail
Both chores are pure frontend over existing data: Chore 1 mirrors the established `localStorage` settings-default
pattern (theme / hide-uncertain / auto-scan) and threads through the existing axis prop chain; Chore 2 filters the
already-fetched `/tags` list by the `source` field exposed in inc 100. No Python, no migration, no egress, no new
endpoint.

## Manual verification script (delegated)
1. **Settings → Axes → Default axis cutoff:** drag the slider; create or expand an **unscored** axis → its
   re-score "Cutoff" flipper starts at your default (a scored axis still shows its stored gain). Reload → the
   default persists.
2. **Sidebar Tags panel:** with a library that has both imported keyword tags (Crossref/Zotero) and tags you
   typed, an **All / Yours / Keywords** row appears; clicking **Keywords** shows only imported keyword tags,
   **Yours** only the ones you added; it composes with the text filter. (Hidden when the library has only one
   kind.)

## Pytest
**411 passed, 1 skipped** — unchanged (frontend-only; no Python touched). `ruff` clean; the opt-in Playwright
smoke passed (0 console errors); `callosum-app.html` rebuilt.
