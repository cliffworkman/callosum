# Increment 42 Notes — Resizable + collapsible side panels

Frontend-only UX: the left (Axes) and right (Synthesis/Detail) panels can be **drag-resized** and
**collapsed/expanded** so the user can focus on the center PDF/library area.

## What changed (`app/frontend/js/40_app.jsx` + `styles.css`; rebuilt `callosum-app.html`)
- The `.app` 3-column grid became a 5-track grid (panel · divider · center · divider · panel) whose
  side widths are React state, set via inline `gridTemplateColumns`. Center is `minmax(340px, 1fr)`, so
  it expands as a side collapses.
- New `Divider` component between each side panel and the center: a full-height **drag grip**
  (`col-resize`, clamped 180–600px left / 280–640px right) plus a centered **chevron toggle** to
  collapse/expand. A collapsed panel renders a 0-width placeholder, leaving only the 12px divider rail
  with an "expand" chevron.
- Layout is **persisted** to `localStorage` (`callosum.leftW/rightW/leftOpen/rightOpen`, guarded by
  try/catch) so the user's preferred layout sticks across reloads.
- Removed the old `@media (max-width:1100px)` auto-hide of the right pane — manual collapse supersedes it.
- No backend change, no migration, no new endpoint/egress (no security audit needed).

## Verification
- **pytest: 143** (unchanged — Python untouched).
- **Live browser E2E** (`.local/panels_e2e/`): collapse left → sidebar removed + center widens; expand →
  restored to prior width; drag grip → width increases; collapse right → right pane removed; **0 console
  errors**. (Note: the collapse chevron sits at the grip's vertical center, so drag from elsewhere on the
  tall grip — the E2E aims away from center.)

## Roadmap (next, per the user)
1. **Axis-management tree**: sortable, expand/collapse, checkbox multi-select for bulk delete/merge
   (merge needs a defined backend op).
2. **Suggest optimal axes**: unsupervised discovery + coverage-with-diversity (MMR) so suggested axes
   cover the library without redundant near-duplicates.
