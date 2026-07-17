<!-- qa-coverage
fe: 03_library.jsx, 04b_workspaces.jsx, 08b_methods_citation_equity.jsx, 08c_methods_citation_context.jsx, 08g_methods_metaanalysis.jsx, 08i_methods_effectsize.jsx, 08j_reference_integrity.jsx, 10_pdf_layer.jsx, 15_axes.jsx, 15b_axis_card.jsx, 20_synthesis.jsx, 30c_frame.jsx, 30d_discover.jsx, 30e_feed.jsx, 31_mypubs_dashboard.jsx, 37_cite.jsx, 38_credit.jsx, 40_app.jsx
-->

# ROUTE 73 - Workspaces menu bar (two-level center navigation)

**Tier:** 1 local-stateful (no egress of its own)
**Goal:** Exercise the inc-280/286 menu bar — the second nav dimension inside the center (Library) pane — and prove it
switches workspaces cleanly, keeps the three panes separate + full-height, nests open PDFs under Library with the
selected-paper pre-open affordance + draggable open-PDF tab order, and that
the relocated tools (Synthesis as its own workspace; Wanted/Gaps/Overlooked/Search/Feed/Journals/Funding under
Discover; Cite/Meta Reference List/Citation Concentration/How-it's-cited/CRediT under Work; Effect-Size/Meta-Analysis
under Extract; My Publications in the menu bar; Help/Settings as utility views) work in their new homes. Also covers the inc-284/286 one-time Library
hint that tells returning users where those relocated tools moved. Pure client navigation; no new API surface.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment) with ≥3 processed papers and ≥1 axis. Register listeners before
navigation. Run once read-write; note the read-only companion behavior (write-only workspaces/tabs hidden).

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **The menu bar lives inside the center pane; the three panes stay separate + full height.** The left (Axes) +
  right (Details) accordions remain visible and full-height in every workspace; only the center swaps. A menu bar
  spanning the whole app width, or a pane that loses height when switching, is a regression (Medium).
- **Library owns selected + open PDFs.** Selecting a paper without opening it shows a pinned, distinct selected-paper
  tab immediately after **Library**; clicking it opens the PDF. Once opened, the selected-paper tab disappears and a
  normal PDF tab appears. Open PDF tabs can be dragged to reorder them; the selected-paper tab stays pinned and is
  not draggable.
- **Library owns open PDFs.** Opening a PDF lands a sub-tab under **Library** and selects the Library workspace; the
  PDF tab is hidden (not closed) while Discover/Extract/My Publications is active, and reappears on return.
- **Discover carries selected-paper context where it matters.** In Discover → Journals/Funding, the selected paper is
  shown before the Discover sub-tabs using the Library tab visual language: dashed selected-paper styling when not
  open, normal open-PDF tab styling when already open. Search stays just Search/Wanted/Gaps/Overlooked + Feed.
- **Workspace subsection scroll.** Long Discover/Extract sub-tabs scroll inside their active body; their tab strip and
  the menu bar remain fixed.
- **Active workspace persists** (`callosum.workspace`) across reload; Library is the default on first load.
- **One-time moved-tools hint:** on a read-write instance, the Library workspace shows the thin "New layout" banner
  until dismissed; dismissing writes `callosum.workspaces-whatsnew=1` and it stays gone after reload.
- **Read-only companion:** write-only workspaces/tabs (Discover, Extract, Work → CRediT and paper-audit Cite tabs) are
  hidden; Profile, Library, Synthesis history, and Work → Cite → Suggest show. A visible moved-tools hint on a
  read-only instance is High.

## Adversarial checklist

- Rapidly switch My Publications→Library→Synthesis→Discover→Work→Extract→Help→Settings and back; confirm no flicker/stuck state, no console
  errors, and each center swaps while the side panes hold.
- Select a paper but do not open it → the selected-paper tab appears after **Library**; click it → the PDF opens and
  the selected-paper tab disappears. With a selected-but-unopened paper, switch to Discover → Journals/Funding and
  confirm the same dashed cue appears before the Discover sub-tabs.
- Open 2+ PDFs, drag their PDF tabs to reorder them, switch to Discover, switch back to Library → both PDF tabs still
  there in the chosen order; in Journals/Funding the selected-open paper cue uses the normal open-PDF tab style and
  clicking it returns to the Library reader tab. Close one → falls back to the Library list, not a blank pane.
- Extract → Workbench "select in PDF": arm a capture → it jumps to Library + opens the paper → select → snaps back to
  Extract with the anchor applied (the cross-workspace capture path).
