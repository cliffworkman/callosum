# Increment 286 — Discover Search owns discovery launchers + Feed

Follow-up to the workspace navigation polish on `feature/workspaces-ux-polish`: consolidate the discovery surfaces so
Search, Wanted, Gaps, Overlooked, and Feed all live inside the Discover workspace rather than split across Library and
a standalone Feed sub-tab.

## Implemented

- `app/frontend/js/10_pdf_layer.jsx`: removed the **Wanted**, **Gaps**, and **Overlooked** buttons from the Library
  header. The existing modals and modal state remain intact.
- `app/frontend/js/40_app.jsx` + `app/frontend/js/04b_workspaces.jsx`: passed the existing modal open handlers through
  the Discover workspace context and removed the standalone Discover `feed` tab registration.
- `app/frontend/js/30d_discover.jsx`: added **Wanted**, **Gaps**, and **Overlooked** as `btn btn-primary` buttons in
  the Search action row immediately after **Search**. The titles preserve the modal explanations from their Library
  buttons.
- `app/frontend/js/30e_feed.jsx`: added an embedded rendering mode so Feed can be mounted inside Search without the
  outer standalone Discover pane wrapper.
- `app/frontend/styles.css`: added a minimal embedded Feed divider using existing tokens.
- `app/frontend/js/09_placeholders.jsx`, `app/backend/help/help_content.md`, `.claude/DESIGN.md`, and
  `.claude/qa-routes/route_73_workspaces.md`: updated navigation/help/QA text to describe Discover Search as the home
  for Wanted, Gaps, Overlooked, and the embedded Feed.
- `app/frontend/js/30c_frame.jsx`: updated the one-time layout notice copy so returning users are pointed to
  `Discover -> Search` for Wanted/Gaps/Overlooked.
- `tests/test_frontend_assembly.py`: extended the workspace assembly guard for the removed Feed tab, embedded Feed,
  Discover Search modal launchers, removed Library header launchers, and updated banner/help placeholder copy.
- `callosum-app.html`: rebuilt with `python tools/build_frontend.py`.

## Key technical detail

The modals were not rewritten. `WantedModal`, `GapFinderModal`, and `OverlookedLensModal` still live at the app level
and are opened by the same `setWantedOpen`, `setGapsOpen`, and `setOverlookedOpen` state setters; the only change is
where their trigger buttons are rendered. Feed still receives the same `onSaved` and `active` inputs, now with
`active` tied to the Search tab because it is part of that surface.

## Experience pass

Persona: returning user looking for discovery tools after the workspace split.

Finding: fix-now complete. Library is cleaner and focused on owned papers. Discover Search now groups the user's
outward-facing literature discovery actions in one place: run a public metadata search, open the Wanted/Gaps/Overlooked
modals, and scan Feed below the Search content. No evidence/scoring behavior changed; this is navigation and placement
only.

## Manual verification

Playwright desktop viewport (`1440x1000`) against the local app on `http://127.0.0.1:8888/`:

- Library header no longer shows Wanted/Gaps/Overlooked.
- Discover sub-tabs are Search, Journals, and Funding; no standalone Feed tab appears.
- Discover Search shows Search, Wanted, Gaps, and Overlooked as the same primary button style.
- Feed is visible below the Search empty/results area.

Playwright narrow viewport (`390x844`):

- Discover Search remains selected after navigation.
- Search/Wanted/Gaps/Overlooked wrap cleanly within the action row.
- Feed remains beneath the Search empty/results area.

## Verification

- `python tools/build_frontend.py` rebuilt `callosum-app.html`.
- `python -m pytest tests/test_frontend_assembly.py tests/test_help.py` **35 passed**.
- `python tools/qa/build_surface_map.py check` reported **245/245 API** and **1143/1143 FE** covered.
- `python -m pytest` on the final formatted tree: **1237 passed, 1 skipped** in 20:38.
- `ruff check .` passed.
- `ruff format --check .` passed (`464 files already formatted`).
- `python tools/check_line_budget.py` passed (`all 342 application-source files within the 600-line cap`).
