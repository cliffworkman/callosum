<!-- qa-coverage
api: POST /library/credit/status
fe: 03_library.jsx, 04b_workspaces.jsx, 05_method_credit.jsx, 08b_methods_citation_equity.jsx, 08c_methods_citation_context.jsx, 08i_methods_effectsize.jsx, 08j_reference_integrity.jsx, 08x_methods_critical.jsx, 10_pdf_layer.jsx, 10b_libmenus.jsx, 10d_papercard.jsx, 15_axes.jsx, 15b_axis_card.jsx, 20_synthesis.jsx, 25_detail.jsx, 30c_frame.jsx, 30d_discover.jsx, 30e_feed.jsx, 31_mypubs_dashboard.jsx, 37_cite.jsx, 37b_meta_reference.jsx, 38_credit.jsx, 40_app.jsx, 45_workbench.jsx
-->

# ROUTE 73 - Workspaces menu bar (two-level center navigation)

**Tier:** 1 local-stateful (no egress of its own)
**Goal:** Exercise the menu bar — the second nav dimension inside the center (Library) pane — and prove it
switches workspaces cleanly, keeps the three panes separate + full-height, nests open PDFs under Library with the
selected-paper pre-open affordance + draggable open-PDF tab order, and that the relocated tools (Synthesize as its
own workspace with Ask/Critique; Feed/Search/Wanted/Gaps/Overlooked/Journals/Funding under Discover; Cite/
Meta-Reference/CRediT/Meta-Analyze under Work — Extract was folded into Work in a later reorg, with Effect-Size
folded further into Meta-Analyze as a subsection of Workbench, and Meta-Analysis relocated into the METHODS
accordion (`08g_methods_metaanalysis.jsx`, covered by route_62) rather than staying under Work; My Publications in
the menu bar; Help/Settings as utility views) work in their new homes. Also covers the one-time Library hint that
tells returning users where relocated tools moved. Pure client navigation; no new API surface.

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
  PDF tab is hidden (not closed) while Discover/Work/My Publications is active, and reappears on return.
- **Discover carries selected-paper context where it matters.** Discover sub-tabs appear in the order
  **Feed · Search · Journals · Funding**. In Discover → Journals/Funding, the selected paper is
  shown before the Discover sub-tabs using the Library tab visual language: dashed selected-paper styling when not
  open, normal open-PDF tab styling when already open. Search stays just Search/Wanted/Gaps/Overlooked.
- **Retractions are registry signals with evidence.** The Library header includes **Retractions ↻** before
  **Text Health**. Running it refreshes the Retraction Watch mirror when available, falls back to the existing mirror
  when unavailable, and surfaces retracted papers as noninteractive **RETRACTED** badges on cards/details plus the
  evidence-bearing signal row in **Synthesize → Critique**'s Tier-1 backbone (route 39/67).
- **Credit buttons are honest about existing sources.** The shared lineage buttons say **＋ add missing to library**
  while any DOI-backed source is absent, say **✓ added to library** when all DOI-backed sources are already present,
  and import only missing items in partial multi-source cases.
- **Workspace subsection scroll.** Long Discover/Work sub-tabs scroll inside their active body; their tab strip and
  the menu bar remain fixed.
- **Active workspace persists** (`callosum.workspace`) across reload; Library is the default on first load.
- **One-time moved-tools hint:** on a read-write instance, the Library workspace shows the thin "New layout" banner
  until dismissed; dismissing writes `callosum.workspaces-whatsnew=1` and it stays gone after reload.
- **Read-only companion:** write-only workspaces/tabs (Discover, Synthesize → Critique, Work → Meta-Reference,
  Work → CRediT, Work → Meta-Analyze) are hidden; Profile, Library, Synthesize → Ask history, and Work → Cite show.
  A visible moved-tools hint on a read-only instance is High.

## Adversarial checklist

- Rapidly switch My Publications→Library→Synthesize→Discover→Work→Help→Settings and back; confirm no flicker/stuck state, no console
  errors, and each center swaps while the side panes hold.
- Select a paper but do not open it → the selected-paper tab appears after **Library**; click it → the PDF opens and
  the selected-paper tab disappears. With a selected-but-unopened paper, switch to Discover → Journals/Funding and
  confirm the same dashed cue appears before the Discover sub-tabs.
- Open 2+ PDFs, drag their PDF tabs to reorder them, switch to Discover, switch back to Library → both PDF tabs still
  there in the chosen order; in Journals/Funding the selected-open paper cue uses the normal open-PDF tab style and
  clicking it returns to the Library reader tab. Close one → falls back to the Library list, not a blank pane.
