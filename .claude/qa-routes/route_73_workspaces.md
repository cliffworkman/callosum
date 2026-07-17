<!-- qa-coverage
fe: 04b_workspaces.jsx, 30c_frame.jsx
-->

# ROUTE 73 - Workspaces menu bar (two-level center navigation)

**Tier:** 1 local-stateful (no egress of its own)
**Goal:** Exercise the inc-280 menu bar — the second nav dimension inside the center (Library) pane — and prove it
switches workspaces cleanly, keeps the three panes separate + full-height, nests open PDFs under Library, and that
the relocated tools (Journals/Funding under Discover; Effect-size/Meta-analysis under Extract; Help/Settings as
utility views) work in their new homes. Also covers the inc-284 one-time Library hint that tells returning users
where those relocated tools moved. Pure client navigation; no new API surface.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment) with ≥3 processed papers and ≥1 axis. Register listeners before
navigation. Run once read-write; note the read-only companion behavior (write workspaces hidden).

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **The menu bar lives inside the center pane; the three panes stay separate + full height.** The left (Axes) +
  right (Details) accordions remain visible and full-height in every workspace; only the center swaps. A menu bar
  spanning the whole app width, or a pane that loses height when switching, is a regression (Medium).
- **Library owns open PDFs.** Opening a PDF lands a sub-tab under **Library** and selects the Library workspace; the
  PDF tab is hidden (not closed) while Discover/Extract/Profile is active, and reappears on return.
- **Active workspace persists** (`callosum.workspace`) across reload; Library is the default on first load.
- **One-time moved-tools hint:** on a read-write instance, the Library workspace shows the thin "New layout" banner
  until dismissed; dismissing writes `callosum.workspaces-whatsnew=1` and it stays gone after reload.
- **Read-only companion:** the write workspaces (Discover, Extract) + their tabs are hidden; Profile + Library show.
  A visible Discover/Extract or moved-tools hint on a read-only instance is High.

## Adversarial checklist

- Rapidly switch Profile→Library→Discover→Extract→Help→Settings and back; confirm no flicker/stuck state, no console
  errors, and each center swaps while the side panes hold.
- Open 2+ PDFs, switch to Discover, switch back to Library → both PDF tabs still there; close one → falls back to the
  Library list, not a blank pane.
- Extract → Workbench "select in PDF": arm a capture → it jumps to Library + opens the paper → select → snaps back to
  Extract with the anchor applied (the cross-workspace capture path).
- Leave the **Settings** workspace → the panes re-read egress state (the old modal-close behavior); no stale "AI off".
- Resize to `375x812`, hard refresh → the menu bar + center are usable; no horizontal overflow.

## Steps

1. Confirm the **menu bar** sits at the top of the center pane: **Profile · Library · Discover · Extract** left,
   **Help · Settings** right. Library is active by default; the left/right accordions are present + full height.
   Confirm the Library workspace shows the one-time "New layout" banner pointing Journals/Funding to Discover,
   Effect-size/Meta-analysis to Extract, and Help/Settings to the menu bar.
2. **Discover** → confirm four sub-tabs **Search · Feed · Journals · Funding**. Select a paper first, then open
   **Journals** / **Funding** → they show the paper-mode (vs the paste/manual mode when nothing is selected).
3. **Extract** → confirm three sub-tabs **Workbench · Effect-size · Meta-analysis**. **Meta-analysis** with a paper
   selected runs its per-paper audit + a source link opens the PDF (the `onOpenPaper` + active-check adapter).
4. **Profile** → the impact dashboard renders (the axis-card 📊 also lands here).
5. **Help** → the help corpus renders as a wide center view (no modal overlay); **Settings** → the settings render as
   a wide center view; both are reached from the menu bar (the sidebar has no `?`/`⚙`).
6. Open a PDF from the Library list → a Library sub-tab; switch to Discover → the PDF tab is hidden; return → it's
   back. Reload → the last workspace is restored.
7. Return to Library, click the banner's **Dismiss** button, and reload. Confirm the banner is gone and
   `localStorage.getItem("callosum.workspaces-whatsnew") === "1"`.

## Pass criteria

- All six workspaces switch cleanly; 0 console/page errors; the three panes stay separate + full-height throughout.
- Relocated tools work in their new homes (Journals/Funding read the selection; Meta opens the PDF; Effect-size runs).
- Help + Settings render as center views; the sidebar header shows only the brand.
- Open PDFs nest under Library + persist; the active workspace persists across reload; read-only hides the write
  workspaces and the moved-tools hint. The cross-workspace Extract capture round-trips.
- The moved-tools hint appears once on read-write Library, dismisses cleanly, persists dismissal across reload, and
  does not return after workspace switching.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_73_workspaces.md` + `screenshots/` (see `_TEMPLATE.md`).
