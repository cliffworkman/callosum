# Increment 222 — split 15_axes.jsx (the axis-card subsystem → 15b_axis_card.jsx)

## Implemented

A behavior-preserving refactor clearing the **last over-cap file** — `app/frontend/js/15_axes.jsx` had been
**614 (>600)** since inc 211/212 (the curated-axis SP1/SP2 grew it; the footers had mis-noted 551/562, corrected
in inc 220/221). No feature lands in this increment; it's the standing rule-#1 split the maintainer picked.

Extracted the **axis-card rendering subsystem** into a new chunk **`app/frontend/js/15b_axis_card.jsx`**
(224 lines), verbatim:

- `axisConfidenceLabel`, `AxisTierBadge`, `AxisPaperRow`, `AxisCutoffFlipper` — the per-row/per-card
  presentational helpers.
- **`AxisItem`** (166 lines) — the one-axis card: header (label + ✎/＋/❄/↩/📊/🗑 + the count badge), the
  re-score row (keyword) / curated hint (curated), and the member list (`renderPapers` — the keyword
  filter+sort+domain-group path *and* the curated drag-reorder path).
- `_tierRank` — `AxisItem`'s member sort key.

`15_axes.jsx` (**395 lines**) keeps `MyPubsPrompt`, **`AxesPanel`** (the container — state, the data
loaders, all the handlers `score`/`remove`/`confirmPaper`/`dropPaper`/`reorderToIndex`/`freeze`/
`convertToKeyword`/`createCurated`/`bulkDelete`/`openMerge`/…, the sort/filter, and the
edit/merge/suggest modals), and the `registerPaneTab` registration.

## Key technical detail — the cross-chunk function hoist

The chunks are concatenated into one IIFE and esbuild-transpiled together, so **top-level `function`
declarations hoist across chunk boundaries** (the inc-208 `10b_libmenus.jsx` / inc-182 `30c_frame.jsx`
precedent). `AxesPanel` (in `15_axes.jsx`) renders `<AxisItem/>` (now in `15b_axis_card.jsx`) regardless of
which chunk loads first — and indeed `15_axes.jsx` sorts before `15b_axis_card.jsx`, so AxesPanel is *textually
before* its dependency, which only works because of the hoist. Every extracted symbol is a `function`
declaration (not a `const` arrow), so they all hoist; esbuild keeps `AxisItem` (its DCE only strips
*unreferenced* top-level functions, and `AxesPanel` references it). The cut was done by a deterministic
line-range script (no transcription of the 166-line `AxisItem`), with boundary assertions on every function
start/end.

The QA route `route_15_axes.md`'s `fe:` claim gained `15b_axis_card.jsx` — the 36 FE surfaces (the moved
`AxisItem` subsystem's elements) re-attach to the route, so the surface map stays 0-uncovered.

## Manual verification script — behavior-preservation, the discipline

Frontend behavior isn't pytest-covered, so I reused **two existing axis drivers** as a baseline-then-after
regression check (the inc-221 discipline): run GREEN on the **pre-refactor** code, then GREEN after.

- `.local/visual/drive_inc212_dragreorder.py` — the **curated** `AxisItem` path: expand a curated axis →
  `AxisPaperRow` (curated, the ⠿ grip) renders → HTML5 drag member A onto C → order persists across a reload;
  asserts no ↑/↓ buttons remain.
- `.local/visual/drive_inc204_hide_uncertain.py` — the **keyword** `AxisItem` path: a seeded
  assigned(0.6)/uncertain(0.2)/manual(NULL) axis → the re-score row + `AxisCutoffFlipper` + `AxisTierBadge` +
  the 👁 hide-uncertain toggle → the badge carries hide-state to the library filter ("· assigned only").

Both **GREEN before and after**, deterministic, 0 console/page/genai. (`drive_inc211_curated.py` is **stale** —
it still clicks the ↑/↓ "Move down" buttons that inc 212 replaced with drag — so it's not a valid baseline; 212
is its current replacement.) The build (esbuild) + `test_frontend_assembly` (5/5) catch scope/sync errors.

## Pytest

**785 unchanged** (frontend-only — no Python touched; `test_frontend_assembly` confirms `callosum-app.html` is
in sync + every chunk, including `15b_axis_card.jsx`, is in the assembly). QA surface **161/161 API + 719/719
FE, 0 uncovered**. `ruff check` + `ruff format --check` clean.

## Rule #1

`15_axes.jsx` **614 → 395**; `15b_axis_card.jsx` **224** — both comfortably under cap. **This clears the last
over-cap file in the tree.** Watch (re-measure before trusting): `js/40_app.jsx` (212 after the inc-221 split),
`js/30_viewer.jsx` (580), `clustering/my_publications.py` (~594, the closest backend file).

## NEXT

The standing rule-#1 backlog is now empty. The remaining work is the design-gated **B-items** (B2
collaboration/shared libraries, B3 OCR, B4 citation-context classifier, B5 mobile reading) — each its own
brainstorm + the maintainer's pick.
