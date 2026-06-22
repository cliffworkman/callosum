# Increment 110 — PDF viewer page-view options (fit-width / two-up) — backlog item 2

## Implemented
The PDF viewer (`app/frontend/js/30_viewer.jsx`) gains two page-view modes alongside the existing manual zoom:
- **Fit width** — auto-scales so one page fills the scroller's width.
- **Two-up** — pages render two-per-row, each auto-fit to ~half the width.

The mode is a `pageView` state (`"page"` = manual zoom, the default + prior behavior | `"width"` | `"two"`),
**persisted** to `localStorage["callosum.pageView"]` via the existing `_loadLayout`/`_saveLayout` helpers (same as
the other view prefs). Two toolbar buttons reuse the **`.pdf-annot-toggle`** recipe (no new tokens): "Fit width"
and "Two-up", each a toggle (click again → back to manual). Pressing the **+/− zoom** buttons drops back to manual
mode (zooming exits fit). CSS: one new layout rule `.pdf-pages.pdf-two-up { flex-direction: row; flex-wrap: wrap;
… }` (styles.css) — pages wrap two per row; gap/padding inherited.

## Key technical detail
Fit modes only **choose the `scale` value** and then feed the **same single-scale render pipeline** — so the
inc-34 alignment invariant (canvas / text layer / overlays all derive from one `getViewport({scale})`) is
**untouched**. Page-1's unscaled width is captured at doc-load (`baseWidthRef = doc.getPage(1).getViewport({scale:1}).width`);
a `ResizeObserver` on the scroll container recomputes `scale = floor((clientWidth − padding − gaps) / (cols ×
baseWidth))` (cols = 2 for two-up) and `setScale`s, which re-runs the existing per-page render effect. `floor` (not
round) keeps two pages from overflowing the row by a rounding hair. Manual mode installs no observer (fixed scale).
`clientWidth` already excludes the scrollbar, so the fit settles in ≤2 recompute passes once the scrollbar appears.

## Manual verification script (NOT run — no browser in this session; do this to confirm)
1. `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080`; open `http://127.0.0.1:8080/`; open a paper with
   a local PDF (double-click a library card).
2. **Fit width:** click "Fit width" in the PDF toolbar → the page should grow/shrink so its width fills the pane;
   the button shows active (accent). Resize the window / drag the right divider → the page re-fits live. The
   zoom % updates to the fit value.
3. **Two-up:** click "Two-up" → pages should lay out **two side-by-side per row**, each fit to half the width;
   resize → re-fits, still two per row (never 1 or 3). Button active; "Fit width" inactive (mutually exclusive).
4. **Manual:** click **+** or **−** → mode returns to manual (both toggles inactive), scale steps by 0.2; the
   value persists only within session as before.
5. **Persistence:** set "Fit width" (or "Two-up"), reload the page, reopen a PDF → the mode is remembered
   (`localStorage["callosum.pageView"]`).
6. **Honesty/alignment (inc-34) regression:** in each mode, select text and add a highlight → the highlight rect
   must still land exactly on the text; a citation jump must still align. (Fit only changes the scale value, so
   this should hold — confirm.)

## Pytest
424 passing, 1 skipped (no change — JSX/CSS only; `test_frontend_assembly.py` confirms the bundle assembles +
transpiles + `callosum-app.html` is in sync). `node --check` on the rebuilt bundle: OK (0 leftover JSX). ruff
clean (no Python touched). **Visual click-through (steps 2–6) is the one check a headless session can't run —
flagged for Cliff.**
