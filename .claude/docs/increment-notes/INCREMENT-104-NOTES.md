# Increment 104 — Panel min-widths + Spotify pull-to-collapse + sidebar-button reposition

Three small layout tweaks the user requested, all in `app/frontend/`.

## Implemented
- **`js/40_app.jsx` — side-panel min widths + pull-to-collapse**
  - New module constants: `LEFT_MIN=300, LEFT_MAX=600, LEFT_COLLAPSE_AT=220` and
    `RIGHT_MIN=415, RIGHT_MAX=640, RIGHT_COLLAPSE_AT=335` (collapse threshold = min − 80).
  - `leftW`/`rightW` init now clamps the persisted value up to the new min (`Math.max(MIN, stored || MIN)`), so an
    old saved width (or the prior 270/400 defaults) can't load below the min.
  - Both divider `onDragStart` handlers compute the unclamped `proposed` width and: if it drops below
    `COLLAPSE_AT` → `setLeftOpen/​setRightOpen(false)` (auto-collapse); otherwise keep the panel open and
    `setW(_clampW(proposed, MIN, MAX))`. (Left widens as the divider moves right: `sw + (x-sx)`; right widens as it
    moves left: `sw - (x-sx)`.)
- **`styles.css` — reposition the two sidebar-header buttons** (position-only; rule #8 — no token/color change):
  - `.icon-help`: `top:12px → 19px` (down 7), `right:14px → 33px` (left 4, then both nudged left 15px).
  - `.icon-gear`: `top:12px → 19px` (same Y as help), `left:14px` → `right:60px` (27px left of help). The two
    buttons are now a right-aligned pair; the top-left corner is vacated.
  - Both buttons now carry an **always-on outline** — base `border` changed `transparent` → `currentColor` (so the
    resting outline is the icon's own `--ink-3` color); the hover rules are untouched (`--line-2` border +
    `--accent` text + `--panel` bg), so the mouseover look is preserved.

## Key technical detail
`_beginDrag` registers **document-level** mousemove/mouseup listeners, so a drag keeps running even after the panel
collapses mid-drag (the divider's grip element unmounting doesn't end the drag). This makes the Spotify feel work:
the panel **sticks at its min** while `proposed` is between the threshold and the min (the clamp floors it), then
**snaps collapsed** once `proposed` crosses the threshold — and within the *same* continuous drag the user can
pull back past the threshold to re-expand. Re-expanding from a *released* collapsed state uses the existing
collapse chevron (the collapsed divider shows no grip; drag-to-reopen-from-collapsed was out of scope). The
auto-collapse persists like a chevron collapse (`leftOpen`/`rightOpen` are saved); `leftW`/`rightW` stay ≥ min.

## Manual verification script (delegated)
1. Drag the left (AXES) resizer leftward → it sticks at 300px, then snaps the panel closed once pulled well past
   (~80px). The collapse chevron re-expands it to ≥300px. Same for the right (Synthesis/Details) at 415px.
2. The two header buttons: help sits 7px lower / 4px left of where it was; settings sits at the same height, 30px
   to the left of help (right-aligned pair). The top-left corner is empty.

## Pytest
**411 passed, 1 skipped** — unchanged (frontend-only; no Python touched). `ruff` clean; the opt-in Playwright smoke
(incl. the reading-mode panel test) passed with 0 console errors; `callosum-app.html` rebuilt.

**Tunables (single-line):** the two `*_COLLAPSE_AT` thresholds (how far past the min before it snaps shut) and the
two button offsets, if the visual wants a nudge.
