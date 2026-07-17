# Codex handoff — 2026-07-17 (session 2): Library/workspaces UX polish list

You (Codex) are picking up **callosum** with the maintainer (Cliff) **supervising live** — you'll work through the
list below together. **Read `.claude/CLAUDE.md` in full first** (invariants, rules, commands, verification, the four
gates). Everything below assumes you've read it.

## Git state (read carefully — base on the right thing)

- **`main`** has **Increment 283 = PDF text-health section-labels fix** (Opus, this session; pushed).
- **`feature/workspaces-ux-polish`** (pushed to origin) has Codex's four workspace increments (numbered 283–286 in
  that branch): DESIGN §5 rewrite · one-time "what moved" hint · Discover→Search consolidation (Wanted/Gaps/
  Overlooked/Feed) · **Synthesis + Work workspaces** (Cite + nested tabs + CRediT moved out of THEORY). Opus reviewed
  these: build matches source, ruff (both), line-budget, QA (0 uncovered), and the honesty panels are pure relocations
  — all green; the full suite was mid-run at handoff.

### Task 0 — FIRST: get the workspaces work onto `main` (if not already done)
Check `git log --oneline main | head`. **If you see "Increment 287 / synthesis and work workspaces" already on main,
Opus finished the merge — skip to Task 1 and branch off `main`.** Otherwise finalize it:
1. `git checkout -b integrate-workspaces main` (or reuse the existing one) and
   `git merge feature/workspaces-ux-polish`.
