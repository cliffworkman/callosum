# Increment 289 — Workspace scroll + My Publications workspace polish

Group B from the `feature/library-ux-polish` handoff: make long workspace subsections scroll, normalize Extract labels,
and make the My Publications workspace load independently from the old axis-card entry point.

## Implemented

- `app/frontend/styles.css`: gave `.workspace-body` its own `overflow-y:auto` inside the bounded
  `.workspace-pane`, so long registered workspace tabs scroll within the active body while the menu bar and sub-tab
  strip stay put. This covers Discover → Journals/Funding and Extract → Effect-Size/Meta-Analysis.
- `app/frontend/js/04b_workspaces.jsx`: changed the menu-bar label from **Profile** to **My Publications**.
- `app/frontend/js/08i_methods_effectsize.jsx` and `08g_methods_metaanalysis.jsx`: changed Extract tab labels to
  **Effect-Size** and **Meta-Analysis**.
- `app/frontend/js/31_mypubs_dashboard.jsx` and `40_app.jsx`: My Publications now resolves its own
  `my_publications` axis from `/axes` and refetches dashboard data when `axisRefresh` changes, so a Settings refresh
  populates the workspace without interacting with the old My Publications axis card.
- `app/frontend/js/15_axes.jsx` and `15b_axis_card.jsx`: removed the redundant My Publications axis-card dashboard
  button/plumbing; the menu-bar workspace is the dashboard entry point.
- `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_73_workspaces.md`, and
  `tests/test_frontend_assembly.py`: updated docs and guards for the labels, scrolling recipe, and Profile loading.
- `callosum-app.html`: rebuilt with `python tools/build_frontend.py`.

## Experience pass

Persona: a user moving between discovery, extraction, and their own publication dashboard during a long session.

Finding: fix-now complete. Long workspace subsections now scroll in place instead of trapping content below the
viewport. The My Publications dashboard has one obvious top-level entry point and reloads after a refresh without
requiring the user to poke the Axes card first.

## Verification

- `python tools/build_frontend.py` rebuilt `callosum-app.html`.
- `python -m pytest tests/test_frontend_assembly.py tests/test_help.py tests/test_my_publications.py`:
  **78 passed**.
- `python tools/qa/build_surface_map.py check` reported **245/245 API** and **1145/1145 FE** covered.
- Browser smoke against the fresh static bundle on `http://127.0.0.1:8765/callosum-app.html`: desktop/narrow DOM
  checks confirmed **My Publications** replaces Profile, Extract shows **Effect-Size** and **Meta-Analysis**, the old
  axis-card dashboard button is absent, visible Discover/Extract workspace bodies are bounded with `overflow-y:auto`,
  and narrow viewport (`390x844`) keeps page `scrollWidth` at viewport width while the menu bar scrolls internally.
  Static-bundle API console errors were expected because no backend was attached.
- `python -m pytest` on the final tree: **1241 passed, 1 skipped** in 25:14.
- `ruff check .` passed.
- `ruff format --check .` passed (`464 files already formatted`).
- `python tools/check_line_budget.py` passed (`all 342 application-source files within the 600-line cap`).
