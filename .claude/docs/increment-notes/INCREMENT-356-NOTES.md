# Increment 356 — WIP context actions and tab reorder parity

## Context

WIP cards supported select/open keyboard behavior, and manuscript tabs could open/close, but the approved MVP also
calls for entity-specific context actions and the tab behaviors already available to Library papers. This increment
closes those interaction-parity gaps without adding new backend authority.

## Implemented

- Right-click or Context Menu/Shift+F10 opens a manuscript-only action surface.
- Connected actions open the workspace, change stage, pause/resume tracking, archive/restore, and rescan files.
  Evidence-producing actions remain in the full workspace so results and errors cannot disappear behind a shortcut.
- Escape/outside interaction closes the menu; position clamps within desktop and mobile viewports.
- Open WIP tabs now use their own drag MIME type and reorder callback, preserving entity separation while matching
  the existing PDF-tab interaction.

## Principles gate

Principles 1, 4, 6, 8, and 10 apply. Context actions mutate only explicit manuscript workflow state, never infer
quality, effort, or completion. The rejected shortcut was adding silent **Run check** or checkpoint commands without
the evidence/result feedback available in the workspace.

## Experience pass

The concrete persona was a keyboard-oriented researcher triaging drafts and arranging several open manuscripts.
They can reach every card action without a pointer and place tabs in their working order while WIP badges and the
separate drag type prevent paper/manuscript ambiguity.

## Manual verification

1. Focus a WIP card and press Space, Enter, then Shift+F10; confirm selection, open, and action-menu behavior.
2. Change stage, pause/resume, archive/restore, and rescan; confirm cards/Details/Activity refresh.
3. Open two WIPs and a paper tab, drag both WIP orders, and confirm paper-tab order/state is unchanged.
4. Close an active WIP tab and confirm the WIP collection becomes active without closing another tab.
5. Repeat menu open/close at desktop/mobile widths and confirm it remains inside the viewport.

## Verification

- `pytest -n auto -q` — **1456 passed, 1 skipped**.
- Focused frontend/WIP suites — **54 passed**.
- Frontend rebuild, 600-line budget, and QA surface map pass (**293/293 API surfaces**; 21 unrelated existing
  frontend checklist entries remain).
- Chromium at 1440×900 and 375×812 verifies keyboard/right-click menus, every connected action, two-tab drag
  reorder, close isolation, zero console errors, zero non-loopback requests, and zero document overflow.

## Next slice

Run the final WIP acceptance matrix and publish the implementation report, documenting repository-driven deviations
such as host tab persistence/pinning not existing for either entity type.
