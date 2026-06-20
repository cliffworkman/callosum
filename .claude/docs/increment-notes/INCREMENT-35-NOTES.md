# Increment 35 Notes

Fix multi-line highlight opacity doubling (overlapping per-line rects composited darker in the
interior). Frontend-only (`callosum-app.html`); no geometry/coordinate change.

## Problem

A multi-line user highlight is painted as one translucent div per line fragment
(`getClientRects()`). Adjacent line-box rects overlap vertically (line leading), so the overlap
zones were filled twice → the interior rows rendered darker (~0.80 effective vs ~0.55 at the
single-painted top/bottom edges) — an uneven, muddy band. The pre-existing per-fill
`mix-blend-mode: multiply` did **not** help: multiply blends each fill against its backdrop, so two
overlapping same-color fills *compound* (≈c²) — it is not idempotent. `isolation` on the layer only
contains the blend; it doesn't stop the rects compounding within it. (Confirmed: multiply was already
on `.pdf-user-highlight` and the band persisted.)

## Fix — flatten per annotation, then composite once (group multiply)

Per-annotation **isolated group**: each annotation's line-rects are painted **opaque** (same color)
so they **union with no doubling**, and the *group* composites once, translucently, via multiply:

```css
.pdf-user-highlight-group { position:absolute; inset:0; isolation:isolate; mix-blend-mode:multiply; opacity:0.7; }
.pdf-user-highlight       { position:absolute; border-radius:1px; }   /* opaque fill (JS), no per-fill blend/border */
```
- JS (`renderUserAnnotations`): wrap each annotation's rects in a `.pdf-user-highlight-group`
  (`inset:0`, so the rects' percentage positions still resolve against the full page box — geometry
  unchanged); fill is now `hexToRgba(ann.color, 1)` (opaque; translucency comes from the group).
  `clearUserAnnotations` removes the groups.
- Removed the per-fill `mix-blend-mode: multiply` **and** the `box-shadow: inset 1px` (the inset
  border would have drawn seams where the unioned rects meet).
- **Why it's uniform:** opaque same-color rects union to a flat shape inside the isolated group
  (no overlap doubling); the group then multiplies against the page once → `page·(0.3+0.7·C)` on
  every row, identical interior vs edge. Multiply keeps black text legible (`C·0 = 0`).
  `isolation: isolate` (reinforced by `opacity<1`) keeps the blend within the group + against the
  canvas; the text layer is above (never a backdrop) → unaffected.

The percentage-coordinate model, zoom-robustness, and selection→bbox are untouched (compositing-only).

## Citation/provenance overlay — left as-is (noted)
The citation overlay (`.pdf-highlight`) also paints per-rect, but its style is low-alpha (0.22) and
bordered, and it's a single transient target highlight — its overlap doubling isn't visibly a
problem, so per the task it was left unchanged. The **text layer** is untouched (above everything,
transparent spans). Both confirmed unaffected by the annotation-layer change.

## Verification (headless Chromium)
- 60-rect (many-line) highlight: inter-line **gap-row fill luminance** top/mid/bottom =
  **250.7 / 253.1 / 251.9 → spread 2.4 (~1%)** — uniform, no darker interior band. (Before: the
  interior leading was visibly darker — ~0.80 vs ~0.55 effective.) Screenshot confirms an even band.
- **Reload-drift = 0.0px**; zoom unchanged (same percentage model; group is `inset:0`).
- No console errors. `pytest`: **126 passed**.

## Rough edges
- Two **separate** same-color highlights that overlap each other still multiply-compound at their
  overlap (each annotation is its own group). That's rare (re-highlighting the same text); within a
  single multi-line highlight it's now uniform — the reported bug.
- `opacity: 0.7` is the strength knob (tunable). Yellow stays light because yellow·white keeps the
  red channel at full — inherent to multiply, same as before.
- The note-dot (`.has-note::after`) and jump **flash** now composite through the group (slightly
  muted but still clearly visible).
