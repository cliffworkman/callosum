# Increment 299 Notes — Discover Search/Journals recent-query recall

Date: 2026-07-18

## What Changed
- Added a browser-local recent-query list to **Discover → Search**.
  - Stores the query and selected source provider.
  - **Recent searches** recalls by re-running the stored query/source, not by replaying old rows.
  - **Clear ×** resets the active query, results, error, cursor, expanded abstracts, and relevance badges.
  - **Clear history** clears only the local recent-query list.
- Added a browser-local recent-run list to **Discover → Journals**.
  - Stores selected-paper runs as `paperId` + label.
  - Stores pasted-abstract runs as abstract + subject.
  - **Recent journal searches** recalls by re-running the stored input shape for fresh journal results.
  - The output weighting adjuster re-runs the last active input, including recalled inputs.
- Updated served help, DESIGN, and QA routes for the new controls.

## Design Notes
- History is lightweight browser state in `localStorage`; no backend schema or named-saved-search interaction.
- Recall means "run this input again" because discovery evidence can change and provider coverage can shift.
- Search still shows the complete returned list from the selected provider set. Journals still surfaces facts to weigh, not verdicts.
- Controls reuse `.lib-sort` and `.btn.btn-primary` so the action row stays visually consistent.

## Verification
- `python tools/build_frontend.py` — passed; rebuilt `callosum-app.html`.
- `python -m pytest tests/test_frontend_assembly.py tests/test_help.py -q` — 47 passed.
- `python -m pytest tests/test_discovery.py tests/test_publishers.py tests/test_frontend_assembly.py tests/test_help.py -q` — 80 passed.
- `python -m ruff check .` — passed.
- `python -m ruff format --check .` — passed after formatting `tests/test_frontend_assembly.py`.
- `python tools/check_line_budget.py` — passed.
- `python tools/qa/build_surface_map.py check` — 248 API / 1151 FE, 0 uncovered.
- `python -m pytest -q` — 1261 passed, 1 skipped.

## Manual QA To Eyeball
- Search: run two queries with different source settings, recall one, confirm fresh re-run and source restoration.
- Search: **Clear ×** empties only the active query/results; **Clear history** removes the recall list.
- Journals: recall both a selected-paper run and a pasted abstract+subject run; adjust weighting after recall and confirm it re-runs that same recalled input.
- Reload and confirm both history lists persist until cleared.

## Revert
Restore the files listed in `.claude/changes.md` for increment 299 and rebuild `callosum-app.html`.
