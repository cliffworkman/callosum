<!-- qa-coverage
api: /workbench*
fe: 45_workbench.jsx
-->

# ROUTE 65 - Extraction workspace (meta-analysis workbench SP2a-1)

**Tier:** 1 local-stateful
**Goal:** Exhaust the "Extract" workspace — assemble a project (template) -> rows (one effect each, optionally linked
to a paper) -> provenance-anchored cells -> convert each row via the SP1 converter -> export a metafor/JASP-ready CSV
+ a provenance audit. It **extracts / structures / converts / exports — it NEVER pools, models heterogeneity,
meta-regresses, or does bias inference.** Fully local — no LLM, no egress. A value is only ever set by a human.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment; ≥2 papers seeded). **Egress UNSET** (the workspace is local —
assert no genai-host request regardless). Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** The workspace is local; ANY request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Extract, never synthesize (Critical if violated).** There is NO control that pools rows, computes a summary
  estimate / I²/τ²/Q, meta-regresses, or draws a forest plot. Export is the dataset + provenance, never a synthesized
  result. The intro/note state it converts one study and hands off to metafor/JASP/RevMan.
- **Provenance + human-entry.** Every value is hand-entered *or* captured by selecting it in the PDF (SP2a-2) — the
  selected text becomes the cell value **verbatim and stays editable** (nothing is parsed, inferred, or auto-derived;
  the human still vets + can overwrite it). An anchored cell opens its paper's PDF at its page.
- **Coordinate honesty on the anchor (Critical if violated — invariant #2).** A cell anchored by **selecting in the
  PDF** carries a real bbox → opening it draws an **exact** highlight rectangle on that passage. A cell anchored only
  by a **hand-typed page** (no bbox) opens at **region** precision — it scrolls to the page and draws **no** exact
  rect. Region/page-only provenance is never presented as an exact highlight; editing a captured value's number does
  not silently keep claiming the old exact box as the source of the new number.
- **Template spine is protected.** A design's converter-input (role) columns cannot be removed or hijacked (a 422 at
  the boundary); moderator/notes columns can be added.

## Adversarial checklist

- create a project with a blank name / unknown design -> 422-class, no crash
- add a row with an unknown paper_id -> 404-class, no crash
- write to a cell field that isn't in the template -> 422-class
- convert a row with empty/degenerate cells -> 422-class, a legible "fill the fields" message, no crash
- delete a project -> its rows/cells go; a re-GET is 404
- arm a select-in-PDF capture, then cancel the banner (or select nothing) -> no cell is written, the arm clears, no crash
- capture a value, then hand-edit the number in the cell -> the row's converted **g clears** (never a stale g on a changed value)
- resize to `375x812`, no horizontal overflow of the whole pane (the grid may scroll horizontally on its own)

## Steps

1. Open the **Extract** center-tab. Confirm the intro (converts one study; hands off to metafor/JASP/RevMan) + the
   New-project form (name + a design picker) + any existing projects.
2. Create a project (name + **two-group continuous**) -> the project view: the header (editable name, protocol note),
   the template columns (N/Mean/SD ×2), the empty grid, **+ Add row / + Add paper**, and **Export CSV / Provenance**.
3. **+ Add paper** -> search the library -> pick a paper -> a row appears linked to it (its title opens the PDF).
4. **Select-in-PDF capture (SP2a-2).** On one cell, click the **📎 anchor** -> the hub popover offers **◎ Select the
   value in the PDF** + manual page/quote. Click **Select** -> the paper opens with an amber "select the value…"
   banner. Select a reported number in the page -> the app returns to **Extract** and the cell is filled with the
   **verbatim selected text** (confirm it's editable — overwrite it, it takes) and the 📎 turns solid. Re-open the
   hub -> **Open at anchor →** -> the PDF opens and draws an **exact highlight rectangle** on that passage. Cancel the
   banner mid-capture -> nothing is written, the arm clears.
5. On a *second* cell, use the **manual** path: 📎 -> type a page + quote -> **Save anchor** -> 📎 solid. **Open at
   anchor →** now scrolls to the page and shows an **approximate-location note, no exact rect** (region precision) —
   the honesty contrast with the captured cell above.
6. **Convert →** on the row -> a green **Hedges' g = …** (its variance in the tooltip) appears; nothing is pooled.
7. **Export CSV** -> a `/workbench/projects/{id}/export?format=csv` download (rows × template columns + the converted
   g/variance). **Provenance JSON** -> the audit trail (per-cell page/quote).
8. Add a **+ col** (a moderator column) -> it appears in the grid + export. Confirm you cannot remove a role column
   (the API rejects it; the UI never offers it).
9. Adversarial: blank-name / unknown-design create -> 422; unknown paper -> 404; convert an empty row -> 422 with a
   legible message; delete the project -> re-GET 404. Confirm **no pool/aggregate/forest control** anywhere in the
   pane.

## Pass criteria

- The workspace creates a project, assembles provenance-anchored rows, converts each row (via the SP1 converter), and
  exports a CSV dataset + a provenance JSON.
- 0 console/page errors; **0 genai-host requests** (local).
- **No aggregation control** (no pooling / heterogeneity / meta-regression / forest plot); export = data + provenance;
  every value is hand-entered **or captured verbatim-and-editable by selecting it in the PDF**; the role-column spine
  is protected.
- **Anchor precision is honest:** a PDF-selected cell opens at **exact** (a drawn rect on the passage); a page-only
  cell opens at **region** (a note, no rect). No page-only anchor is ever drawn as an exact highlight.
- Bad inputs fail closed (422/404-class) with legible messages; mobile viewport has no whole-pane horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_65_workbench.md` + `screenshots/` (see `_TEMPLATE.md`).
