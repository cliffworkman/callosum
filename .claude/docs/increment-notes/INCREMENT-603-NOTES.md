# Increment 603 — Axis cards → 3×2 grid (declutter the Axes pane)

Since inc 602 added the ✦ "Ask this axis" button, an ordinary axis card's action row carried **five** icon
buttons (✦ ✎ ＋ ❄ 🗑) plus the count badge on the **same line as the title**. In the narrow Axes rail the
title was squeezed into a thin sliver and wrapped to 3–4 lines with **mid-word breaks** ("Late-Life
Depressi/on Neuropat/hology"). This reflows the ordinary axis card into a 3×2 grid so the title gets its own
full-width row and the buttons drop to the row below — same elements, same colors/semantics, but legible.

## Implemented
- **`app/frontend/js/15b_axis_card.jsx` (`AxisItem`):** the `.axis-row-head` is now a 4-child grid layout —
  the count badge (`.axis-count-badge`) was moved **out of** `.axis-card-actions` to be a direct sibling (so
  it can occupy col 3 on its own); `title={axis.label}` added to `.axis-label` so a truncated title stays
  readable on hover. **My Publications is an explicit compact single-row exception** — the `.compact` modifier
  class is applied to `.axis-row-head` from the existing `isMyPubs` semantic flag (`axis.kind ===
  "my_publications"`), **never** inferred from "no checkbox" / rendered text, so a future read-only or
  no-checkbox card does not inherit the My-Pubs layout. No handler/logic/behavior change.
- **`app/frontend/styles.css`:** `.axis-row-head:not(.compact)` → `display:grid;
  grid-template-columns: 16px minmax(0,1fr) auto; grid-template-rows: auto auto`. `.axis-select` (col 1) and
  `.axis-count-badge` (col 3) span both rows (`grid-row: 1 / span 2`, `align-self:center`) — the **stable side
  columns**. `.axis-label` (col 2 row 1) wraps at word boundaries (`word-break:normal; overflow-wrap:
  break-word`) and clamps to **≤2 clean lines** then ellipsis (`-webkit-line-clamp:2`). `.axis-card-actions`
  (col 2 row 2) is **left-aligned** (`justify-content:flex-start`) so the buttons share the title's left edge.
  `.axis-row-head.compact` keeps the prior flex single-row for My Publications. **No new tokens/hex; count-badge
  scoring colors unchanged** (DESIGN.md rule #8).

## Key technical detail
The grid vs. compact split is keyed on an **explicit semantic** (`isMyPubs`), not a structural coincidence.
Grid-placement rules are scoped `:not(.compact)`, so in the compact (flex) variant the `grid-*` properties on
the children are simply inert — one component, two intentional layouts. Col 1 is a fixed 16px so ordinary
cards keep a consistent title left-edge whether or not the checkbox renders (read-only companion has none).

## Manual verification (done — Playwright, real library disposable copy, main code)
Drove the Axes pane at the default width and at the **narrowest supported rail width (`LEFT_MIN = 300px`,
`04_layout.jsx`)**:
- Ordinary axes: title on its own row, wrapping cleanly to ≤2 lines with **no mid-word breaks** (Late-Life
  Depression Neuropathology; Neural basis of moral conviction); buttons left-aligned on the row below; count
  badge right and vertically centered.
- At 300px every card's 5-button row measured **1 row, no overflow** (action column ~175px vs 104px of
  buttons) — constraint held with slack; no gap tuning needed.
- **My Publications** stayed a compact single row (✦ 🗑 + count inline), no empty checkbox column.
- Truncated titles expose the full text on hover (`title=`).

## Pytest
`tests/test_frontend_assembly.py` — 87 passed. `ruff format --check`/`ruff check` clean; line budget OK
(`15b_axis_card.jsx` 230 lines).
