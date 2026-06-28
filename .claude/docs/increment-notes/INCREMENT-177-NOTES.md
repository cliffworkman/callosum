# Increment 177 — next/prev-mark navigation (reading-pane)

Cycle through a paper's highlights in page order from the viewer toolbar — review your marks without hunting the
Notes panel. Enabled by the inc-176 headroom.

## Implemented (`app/frontend/js/30_viewer.jsx`)
- `markCursorRef` + `stepMark(dir)`: sorts `annotations` by `page` then `id`, advances a wrapping cursor, and
  `jumpToAnnotation`s the mark (scroll-into-view + flash). Uses `annotationsRef` (always fresh).
- Two toolbar buttons (shown when ≥1 highlight): **◂ Mark** / **Mark ▸** — reuse the existing `.pdf-annot-toggle`
  style (no new CSS, rule #8). 30_viewer 573 → **586** (under cap).

## Gates
- Frontend-only; no backend/migration/egress; Principles non-triggering. Surface **121/121 API + 616/616 FE, 0
  uncovered** (the 2 buttons in 30_viewer, covered by route_32). Frontend rebuilt; `test_frontend_assembly` 5/5;
  pytest **619**; no Python → ruff n/a.

## Verification
**Headed, no egress** (`.local/visual/drive_inc177_marknav.py`): Mark ▸ → a highlight flashes; again → the next;
◂ Mark → the previous; 0 console/page/genai.

## Reading-pane status
Shipped across 175–177: remembered scroll · Notes-panel extraction + noted-only filter + note/text search ·
next/prev-mark navigation. Remaining (diminishing / nuanced): fit-page (cap-risky — touches the fit-mode logic),
keyboard hotkeys for mark-nav (active-tab + input gating), free-form note colors, a scrollbar minimap.
