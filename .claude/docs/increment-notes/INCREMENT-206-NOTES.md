# Increment 206 — A6: drag-and-drop a library paper onto an axis to add it

## Implemented

The fourth close-out of the cheapest-first wrap-up pass (A6) — a faster input for the existing manual-axis-add path,
**frontend-only** (rides the inc-50 `POST /axes/{axis_id}/papers` manual-override endpoint; no backend/migration/audit).

- **`app/frontend/js/10_pdf_layer.jsx` (`PaperCard`):** the library card is now `draggable`; `onDragStart` writes the
  paper id to a custom MIME `application/x-callosum-paper` (`effectAllowed = "copy"`). The custom MIME means only our
  cards trigger an axis drop. The card's click-to-select / double-click-to-open are unaffected (a drag only starts on
  mouse-move-after-mousedown).
- **`app/frontend/js/15_axes.jsx` (`AxisItem`):** the `.axis` header div is a drop target **for non-My-Pubs axes only**
  (`canDrop = !isMyPubs`). `onDragOver` accepts the drag iff `dataTransfer.types.includes("application/x-callosum-paper")`
  (sets `dropEffect="copy"` + a `dragOver` state → the `.drag-over` highlight); `onDrop` reads the id and calls
  `handlers.dropPaper(axis.id, pid)`. The new `AxesPanel.dropPaper` mirrors the `confirmPaper` standard-axis branch —
  `apiPost('/axes/{id}/papers', {paper_id})` → `loadDetail(axisId)` + `loadAxes()` (so the badge count + the open card
  update) + a success flash ("Added to <axis>").
- **`app/frontend/styles.css`:** `.axis.drag-over` — a **dashed `--accent` border + `--accent-soft` fill** (dashed =
  transient/pending; distinct from the solid `.active` state). Recorded as a reusable drop-invite recipe in DESIGN.md.

## Key technical detail

The drag payload rides the **native `dataTransfer`**, so a card in the center library pane can be dropped on an axis
card in the left THEORY pane with **no React state plumbing between the panes** — the only shared channel is the
browser's drag data. **My-Pubs is deliberately not a drop target:** its membership is authorship-resolved (ORCID/DOI
+ ✓/✕ confirm), so adding a paper by a drag gesture would misrepresent it as an own-paper — `canDrop` gates the
handlers off for `kind === "my_publications"`.

## Manual verification script

**Headed (no egress):** `.local/visual/drive_inc206_drag_axis.py` — seed one paper + one empty axis; dispatch an HTML5
drag (a shared `DataTransfer` handle: dragstart on `.paper` → dragover + drop on `.axis`); assert the axis count badge
goes **0 → 1** (the paper became a manual member). 0 console/page/genai. (The My-Pubs no-drop guard is correct by
construction — the handlers are omitted when `isMyPubs`.)

## Gates

- **pytest:** full suite unchanged — **713 passed, 1 skipped** (frontend-only; `POST /axes/{id}/papers` is already
  covered by `test_axes.py`; the DnD wiring is headed-verified).
- **ruff** clean; frontend rebuilt (`callosum-app.html`).
- **QA surface unchanged** — 136/136 API + 661/661 FE, 0 uncovered (the drag handlers ride existing claimed
  `.paper`/`.axis` elements, not new controls); `route_15_axes.md` gained an A6 drag-to-add step (+ the My-Pubs
  no-drop assertion).
- **Audit:** none triggered (no endpoint/egress/migration/dependency). **Principles non-triggering** (a faster input
  to the existing manual-override path; a manual add is a human choice, not a scorer/AI decision).
- **DESIGN.md** records the drop-invite recipe (rule #8). **Help corpus** updated (the axes section gained a
  drag-to-add line + the My-Pubs exception; `HELP-DOCS-SYNCED` → 206).

## NEXT (continuing the cheapest-first close-out)

**Inc 207 — A5** color tags / ratings / flags (a `color` on tags + a user `rating`/`flag` on papers + UI — a small
migration; a rating is a **user field, never an AI score**). Then **A1** saved searches (a `saved_searches` table +
header recall), **A3** full-text FTS5 search (migration + a security audit), **A2** citation counts, and **A7 Curated
Axis** (its own design pass).
