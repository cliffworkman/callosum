# Increment 280 — Workspaces: a two-level center navigation (menu bar)

A structural IA change: the center pane's flat tab strip (**Library | Discover | Feed | Extract | open-PDFs |
My-Pubs**) becomes a **two-level** navigation — a **menu bar of workspaces** *inside the center (Library) pane*
above a per-workspace sub-tab strip. A **second nav dimension**: the menu bar = *what you're doing* (workspaces);
the THEORY/METHODS side accordions stay = *lenses on the current paper*. Design + plan:
`.claude/backups/plans/2026-07-16_workspaces-nav.md`. Branch `feature/workspaces-nav`.

## Implemented (4 stages, one commit group each)

**Stage 1 — the shell.** New workspace registry `app/frontend/js/04b_workspaces.jsx` (`registerWorkspace` /
`registerWorkspaceTab` / `workspaces` / `workspaceTabs` / `getWorkspace` + `MenuBar` + `WorkspacePane`), a near-mirror
of `05_panes.jsx`'s pane registry (sections-are-data). Core workspaces: **Profile · Library · Discover · Extract**
(Library default; Discover = Search·Feed, Extract = Workbench). `30c_frame.jsx::LibraryFrame` became the **Library
workspace body** (list + open-PDF sub-tabs + Read toggle); the Discover/Feed/Extract fixed buttons + the My-Pubs
dashboard tab left it. The Extract "select-in-PDF" capture (inc 255) **hoisted to the shell** (40_app) since Extract
and the Library PDF tabs are now different workspaces — arming opens the paper under Library, applying snaps back to
Extract. My Publications → the **Profile** workspace. `40_app.jsx`: `activeWorkspace` state (persisted `callosum.workspace`)
+ a `gotoLibrary` wrapper so library-list navigations switch to Library; the center mounts all workspaces
(mount-but-hide). **Per feedback the menu bar lives INSIDE the center pane** (not app-wide) — the three panes stay
separate + full height (`.app` single grid row; `.menubar` a `flex:0 0 auto` bar atop `.workspace-frame`). Brand text
dropped.

**Stage 2 — relocations.** Four sections swapped `registerPaneSection` → `registerWorkspaceTab`, render reused:
Journals (`08e`, was THEORY "Where to submit") + Funding (`08k`, was THEORY "Funding Discovery") → **Discover**;
Effect-size (`08i`) + Meta-analysis (`08g`, was METHODS) → **Extract**. So Discover = Search·Feed·Journals·Funding,
Extract = Workbench·Effect-size·Meta-analysis. `workspaceCtx` gained `selectedPaper` + `onOpenPaper` (the relocated
renders read them). THEORY lost 2 sections, METHODS lost 2.

**Stage 3 — Help + Settings as center views.** `HelpModal`/`SettingsModal` → `HelpView`/`SettingsView` (overlay + ×
dropped), registered as right-aligned **utility** workspaces (`utility: true`), lazy-mounted + scrolling in a
`.workspace-view`. The `?`/`⚙` left the Sidebar header (menu bar owns them). Modal state retired;
`onOpenSettings`/`onOpenHelp` → `selectWorkspace`; **leaving** the Settings workspace bumps `settingsNonce` (the old
modal-close egress re-read, inc 148).

**Stage 4 — docs + QA + experience.** Help corpus brought current ("Finding your way around" rewritten for the menu
bar; the 4 moved-section locations + the "gear in the sidebar" fixed). QA **route 73** (workspace surfaces → 0
uncovered FE). DESIGN.md §5 gained the workspace-model note + menu-bar recipe. This note + changes.md + CLAUDE.md.

## Key technical detail

- **Two registries, one philosophy.** The workspace registry mirrors `05_panes.jsx` exactly (idempotent by id,
  order-sorted, `hideInReadOnly`, mount-but-hide bodies). A workspace with 0 registered tabs is **shell-rendered**
  (Library/Profile/Help/Settings — 40_app supplies the bespoke body); a workspace with ≥1 tab renders its
  `.tags-srcfilter` sub-tab strip via `WorkspacePane`. Read-only hides a workspace whose every tab is `hideInReadOnly`.
- **The relocations are one line each** because the sections already render center-agnostically. The only adapters:
  `workspaceCtx` gained `selectedPaper`/`onOpenPaper`, and Meta's active-check rides `{...ctx, methodsOpen: active ?
  "meta" : null}` (the `active` 2nd render arg of `WorkspacePane`) so `MetaSection` is unchanged.
- **esbuild tree-shakes** unused declarations — the registry was stripped from the build until 40_app referenced it
  (the raw-assembly assembly test is the right gate, not the built HTML).

## Experience pass (rule #11) — inhabited, "returning user re-finding a moved tool"

Goal-in-the-moment: *"I used 'Where to submit' from the left panel last week — where did it go?"* Walk:
- **Reception:** the left panel no longer lists Where-to-submit / Funding / Effect-size / Meta — a moment of "where
  did it go?" But the menu bar's **Discover** / **Extract** are plausible homes, and the tools are one click in. The
  **rename** (Where to submit → **Journals**) is the main re-learning cost — a user searching by the old name won't
  see it; mitigated by the help corpus ("Journals (formerly Where to submit)") + the sensible grouping.
- **Help/Settings** moved from the `?`/`⚙` icons to **text labels** on the menu bar — a net *improvement* in
  discoverability (label > glyph).
- **Intended use:** once found, every tool works unchanged (same components); the panes persist (no layout jump).
  No dead-ends. **Finding (minor, backlogged):** returning users pay a one-time re-learning cost for the moved/renamed
  tools — worth a future one-time "what moved" hint or a Where-to-submit alias; not blocking, and the renames were the
  user's explicit choice.

## Manual verification script (UI — OWED; no browser automation in-session; the user is verifying hands-on)

Start the app (`:8888`). Confirm: the **menu bar** inside the center pane (Profile·Library·Discover·Extract + Help·Settings
right); the left/right accordions stay separate + full height; **Discover** shows Search·Feed·Journals·Funding;
**Extract** shows Workbench·Effect-size·Meta-analysis; **Profile** = the dashboard; **Help**/**Settings** render as
wide center views (no `?`/`⚙` in the sidebar); open a PDF → a **Library** sub-tab that hides under other workspaces +
persists; the Extract → select-in-PDF capture round-trips; leaving Settings clears an "AI off" nudge; the active
workspace survives reload.

## Pytest

Full suite **1236 passed, 1 skipped** (the 1 failure — `test_funding_discovery.py`'s pinned `label: "Funding
Discovery"`/`order: 31` — updated to the relocated `Funding`/`order: 40`). `test_frontend_assembly.py` extended with
the workspace-structure guard (registry + menu bar + the 4 core + the relocated tabs + Help/Settings views, and the
old pane-section registrations absent). QA surface map: 0 uncovered (API + FE).
