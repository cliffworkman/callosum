# Increment 298 Notes — Synthesize Ask/Critique split

Date: 2026-07-18

## What Changed
- Renamed the center workspace label from **Synthesis** to **Synthesize** while keeping the internal workspace id `synthesis`.
- Converted Synthesize into registered workspace tabs:
  - **Ask**: the existing synthesis Q&A surface.
  - **Critique**: the single-paper Critical Read surface.
- Moved single-paper Critical Read registration out of the METHODS accordion and into **Synthesize → Critique**.
- Updated selection summarize flow to request **Synthesize → Ask** so a remembered Critique tab does not intercept the user.
- Updated help, design notes, and QA routes to point users and maintainers at the new location.

## Design Notes
- Synthesize now names the action space, matching the active-verb menu pattern used by Discover and Extract.
- Critique remains signal-not-verdict: it surfaces evidence and candidates, never a score or final judgment.
- METHODS keeps the narrow paper-method checks; the wider critical-read workflow now has center-pane space.

## Verification
- `python tools/build_frontend.py` — passed; rebuilt `callosum-app.html`.
- `python -m pytest tests/test_frontend_assembly.py tests/test_help.py tests/test_critical_review.py tests/test_critical_review_set.py -q` — 73 passed.
- `python -m ruff check .` — passed.
- `python -m ruff format --check .` — passed after formatting `tests/test_frontend_assembly.py`.
- `python tools/check_line_budget.py` — passed.
- `python tools/qa/build_surface_map.py check` — 248 API / 1141 FE, 0 uncovered.
- `python -m pytest -q` — 1260 passed, 1 skipped.

## Manual QA To Eyeball
- Menu bar reads **My Publications · Library · Synthesize · Discover · Work · Extract**.
- Synthesize shows **Ask · Critique**.
- Library selection summarize opens **Synthesize → Ask**.
- Single-paper Critical Read appears under **Synthesize → Critique**, not in METHODS.
- Read-only mode hides **Critique** and keeps **Ask** available.

## Revert
Restore the files listed in `.claude/changes.md` for increment 298 and rebuild `callosum-app.html`.