- Work → Meta-Analyze → Workbench "select in PDF": arm a capture → it jumps to Library + opens the paper → select →
  snaps back to Work → Meta-Analyze with the anchor applied (the cross-workspace capture path).
- Leave the **Settings** workspace → the panes re-read egress state (the old modal-close behavior); no stale "AI off".
- Resize to `375x812`, hard refresh → the menu bar + center are usable; no horizontal overflow.
- At `375x812`, confirm the desktop workspace tab strip is replaced by a compact **Workspace** select in the center
  region; choosing My Publications / Library / Synthesize / Discover / Work / Help / Settings switches
  the active workspace without horizontal overflow.

## Steps

1. Confirm the **menu bar** sits at the top of the center pane: **My Publications · Library · Synthesize · Discover · Work** left,
   **Help · Settings** right (no **Extract** — folded into Work). Library is active by default; the left/right
   accordions are present + full height. Confirm the Library workspace shows the one-time "New layout" banner
   pointing Synthesize to the menu bar, Cite/Meta-Reference/CRediT/Meta-Analyze to Work, and Discover tools to
   Discover Search. Resize to phone width and confirm that same workspace list is reachable from the **Workspace**
   dropdown, grouped into Workspaces and Utilities, while the bottom mobile nav still switches only **Library /
   Panels / Details**.
2. **Discover** → confirm four sub-tabs **Feed · Search · Journals · Funding**. In **Feed**, confirm the standalone
   Feed controls render there and not inside Search. In **Search**, confirm the search row has
   **Search**, **Clear ×**, **Recent searches**, **Clear history**, **Wanted**, **Gaps**, and **Overlooked** controls;
   click each discovery button and confirm it opens its existing modal. Run two searches, recall the first from
   **Recent searches**, and confirm it re-runs; **Clear ×** empties the active Search query/results and **Clear
   history** removes the local recall list. Confirm **Feed** does not appear below the Search results area.
   Select a paper first, then open **Journals** / **Funding** → they show the paper-mode (vs the paste/manual mode
   when nothing is selected). With the selected paper not yet open, confirm **Journals** and **Funding** show the
   dashed selected-paper cue before **Feed · Search · Journals · Funding**; click it and confirm it opens the PDF. Return to
   Discover → Journals/Funding with that paper open and confirm the cue now uses the normal open-PDF tab styling and
   clicks back to the reader. In **Journals**, run a selected-paper search and a pasted abstract+subject search, then
   recall both from **Recent journal searches** and confirm each re-runs its stored input shape; **Clear history**
   removes that local list. Confirm **Search** does not show this cue. With enough content to overflow, confirm each
   body scrolls vertically without moving the Discover sub-tab strip.
3. **Synthesize** → confirm sub-tabs **Ask · Critique**. In **Ask**, ask a small query or use Library selection
   **summarize**; confirm the workspace opens to Ask and the history/result state stays mounted when switching away
   and back. In **Critique**, select a processed paper and confirm the single-paper critical-read surface auto-runs
   there, not in the METHODS accordion.
