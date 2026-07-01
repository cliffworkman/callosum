# Increment 239 — B5 SP3: the mobile PDF reader (the deferred B5 slice)

The B5 SP2 note left a deferred slice: "a mobile-tuned PDF reader + synthesis→PDF exact-highlight overlays on
mobile." This builds it. Maintainer forks (AskUserQuestion): a **"← Synthesis" back pill** + **core + pinch-to-zoom**.

## The grounding win — half was already built

Investigating the viewer before designing revealed two things already done:

- **Fit-to-width already exists.** `PdfViewer` has `pageView: "page" | "width" | "two"` (a fit-width mode that derives
  the scale from the scroller's `clientWidth` and re-fits on resize). It just **defaults to `"page"`** (manual zoom),
  which renders at a fixed scale that overflows a phone → horizontal scroll.
- **Exact-highlight overlays are already screen-agnostic** (inc 34: positioned as % of page dims), so a synthesis
  citation's exact rect lands correctly on any screen. The missing piece on mobile was *reachability*, not geometry.

So the reader is three moves.

## 1. Fit-width by default on mobile

`mobile` is threaded `40_app.jsx` → `LibraryFrame` (30c_frame) → `PdfViewer` (30_viewer). `pageView` inits to
`"width"` when `mobile` (the existing fit-width mode); **Two-up is hidden** on a phone (nonsensical). Desktop keeps
the saved pref — the branch never runs above 760px.

## 2. Pinch-to-zoom (`usePinchZoom`, new `js/30f_pdf_gestures.jsx`)

A native touch listener (`{passive:false}`) on `.pdf-scroll`, active only on mobile + when the doc is ready:

- **During** a two-finger gesture: compute the distance ratio, clamp to a target scale, and apply a cheap CSS
  `transform: scale()` to `.pdf-pages` (a visual preview — **no per-move pdf.js re-render**). `e.preventDefault()` on
  the 2-finger move stops the browser also scrolling/zooming mid-pinch.
- **On release**: `onCommit(target)` → `setScale(target)` (a crisp re-render through the inc-34 single-scale pipeline)
  + drop out of fit mode + reset the transform.
- `.pdf-scroll` gets **`touch-action: pan-x pan-y`** on mobile: single-finger pan still works natively, but the
  browser's own pinch-zoom is disabled (delivered to our listener instead).
- A `scaleRef` mirrors the current scale so the once-attached listener reads it without re-attaching.

## 3. The navigation — reachability + a back pill (`40_app.jsx`)

On mobile the three regions (Library / Panels / Details) show one at a time (`mobilePane`). A synthesis lives on the
**Panels** region; tapping a citation opened the PDF in the **Library** (reader) region — which the phone wasn't
showing. Fix:

- `openPdf`/`openCitation` **switch `mobilePane` to `"library"`** on mobile, so the highlight lands in view.
- A **`.pdf-back-pill`** ("← Synthesis") — a fixed pill above the bottom nav, rendered only while reading the source a
  citation opened — returns to the exact synthesis in one tap. State: `citationReturn` (set true by `openCitation` on
  mobile, cleared by `openPdf` [a plain open] and by any manual `MobileNav` tap). This is the deadline-citer's
  read-check-read loop.

## Rule-#1 split

`30_viewer.jsx` was **580 at HEAD**; the ~44-line pinch effect took it to **629 (> 600)**. Extracted verbatim into a
new **`js/30f_pdf_gestures.jsx`** (64): `MinimapTrack` (inc 215, a leaf) + `usePinchZoom` (a hook). Both are top-level
declarations → they hoist in the shared esbuild IIFE, so `PdfViewer` (in 30_viewer, textually before) references them
regardless of chunk load order (the inc-182/208/222/238 precedent). `30_viewer.jsx` → **573**.

## Verification

**Frontend-only** — no Python touched → `HF_HUB_OFFLINE=1 python -m pytest -q` = **884 passed, 1 skipped** (unchanged;
`test_frontend_assembly` 5/5 confirms `30f_pdf_gestures.jsx` is in the build + `callosum-app.html` is in sync).
`ruff check` + `ruff format --check` clean (no Python changed). **QA surface 173/173 API + 760/760 FE, 0 uncovered**
(`route_32_viewer_annotations.md` claims `30f_pdf_gestures.jsx` — the minimap moved there; no new API surface). No
audit/Principles trigger (a reading UX; the minimap positions by page fraction, never a fabricated exact rect —
coordinate honesty #2 unchanged).

**Headed-verified at 390×844, 0 console/page errors** (`.local/visual/drive_inc239_mobilereader.py` — seeds a paper +
PDF + highlight + a native synthesis citing chunk on p.2): open the PDF from the library → **fit-width active + no
Two-up button + a minimap tick** (30f intact); **pinch-out raised the zoom 74% → 148%**; go to Panels → open the
Synthesis accordion → load the synthesis → expand + tap its citation → **the reader shows + the "← Synthesis" pill
appears** → tap it → **the synthesis returns + the pill clears**.

## Deferred (own increment if ever wanted)

A mobile-tuned *annotation authoring* flow — creating highlights by touch (select-to-note is a mouse gesture today),
vs the current tap-a-citation *reading* which is fully covered.
