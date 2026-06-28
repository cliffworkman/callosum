<!-- qa-coverage
api: GET /health, GET /papers, GET /papers/item-types, GET /papers/{paper_id}, GET /papers/{paper_id}/chunks, GET /papers/{paper_id}/pdf, GET /papers/{paper_id}/annotations, GET /tags, GET /axes, GET /help/corpus, GET /citations/styles, GET /summaries
fe: 04_layout.jsx, 05_panes.jsx, 10_pdf_layer.jsx, 15_axes.jsx, 20_synthesis.jsx, 25_detail.jsx, 30_viewer.jsx, 30c_frame.jsx, 35_settings.jsx, 18_help.jsx, 40_app.jsx
-->

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
2. **Library shell** (`10_pdf_layer.jsx`): the seeded papers list; the search box; the search-scope dropdown;
   the Sort dropdown; the Type filter dropdown; the "+ Add ▾" menu (open it — the entries are **Watched
   folders…** and **Import file…** [scanning is reached *via* Watched folders, not a top-level entry], then
   close); the Unsorted toggle; the Duplicates / Wanted buttons; pagination if present; the per-card
   copy-BibTeX button + checkbox. Click each control that has a read-only or menu-opening effect; do **not**
   mutate. Confirm each responds (no dead clicks).
3. **PDF viewer** (`30_viewer.jsx`): open the seeded **Renderable Seed Paper** (the one paper backed by a real
   on-disk PDF — see `_TEMPLATE.md` → Seed contract). Confirm the 2 pages render, the text layer aligns (no
   gross drift), zoom in/out re-renders, and the citation/annotation overlay layers mount. Screenshot. Then open
   **Facial Anomaly Perception** and confirm it shows the honest **"PDF not available locally"** null-state
   (its attachment rows point at files that aren't on disk — this is the coordinate-honesty `null` case and the
   *correct* behavior, NOT a bug; the resulting `/papers/{id}/pdf` 404 + its browser console line are expected).
4. **THEORY accordion — left pane** (`05_panes.jsx` + `15_axes.jsx`/`20_synthesis.jsx`/`10_pdf_layer.jsx`):
   the left pane is an **accordion** with section headers **AXES · SYNTHESIS**, one body open at a time (AXES open
   by default). The **AXES** section has two **tabs** (`.pane-tabs` segmented chips), **Axes** (default) and
   **Tags** (inc 139 — Tags is no longer its own section). Click the **Tags** tab → the tag list renders, or the
   **"No tags yet — add tags from a paper's Details pane"** hint when the library has none; click **Axes** back →
   the axis view returns (mount-but-hide — the axis state is preserved). Click the **SYNTHESIS** header → AXES
   collapses and the synthesis query box renders (empty state ok). Reload and confirm the open section **persists**
   (`callosum.theoryOpen`) and the active AXES tab persists (`callosum.panetab.axes`).
5. **METHODS accordion — right pane** (`25_detail.jsx`): the right pane is the **DETAILS** accordion section. On
   load the **top library paper is auto-selected** (inc 138), so DETAILS shows its editable Details right away (not
   the empty hint); selecting a different paper updates it. The **"Select a paper to see its details"** hint shows
   only when nothing is selected (e.g. an empty library — no paper to auto-select). (AXES scoring/merge/suggest is
   exercised in its own route — here just confirm AXES lists the seeded axis.) Bonus check: switch THEORY to
   SYNTHESIS, select another paper (METHODS shows its details), switch THEORY back to AXES — the synthesis section's
   state is preserved (mount-but-hide).
6. **Settings** (`35_settings.jsx`): open the gear. Confirm theme toggle, default-axis-cutoff slider,
   hide-uncertain toggle, watched-folder auto-rescan toggle, help-assistant section all render. Toggle dark
   mode on/off and confirm the chrome re-themes while the (future) PDF page stays light. Close.
7. **Help** (`18_help.jsx`): open the `?` modal. Confirm the TOC + sections render from `/help/corpus`; click
   a TOC entry and confirm it scrolls/flashes the section. Close.
8. **Reading mode / panels** (`40_app.jsx`): toggle reading mode (both panels collapse, center remains
   visible, Esc/Exit restores); drag a divider to resize; collapse/expand a panel. Confirm reading mode does
   NOT persist across reload.
9. **Responsive**: resize to `375x812`, hard refresh, confirm no horizontal overflow on the library view.

## Pass criteria

- App mounts; "Callosum" present; 0 page errors. Console errors = 0 **except** the single browser-emitted
  "Failed to load resource: 404" from deliberately opening the no-local-PDF paper in step 3 (that 404 is the
  expected null-state, handled by the UI as "PDF not available locally") — any *other* console error is ≥ Medium.
- Every control above is present and responds (no dead clicks, no uncompletable control).
- 0 requests to any genai/Gemini host.
- No unexpected 4xx/5xx in the network log (the `/papers/{id}/pdf` 404 for the no-local-PDF paper is expected).
- No horizontal overflow at `375x812`.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_00_smoke_readonly.md` + `screenshots/` (see `_TEMPLATE.md`).
