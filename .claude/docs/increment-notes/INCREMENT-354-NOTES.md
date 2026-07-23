# Increment 354 — Stable WIP relink and reverse navigation

## Context

WIP records retained metadata when a folder disappeared, but a user could not explicitly reconnect a moved folder
to that stable record. Library papers also exposed WIP relationships only inside the manuscript workspace. This
increment completes the identity-recovery and reverse-navigation portion of WIP-9.

## Implemented

- **Relink folder** in WIP Overview inspects an existing non-symlink directory, updates the registered folder, and
  reconciles its files in one transaction.
- Relink preserves the manuscript UUID, stage and other workflow data, Library references, checkpoints, tool runs,
  findings, and matching root-relative file IDs. A missing manuscript returns to active; archived/paused state is
  not silently changed.
- A target already owned by another manuscript, or registered as an incompatible parent root, returns a conflict
  instead of merging or guessing. Activity records the old and new paths.
- Library Details now shows **Used in WIPs** for linked papers. Opening a relationship fetches the complete canonical
  manuscript before opening its distinct WIP tab.
- WIP cards are keyboard reachable: Space selects and Enter opens the manuscript workspace.

## Principles gate

Principles 2, 3, 6, 8, and 10 apply. Identity is user-confirmed and deterministic; no fuzzy path/content heuristic
decides that two unpublished folders are the same manuscript. Reverse navigation reveals an existing relationship
without copying or reclassifying either record.

## Experience pass

The concrete persona was a researcher returning after reorganizing a project directory. Their accumulated
workflow and evidence remain attached to the draft after one explicit relink, and a cited Library paper provides a
direct route back to every manuscript using it. The WIP badge and full manuscript hydration preserve the visual and
data-model distinction from published papers.

## Manual verification

1. Add a WIP folder, assign workflow metadata, make a file primary, link a Library paper, and open its workspace.
2. Move the folder outside Callosum, rescan until it is missing, then use **Overview → Relink folder**.
3. Confirm the UUID, file ID, workflow, relationship, checkpoints/runs, and activity remain; confirm the new path.
4. Attempt to relink another manuscript to the same target and confirm Callosum refuses the collision.
5. Select the linked paper in Library Details, choose **Used in WIPs**, and confirm the complete WIP workspace opens.
6. Tab to a WIP card; confirm Space selects it and Enter opens it.

## Verification

- `pytest -n auto -q` — **1455 passed, 1 skipped**.
- Focused WIP/workflow/frontend/health suites — **61 passed**.
- Ruff, frontend rebuild, 600-line budget, and QA surface map pass (**293/293 API surfaces**; 21 unrelated existing
  frontend checklist entries remain).
- Headless Chromium at 1440×900 and 375×812 verifies keyboard select/open, moved-folder relink with live path and
  tab-title refresh, Library **Used in WIPs** reverse navigation into the complete seven-view manuscript workspace,
  zero console errors, zero non-loopback requests, and zero page-level horizontal overflow.

## Next slice

Finish the remaining WIP-9 completeness matrix: remaining browser filters/sorts/context actions, dense accessibility
review, and graduation against every acceptance criterion.
