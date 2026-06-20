# Increment 57 Notes — Always-on Synthesis + contextual Details split (backlog F)

The right pane was **tabbed** (Synthesis | Detail) — you clicked "Detail" to see/edit a paper's metadata,
and switching away hid the synthesis. **F** makes it a research workspace: **Synthesis stays on top
always**, and selecting a paper slides its (editable, inc-49) **Details into a lower section** — no
tab-switching, no lost context.

## Implemented (`app/frontend/js/20_synthesis.jsx` `RightPane` + `styles.css`; `40_app.jsx` 1-line)
- `RightPane` is now a **vertical flex column** (`.pane-split`: `flex-direction:column; overflow:hidden`
  over the existing `height:100vh`): a top `.rp-synth` (`flex:1; overflow:auto`) holding the "Synthesis"
  eyebrow + `<SynthesisPane>` (unchanged), and — **only when `paperId != null`** — a `.divider-h` drag
  grip + a bottom `.rp-detail` (`flex:none; height:{detailH}px; overflow:auto`) with a compact "Detail"
  eyebrow + `<DetailContent>` (unchanged). With nothing selected, Synthesis fills the pane and the Details
  section isn't even mounted.
- **Draggable split** reusing the inc-42 resizer: `detailH` state seeded from + persisted to
  `localStorage["callosum.detailH"]` (default 300, clamp [180, 760]); the grip's drag → `_clampW(startH -
  (y - startY), …)` (drag up → Details grows). Each section scrolls independently, so deep metadata editing
  still works (drag the divider up for more room).
- The tabs (`tab` state + `.pane-tabs` JSX **and** the now-dead `.pane-tabs` CSS) are removed (rule #5).
- `RightPane`'s props + its mount in `40_app.jsx` are unchanged.

## Key technical detail
The inc-42 `_beginDrag(e, onMove)` hard-coded `onMove(ev.clientX)` (horizontal side panels only). It now
passes **both** axes — `onMove(ev.clientX, ev.clientY)` — so the existing horizontal callers (which take
`(x) => …`) are unaffected, and the new vertical split takes the `y`. The helpers
(`_beginDrag`/`_clampW`/`_loadLayout`/`_saveLayout`) are hoisted top-level functions, so `RightPane`
(an earlier chunk) can call them across the concatenated script.

## Manual verification script
1. Rebuild (`python tools/build_frontend.py`), restart uvicorn, hard-reload.
2. With nothing selected, the right pane shows **Synthesis** full-height (no tabs). Click a library paper
   → its **Details** appear below the synthesis automatically; the synthesis input stays visible. Drag the
   thin divider between them to resize; reload → the split height is remembered. Confirm the left/right
   side-panel resizers still work (the shared drag helper change is backward-compatible).

## Verification
- **pytest: 199** (unchanged — frontend-only).
- **Live E2E** (`.local/synthesis_split_e2e/`): no selection → Synthesis only (no `.pane-tabs`,
  no `.rp-detail`); select a paper → `.rp-synth` **and** `.rp-detail` (with `.detail-title-input`) both
  visible + the synthesis input present; drag the divider → Details grows (300→394px) + persists; survives
  a reload; **0 console errors**. Screenshot captured.
- No audit gate (frontend-only). `20_synthesis.jsx` 311 (< 600).

## Backlog
Done: **F** (always-on Synthesis + contextual Details). Next: library **merge** (last, destructive —
needs design decisions); terms-as-first-class; DESIGN.md `.btn-*` DRY; embedding-text JATS cleanup;
permanent-delete/empty-trash; persistent dedup-dismiss.
