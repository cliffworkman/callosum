# Increment 283 — DESIGN §5 workspace/lens rewrite

Task 1 from the Codex handoff: rewrite `.claude/DESIGN.md` §5 so the inc-280 workspace menu bar is documented as
the shipped architecture, not an interim note attached to the older THEORY/METHODS accordion rubric. Branch:
`feature/workspaces-ux-polish`.

## Implemented

- `.claude/DESIGN.md` §5 now describes the two navigation dimensions as one model:
  - **Workspaces** are center-pane modes of work: Profile / Library / Discover / Extract, plus Help / Settings
    utilities. Outward-facing, generative, cross-paper, or wide-output tools belong here.
  - **THEORY / METHODS side accordions** are lenses on the selected paper. Per-paper interpretation, citation,
    details, method checks, and review workflows stay here.
- Folded the placement rubric into one question: **is the user entering a mode, or applying a lens to the current
  paper?**
- Preserved the concrete shipped mechanics from `04b_workspaces.jsx` and `05_panes.jsx`: `registerWorkspace`,
  `registerWorkspaceTab`, `MenuBar`, `WorkspacePane`, `registerPaneSection`, `registerPaneTab`, persisted layout
  keys, read-only hiding, tab metadata ownership, mount-but-hide bodies, and the esbuild registration gotcha.
- Preserved the existing recipes: `.menubar` token use, `.menubar-item.active` accent semantics,
  `.workspace-tabs` / `.pane-tabs` on the shared `.tags-srcfilter` segmented strip, `.pane-tab` mount-but-hide,
  accordion body scrolling, coming-soon stubs, AI/finding honesty contracts, and accessibility rules.
- Removed the old "interim record / stage-4 task" framing. No CSS or application code changed.

## Key technical detail

The rewrite is documentation-only but was checked against the shipped registry code. `04b_workspaces.jsx` owns the
center menu-bar dimension and mirrors the data-driven registry pattern from `05_panes.jsx`; `05_panes.jsx` remains
the side-accordion lens registry. The DESIGN text now names that split directly and keeps the placement rule tied to
the user's cognitive task rather than implementation category.

## Manual verification script

Static documentation verification: read `.claude/DESIGN.md` §5 beside `app/frontend/js/04b_workspaces.jsx` and
`app/frontend/js/05_panes.jsx`. Confirm that every documented registry function, layout key, tab recipe, read-only
hiding rule, and mount-but-hide behavior matches the code. No browser verification applies because this increment
does not alter frontend source or built assets.

## Pytest

Full suite: **1237 passed, 1 skipped** in 18:50.

Additional gates: `ruff check .`, `ruff format --check .`, and `python tools/check_line_budget.py` clean.

## Not done

Task 2, the optional one-time "what moved" Library hint, was not started in this increment. It remains a separate
frontend change requiring `tools/build_frontend.py`, `tests/test_frontend_assembly.py`, the full suite, and a visual
placement caveat.
