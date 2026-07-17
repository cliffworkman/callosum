# Increment 284 — One-time workspace "what moved" hint

Task 2 from the Codex handoff: add a small, dismissible Library workspace hint for returning users who are re-finding
tools moved by the inc-280 workspace navigation. Branch: `feature/workspaces-ux-polish`.

## Implemented

- `app/frontend/js/30c_frame.jsx`: added `WorkspacesWhatsNewHint` at the top of `LibraryFrame`, above the frame tabs.
  The hint tells users:
  - **Where to submit** + **Funding** are now under **Discover**.
  - **Effect-size** + **Meta-analysis** are under **Extract**.
  - **Help** + **Settings** are on the menu bar.
- One-time behavior uses the existing `_loadLayout` / `_saveLayout` helpers from `04_layout.jsx` and the key
  `callosum.workspaces-whatsnew`. Dismissing writes `"1"` and hides the banner for future loads.
- The hint renders only when `readOnly === false`, so the read-only companion does not show a relocation prompt for
  write-oriented workspaces it hides.
- `app/frontend/styles.css`: added a thin neutral `.workspace-whatsnew` banner using existing tokens only
  (`--panel-2`, `--line`, `--ink-2`) plus the canonical `.btn-icon` dismiss button recipe.
- `tests/test_frontend_assembly.py`: extended the workspace assembly guard to assert the hint copy, localStorage key,
  component, and persisted dismissal write are present.
- `.claude/qa-routes/route_73_workspaces.md`: extended the existing workspace route to cover banner visibility,
  dismissal, reload persistence, and read-only absence.
- `callosum-app.html`: rebuilt with `python tools/build_frontend.py`.

## Key technical detail

The banner lives in `LibraryFrame` because the Library workspace body owns the frame tabs and paper list. It is
stateful but local-only: no API, no backend state, and no new data path. Using `readOnly === false` intentionally
waits for `/health` before showing the banner, avoiding a brief read-only flash while health is still unresolved.

## Experience pass

Persona: returning user / migrator re-finding moved tools after the workspace navigation change.

Reception: the banner appears exactly at the point of confusion, before the Library tabs, and names both the old tool
name ("Where to submit") and the new destinations. The next step is obvious: click Discover or Extract in the menu
bar, or use Help/Settings directly from the same bar.

Intended use: the banner is useful once and then should get out of the way. The dismiss button makes that path
explicit, and persistence prevents repeated interruption. No ethics/principles issue: it is navigation help, not a
claim or signal about the literature.

Finding: fix-now complete. No backlog item needed. **Visual placement is unverified in-browser**; static checks only
confirm source/build presence and QA route coverage.

## Manual verification script

Start the app on a read-write instance, clear `localStorage.removeItem("callosum.workspaces-whatsnew")`, and open
Library. Confirm the thin banner appears above the Library frame tabs, points the moved tools to Discover/Extract and
Help/Settings to the menu bar, and does not occlude the frame tabs or list. Click dismiss, reload, and confirm the
banner stays hidden with `localStorage.getItem("callosum.workspaces-whatsnew") === "1"`. Repeat on a read-only
companion and confirm the banner does not appear. **Not run in this session; visual placement owed.**

## Pytest

Targeted: `tests/test_frontend_assembly.py` **21 passed**.

Full suite on final formatted tree: **1237 passed, 1 skipped** in 28:59.

Additional gates: `python tools/build_frontend.py` rebuilt `callosum-app.html`; `python
tools/qa/build_surface_map.py check` reported **245/245 API** and **1143/1143 FE** covered; `ruff check .`,
`ruff format --check .`, and `python tools/check_line_budget.py` clean.
