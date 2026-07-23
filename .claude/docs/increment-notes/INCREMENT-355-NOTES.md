# Increment 355 — Manuscript-specific WIP facets and count sorts

## Context

The WIP collection already supported title search, stage/state filters, and basic sorting, but the approved MVP
requires users to find manuscripts by workflow and provenance state. This increment closes acceptance criterion 6
without exposing Library-specific bibliographic filters.

## Implemented

- Search now includes derived/overridden title, manuscript type, target journal, and notes.
- WIP-specific facets cover stage, lifecycle state, type, journal, overdue/next-30-days/no deadline, modified in
  7/30/90 days, open tasks, unresolved findings, stale checks, and missing/unavailable primary file.
- Sort includes last modified, title, stage, deadline, created date, open-task count, and unresolved-finding count.
- One SQL listing projection supplies file, task, unresolved-finding, stale-check, and primary-file state. Stale
  counts apply the same snapshot identity semantics as the Checks view.
- Cards expose nonzero open-task, unresolved-finding, and stale-check counts plus missing-primary state.
- Query state stays mounted independently from Library state. The query/facet component lives in its own WIP module,
  not as hidden reference controls or scattered entity checks.

## Principles gate

Principles 1, 2, 4, 6, 8, and 10 apply. The facets are deterministic projections of explicit workflow/provenance
state. “Unresolved” and “stale” retain their established meanings; neither is a manuscript-quality verdict.

## Experience pass

The concrete persona was a researcher triaging several active drafts before a work session. They can narrow to
overdue systematic reviews with open tasks, or to manuscripts whose checks need review/rerun, without opening every
workspace. Counts appear only when nonzero and lead back to the existing detailed workflow surfaces.

## Manual verification

1. Open WIP with manuscripts spanning stages, types, journals, deadlines, task states, and primary-file states.
2. Apply each text/select/toggle facet alone and in combination; confirm **Clear filters** restores the base view.
3. Create an open task and unresolved finding; confirm exact card counts and count-based sort order.
4. Change a checked primary file and rescan; confirm the stale-check facet/card count follows the Checks view.
5. Switch Library → WIP and confirm both collections retain independent query/filter/sort/selection state.
6. Repeat at desktop and mobile widths in light/dark themes; confirm wrapping without document overflow.

## Verification

- `pytest -n auto -q` — **1456 passed, 1 skipped**.
- Focused WIP/workflow/check/frontend/health suites — **65 passed**.
- Ruff, frontend rebuild, 600-line budget, and QA surface map pass (**293/293 API surfaces**; 21 unrelated existing
  frontend checklist entries remain).
- Chromium at 1440×900 dark and 375×812 light verifies combined facets, contradictory empty state, clear action,
  exact card counts, count sort, Library/WIP state retention, full-width mobile wrapping, zero console errors, zero
  non-loopback requests, and zero document horizontal overflow.

## Next slice

Complete remaining WIP-9 graduation items: entity-specific context actions, tab persistence/reorder parity where
the host tab manager supports it, and the final accessibility/acceptance matrix.
