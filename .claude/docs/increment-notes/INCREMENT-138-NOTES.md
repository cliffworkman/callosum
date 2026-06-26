# Increment 138 — Auto-select the top library paper on load (Details populated)

## Implemented

On app load the **top library paper is auto-selected**, so the METHODS → DETAILS section starts **populated**
(its editable Details) instead of the empty "Select a paper to see its details" hint — the user no longer has to
click a paper to see anything in the right pane.

- **`app/frontend/js/40_app.jsx`** (frontend-only): a new effect sets `selected` to `listState.papers[0].id` when
  **nothing is selected** and the **(non-trash) list is ready with papers**. It fires on first load and also when
  the selection clears to null (e.g. the selected paper was trashed → inc-54's `setSelected(prev => …)`), and it
  **never overrides** a paper the user has already selected (guarded on `selected == null`).

## Key technical detail

- `selected` is the selected paper **id** (`useState(null)`); the METHODS **DETAILS** section
  (`05_panes.jsx`, `methodsOpen` default `"details"` → open) renders `DetailContent` when `selectedPaper != null`
  else the hint. So setting `selected` is sufficient to populate Details — no new component or prop.
- The guard `selected == null` makes the effect idempotent (after it sets the id, the condition is false → no
  loop, no fighting the user's later clicks). `!trashView` keeps it from auto-selecting into the Trash listing.
- This auto-selects for **Details only** — it does **not** open a PDF tab (`openPdf` is a separate action), so the
  center pane stays on the library; the right pane just starts useful.

## Manual verification script

1. `python .local/visual/drive_inc138_autoselect.py` (free port + own-process-alive check; seeds 3 papers, no
   network). On load with **no clicks**: DETAILS shows the top paper's editable title ("Alpha Paper On Vision"),
   the "Select a paper …" hint is absent, the top library card matches; clicking the 2nd paper updates Details.
2. Result: **PASS** — 0 console errors, 0 page errors, 0 genai hits.

## Gates

- **No Principles trigger** — auto-triggers an existing view-state (paper-selected); no new claim/signal,
  provenance, or egress posture.
- **Rule #10** — no new API/FE surface (no new element or endpoint); surface map unchanged
  (**106/106 API + 528/528 FE, 0 uncovered**). Updated `route_00_smoke_readonly.md` step 5 to reflect that DETAILS
  starts populated on load (the hint shows only when nothing is selectable — an empty library). route_33/route_38
  use "select a paper" only as an action → unaffected.

## Pytest

**519 passed, 1 skipped** (unchanged — frontend-only). `ruff` clean; build + assembly green; rebuilt
`callosum-app.html`.

## Next (queued)

- The accordion-tabs design rule (tabs-within-a-section for like-with-like — Axes+Tags tabs; order Data-consistency
  before Statistics-check; codify in `DESIGN.md`).
- Gap-finder followed-authors / similarity ranking; a cadence auto-refresh.
- **Watch (rule #1):** `clustering/my_publications.py` at **594/600** — split before the next backend addition there.
