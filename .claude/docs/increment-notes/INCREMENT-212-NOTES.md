# Increment 212 — A7 SP2: drag-to-reorder curated members

## Implemented

The frontend-only follow-on to inc 211 (A7 SP1), completing the Curated Axis feature: the per-row **↑/↓** reorder
buttons are replaced by **HTML5 drag-to-reorder**. **No backend change** — it reuses the inc-211 `PUT /axes/{id}/order`
endpoint (already tested + the validation in place).

- `15_axes.jsx`: a curated member row now shows a **⠿ grip** (`.axis-grip`) instead of ↑/↓; each `.axis-member-drag`
  wrapper is an HTML5 drag **source + drop target** via a member-only MIME **`application/x-callosum-axismember`**
  (distinct from A6's `application/x-callosum-paper`, so dragging a member never triggers the card-level drop-to-add).
  Dropping member X onto member Y moves X to Y's slot and `PUT`s the full id list → `reorderToIndex(axisId,
  draggedId, targetId)` (splice-out + splice-in on the current `position` order). A `dragMemberOver` state drives a
  `.dragover` drop indicator (an inset top `--accent` line). The old `reorderPaper` (↑/↓) callback is removed.
- `styles.css`: `.axis-grip` (grab cursor) + `.axis-member-drag.dragover` replace the `.axis-reorder` recipe.

## Key technical detail

The member-drag MIME is deliberately different from the A6 drop-to-add MIME, so the two DnD flows on the same card
don't collide: the axis card's A6 `onDragOver` only accepts `…-paper`, and the member rows only accept
`…-axismember`. `reorderToIndex` operates on the current server (`position`) order from `details[axisId].papers`, so
the dragged member lands exactly at the target row's slot; the endpoint then validates the id set == the members.

## Manual verification script

**Headed (no egress):** `.local/visual/drive_inc212_dragreorder.py` — a curated axis [Alpha, Beta, Gamma]; drag
Alpha onto Gamma (a shared-DataTransfer dispatch) → order becomes [Beta, Alpha, Gamma] and **persists across a
reload**; no ↑/↓ buttons remain; 0 console/page/genai.

## Gates

- **pytest:** unchanged — a frontend-only edit with no Python/test change (the inc-211 suite stays **733 passed, 1
  skipped**); `test_frontend_assembly` confirms the rebuilt `callosum-app.html` is in sync. CI re-runs the full suite.
- **ruff** clean (no Python touched); frontend rebuilt; **no migration / no new endpoint / no audit / no dependency.**
- **QA surface** — **145/145 API + 685/685 FE, 0 uncovered** (FE count drops by 4 — the removed ↑/↓ buttons;
  `route_15_axes.md`'s curated step updated to the drag mechanism). Help corpus + DESIGN updated (`HELP-DOCS-SYNCED`
  → 212). **Principles non-triggering** (a reorder interaction over an existing endpoint).
- **Rule-#1:** `js/15_axes.jsx` ends at **562**.

## NEXT

A7 is now **complete** (SP1 inc 211 + SP2 inc 212), which **closes the entire competitive-benchmark A-list (A1–A10)**.
The remaining backlog is the deferred **B-items** — B1 read-first/write-gated MCP server, B4 citation-context
classifier, B2 collaboration/shared libraries, B3 OCR, B5 mobile reading — each a larger, own design pass.
