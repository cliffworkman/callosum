# Increment 34 Notes

Fix PDF text-layer ↔ canvas misalignment (scale/DPR sync) and harden zoom. Frontend-only
(`callosum-app.html`); no backend/schema change.

## Root cause (confirmed)

Three independent desyncs between the canvas and the PDF.js text layer:
1. **Floor truncation:** `canvas.width/height` and the text-layer container were `Math.floor`-ed,
   but the canvas rendered with the *un-floored* viewport and the text layer positioned spans in
   un-floored coords scaled by `--scale-factor` → a sub-pixel-per-line discrepancy that accumulates
   linearly down the page.
2. **Responsive shrink (the dominant visible bug):** `.pdf-page-wrap{max-width:100%}` +
   `.pdf-page{width:100%}` let the canvas shrink to fit a narrow pane, while the text layer was a
   fixed `floor(viewport.width)px` → the two desync by the shrink ratio, worse toward the bottom-right.
3. **No `devicePixelRatio`:** the backing store wasn't device-resolution, so HiDPI / browser zoom
   rendered blurry and could desync.

## Fix — single-source the scale; one viewport, identical CSS boxes, DPR-aware

In the page-render block, every layer for a page derives from one `getViewport({ scale })` with the
**exact, un-floored** CSS dimensions (`cssW = viewport.width`, `cssH = viewport.height`):
- **Canvas:** backing store at device resolution — `canvas.width = round(cssW*dpr)`,
  `canvas.height = round(cssH*dpr)`, rendered with `transform: [dpr,0,0,dpr,0,0]`; CSS box set to the
  exact `cssW×cssH` via `style`.
- **Text layer + page wrapper + overlay layers:** sized to the same exact `cssW×cssH`;
  `--scale-factor = scale`. All boxes pixel-identical.
- `dpr = window.devicePixelRatio || 1`.
- **CSS:** removed `.pdf-page-wrap{max-width:100%}` and `.pdf-page{width:100%;height:auto}` (no more
  responsive shrink — a too-wide page scrolls via `.pdf-scroll{overflow:auto}`); this keeps the
  fixed-px text layer in sync with the canvas.

**Zoom** already re-renders (the render effect's deps include `scale`) — confirmed it re-renders from
a fresh `getViewport`, never a CSS transform of a stale layer. **DPR change** (HiDPI / Ctrl+−
browser zoom): a `matchMedia('(resolution: Ndppx)')` listener (re-armed per DPR) bumps a `dpr` state
that's in the render deps, so the layers re-render at the new ratio; any zoom action also recomputes
`dpr` as a fallback.

The percentage-based highlight/citation overlay model is untouched (it was already correct/zoom-robust).

## Verification (headless Chromium; vertical text-layer-vs-canvas-ink offset, px)

Measured each span's ink centroid vs its CSS box center; **drift = bottom − top** (and a
regression slope × page-height as a robust, outlier-immune metric).

| Case | Before | After |
|---|---|---|
| Wide window @115% (page > pane → shrink) | top −3.1, bottom −11.1 → **drift −7.97** | top 0.8, bottom 0.6 → **drift −0.20**; regression across page **−0.83** |
| Narrow pane (760px) @115% | text layer desynced from shrunk canvas (bottom unmeasurable) | **−0.20** (identical to wide — no shrink) |
| Window @50% (page already fit) | −1.89 | −1.6 (regression −1.12) |
| HiDPI dpr=2 @115% | (blurry, half-res backing) | backing **1387 = 2×693**, exact 693px CSS box; bottom −0.10, regression **−1.62** |

The residual ~1px after the fix is **measurement noise** (ink-centroid vs CSS-box-center varies
per span); it's flat (constant, not growing toward the bottom), unlike the real −7.97 progressive
drift before.

**Highlight reload-drift = 0.0 px** at scales 50%, 75%, 115%, 195% **and** at HiDPI dpr=2 (the
percentage overlay model stayed correct at every zoom).

`pytest`: **126 passed** (frontend-only change; no backend impact).

## DPR-change re-rendering: implemented
Via `matchMedia('(resolution: …dppx)')` (re-armed on each change) → `dpr` state in render deps.
Covers Ctrl+− browser zoom on Chrome/Firefox; any in-app zoom also recomputes the current DPR.

## Rough edges
- **No more shrink-to-fit:** a page wider than its pane now scrolls horizontally (the deliberate
  trade for layer sync). Use the in-app zoom (−) to fit a narrow pane. (At the user's 50–70% browser
  zoom, pages fit comfortably.)
- The ~1px residual offset is measurement-method noise, not real drift.
- Rotated pages keep the existing no-overlay limitation (out of scope).
- `matchMedia` resolution-change detection is browser-dependent; the zoom-action DPR recompute is the
  backstop.