- Leave the **Settings** workspace → the panes re-read egress state (the old modal-close behavior); no stale "AI off".
- Resize to `375x812`, hard refresh → the menu bar + center are usable; no horizontal overflow.

## Steps

1. Confirm the **menu bar** sits at the top of the center pane: **My Publications · Library · Synthesis · Discover · Work · Extract** left,
   **Help · Settings** right. Library is active by default; the left/right accordions are present + full height.
   Confirm the Library workspace shows the one-time "New layout" banner pointing Synthesis to the menu bar,
   Cite/Meta Reference List/CRediT to Work, Discover tools to Discover Search, and Effect-Size/Meta-Analysis to Extract.
2. **Discover** → confirm three sub-tabs **Search · Journals · Funding**. In **Search**, confirm the search row has
   **Search**, **Wanted**, **Gaps**, and **Overlooked** buttons styled identically; click each discovery button and
   confirm it opens its existing modal. Confirm **Feed** appears below the Search results area, not as its own sub-tab.
   Select a paper first, then open **Journals** / **Funding** → they show the paper-mode (vs the paste/manual mode
   when nothing is selected). With the selected paper not yet open, confirm **Journals** and **Funding** show the
   dashed selected-paper cue before **Search · Journals · Funding**; click it and confirm it opens the PDF. Return to
   Discover → Journals/Funding with that paper open and confirm the cue now uses the normal open-PDF tab styling and
   clicks back to the reader. Confirm **Search** does not show this cue. With enough content to overflow, confirm each
   body scrolls vertically without moving the Discover sub-tab strip.
3. **Synthesis** → ask a small query or use Library selection **summarize**; confirm the workspace opens and the
   history/result state stays mounted when switching away and back.
4. **Work** → confirm sub-tabs **Cite · CRediT statement**. Inside **Cite**, confirm nested tabs
   **Suggest · Meta Reference List · Citation concentration · How it's cited**. With a selected paper, click a
   Library **ref signal** badge and confirm it jumps directly to **Work → Cite → Meta Reference List**.
5. **Extract** → confirm three sub-tabs **Workbench · Effect-Size · Meta-Analysis**. **Meta-Analysis** with a paper
   selected runs its per-paper audit + a source link opens the PDF (the `onOpenPaper` + active-check adapter). Confirm
   Effect-Size and Meta-Analysis bodies scroll vertically if their content overflows.
6. **My Publications** → the impact dashboard renders from the menu bar. After **Settings → My Publications → Refresh**,
   return here and confirm the dashboard and publications list populate without using the Axes card; the old axis-card
   dashboard/profile button is absent.
7. **Help** → the help corpus renders as a wide center view (no modal overlay); **Settings** → the settings render as
   a wide center view; both are reached from the menu bar (the sidebar has no `?`/`⚙`).
8. Select a Library paper without opening it → a distinct selected-paper tab appears immediately after **Library**.
   Click that tab → it opens the PDF through the normal reader path and the selected-paper tab disappears. Open a
   second PDF, drag the open PDF tabs to reorder them, then switch to Discover → the PDF tabs are hidden; return →
   they are back in the chosen order. Reload → the last workspace is restored.
9. Return to Library, click the banner's **Dismiss** button, and reload. Confirm the banner is gone and
   `localStorage.getItem("callosum.workspaces-whatsnew") === "1"`.

## Pass criteria

- All primary workspaces plus Help/Settings switch cleanly; 0 console/page errors; the three panes stay separate +
  full-height throughout.
- Relocated tools work in their new homes (Wanted/Gaps/Overlooked open from Discover Search; Feed appears below
  Search results; Synthesis opens from the menu and selection summarize; Work → Cite owns Suggest/Meta Reference
  List/Citation Concentration/How-it's-cited; Work → CRediT opens; Journals/Funding read the selection; Meta opens
  the PDF; Effect-Size runs).
- Long Journals, Funding, Effect-Size, and Meta-Analysis bodies scroll inside their workspace body without moving the
  menu bar or sub-tab strip.
- Help + Settings render as center views; the sidebar header shows only the brand.
- Selected-but-unopened papers show the pinned selected-paper tab; clicking it opens the PDF; open PDF tabs nest under
  Library, reorder by drag, and persist. Discover → Journals/Funding reuse that selected/open paper cue before their
  sub-tabs and click through to the reader. The active workspace persists across reload; read-only hides the write
  workspaces and the moved-tools hint. The cross-workspace Extract capture round-trips.
- The moved-tools hint appears once on read-write Library, dismisses cleanly, persists dismissal across reload, and
  does not return after workspace switching.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_73_workspaces.md` + `screenshots/` (see `_TEMPLATE.md`).
