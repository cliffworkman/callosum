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
- **Provenance + human-entry.** Every value is hand-entered; a cell can be anchored to a page + quote; an anchored
  cell opens its paper's PDF at that page (region precision). Nothing is auto-filled or inferred.
- **Template spine is protected.** A design's converter-input (role) columns cannot be removed or hijacked (a 422 at
  the boundary); moderator/notes columns can be added.

## Adversarial checklist

- create a project with a blank name / unknown design -> 422-class, no crash
- add a row with an unknown paper_id -> 404-class, no crash
- write to a cell field that isn't in the template -> 422-class
- convert a row with empty/degenerate cells -> 422-class, a legible "fill the fields" message, no crash
- delete a project -> its rows/cells go; a re-GET is 404
- resize to `375x812`, no horizontal overflow of the whole pane (the grid may scroll horizontally on its own)

## Steps

1. Open the **Extract** center-tab. Confirm the intro (converts one study; hands off to metafor/JASP/RevMan) + the
   New-project form (name + a design picker) + any existing projects.
2. Create a project (name + **two-group continuous**) -> the project view: the header (editable name, protocol note),
   the template columns (N/Mean/SD ×2), the empty grid, **+ Add row / + Add paper**, and **Export CSV / Provenance**.
3. **+ Add paper** -> search the library -> pick a paper -> a row appears linked to it (its title opens the PDF).
4. Fill the row's 6 cells (means/SDs/Ns). On one cell, click the **📎 anchor** -> set a page + quote -> Save -> the
   📎 turns solid; clicking it now opens that paper's PDF at that page (region precision).
5. **Convert →** on the row -> a green **Hedges' g = …** (its variance in the tooltip) appears; nothing is pooled.
6. **Export CSV** -> a `/workbench/projects/{id}/export?format=csv` download (rows × template columns + the converted
   g/variance). **Provenance JSON** -> the audit trail (per-cell page/quote).
7. Add a **+ col** (a moderator column) -> it appears in the grid + export. Confirm you cannot remove a role column
   (the API rejects it; the UI never offers it).
8. Adversarial: blank-name / unknown-design create -> 422; unknown paper -> 404; convert an empty row -> 422 with a
   legible message; delete the project -> re-GET 404. Confirm **no pool/aggregate/forest control** anywhere in the
   pane.

## Pass criteria

- The workspace creates a project, assembles provenance-anchored rows, converts each row (via the SP1 converter), and
  exports a CSV dataset + a provenance JSON.
- 0 console/page errors; **0 genai-host requests** (local).
- **No aggregation control** (no pooling / heterogeneity / meta-regression / forest plot); export = data + provenance;
  every value is hand-entered + anchorable; the role-column spine is protected.
- Bad inputs fail closed (422/404-class) with legible messages; mobile viewport has no whole-pane horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_65_workbench.md` + `screenshots/` (see `_TEMPLATE.md`).
