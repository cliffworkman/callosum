# Increment 424 — align Meta-Reference actions in one fixed-width column

## Implemented

- Reworked the five Work → Meta-Reference action rows across
  `08j_reference_integrity.jsx`, `08b_methods_citation_equity.jsx`, and
  `08c_methods_citation_context.jsx` so the descriptive copy stays on the left and the action sits on the same
  row in a shared right column.
- Added one `.meta-ref-action-*` layout recipe in `styles.css`: a flexible copy column, a 24px gap, and a flush-right
  150px action slot sized for the longest label, **Find overlooked work**. Every canonical primary button fills
  that slot, so Check references / Run audit / Find overlooked work / Fetch citations / Fetch references have
  identical widths and right edges.
- Added the phone-width fallback: the action moves below the copy, stays right-aligned at 150px, and does not
  squeeze the prose or create horizontal overflow.
- Documented the layout recipe in `DESIGN.md`, extended workspace QA route 73 with desktop/mobile geometry checks,
  added a frontend-assembly regression test, and rebuilt `callosum-app.html`.

## Key technical detail

The action slot owns the fixed width and its child `.btn-primary` uses `width:100%; box-sizing:border-box`; the
button recipe itself remains canonical and unchanged. This keeps the button column exactly flush to the button
edges rather than adding a second padded wrapper. The mobile rule changes only the grid to one column and moves
the same fixed-width slot to `justify-self:end`.

## Manual verification

Verified against the maintainer's local library in Chromium through the registered Playwright session:

1. At `1920x889`, opened Work → Meta-Reference with a DOI'd paper selected.
2. Measured all five rendered action rows: every button was exactly **150px** wide, each right edge was **1474px**,
   and each computed grid was `970px 150px` with a **24px** column gap.
3. Resized to `375x812`: every action stacked below its copy with an **8px** row gap, remained **150px** wide and
   right-aligned, and the document reported `scrollWidth === clientWidth === 375` (no horizontal overflow).
4. Browser console: **0 errors, 0 warnings**.

## Experience pass

**Deadline citer, goal: scan a selected paper's reference checks and choose the next inspection action quickly.**
The equal right-edge alignment makes the five actions legible as one repeated control column while preserving the
full explanatory and egress copy. The mobile stack avoids trading prose readability for strict same-row placement.
No dead end or follow-up finding surfaced.

## Verification

- `python tools/build_frontend.py` — rebuilt `callosum-app.html`.
- `python -X utf8 tools/check_line_budget.py --list` — all 418 application-source files ≤ 600 lines.
- `pytest tests/test_frontend_assembly.py -q` — **58 passed**.
- `ruff format tests/test_frontend_assembly.py` + `ruff format --check .` — clean (558 files formatted).
- `pytest -n auto -q` — **1713 passed, 1 skipped** in 729.23s.
- `git diff --check` — clean.

No security-audit gate triggered: this is presentation-only, with no new endpoint, request contract, external fetch,
file path, auth logic, dependency, or data-flow change.
