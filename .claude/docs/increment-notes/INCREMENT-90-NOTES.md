# Increment 90 — Sidebar header redesign: horizontal logo + larger wordmark, buttons in the top corners

## Implemented
Reorganized the sidebar brand header (the region above the AXES panel) per the user's mockup + alignment
guides (with two follow-up tweaks they asked for after seeing it). Was a vertical stack (`?` top-left, `⚙`
top-right, then a centered logo, then a 19px "Callosum" wordmark beneath it). Now: the logo and a **36px**
"Callosum" wordmark sit **side by side on one horizontal row**, the `⚙` settings button sits in the
**top-left** corner, and the `?` help button sits in the **top-right**.

**CSS-only** — `app/frontend/styles.css` (~4 rules); the JSX (`app/frontend/js/10_pdf_layer.jsx` `Sidebar`)
already had the structure, so no JSX change:
- `.brand` — `flex-direction: column` → `row`, added `justify-content: center` + `gap: 14px` + `margin-top:
  8px` (clears the corner buttons). Logo is first in DOM → renders left; the `<h1>` renders right.
- `.brand h1` — `font-size: 19px` → `36px`, `letter-spacing: -0.01em` → `-0.02em`, added `white-space:
  nowrap`. Kept `var(--serif)` / weight 600 / `var(--ink)`.
- `.icon-gear` (settings) — moved to the **top-left** (`right: 14px` → `left: 14px`).
- `.icon-help` (help) — moved to the **top-right** (`left: 14px` → `right: 14px`).
- Refreshed the stale "logo stacked above the wordmark" comment.

Rebuilt `callosum-app.html` via `python tools/build_frontend.py`.

## Key technical detail
The whole reorg is layout-only because the two buttons are `position: absolute` (DOM order is irrelevant to
placement — corner placement is just `left`/`right` values) and `.brand` is a flex container whose axis is set
in CSS. The connection-status mechanism (inc 47 — `.brand-logo.connected` swaps to the green-dot
`--logo-*-on` variant, theme-matched) is untouched. No new tokens/hexes: the wordmark keeps the `--serif`
type role + `--ink`; the buttons keep their existing `.icon-*` recipes. Font-size (36px, after a ~10%
trim from the first-pass 40px) is the one tunable, chosen to match the mockup's proportions against the 62px
logo.

## Manual verification script
1. Hard-refresh (Ctrl+Shift+R). The header should show: the brain logo on the left, a "Callosum" wordmark to
   its right on one row, the `⚙` settings button in the top-left corner, and the `?` help button in the
   top-right.
2. Toggle dark mode (Settings ⚙) → the logo still theme-swaps; the green connection dot still shows when
   connected.
3. Drag the sidebar narrower (inc-42 grip) → confirm the lockup degrades gracefully (if it clips at a narrow
   width, dial `.brand h1` font-size down — the flagged tunable).
   _(Visual check delegated to the user — no committed browser-automation dependency.)_

## Pytest
**384 passed, 1 skipped** — unchanged (frontend-only; no Python touched; confirmed by a full background run).
No migration, no new endpoint, no egress, no audit gate.
