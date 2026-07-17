# Increment 288 — Library header polish + positive Open Data signal

Group A from the `feature/library-ux-polish` handoff: make Library header controls stable, shorter, and clearer.

## Implemented

- `app/frontend/js/10b_libmenus.jsx`: changed the library-wide metadata button from **Enrich metadata ↻** / dynamic
  **Filled N** text to stable **Metadata ↻**. The filled-fields/DOI summary and last-run time now live in the tooltip.
- `app/frontend/js/10b_libmenus.jsx`: changed the citation-count button to keep **Citations ↻** as the idle label and
  move the last refreshed date into the tooltip.
- `app/frontend/js/10b_libmenus.jsx`, `26b_text_health.jsx`, and `19_synthesis_failures.jsx`: changed visible
  **Text health** / **PDF text health** copy to **Text Health** / **PDF Text Health** and kept text-health counts in
  tooltips instead of the header label.
- `app/frontend/js/10_pdf_layer.jsx`: changed Library chips to **⚠ Flagged · N**, **⚠ Retracted · N**,
  **📋 Review · N**, and **🔎 Open Data · N**.
- `app/backend/persistence/signals_repo.py`, `repository.py`, and `api/routers/transparency.py`: added the positive
  `transparency-data-detected` filter and `data_detected` summary count while preserving the existing
  `data_not_detected` review-queue count for the transparency panel.
- `app/backend/help/help_content.md`, `tests/test_frontend_assembly.py`, and `tests/test_transparency_findings.py`:
  updated served help and guards for the new labels and positive Open Data signal.
- `callosum-app.html`: rebuilt with `python tools/build_frontend.py`.

## Principles gate

Read `.claude/PRINCIPLES.md` because the Open Data chip changes signal direction. The shipped version follows the
signal-not-verdict rule: **Open Data** means the deterministic transparency auditor detected a data-availability
disclosure in extracted text, and clicking the chip filters to those evidence-bearing papers. It is not an openness
score, not a ranking, and not a claim that papers without the chip lack data.

## Experience pass

Persona: a user repeatedly scanning the Library header while running batch maintenance.

Finding: fix-now complete. The controls no longer shift from "Enrich metadata" to "Filled N" or from "Citations" to a
date-labeled button after a run. Counts and run summaries remain available on hover, while the visible labels stay
short and predictable.

## Verification

- `python tools/build_frontend.py` rebuilt `callosum-app.html`.
- `python -m pytest tests/test_frontend_assembly.py tests/test_help.py tests/test_transparency_findings.py`:
  **44 passed**.
- `python tools/qa/build_surface_map.py check` reported **245/245 API** and **1147/1147 FE** covered.
- `python -m pytest` on the final formatted tree: **1240 passed, 1 skipped** in 24:05.
- `ruff check .` passed.
- `ruff format --check .` passed (`464 files already formatted`).
- `python tools/check_line_budget.py` passed (`all 342 application-source files within the 600-line cap`).
