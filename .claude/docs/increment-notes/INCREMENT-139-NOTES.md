# Increment 139 — Accordion tabs-within-a-section (Tags → a tab of AXES; METHODS reordered)

## Implemented

Codifies the information-architecture rule the user asked for: **accordion sections are broad tool *categories*;
within a section, TABS present like-with-like submenus** — so the accordion stays shallow instead of sprouting a
sibling section for every variant.

- **`05_panes.jsx` (registry gains tabs):** `registerPaneTab({id,label,paneId,order}, {id,label,order,render})`
  adds a tab to a **find-or-created** host section; `registerPaneSection({…,render})` becomes sugar for a one-tab
  section. A section with one tab renders it directly (no strip); with **≥2 tabs** it renders a **segmented tab
  strip** (reuses the `.tags-srcfilter` chip recipe — the user-approved style) + **mount-but-hides** the inactive
  tabs (`.pane-tab:not(.active){display:none}`), so an open axis / running action survives a tab switch. The
  active tab persists per section (`callosum.panetab.<sectionId>`).
- **THEORY — Tags becomes a tab of AXES:** `15_axes.jsx` registers the **Axes** tab and `10_pdf_layer.jsx` the
  **Tags** tab, both under the `axes` host (`[Axes | Tags]`). Tags is no longer its own accordion section
  (like-with-like — your labels beside your conceptual lenses). Discoverability is *preserved*: the Tags tab is
  always visible when AXES is open (the default section).
- **METHODS reordered by cognitive task:** **Data consistency (GRIM)** `order: 30 → 20` and **Statistics check**
  `order: 20 → 30`, so the raw-data check precedes the analysis check. Future stat checks become **tabs** within
  Statistics check, not new sections.
- **`styles.css`:** `.pane-tabs` (a margin wrapper on the `.tags-srcfilter` strip) + `.pane-tab:not(.active){display:none}`
  — layout-only, no new tokens (rule #8).
- **`DESIGN.md` §5:** the new "Tabs within a section" rule + the cognitive-task ordering note; the THEORY/METHODS
  section lists updated.

## Key technical detail

- The accordion's tab state lives in `PaneAccordion` (`useState` map sectionId→tabId), seeded lazily from
  `_loadLayout("callosum.panetab.<id>", tabs[0].id)` and saved on switch — so it survives reloads without threading
  state through App. Single-tab sections render `tabs[0].render(ctx)` **directly** (no `.pane-tab` wrapper), so the
  five existing single-content sections (Details / Synthesis / GRIM / Statistics / Review) are byte-identical to
  before — only the multi-tab AXES section gets the strip + wrappers.
- **esbuild DCE:** `registerPaneTab` is referenced (called in 15_axes / 10_pdf_layer after 05 loads), so it
  survives the build; the gate is raw-assembly inclusion + a successful build (`test_frontend_assembly.py`).

## Manual verification script

1. `python .local/visual/drive_inc139_panetabs.py` (free port + own-process-alive; seeds 2 papers + an axis
   "Zaxis" + a tag "zztag", no network). Asserts: THEORY = `[AXES, SYNTHESIS]` (no standalone Tags); the AXES
   section shows an `[Axes | Tags]` tab strip; Axes tab active by default (axis visible, tag hidden); clicking
   **Tags** shows the tag + hides the axis (mount-but-hide), clicking **Axes** restores it; METHODS order has
   **Data consistency (GRIM)** before **Statistics check**.
2. Result: **PASS** — 0 console errors, 0 page errors, 0 genai hits.

## Gates

- **No Principles trigger** — pure information-architecture (grouping/ordering), no new claim/signal/provenance/egress.
- **Rule #10** — `route_00` + `route_20_tags` repointed to the Tags tab; surface map **106/106 API + 530/530 FE,
  0 uncovered** (the new `.pane-tabs` strip + tab buttons, covered by route_00).
- **Rule #8** — the tab strip reuses the existing `.tags-srcfilter` segmented-chip recipe (the user-chosen style);
  the only new CSS is layout (`.pane-tabs` margin + `.pane-tab` hide).

## Pytest

**519 passed, 1 skipped** (unchanged — frontend-only). `ruff` clean; build + assembly green; rebuilt
`callosum-app.html`.

## Next (queued)

- Gap-finder followed-authors / embedding-similarity ranking; a cadence auto-refresh.
- **Watch (rule #1):** `clustering/my_publications.py` at **594/600** — split before the next backend addition there.
