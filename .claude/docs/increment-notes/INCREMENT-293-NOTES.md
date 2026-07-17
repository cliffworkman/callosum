# Increment 293 — Credit-the-lineage add-missing states

Group F from the `feature/library-ux-polish` handoff: make every method-credit lineage button tell the truth about
whether its credited sources are already in the Library, and avoid re-importing sources that can be matched by DOI.

## Implemented

- `app/backend/api/routers/library.py`: added `POST /library/credit/status`, a read-only DOI presence check that
  normalizes DOI inputs and reuses `find_existing_paper_by_identity(...)` instead of introducing a parallel lookup.
- `app/frontend/js/05_method_credit.jsx`: added shared `MethodCreditButton`, plus DOI normalization and missing-item
  selection helpers. It checks credited DOI-backed sources on mount, labels missing/partial states as
  **＋ add missing to library**, imports only missing CSL items through `/library/import`, and labels complete states as
  **✓ added to library**.
- Converted the existing `.method-credit` lineage buttons in statcheck, GRIM/GRIMMER, citation equity/context,
  Bayesian statistics, LMM, meta-analysis reporting, transparency, effect-size conversion, p-curve, Overlooked, and
  CRediT to use the shared helper.
- Left non-lineage import actions alone, including the regular Library import UI and the Settings OpenURL credit flow.
- `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_73_workspaces.md`, and
  `tests/test_{citation_import,frontend_assembly}.py`: updated user-facing help, design contract, route guidance, and
  regression coverage.
- `callosum-app.html`: rebuilt with `python tools/build_frontend.py`.

## Principle boundary

The new endpoint is a deterministic library-presence check, not an import job or metadata enrichment path. It only
answers whether normalized credited DOIs already resolve through the canonical identity lookup. The frontend still uses
the existing CSL JSON import route for the actual add action.

## Verification

- `python tools/build_frontend.py` rebuilt `callosum-app.html`.
- `python -m ruff check app/backend/api/routers/library.py tests/test_citation_import.py tests/test_frontend_assembly.py`
  passed.
- `python -m pytest tests/test_citation_import.py tests/test_frontend_assembly.py tests/test_help.py -q`:
  **52 passed**.
- `python tools/qa/build_surface_map.py check` reported **246/246 API** and **1131/1131 FE** covered.
- `python -m pytest` on the final tree: **1247 passed, 1 skipped** in 18:48.
- `ruff check .` passed.
- `ruff format --check .` passed (`464 files already formatted`).
- `python tools/check_line_budget.py` passed (`all 343 application-source files within the 600-line cap`).
