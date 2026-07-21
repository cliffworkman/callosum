# Increment 315 — METHODS pane regroup: Details / Data / Statistics / Checklists

## Context
The user asked for a "slight restructuring of the METHODS panel": rename "Data consistency (GRIM)" → "Data" and
"Statistics check" → "Statistics" in place, and fold the 4 reporting-completeness auditors (Transparency,
Mixed-model, Bayesian, Meta-analysis) — previously 4 independent top-level accordion sections — into one new
"Checklists" section, presented as a 2×2 grid of tabs in the requested read order (Transparency, Mixed-Models,
Bayesian, Meta-Analysis). Planned (plan mode, self-initiated per CLAUDE.md rule #1 — architectural, 6+ files)
before touching code.

## The bug the plan caught before writing any code
`08d_methods_bayes.jsx`/`08f_methods_lmm.jsx`/`08g_methods_metaanalysis.jsx`/`08h_methods_transparency.jsx` each
gated their own per-paper auto-run on `active={ctx.methodsOpen === "<own-id>"}`. `ctx.methodsOpen` reflects the
open accordion **section** id — once these four become tabs inside one `checklists` section, `ctx.methodsOpen`
reads `"checklists"` regardless of which tab is selected, so `=== "bayes"` etc. would never be true again,
silently killing every tool's auto-run. Found by grepping all 6 files for `methodsOpen` usage before writing
any implementation.

## Implemented
1. **Renames, no structural change:** `07_methods_grim.jsx`'s section label → "Data" (id `grim`, order 20
   unchanged); `06_methods_statcheck.jsx`'s → "Statistics" (id `statcheck`, order 30 unchanged). A dead-but-inert
   duplicate host label in `09_placeholders.jsx`'s `registerPaneTab` call (never authoritative — `06_methods_
   statcheck.jsx`'s `registerPaneSection` always loads first and marks the section `defined`) was kept in sync
   for consistency (rule #5 spirit).
2. **`PaneAccordion` now threads a real visibility bool into every render** (`05_panes.jsx`): multi-tab bodies get
   `t.render(ctx, s.id === active && t.id === at)`, the single-tab branch gets `tabs[0].render(ctx, s.id ===
   active)` — mirrors `WorkspacePane`'s existing `render(ctx, active)` contract exactly, no new pattern invented.
   `statcheck`/`grim`/`details` are untouched (their own `ctx.methodsOpen === id` checks stay correct).
3. **The 4 checklist tools converted from `registerPaneSection` to `registerPaneTab`** against one shared host
   (`{id:"checklists", label:"Checklists", paneId:"methods", order:40}`), each dropping its internal
   `ctx.methodsOpen === "..."` derivation for a real `active` prop threaded from step 2: `transparency` → tab
   order 10 (top-left), `lmm` → order 20 (top-right), `bayes` → order 30 (bottom-left), `meta` → order 40
   (bottom-right) — the grid reads in the requested Transparency/Mixed-model/Bayesian/Meta-analysis order.
4. **The 2×2 grid is CSS-only**, via a new generic per-section `pane-tabs-<id>` className hook on the tab strip
   (zero effect on any other multi-tab section, e.g. Axes/Tags or Statistics/More-checks, since no matching rule
   targets them): `.pane-tabs.pane-tabs-checklists { display:grid; grid-template-columns: repeat(2, minmax(0,
   1fr)); gap:4px; }` + `.app.mobile .pane-tabs-checklists { grid-template-columns: 1fr; }`.

## Key technical detail
The grid rule had to be a **compound selector** (`.pane-tabs.pane-tabs-checklists`), not the bare
`.pane-tabs-checklists` the plan originally specified. `.tags-srcfilter { display: flex; ... }` (styles.css:446)
shares the same 1-class specificity and is declared *after* the new rule in source order, so with equal
specificity the later declaration won — the grid rule was silently overridden and the Checklists tab strip
rendered as a cramped 4-across flex row (all viewport widths, not just mobile). Caught by an actual Playwright
screenshot at both viewports, not a static read — a static diff of the CSS text would have looked correct.
Fixed by raising specificity above `.tags-srcfilter`'s regardless of source order, rather than reordering rules
(the more robust fix — it survives a future rule inserted between them).

## Manual verification (Playwright, this session, against the real ~250-paper testing DB)
1. Confirmed exactly 4 top-level METHODS accordion headers: **Details / Data / Statistics / Checklists**.
2. Selected a real paper ("Typical is Trustworthy..."), opened Checklists: **Transparency signals** (the
   default-active tab) auto-ran with no manual click, showing its 7-check disclosure tally. Switched to
   **Bayesian statistics**: it auto-ran too (confirming the `active`-prop fix — `ctx.methodsOpen` was
   `"checklists"` throughout, so the old `=== "bayes"` check would have silently failed here). 0 console errors
   at every step.
3. First attempt at the mobile check (375×812) exposed the specificity bug above — all 4 tabs crammed onto one
   row instead of collapsing to 1 column. Fixed per above, rebuilt, re-verified: desktop shows the correct 2×2
   grid (screenshot), mobile collapses cleanly to 1 column with no overflow, and the previously-selected
   Bayesian tab's state survived the resize (mount-but-hide, not remounted).

## Pytest
Full suite **1295 passed, 1 skipped** (up from 1294). `tests/test_frontend_assembly.py` gained
`test_methods_pane_regrouped_details_data_statistics_checklists` (label renames, the `checklists` host + its 4
tabs' ids/labels/orders, the `active`-prop threading in `PaneAccordion` + all 4 merged files, the stale
`ctx.methodsOpen === "..."` checks gone, and the CSS grid rule) and the pre-existing stale
`'id: "meta", label: "Meta-analysis reporting", paneId: "methods", order: 35'` assertion (a standalone-section
literal) was corrected to the new tab literal. `ruff check .` / `ruff format --check .` clean;
`python tools/check_line_budget.py` clean (348 files).

## Gates
- **DESIGN.md (#8):** "Side-pane ordering" rewritten for Details/Data/Statistics/Checklists; "Tabs within a
  section or workspace" documents the new `pane-tabs-<id>` hook and the `render(ctx, isVisible)` contract
  extension, including the "don't re-derive from `ctx.methodsOpen`" warning for future tab-owning components.
- **QA (#10):** 9 routes updated — `route_00` (header list), `route_33`/`route_37` (label-only), `route_59`/
  `route_61`/`route_62`/`route_63` (navigation → Checklists → tab, + the active-prop-not-methodsOpen assertion),
  `route_70` (2×2 grid + mobile-collapse walk), `route_73` (stale "Statistics check"/"Bayesian statistics"
  top-level mention corrected).
- **Principles (#9):** pure navigation/layout restructuring — no change to any tool's evidence, verification, or
  egress posture; not gated beyond the design/QA passes above.

## Next
None outstanding from this restructure.