2. **Conflicts are only docs.** Keep Opus's `INCREMENT-283-NOTES.md` (section labels). Reconcile `.claude/changes.md`
   (both added entries). **Increment renumber (uniform +1 for Codex's four):** Opus's section-labels stays **283**;
   Codex's DESIGN-rewrite→**284**, hint→**285**, discover→**286**, synthesis/work→**287**. Rename the four
   `INCREMENT-28{3,4,5,6}-NOTES.md` accordingly and bump each H1. Update the six `// inc 286` provenance comments
   (03_library ×2, 08b, 08c, 20_synthesis, 37_cite) → `inc 287`. Set the `HELP-DOCS-SYNCED` marker to "through inc 287".
3. Bump `.claude/CLAUDE.md` (currently "Increment 283 / 1239 tests") to the new top increment + the real final
   pytest count.
4. `python tools/build_frontend.py` (comments are stripped, so the HTML shouldn't change — confirm no unexpected
   diff), full `pytest`, both ruff gates, line-budget, QA check — then merge to `main` + push. Delete the branch.

**All the list items below assume the workspaces IA (Synthesis/Work workspaces, Discover=Search·Journals·Funding,
Extract=Workbench·Effect-Size·Meta-Analysis, Profile) is present** — so land Task 0 first, then branch for the list.

## Hard rules for THIS session

1. **Feature branch; do NOT push to `main` without Cliff's OK.** `git checkout -b feature/library-ux-polish`.
2. **Verification is not optional and not claimed without running it** (Opus re-verifies on return):
   - full `python -m pytest` (~20 min) green; `ruff check .` **and** `ruff format --check .` both pass;
     `python tools/check_line_budget.py` clean.
   - After ANY `app/frontend/` edit: `python tools/build_frontend.py`, then `pytest tests/test_frontend_assembly.py`;
     commit the rebuilt `callosum-app.html`.
3. **Gates (CLAUDE.md #8–#11):** read `.claude/DESIGN.md` before any CSS/inline-style (rule #8 — reuse tokens/recipes,
   no new raw hex, no borrowed color semantics). **Run the Principles gate (#9)** for the signal-touching items
   (open-data inversion, RETRACTED styling, retraction auto-update) — read `.claude/PRINCIPLES.md`; these must stay
   *signal-not-verdict*, evidence-shown, inspectable. Add/extend a **QA route (#10)** in the same increment for every
   changed surface (`.claude/qa-routes/`, then `python tools/qa/build_surface_map.py check`). Run the **experience
   pass (#11)** on each user-facing change.
4. **Do NOT touch the design invariants** (egress gate; coordinate honesty; signal-not-verdict / no composite scores;
   evidence always shown). Nothing here should — if something seems to, stop and leave a note.
5. **No over-claiming.** Report the actual pytest pass count; say "partial"/"unverified" honestly (esp. visual
   placement — flag what Cliff should eyeball).
6. Minimal diffs (#7). One increment-notes file per real increment (bump the number); `.claude/changes.md` entry each;
   keep CLAUDE.md current. **Watch the 600-line cap** on the frontend chunks you touch (`10_pdf_layer.jsx`,
   `30c_frame.jsx`, `40_app.jsx`, `04b_workspaces.jsx` are the big ones — split with the shared-IIFE hoist precedent).

---

## The list (group into a few increments; suggested grouping A–F)

### A. Library-header buttons — labels, formats, tooltips
Files: the Library header + its count chips live in `app/frontend/js/10_pdf_layer.jsx` +
`10b_libmenus.jsx` + `10d_papercard.jsx`; find each chip/button by its current text.
1. **"Enrich metadata" → "Metadata".** Keep the little refresh icon; clicking still restarts the refresh.
   **Do NOT change the label to "Filled #"** — a changing label (e.g. to a count) misleads users into thinking the
   click *shows* the filled papers rather than *re-runs* enrichment. Label stays stable ("Metadata"); the count/last-run
   goes in the tooltip (item 6).
2. **"🔎 # - open data not detected" → "🔎 Open Data · #", and invert the set:** show papers **with** open data
   detected (count + filter), not those without. **(Principles gate #9 — this changes what a signal reports; keep it a
   checkable signal, not a verdict.)** Update the corresponding filter so clicking lists the open-data papers.
3. **"⚠# flagged" → "⚠ Flagged · #".**
4. **"⚠# retracted" → "⚠ Retracted · #".**
5. **"📋 # to review" → "📋 Review · #".**
6. **Move "last refreshed" out of the button text into the tooltip** for every refreshable Library tool (metadata,
   text-health, citation refresh, retractions). Button shows the stable label + refresh icon; `title=` carries
   "Last refreshed <date>". (Prevents the label from shifting under the user between runs.)
7. **"Text health" → "Text Health"** (also the modal title in `26b_text_health.jsx`).

### B. Workspace-subsection scrolling, labels, My Publications/Profile
8. **Discover → Journals + Funding subsection bodies don't scroll.** Files: `08e_methods_publishers.jsx` (Journals),
   `08k_funding_discovery.jsx` (Funding), the `.workspace-body`/`.workspace-pane` CSS in `styles.css`. Give the tab
   body an `overflow-y:auto` + bounded height so long content scrolls (check DESIGN.md for the pane recipe first).
9. **Extract → same scroll fix for Effect-size + Meta-analysis** (`08i_methods_effectsize.jsx`,
   `08g_methods_metaanalysis.jsx`). **Rename labels: "Meta-analysis" → "Meta-Analysis"; "Effect-size" → "Effect-Size".**
10. **"Publications" → "My Publications"** (the Profile workspace / dashboard: `31_mypubs_dashboard.jsx` + the menu-bar
    label in `04b_workspaces.jsx`/`40_app.jsx`).
11. **Profile doesn't populate after a refresh** until you interact with the My-Publications axis. Fix so the Profile
    dashboard loads its data on view (its own fetch/effect), independent of the axis. Trace where My-Pubs data is
    fetched (`31_mypubs_dashboard.jsx`, the My-Pubs axis in `15_axes.jsx`/`15b_axis_card.jsx`, `MyPubsPrompt`) — the
    dashboard should not depend on the axis being touched.
12. **Remove the "Profile" button from the My-Publications axis** (redundant now that Profile is a menu-bar workspace).
    In `15_axes.jsx`/`15b_axis_card.jsx` / `MyPubsPrompt`.

### C. Selected-paper "dummy" tab + draggable tabs (`40_app.jsx` + `30c_frame.jsx` + `04b_workspaces.jsx`)
13. **A "selected paper" tab:** when a paper is *selected but not yet open* in the reader, show a tab **first, right
    after the Library tab**, representing that paper. **Distinct color** (signals "selected, not opened" — pick from the
    DESIGN token set, don't invent a hex; read DESIGN.md #8). **Clicking it opens the PDF immediately** (calls the
    existing `openPdf`). Only render it when the selected paper is **not already** an open reader tab.
14. **Make the open-PDF tabs draggable to reorder** (there's an axis drag-reorder precedent — see
    `drive_inc212_dragreorder.py` / the axis card DnD). **But preserve the selected-paper tab's primacy:** it stays
    pinned first-after-Library and is only shown while a paper is selected-but-not-open (not draggable out of that slot).
    Experience pass (#11): does reorder feel natural; does the selected tab's color read as "not yet opened"?

### D. Selected-paper cue inside Discover subsections
15. In **Discover → Journals**, render the **selected-paper tab (dummy styling) OR the current open-paper tab (opened
    styling)** — styled *exactly* as those tabs already are — **before** the Search…Funding sub-tabs, keeping those
    sub-tabs' own (aesthetically distinct) styling. Purpose: reuse the existing visual dictionary so users see at a
    glance what "Selected paper" refers to. **Do the same in Discover → Funding.** (Reuse the tab component from item 13
    / the open-PDF tab; don't fork its styles.)

### E. Retractions
Files: `app/backend/api/routers/methods_retraction.py` (per-DOI detection + the Retraction Watch DB mirror),
the Library header, `styles.css` + DESIGN.md for the badge.
16. **"Check all papers for retractions" auto-updates the DB first:** by default, check whether the Retraction Watch
    mirror has an update and, if so, download + apply it **before** running the library check. (Keep it local/offline-
    tolerant: if the update fetch fails, fall back to the existing mirror and say so — don't hard-fail. **Principles
    gate #9:** retraction is a *signal with evidence* (the RW record), not a verdict — keep the source/date shown.)
17. **Retracted-paper styling:** a clear card/badge reading **"RETRACTED"** using the **same text/size/shape recipe as
    the "CHUNKED" badge** (find the CHUNKED badge in the paper card — `10d_papercard.jsx` / `25_detail.jsx` — and mirror
    it with `--danger` semantics per DESIGN.md; red = retracted/destructive is the existing meaning). Show it wherever
    a paper is presented (card + detail).
18. **Add a "Retractions" button (with a refresh icon) to the Library header, placed BEFORE "Text Health".** Wire it to
    the retraction check (item 16); last-run in the tooltip (item 6). QA route + experience pass.

### F. Credit-the-lineage button — "add missing" states
Files: the shared `.method-credit` recipe + its button; the overlooked lens credit is `36b_overlooked.jsx`
(`OverlookedCredit`), and statcheck/GRIM/etc. share the same affordance (grep `.method-credit` /
`add to library`). Import path: `POST /library/import` (csl-json). Many credits add **one** paper; some add **several**.
19. **Change the button text to "＋ add missing to library".**
20. **When all the credit's item(s) already exist in the library**, show **"✓ added to library"** with the existing
    post-click styling (the current success state).
21. **Partial case (a credit that adds >1 item, some present, some not):** show **"＋ add missing to library"**;
    clicking imports **only the missing** items, then flips to **"✓ added to library"** (success styling).
    → Needs a "which of these DOIs/items are already in the library?" check on mount. Reuse the existing library
    lookup (by DOI) rather than importing blind; `/library/import` is idempotent, but the button STATE must reflect
    present-vs-missing so the label is honest. Keep it per-credit-component (the shared affordance).

---

## When done / window ends
Leave the branch un-merged with clean commits (push the branch to origin as backup is fine). Append a **"Codex session
summary"** to the BOTTOM of this file per group: what changed, the **actual** pytest pass count + both ruff results,
what's partial/unverified (flag visual placements for Cliff/Opus to eyeball), any blocker. Opus re-verifies against it.

---

## Codex session summary — Task 0 workspace integration — 2026-07-17

Branch: `integrate-workspaces`.

What changed:
- Merged the `feature/workspaces-ux-polish` work onto current `main`, preserving Opus increment 283 for the PDF text-health section-label fix.
- Renumbered Codex workspace increments to avoid the collision: DESIGN rewrite = 284, workspace hint = 285, Discover/Search consolidation = 286, Synthesis/Work split = 287.
- Renamed/retitled the increment note files, moved the help sync marker through inc 287, updated the six workspace provenance comments from inc 286 to inc 287, and bumped `.claude/CLAUDE.md` to Increment 287.
- Rebuilt `callosum-app.html` after the merge/renumber reconciliation.

Verification:
- `python tools\build_frontend.py` passed.
- `python -m pytest tests\test_frontend_assembly.py tests\test_help.py`: 35 passed.
- `python tools\qa\build_surface_map.py check`: API 245/245, FE 1145/1145, uncovered 0.
- `python -m pytest`: 1239 passed, 1 skipped in 1464.65s.
- `ruff check .`: passed.
- `ruff format --check .`: 464 files already formatted.
- `python tools\check_line_budget.py`: all 342 application-source files within the 600-line cap.

Partial/unverified:
- This integration pass did not rerun the browser visual smoke checks; the feature branch had already recorded desktop/narrow Playwright checks for the workspace UI.
- Pre-existing untracked artifacts were left untouched: `.claude/funding-ui-pass-*.png` and `www/`.

Blockers: none.
