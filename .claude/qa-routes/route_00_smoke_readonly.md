<!-- qa-coverage
api: GET /health, GET /papers, GET /papers/item-types, GET /papers/{paper_id}, GET /papers/{paper_id}/chunks, GET /papers/{paper_id}/pdf, GET /papers/{paper_id}/annotations, GET /tags, GET /axes, GET /help/corpus, GET /citations/styles, GET /summaries
fe: 02_mobilenav.jsx, 04_layout.jsx, 04b_workspaces.jsx, 05_panes.jsx, 10_pdf_layer.jsx, 10b_libmenus.jsx, 10d_papercard.jsx, 15_axes.jsx, 20_synthesis.jsx, 25_detail.jsx, 30_viewer.jsx, 30c_frame.jsx, 35_settings.jsx, 18_help.jsx, 40_app.jsx
-->

<!-- B5 (inc 237): at a phone-width viewport (≤760px) the app renders single-column with a bottom `.mobile-nav`
(Library / Panels / Details); tapping a tab switches the region. The center region uses a compact Workspace select
instead of the desktop workspace tab strip. Above 760px the desktop 3-pane grid is unchanged.
Read-only over the tunnel is the CALLOSUM_READ_ONLY method gate (403 on writes) + the read-only cloudflared ingress
allowlist — covered by tests/test_mobile_ingress.py + adapters/mobile/. -->

# ROUTE 00 — Read-only smoke (every surface renders, nothing errors)

**Tier:** 0 read-only
**Goal:** Confirm the app mounts, every primary view renders cleanly, every primary control is present
and clickable, and there are zero console/page errors and no unexpected 4xx/5xx. This is the fast gate
that must pass before any deeper (mutating) route runs.

## Environment

Stand up a clean seeded instance (see `_TEMPLATE.md` → Environment). **Egress UNSET.** Register
console/pageerror/request listeners before navigating.

## Standing assertions

All of `_TEMPLATE.md` → Standing assertions, especially **console budget = 0** and the **egress gate**
(a read-only smoke must make zero genai requests — that is the cheapest possible egress regression catch).

## Steps

1. Load `/`. Wait for `#root` to populate. Baseline screenshot. Assert the brand wordmark "Callosum" rendered.
2. **Library shell** (`10_pdf_layer.jsx` + `10d_papercard.jsx`): the seeded papers list; the search box; the search-scope dropdown;
   the Sort dropdown; the Type filter dropdown; the "+ Add ▾" menu (open it — the entries are **Watched
   folders…** and **Import file…** [scanning is reached *via* Watched folders, not a top-level entry], then
   close); the Unsorted toggle; the Duplicates button (**Wanted moved to Discover → Search** in the inc-280
   workspace IA — it is no longer a Library-header button); pagination if present; the per-card
   copy-BibTeX button + checkbox; single-click selection; double-click/open behavior; paper citation-count button
   where present; and read/priority controls when the instance is read-write. Click each control that has a
   read-only or menu-opening effect; do **not** mutate in this read-only smoke. Confirm each responds (no dead clicks).
