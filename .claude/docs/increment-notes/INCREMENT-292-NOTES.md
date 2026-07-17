# Increment 292 — Library retractions refresh + badges

Group E from the `feature/library-ux-polish` handoff: make the Library header own the retraction batch affordance,
refresh the Retraction Watch mirror before checks when possible, and make retracted papers visibly distinct wherever a
paper is presented.

## Implemented

- `app/backend/api/routers/methods_retraction.py`: `_run_retraction_all_job` now attempts
  `download_retraction_database(...)` before listing/checking papers. `RetractionWatchUnavailable` and unexpected
  refresh errors are recorded as `summary.database_refresh_error` plus response `detail`, then the batch continues
  against the existing local mirror and the configured DOI checkers.
- `app/backend/api/routers/methods_retraction.py`: `RetractionRunSummary` now includes `database_records` and
  `database_refresh_error`, so the UI can say whether the mirror refreshed or fell back.
- `app/backend/persistence/repository.py` + `app/backend/api/routers/{papers,paper_models}.py`: `/papers` and
  `/papers/{id}` now expose the stored `retraction_status` from `open_science_signals`.
- `app/frontend/js/10b_libmenus.jsx`: added `RetractionCheckButton`, a Library-header `.trash-toggle` button labeled
  **Retractions ↻**. It polls `/methods/retraction/run`, stores the last-run summary/detail in the tooltip, and calls
  back on completion.
- `app/frontend/js/03_library.jsx` + `10_pdf_layer.jsx`: placed **Retractions ↻** after **Metadata ↻** and before
  **Text Health**, and refreshes the retraction chip, paper list, and findings queue when the run finishes.
- `app/frontend/js/10d_papercard.jsx` + `25_detail.jsx` + `styles.css`: added the noninteractive **RETRACTED** badge
  using the same `.tier` pill recipe as chunking badges, colored by `--danger-line`/`--danger`.
- `app/frontend/js/08_methods_findings.jsx`: updated Review-pane retraction copy/results to include Retraction Watch
  auto-refresh, mirror count, and fallback detail.
- `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_73_workspaces.md`, and
  `tests/test_{retraction,frontend_assembly}.py`: updated help, design contract, manual route checks, and regression
  coverage.
- `callosum-app.html`: rebuilt with `python tools/build_frontend.py`.

## Principle boundary

Retraction remains a deterministic registry signal with source/date/notice evidence, never an author accusation or a
paper-quality verdict. The new red badge is deliberately a noninteractive status pill. A failed Retraction Watch
refresh is not treated as evidence; it is operational state, and the batch says it used the existing mirror.

## Verification

- `python tools/build_frontend.py` rebuilt `callosum-app.html`.
- `python -m pytest tests/test_retraction.py tests/test_retraction_watch.py tests/test_frontend_assembly.py`:
  **55 passed**.
- `python -m pytest tests/test_help.py`: **14 passed**.
- `python tools/qa/build_surface_map.py check` reported **245/245 API** and **1153/1153 FE** covered.
- Throwaway-server Playwright smoke (`tools.qa._qa_serve` + Chromium) confirmed **Retractions ↻** renders as a
  `.trash-toggle`, appears before **Text Health**, has a registry-retraction tooltip, and produced 0 console/page
  errors. A retracted-paper visual smoke was not run against a seeded registry-hit fixture; card/detail badge behavior
  is covered by assembly tests and backend payload tests.
- `python -m pytest` on the final tree: **1245 passed, 1 skipped** in 20:52.
- `ruff check .` passed.
- `ruff format --check .` passed (`464 files already formatted`).
- `python tools/check_line_budget.py` passed (`all 342 application-source files within the 600-line cap`).
- `python -m ruff check app/backend/api/routers/methods_retraction.py app/backend/api/routers/papers.py app/backend/api/routers/paper_models.py app/backend/persistence/repository.py tests/test_retraction.py tests/test_frontend_assembly.py`
  passed after import-order autofix.