4. **Work** → confirm four sub-tabs, in order: **Cite · Meta-Reference · CRediT · Meta-Analyze**.
   - **Cite** renders the Suggest tool directly (no inner tab strip — the nested Cite pane-tabs were removed in
     the reorg).
   - **Meta-Reference** shows **5** stacked subsections on one scrollable panel (a heading + a divider between
     each, no tab-switching): Meta Reference List, Citation concentration, Overlooked work, How it's cited, and
     How it cites its sources — the last two were one toggle-switched subsection before 2026-07-20 and are now
     independently fetchable (running one doesn't reset the other). With a selected paper, click a Library
     **ref signal** badge and confirm it jumps directly to **Work → Meta-Reference** and scrolls to the Meta
     Reference List subsection. With a paper selected but not open, confirm **Meta-Reference** (and only
     Meta-Reference — not Cite/CRediT/Meta-Analyze) shows the same dashed selected-paper cue as Discover →
     Journals/Funding before the Work sub-tab strip; click it and confirm it opens the PDF, after which the cue
     switches to the normal open-PDF tab styling (route_73 §2's Discover-cue behavior, now shared).
   - **CRediT** (renamed from "CRediT statement") — unchanged internally; confirm the By-author/By-role toggle
     still works.
   - **Meta-Analyze** is the relocated Workbench. Confirm the intro sentence now ends cleanly after "...one study
     at a time." (no more "pooling, heterogeneity, and forest plots..." trailing clause). Scroll down and confirm
     an **Effect-size calculator** subsection appears below the main Workbench content (both in the project
     picker and inside an open project) — this is the former standalone "Effect-Size" tab, now folded in. There is
     **no** Meta-Analysis reporting-auditor tool anywhere in this workspace — it moved to the METHODS accordion
     (see route_62_methods_metaanalysis.md) rather than staying under Work, so it must not appear here as dead UI
     or a broken tab.
5. **My Publications** → the impact dashboard renders from the menu bar. After **Settings → My Publications → Refresh**,
   return here and confirm the dashboard and publications list populate without using the Axes card; the old axis-card
   dashboard/profile button is absent.
6. **Help** → the help corpus renders as a wide center view (no modal overlay); **Settings** → the settings render as
   a wide center view; both are reached from the menu bar (the sidebar has no `?`/`⚙`).
7. Select a Library paper without opening it → a distinct selected-paper tab appears immediately after **Library**.
   Click that tab → it opens the PDF through the normal reader path and the selected-paper tab disappears. Open a
   second PDF, drag the open PDF tabs to reorder them, then switch to Discover → the PDF tabs are hidden; return →
   they are back in the chosen order. Reload → the last workspace is restored.
8. Return to Library, click the banner's **Dismiss** button, and reload. Confirm the banner is gone and
   `localStorage.getItem("callosum.workspaces-whatsnew") === "1"`.
9. In the Library header, confirm **Retractions ↻** appears after **Metadata ↻** and before **Text Health** with the
    same `.trash-toggle` visual recipe. Run it on a fixture with at least one registry-hit paper if available; confirm
    the button tooltip gains a last-refreshed summary, fallback text appears if Retraction Watch could not refresh,
    the red **⚠ Retracted · N** chip updates, and a retracted paper shows a **RETRACTED** badge on its card and Details
    pane. Open **Synthesize → Critique** for that paper and confirm the source/date/notice evidence is still visible
    (a Tier-1 signal row + notice link) and worded as a signal, not a verdict.
10. Open several lineage surfaces: Methods → Statistics check, Methods → Bayesian statistics, Work → CRediT, Work →
    Meta-Analyze (Effect-size calculator subsection), and Discover → Search → Overlooked. Confirm their
    `.method-credit` buttons use the common **＋ add missing to library** label before import, flip to
    **✓ added to library** when their DOI-backed sources are present, and for multi-source credits do not re-import
    sources already in the library.

## Pass criteria

- All primary workspaces plus Help/Settings switch cleanly; 0 console/page errors; the three panes stay separate +
  full-height throughout.
- On phone-width screens the workspace switcher is a compact **Workspace** select instead of the desktop tab strip,
  and it switches the same visible workspaces/utilities without horizontal overflow.
- Relocated tools work in their new homes (Synthesize has Ask/Critique; Feed is its own Discover tab;
  Wanted/Gaps/Overlooked open from Discover Search; selection summarize opens Synthesize → Ask; single-paper Critical
  Read opens in Synthesize → Critique; Work → Cite renders Suggest directly; Work → Meta-Reference stacks Meta
  Reference List/Citation Concentration/How-it's-cited as subsections; Work → CRediT opens; Work → Meta-Analyze
  is Workbench with the Effect-size calculator folded in as a subsection; Journals/Funding read the selection).
- Long Journals, Funding, and Meta-Analyze (incl. its Effect-size subsection) bodies scroll inside their workspace
  body without moving the menu bar or sub-tab strip.
- Search/Journals recent-history controls are browser-local recall lists that re-run stored inputs, not cached result
  replay. Their Clear history actions do not touch saved papers; Search **Clear ×** empties only the active query and
  results.
- Help + Settings render as center views; the sidebar header shows only the brand.
- Selected-but-unopened papers show the pinned selected-paper tab; clicking it opens the PDF; open PDF tabs nest under
  Library, reorder by drag, and persist. Discover → Journals/Funding and Work → Meta-Reference reuse that selected/open
  paper cue before their sub-tabs and click through to the reader; every other sub-tab (Feed/Search, Cite/CRediT/
  Meta-Analyze) does not show it. The active workspace persists across reload; read-only hides the write
  workspaces and the moved-tools hint. The cross-workspace Work → Meta-Analyze capture round-trips.
- The moved-tools hint appears once on read-write Library, dismisses cleanly, persists dismissal across reload, and
  does not return after workspace switching.
- Retractions can be launched from the Library header; fallback is visible without hard-failing the batch; retracted
  papers show the red **RETRACTED** card/detail badge while Synthesize → Critique keeps the evidence trail inspectable.
- Credit-the-lineage buttons accurately distinguish missing, already-present, and partial multi-source states, and the
  button label never implies a blind import when every credited source is already in the library.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_73_workspaces.md` + `screenshots/` (see `_TEMPLATE.md`).