3. **PDF viewer** (`30_viewer.jsx`): open the seeded **Renderable Seed Paper** (the one paper backed by a real
   on-disk PDF — see `_TEMPLATE.md` → Seed contract). Confirm the 2 pages render, the text layer aligns (no
   gross drift), zoom in/out re-renders, and the citation/annotation overlay layers mount. Screenshot. Then open
   **Facial Anomaly Perception** (double-click its library card) and confirm it shows the honest
   **"PDF not available locally"** null-state (its attachment rows point at files that aren't on disk — the
   coordinate-honesty `null` case). **Since the inc-308 QA follow-up fix (browser-verified 2026-07-19):** opening
   it via the library card is a **zero-console-error, zero-network-404** path — the card's own `attachment_count`
   (already known client-side) short-circuits the doomed `/papers/{id}/pdf` fetch (`40_app.jsx`'s `openPdf` +
   `PdfViewer`'s `knownNoPdf` prop). A 404 here now is a **regression**, not an expected artifact.
4. **Axes accordion — left pane** (`05_panes.jsx` + `15_axes.jsx`): the left pane is an **accordion** with section
   headers **Axes · Review**, one body open at a time (**Axes** open by default). The **Axes** section has three
   **tabs** (`.pane-tabs` segmented chips): **Axes** (default), **Tags**, and **Queue** (the reading queue, inc 219).
   Click **Tags** → the tag list renders, or the **"No tags yet…"** hint when the library has none; click **Queue**
   → the to-read queue renders (empty state ok); click **Axes** back → the axis view returns (mount-but-hide — state
   preserved). Click the **Review** header → Axes collapses and the findings/candidates review queue renders (empty
   state ok, or the seeded retraction/statcheck facts if present). Reload and confirm the open section **persists**
   (`callosum.theoryOpen`) and the active Axes-section tab persists (`callosum.panetab.axes`).
5. **Details/Methods accordion — right pane** (`25_detail.jsx` + the METHODS modules): the right pane is an
   accordion with section headers **Details · Data consistency (GRIM) · Statistics check · Bayesian statistics ·
   Mixed-model reporting · Transparency signals** (plus further checks below the fold — not exercised here, just
   confirm the pane scrolls to reach them; Cite/CRediT/Meta-Reference/Meta-Analyze live under the Work workspace,
   not this accordion). **Details**
   is open by default. On load the **top library paper is auto-selected** (inc 138), so Details shows its editable
   fields right away (not the empty hint); selecting a different paper updates it. The **"Select a paper to see its
   details"** hint shows only when nothing is selected (e.g. an empty library). Click **Data consistency (GRIM)** →
   Details collapses and the GRIM panel renders (mount-but-hide — Details' state is preserved). (Per-check
   scoring/merge/suggest and the METHODS auditors' own findings are exercised in their own routes; here just confirm
   each header opens its section with no console error.) Reload and confirm the open right-pane section persists
   (`callosum.methodsOpen`).
6. **Settings** (`35_settings.jsx`): open the gear. Confirm theme toggle, default-axis-cutoff slider,
   hide-uncertain toggle, watched-folder auto-rescan toggle, help-assistant section all render. Toggle dark
   mode on/off and confirm the chrome re-themes while the (future) PDF page stays light. Close.
7. **Help** (`18_help.jsx`): open the `?` modal. Confirm the TOC + sections render from `/help/corpus`; click
   a TOC entry and confirm it scrolls/flashes the section. Close.
8. **Reading mode / panels** (`40_app.jsx`): toggle reading mode (both panels collapse, center remains
   visible, Esc/Exit restores); drag a divider to resize; collapse/expand a panel. Confirm reading mode does
   NOT persist across reload.
9. **Responsive**: resize to `375x812`, hard refresh, confirm no horizontal overflow on the library view. In the
   center region, confirm the **Workspace** dropdown switches between Library/Synthesize/Discover/Help while the
   bottom nav continues to switch only Library/Panels/Details.

## Pass criteria

- App mounts; "Callosum" present; 0 page errors, **0 console errors** — including opening the no-local-PDF paper in
  step 3: since the inc-308 QA follow-up fix, that path makes no `/pdf` request at all (a `knownNoPdf` short-circuit
  from the card's own `attachment_count`), so **any** console error here, including a `/papers/{id}/pdf` 404, is a
  regression (≥ Medium) — not an expected artifact as earlier versions of this route assumed.
- Every control above is present and responds (no dead clicks, no uncompletable control).
- 0 requests to any genai/Gemini host.
- No unexpected 4xx/5xx in the network log (the no-local-PDF paper should produce **no** `/pdf` request at all).
- No horizontal overflow at `375x812`.
- The phone-width Workspace dropdown is reachable and does not replace the bottom region nav.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_00_smoke_readonly.md` + `screenshots/` (see `_TEMPLATE.md`).
