# Increment 215 — PDF highlight minimap (the last close-out dreg)

The final small autonomous "dreg" the maintainer asked to clear: a scrollbar-side minimap of a paper's highlights.

## Implemented
A thin **minimap gutter** beside the PDF page-scroller showing one tick per highlight, click-to-jump.
- New `MinimapTrack({ annotations, numPages, onJump })` component in `app/frontend/js/30_viewer.jsx` (module-level,
  hoisted in the shared IIFE): renders a `.pdf-minimap` track with a `.pdf-minimap-tick` per annotation, positioned
  by **page fraction** (`top = ((page-1+0.5)/numPages)%`, clamped) and tinted by the highlight's `color` (fallback
  `--flag`); each tick's title is the page + note snippet; clicking calls `onJump(annotation)` =
  `jumpToAnnotation` (scrolls to + flashes the highlight, the inc-177 path).
- Rendered in `.pdf-body` (a flex row) as a flex sibling of `.pdf-scroll`, shown when
  `state.status === "ready" && annotations.length > 0 && !panelOpen` — i.e. **only when the Notes panel is closed**
  (the panel already lists + jumps, so the minimap is its compact alternative).
- `styles.css`: `.pdf-minimap` (`flex: 0 0 14px`; `--panel-2`; `--line` left border) + `.pdf-minimap-tick`
  (absolute, `top: %`, `var(--radius-sm)`, `--accent` hover outline) — tokens only (rule #8; DESIGN.md updated).

## Key technical detail
Ticks are positioned by **page number / `numPages`**, never by pixel offset — so the minimap is decoupled from the
fragile per-page render geometry (the inc-34/35 canvas/text-layer alignment invariants). The equal-page-height
approximation is honest for a navigation aid ("jump to the highlight on page N"); the actual jump uses the real
`[data-page=N]` scroll, so landing is exact. **No split was needed** — `30_viewer.jsx` was at **557** (inc-182's
LibraryFrame extraction relieved it; the CLAUDE rule-#1 "599/600 MAXED" note was stale); the minimap took it to
**580**, still under the cap.

## Manual verification script
`python .local/visual/drive_inc215_minimap.py` (headed, no egress): seeds a 4-page PDF + 2 highlights (p.1, p.4) →
double-click the paper → the viewer renders → **2 `.pdf-minimap-tick`s**; click the lower tick → the p.4 highlight
flashes; open **Notes** → the minimap hides. 0 console/page/genai.

## Pytest
**748 passed, 1 skipped** (unchanged — frontend-only; `test_frontend_assembly` confirms the rebuilt
`callosum-app.html` is in sync; CI re-runs the full suite). ruff n/a (no Python). `30_viewer.jsx` 580.

## Gates
No backend / endpoint / migration / egress / dependency change → no audit-gate trigger; Principles non-triggering
(a navigation overlay, no claim/signal; coordinate-honest — page-level, the real jump uses the page anchor). QA:
`route_32_viewer_annotations.md` extended with the minimap step; surface **145/145 API + 687/687 FE, 0 uncovered**
(+2 FE = the minimap track + tick, claimed by route_32 via `30_viewer.jsx`). DESIGN.md gained the minimap recipe.
help corpus: the Highlights section is general; the minimap is a self-evident, discoverable affordance — no change.

## NEXT
The autonomous close-out band is now **empty** (A1–A10 closed incs 203–212; the dregs #4/#5/minimap cleared incs
214–215). The remaining backlog is **design-gated B-items** — B1 SP2 (gated agent writes), B2 collaboration, B3 OCR,
B4 citation-context classifier, B5 mobile — each its own brainstorm + the maintainer's pick.
