# Increment 313 — the Work/Extract reorg, Meta-Analysis returns to METHODS, and the sub-tab-bar CSS saga

## Context
Two workspaces ("Work" and "Extract") had drifted into an unclear split — citation tools on one side, a
meta-analysis workbench on the other, with several citation-integrity tools buried three levels deep as nested
tabs-within-a-tab (`CiteWorkspacePane`'s own `CITE_TABS` registry). This increment makes **Work** the single home
for "producing science" (citing, credit statements, reference-list analysis, meta-analysis prep) and removes a
level of nesting along the way. Separately, mid-verification, the user flagged that the Meta-Analysis reporting
auditor had vanished entirely (it was intentionally staged, not deleted) — asked to finish that follow-up in the
same session rather than leave it staged, so it also moved home this increment, into the METHODS accordion where
its 5 statcheck/GRIM/Bayes/LMM/transparency siblings already live.

## Implemented

**The Work/Extract reorg** (`04b_workspaces.jsx`, `37_cite.jsx`, new `37b_meta_reference.jsx`,
`08j_reference_integrity.jsx`, `08b_methods_citation_equity.jsx`, `08c_methods_citation_context.jsx`,
`38_credit.jsx`, `45_workbench.jsx`, `08i_methods_effectsize.jsx`, `40_app.jsx`):
- **Work** now holds 4 tabs in order: **Cite → Meta-Reference → CRediT → Meta-Analyze**. Extract is deleted as a
  workspace.
- **Cite** renders `CitePane` directly — no more inner tab strip. The whole `CITE_TABS`/`registerCiteTab`/
  `CiteWorkspacePane` nested-tab registry is deleted (it existed solely to drive Cite's now-gone inner tabs).
- **Meta-Reference** is a new thin wrapper (`MetaReferencePane`) stacking `MetaReferenceList`,
  `CitationEquitySection`, and `CitationContextSection` as 3 subsections on one scrollable panel (heading + a
  `.settings-subsection` divider between each, no tab-switching) — reusing the existing Settings-redesign divider
  recipe rather than inventing new spacing (DESIGN.md rule #8).
- **CRediT** is renamed from "CRediT statement"; internals (`CreditSection`, the By-author/By-role toggle)
  untouched.
- **Meta-Analyze** is the relocated `WorkbenchPane`, with `EffectSizeSection` folded in as a subsection at the
  bottom (heading + divider) rather than its own former "Effect-Size" tab — visible in both the project picker and
  an open project, since it takes no props/ctx and shares no state with Workbench. The intro sentence was trimmed
  to end cleanly on "...it extracts and converts one study at a time." (dropped the trailing "— pooling,
  heterogeneity, and forest plots belong to your synthesis tool..." clause per the user's request).
- Two real functional bugs caught and fixed during the sweep, neither part of the original file list: `40_app.jsx`'s
  `captureAnchor` (the Workbench "select-in-PDF" return path) still hardcoded `selectWorkspace("extract")`, and
  `openReferenceWarnings` (the paper-card ref-signal-badge handler) still drove the deleted nested-cite-tab system
  (`requestWorkspaceTab("work","cite")` + the now-gone `requestCiteTab("meta-references")`) — both fixed, and the
  entire dead `citeTabRequest` state/setter/callback plumbing removed after confirming via grep it had no other
  callers. A stray "Extract" reference in `30c_frame.jsx`'s `WorkspacesWhatsNewHint` banner copy was also caught
  and fixed proactively.

**Meta-Analysis moves to the METHODS accordion** (`08g_methods_metaanalysis.jsx`): the reporting auditor
(`MetaSection`/`MetaPaper`/`MetaChecklist`/`MetaCredit`) was originally left unregistered — intentionally staged,
not deleted, with a comment marking it for a future move — because it was Extract's third tab and the user had a
separate, not-yet-detailed plan for where it should land. Mid-session the user asked to finish that move now
rather than leave it staged: added `registerPaneSection({id:"meta", label:"Meta-analysis reporting",
paneId:"methods", order:35, hideInReadOnly:true, render:(ctx)=><MetaSection ctx={ctx}/>})`, matching its 5 METHODS
siblings exactly (`06_methods_statcheck.jsx` order 30, `08d_methods_bayes.jsx` order 32, `08f_methods_lmm.jsx`
order 33, `08h_methods_transparency.jsx` order 36 — order 35 slots it between LMM and transparency). No other
change was needed inside the component — `MetaSection` already read `ctx.methodsOpen === "meta"` to gate its
auto-run, written pane-section-shaped from the start. The order value (35) and section label ("Meta-analysis
reporting") were chosen to match `route_62_methods_metaanalysis.md`, a QA route that had been silently describing
this exact location since an earlier increment and was, until now, quietly wrong.

**Sub-tab-bar CSS fixes** (`styles.css`, earlier in this session): the workspace sub-nav bar (`.workspace-tabs`)
conflated two different row-item roles that need different treatment — plain sub-nav **buttons** (Cite/
Meta-Reference/CRediT/Meta-Analyze, Discover's Feed/Search/etc.) want uniform height, vertically centered; the
**selected/open-PDF file tab** that Discover also shows in this bar wants Library's exact flush-bottom `.frame-tab`
treatment (a real tab, not a button — its shape is a deliberate "this is your open paper" marker). Landed on a
`:has(.workspace-paper-cue)` conditional so the bar switches between the two treatments depending on which kind of
child it holds, plus a fixed 40px bar height propagated from Library to every subheading bar (previously Discover →
Journals ran taller). Diagnosed empirically via Playwright (`getBoundingClientRect` vs Canvas `measureText`
ink-ascent/descent vs raw pixel-scanning) after two rounds of user-caught false "it's fixed" claims — the eventual
root cause was `line-height:normal` computing differently for bold vs regular font-weight even when geometrically
centered.

**Also this session:** `AccountSettings` copy fixed to clarify ORCID sign-in is required (not Google/email); the
Help modal's left TOC sidebar made independently scrollable (`.workspace-view .help-toc { position: sticky; ... }`)
— it was previously clipped, unreachable below "Wanted list".

## Key technical detail
`captureAnchor`'s fix (`selectWorkspace("work")`, no explicit tab request) relies on the workspace pane's
mount-but-hide contract: Work's active sub-tab is `useState` that persists across a round trip through the Library
workspace (arming a capture opens the target PDF under Library), so by the time the user's PDF selection completes
and control returns to Work, it lands back on whichever Work tab was active before — Meta-Analyze, unchanged the
whole time. Verified live: armed capture on a Workbench cell, selected PDF text via a real DOM selection + a
dispatched `mouseup` (matching `onPagesMouseUp`'s real listener), and confirmed the app returned to Work →
Meta-Analyze with the captured text populating the cell, zero console errors — the mechanism `openReferenceWarnings`
relies on for the badge-to-Meta-Reference jump is identical, just naming a different tab id.

## Manual verification (Playwright, this session)
1. Loaded `/`, 0 console errors. Menu bar reads `[My Publications, Library, Synthesize, Discover, Work, Help,
   Settings]` — no "Extract".
2. Work's sub-tab bar shows exactly `[Cite, Meta-Reference, CRediT, Meta-Analyze]` in order.
3. **Cite** — `CitePane` renders directly, no inner tab strip, sub-tab bar flush/centered per the CSS fixes.
4. **Meta-Reference** — all 3 subsections (Meta Reference List, Citation concentration, How it's cited) render
   stacked with clear headings/dividers, no breakage.
5. **CRediT** — renamed tab, By-author/By-role toggle intact, lineage-credit block (NISO CRediT + tenzing) present.
6. **Meta-Analyze** — picker view: trimmed intro ends cleanly on "...one study at a time.", Effect-size calculator
   subsection renders below with its own divider. Opened the "Test" project: Effect-size calculator renders
   identically below the dataset table in the project view too.
7. Confirmed no dangling Meta-Analysis auditor UI anywhere under Work (grepped all visible button text for
   "meta.?analysis" — only pre-existing unrelated tag-filter buttons matched).
8. **Workbench capture round-trip**: added a row to the Test project, armed "select in PDF" on the N (group 1)
   cell, selected real PDF text via a DOM Range + dispatched `mouseup`, confirmed the app returned to Work →
   Meta-Analyze with the captured value populating the cell — zero console errors. Cleaned up the test row after.
9. **Meta-analysis reporting** — opened the METHODS accordion, confirmed "Meta-analysis reporting" now sits between
   "Mixed-model reporting" and "Transparency signals"; opened it and the auditor auto-ran on the selected paper,
   rendering the full 7-check reporting checklist (2 reported · 5 not detected · 0 n/a) with an exact-precision
   evidence highlight and cited basis lines, zero console errors.
10. Ref-signal-badge → Meta-Reference navigation verified by code read + mechanism-equivalence (no paper in the
    testing DB currently carries an active reference signal to click live; the identical `requestWorkspaceTab` +
    `selectWorkspace` call proven working by #8 above covers the same code path with a different tab id).

## Pytest
Full suite **1292 passed, 1 skipped** (up from 1291 in inc 312 — `test_frontend_assembly.py`'s
`test_workspace_menubar_structure_present` gained/lost assertions for the new structure but the file's total test
count is unchanged; the +1 is elsewhere in the run). `ruff check .` / `ruff format --check .` clean;
`python tools/check_line_budget.py` clean (349 files). `python tools/qa/build_surface_map.py check`: API 250/250
covered (hard gate clean); FE 1170/1185 covered, the same pre-existing 15-surface gap in `35a_mypubs.jsx`
(unrelated to this increment, from an earlier settings-panel split).

## Gates
- **QA (#10):** `route_73_workspaces.md` rewritten (new structure, new fe: coverage list, Meta-Analysis's absence
  from Work now correctly attributed to its METHODS-pane move rather than "staged/unregistered"); `route_42_cite`,
  `route_51_methods_citation_equity`, `route_53_citation_context`, `route_65_workbench` (+`08i_methods_effectsize.jsx`
  coverage, a new Effect-size-calculator step), `route_66_credit`, `route_68_reference_integrity`,
  `route_00_smoke_readonly` all updated to point at the new Work locations. `route_62_methods_metaanalysis.md`
  needed **no changes** — it already (if until-now-inaccurately) described this exact METHODS-pane location.
- **DESIGN.md (#8):** the Meta-Reference/Effect-size stacked-subsection layout reuses the existing
  `.settings-subsection` divider recipe; no new CSS pattern introduced.
- **Principles (#9):** pure navigation/IA restructuring — no claim/signal/evidence surface changed shape; the
  Meta-Analysis auditor's FLAG-not-ADJUDICATE framing, evidence quotes, and coordinate-precision honesty are
  unchanged, just relocated.

## Next
None outstanding from this reorg. The METHODS accordion's per-increment "watch" note in CLAUDE.md rule #1 didn't
need updating — no file crossed the 600-line cap during this work.
