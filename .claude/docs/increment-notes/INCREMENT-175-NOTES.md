# Increment 175 — remembered scroll position per paper (reading-pane follow-up)

A Close-reader-pass follow-up (backlog §AUTONOMOUS reading-pane list): reopening a PDF now **resumes where you
left off** instead of snapping to the top. "Follow your heart" pick — the highest daily quality-of-life reading
win that doesn't fight the browser (unlike keyboard-zoom hijacking Ctrl+±).

## Implemented (`app/frontend/js/30_viewer.jsx`, `00_lib.jsx`)
- **Save:** `PdfViewer.onScroll` persists the scroller's `scrollTop` to `localStorage["callosum.pdfScroll.<paperId>"]`,
  throttled to ≤1 write / 500ms (`lastScrollSaveRef`). `onScroll` now closes over `paperId`.
- **Restore:** in the render effect's post-render block, **once per paper-open** (`restoredPaperRef`), the saved
  position is reapplied — *unless* a citation/annotation **`target`** is driving the scroll (the target wins), and
  **never on a later zoom re-render** of the same paper (the guard keys on `paperId`). Restore runs after all pages
  render, so `scrollHeight` is final and `scrollTop` lands correctly.
- **Rule-#1 headroom:** `30_viewer.jsx` was at 595/600. Relocated the **pure** `buildAnnotationDigest` (the
  inc-144 highlights/notes digest) to `00_lib.jsx` (its proper home — a pure util; `copyDigest`/`exportDigest` still
  call it via the shared IIFE scope). Net: 30_viewer back to **595** (under cap) with the feature added.

## Key detail / why this shape
The PDF viewer is the app's most fragile file (the inc-34/35 alignment invariants) — so this **does not
restructure the render core**: it relocates one pure string-builder + adds a throttled save + a guarded restore.
Scroll position is stored in **px** (not a fraction) — fine because `scale` defaults to 1.15 and `pageView` is
restored from localStorage, so the zoom is consistent across opens; an over-large saved value just clamps.

## Gates
- Frontend-only; no backend/endpoint/migration/egress → no audit; Principles non-triggering (a convenience).
- **QA (rule #10):** no new surface → 121/121 API + 608/608 FE, 0 uncovered.
- Frontend rebuilt; `test_frontend_assembly` 5/5; pytest **619** unchanged.

## Verification
**Headed, no egress** (`.local/visual/drive_inc175_scroll.py`): a tall 4-page PDF → scroll to 600 → saved 600 in
localStorage → **reload (new session) + reopen → scrollTop restored to 600**; PDF renders post-refactor; 0
console/page/genai. (The reload-then-reopen path is the real cross-session use case.)

## Remaining reading-pane follow-ups (need the bigger split / a decision)
keyboard zoom (Ctrl+± conflicts with browser zoom — a UX call); next/prev-mark hotkeys; a noted-only filter +
note-text search in the Notes panel; free-form note colors; a minimap highlight marker. `30_viewer.jsx` is again
near the cap (595) — **a real Notes-panel extraction is the proper next headroom move** before more viewer features.
