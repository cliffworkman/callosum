# Increment 291 — Discover selected-paper cue for Journals/Funding

Group D from the `feature/library-ux-polish` handoff: reuse the selected/open paper tab language inside Discover so
Journals and Funding make their selected-paper context visible before their controls.

## Implemented

- `app/frontend/js/04b_workspaces.jsx`: added `WorkspacePaperCue`, rendered only for Discover when the active
  sub-tab is **Journals** or **Funding**. The cue appears before the Discover sub-tab buttons.
- `app/frontend/js/04b_workspaces.jsx`: selected-but-not-open papers use the existing
  `.frame-tab.frame-tab-selected` styling and click through to `ctx.onOpenPdf`.
- `app/frontend/js/04b_workspaces.jsx`: selected-and-open papers use the existing `.frame-tab.active` styling and
  click through to `ctx.onActivatePaperTab`, returning to the Library reader tab.
- `app/frontend/js/40_app.jsx`: threads `selectedPaperTab`, the matching `selectedOpenPaperTab`, and
  `onActivatePaperTab` through `workspaceCtx`.
- `app/frontend/styles.css`: adds only `.workspace-paper-cue` spacing so the reused Library tab styles sit cleanly
  before the Discover segmented tabs.
- `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_73_workspaces.md`, and
  `tests/test_frontend_assembly.py`: updated help, design contract, manual route checks, and assembly coverage.
- `callosum-app.html`: rebuilt with `python tools/build_frontend.py`.

## Experience pass

Persona: a user selects a paper in the Library, then uses Discover → Journals or Discover → Funding to look for a
venue or funding opportunities tied to that paper.

Finding: fix-now complete. Journals/Funding now show the same selected/open paper affordance the Library tab strip
uses, so the user can tell which paper those tools are reading without scanning the form body. Search remains clean
because it is corpus-level and does not need the selected-paper cue.

## Verification

- `python tools/build_frontend.py` rebuilt `callosum-app.html`.
- `python -m pytest tests/test_frontend_assembly.py tests/test_help.py`: **39 passed**.
- `python tools/qa/build_surface_map.py check` reported **245/245 API** and **1151/1151 FE** covered.
- Browser smoke against the fresh static bundle with mocked Library/Discover APIs confirmed:
  **Journals** shows the dashed selected-paper cue while the selected paper is not open; **Search** shows no cue;
  **Funding** cue opens the PDF; returning to **Journals** shows the open-PDF styling; clicking that open cue returns
  to the Library reader tab.
- `python -m pytest` on the final tree: **1243 passed, 1 skipped** in 20:29.
- `ruff check .` passed.
- `ruff format --check .` passed (`464 files already formatted`) after formatting the new assembly guard.
- `python tools/check_line_budget.py` passed (`all 342 application-source files within the 600-line cap`).
