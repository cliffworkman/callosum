<!-- qa-coverage
api: /workbench*, /methods/effect-size
fe: 45_workbench.jsx, 46_workbench_propose.jsx, 08i_methods_effectsize.jsx
-->

# ROUTE 65 - Work -> Meta-Analyze (meta-analysis workbench SP2a-1 + SP2b dataset loop + assisted-extraction funnel)

**Tier:** 1 local-stateful
**Goal:** Exhaust **Work -> Meta-Analyze** (formerly its own "Extract" workspace, folded into Work in a later reorg,
with the standalone "Effect-Size" tab folded further in as this pane's own subsection) — assemble a project
(template) -> rows (one effect each, optionally linked
to a paper) -> provenance-anchored cells -> **Convert all** the rows via the SP1 converter (the dataset loop) with an
honest **"k of N converted"** readout -> export the accumulated dataset **stat-package-ready** (generic CSV, a
**metafor** yi/vi table, a **RevMan** raw-data table) + a provenance audit. It **extracts / structures / converts /
exports — it NEVER pools, models heterogeneity, meta-regresses, or does bias inference.** The core loop is fully local —
no egress; the **one** egress channel is the opt-in **assisted-extraction funnel** (SP2b, inc 259: the LLM *proposes*
candidate cell values, gated by the consent gate). **A value is only ever set by a human** — hand-typed, captured from
the PDF, or **accepted** from an AI candidate; the batch convert is the same audited per-study convert, N times.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment; ≥2 papers seeded). **Egress UNSET for the core loop** (steps 1–11
are local — assert no genai-host request there regardless). The **funnel** (step 12) needs AI features on: use a
**loopback/local** provider (still no egress) or a **canned** assistant — never send library text to a real cloud host
in QA. Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** The workspace is local; ANY request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Extract, never synthesize (Critical if violated).** There is NO control that pools rows, computes a summary
  estimate / I²/τ²/Q, meta-regresses, or draws a forest plot. **Convert all** runs the per-study converter over each
  row independently — its response/readout is a **count of rows converted (k of N)**, never a pooled or averaged
  effect. Export is the dataset + provenance, never a synthesized result: the **metafor** file is one row per study
  (yi/vi + moderators, no summary row); the **RevMan** file is *raw* per-group study data (RevMan computes the effect
  itself, callosum does not). The intro/note state it converts one study and hands off to metafor/JASP/RevMan.
- **Honest coverage, never a fabricated value (High if violated).** A row with incomplete/invalid inputs is left
  **un-converted** and named in `convert-all`'s `incomplete` list (and its metafor yi/vi cells export **blank**) —
  never silently filled with a 0 or a guess. The "k of N converted" readout must match the rows that actually carry a
  computed effect.
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

### Assisted-extraction funnel (SP2b, inc 259) — AI proposes, the human filters

- **Egress gate on the Draft control (Critical if violated — invariant #3).** **Draft from PDF** proposes cell values
  from the paper via the LLM — the consent-gated channel. With AI features OFF (a non-loopback provider without
  `Allow AI features`), the button is **disabled with an honest tooltip** and `POST …/rows/{id}/propose` returns
  **403** — **no `generativelanguage`/genai-host request** is made. A row with no empty proposable structured field
  **short-circuits** (`{proposals:[], truncated:false}`) and contacts no provider even with AI on.
- **Fact ≠ candidate — isolation (Critical if violated).** A proposal is a **candidate** in `ma_proposals`, never a
  value. It renders as an **amber** card and **never** appears in a cell's trusted value, in `Convert`/`Convert all`,
  or in ANY export (CSV / metafor / RevMan / provenance) until a human **accepts** it. A proposed value showing up in
  a pre-accept export is a Critical fact/candidate breach.
- **Batch draft is batch-propose only (Critical if violated).** **Draft all un-filled rows** sequentially invokes
  the same per-row proposal path for eligible paper-linked rows. It never accepts a candidate, never replaces a
  row's existing live candidates, shows determinate row progress, and continues past a row-level failure with a
  named partial-failure summary. Existing candidates remain awaiting the same individual accept/edit/reject choice.
- **Every candidate carries its evidence (High if violated — invariant #4).** Each candidate shows its **verbatim
  quote** inline (the passage the value was read from) + an **anchor badge** (exact / region / couldn't-verify) — the
  human vets it without trusting the model. No candidate is shown as a bare number.
- **Coordinate honesty on accept (Critical if violated — invariant #2).** A candidate's precision is derived from the
  **local** anchor (`anchor_proposal`/`locate_quote`), never the model's claim. **Open at anchor** on a candidate draws
  an **exact** rect ONLY when the anchor state is `exact`; a `region`/`unanchored` candidate opens the page with **no**
  exact rect. On **accept**, `bbox_json` is stored ONLY when the anchor was `exact` AND the value was not edited —
  editing the number before accepting drops it to **region** (no fake exact box on a human-changed value). `origin`
  becomes `assisted` and surfaces in the provenance (audit) export **only after** accept.
- **The model never asserts location/confidence.** The proposal's page/quote is the model's *claim*; the app's local
  locator decides the anchor state and the drawn precision. No opaque score is shown on a candidate (Principle #7).

## Adversarial checklist

- create a project with a blank name / unknown design -> 422-class, no crash
- add a row with an unknown paper_id -> 404-class, no crash
- write to a cell field that isn't in the template -> 422-class
- convert a row with empty/degenerate cells -> 422-class, a legible "fill the fields" message, no crash
- delete a project -> its rows/cells go; a re-GET is 404
- arm a select-in-PDF capture, then cancel the banner (or select nothing) -> no cell is written, the arm clears, no crash
- capture a value, then hand-edit the number in the cell -> the row's converted **g clears** (never a stale g on a changed value)
- **Convert all** on a project with a mix of complete + blank rows -> only the complete rows convert; the readout says "k of N converted"; the blank rows stay un-converted (no fabricated value); the response carries only `{total, converted, incomplete}` (no pooled/summary key)
- export **metafor** -> a clean `study,yi,vi,sei,ci_lb,ci_ub,metric,<moderators>` CSV; an un-converted row has blank yi/vi; a **negative** effect size stays a plain number (not a `'`-neutralised cell); no summary/pooled row
- export **RevMan** -> the per-design raw-data columns (continuous: Mean/SD/Total ×2; dichotomous: Events/Total ×2 with Total = events + non-events; correlation: Generic-IV Effect + SE); no computed pooled effect
- a spreadsheet-formula string in a label/moderator (`=cmd`) exports `'`-prefixed in every format (injection-safe)
- resize to `375x812`, no horizontal overflow of the whole pane (the grid may scroll horizontally on its own); the fuller header (Convert all + readout + Export CSV/metafor/RevMan/provenance) wraps rather than overflowing
- **funnel — AI off:** with egress unset, the **Draft from PDF** control is disabled + carries an honest "enable AI features" tooltip; forcing `POST …/rows/{id}/propose` returns **403** and **0 genai-host requests** fire
- **funnel — candidate isolation:** draft a row → amber candidates appear → **before accepting any**, run **Convert** and every **Export** (CSV/metafor/RevMan/provenance) → **no proposed value** appears in any of them; the cell's trusted value is still empty
- **funnel — evidence shown:** every candidate shows its verbatim quote inline + an exact/region/couldn't-verify badge (never a bare number)
- **funnel — coordinate honesty:** **Open at anchor** on an `exact` candidate draws a rect; on a `region`/`unanchored` candidate it opens the page with **no** rect; **edit** a candidate's number then accept → the stored anchor is region (no exact box on the changed number)
- **funnel — accept/reject:** accept one candidate → it becomes the cell's value with `origin='assisted'` (visible in the provenance export); reject one → it disappears and nothing is written; malformed/empty model output → 0 candidates, clean 200, no crash
- **funnel — batch propose:** with a mix of eligible rows, a row already holding candidates, a fully-filled row,
  an unlinked row, and one paper whose draft request fails, **Draft all un-filled rows** calls only the eligible
  rows without candidates, one at a time; determinate progress reaches N/N; successful rows show amber candidates;
  the existing candidates are unchanged; the failed row is named in the summary; no cell value changes and no
  accept endpoint is called

## Steps

1. Open **Work -> Meta-Analyze**. Confirm the intro ends cleanly after "...one study at a time." (no trailing
   "pooling, heterogeneity..." clause) + the New-project form (name + a design picker) + any existing projects.
   Scroll down and confirm an **Effect-size calculator** subsection renders below (the former standalone
   "Effect-Size" tab) — present on the picker view too, not just inside an open project.
2. Create a project (name + **two-group continuous**) -> the project view: the header (editable name, protocol note),
   the template columns (N/Mean/SD ×2), the empty grid, **+ Add row / + Add paper**, and the export row
   (**Convert all** + a "k of N converted" readout once rows exist; **Export: CSV / metafor / RevMan / provenance**).
3. **+ Add paper** -> search the library -> pick a paper -> a row appears linked to it (its title opens the PDF).
4. **Select-in-PDF capture (SP2a-2).** On one cell, click the **📎 anchor** -> the hub popover offers **◎ Select the
   value in the PDF** + manual page/quote. Click **Select** -> the paper opens with an amber "select the value…"
   banner. Select a reported number in the page -> the app returns to **Work -> Meta-Analyze** and the cell is filled with the
   **verbatim selected text** (confirm it's editable — overwrite it, it takes) and the 📎 turns solid. Re-open the
   hub -> **Open at anchor →** -> the PDF opens and draws an **exact highlight rectangle** on that passage. Cancel the
   banner mid-capture -> nothing is written, the arm clears.
5. On a *second* cell, use the **manual** path: 📎 -> type a page + quote -> **Save anchor** -> 📎 solid. **Open at
   anchor →** now scrolls to the page and shows an **approximate-location note, no exact rect** (region precision) —
   the honesty contrast with the captured cell above.
6. **Convert →** on the row -> a green **Hedges' g = …** (its variance in the tooltip) appears; nothing is pooled.
7. Add a second row and leave it blank, then **Convert all →** (the dataset loop) -> the readout updates to
   "**1 of 2 converted**" and a note names the blank row as still needing valid inputs — it is **not** given a
   fabricated value. `POST /workbench/projects/{id}/convert-all` returns `{total, converted, incomplete}` only.
8. **Export → metafor** -> a `?format=metafor` download: `study,yi,vi,sei,ci_lb,ci_ub,metric,<moderators>`; the
   converted row carries numeric yi/vi, the blank row's yi/vi are empty (honest coverage). The tooltip states the R
   handoff (`read.csv(...)` then `rma(yi, vi, data=dat)`) — no summary/pooled row is in the file.
9. **Export → RevMan** -> a `?format=revman` download in this design's raw columns (continuous: Mean/SD/Total ×2);
   confirm it is *raw study data*, not a computed effect. **Export → CSV** = the generic dataset; **provenance** = the
   audit JSON (per-cell page/quote).
10. Add a **+ col** (a moderator column) -> it appears in the grid, the generic CSV, and the metafor export. Confirm
   you cannot remove a role column (the API rejects it; the UI never offers it).
11. Adversarial: blank-name / unknown-design create -> 422; unknown paper -> 404; convert an empty row -> 422 with a
   legible message; `?format=bogus` -> 422; convert-all on an unknown project -> 404; delete the project -> re-GET
   404. Confirm **no pool/aggregate/forest control** anywhere in the pane and **no pooled row** in any export.
12. **Assisted-extraction funnel (SP2b, inc 259).** Enable AI features (a loopback/local provider = no egress, or a
   canned assistant). On a paper-linked row with empty structured cells, click **Draft from PDF** -> a progress bar
   -> **amber candidate** cards appear beside the empty cells, each with a **verbatim quote** + an **anchor badge**
   (exact / region / couldn't-verify). Confirm the candidates are NOT in the cell's trusted value, in Convert, or in
   any export yet. **Open at anchor** on an `exact` candidate draws the passage rect; on a `region`/`unanchored` one it
   opens the page with no rect (invariant #2). **Accept** one (-> it becomes the cell value, `origin='assisted'` in the
   provenance export), **edit** one's number then accept (-> stored anchor drops to region, no exact box), **reject**
   one (-> gone, nothing written). Then **turn AI off** and confirm **Draft from PDF** is disabled with an honest
   tooltip and a forced propose returns 403 with **0 genai-host requests**. Add several paper-linked blank rows,
   leaving accepted values in one and live candidates in another, then click **Draft all un-filled rows**. Confirm
   determinate row progress; only eligible rows without existing candidates are drafted; the live candidates are
   not replaced; each new proposal still waits for an individual accept/edit/reject; one forced row failure is
   named without stopping later rows. With AI off, the batch control is disabled too.
13. **Effect-size calculator subsection.** Scroll to it (present in both the project picker and inside an open
   project). Pick a family (e.g. **SMD -> Hedges' g**, method **group means + SDs**), fill the fields, **Convert**
   -> a result renders (metric = value, variance/SE, 95% CI, the derivation path, any caveats) + a **copy value +
   variance** action + a credit block. Confirm its own intro states it converts **one study** and **never pools or
   models** — same posture as the rest of this pane, and it shares no state with the Workbench grid above it
   (switching projects above doesn't reset or affect it).

## Pass criteria

- The workspace creates a project, assembles provenance-anchored rows, converts every row in one **Convert all**
  (via the SP1 converter) with an honest **"k of N converted"** readout, and exports the dataset three ways (generic
  CSV, metafor yi/vi, RevMan raw data) + a provenance JSON.
- 0 console/page errors; **0 genai-host requests** (local).
- **No aggregation control** (no pooling / heterogeneity / meta-regression / forest plot) and **no pooled row in any
  export**; convert-all returns a count, never an averaged effect; a row without valid inputs stays un-converted with
  **blank** yi/vi (never a fabricated 0); export = data + provenance; every value is hand-entered **or captured
  verbatim-and-editable by selecting it in the PDF**; the role-column spine is protected.
- **Anchor precision is honest:** a PDF-selected cell opens at **exact** (a drawn rect on the passage); a page-only
  cell opens at **region** (a note, no rect). No page-only anchor is ever drawn as an exact highlight.
- Bad inputs fail closed (422/404-class) with legible messages; mobile viewport has no whole-pane horizontal overflow.
- **The funnel is a candidate stream, never a value stream:** AI-proposed cell values render as amber candidates with
  their verbatim quote + an honest exact/region/couldn't-verify anchor badge; they enter the dataset (cell value /
  Convert / any export) **only** on a human **accept**, with precision derived from the local anchor (never the model's
  claim) and `origin='assisted'` in the provenance. **Draft from PDF** is egress-gated (disabled + 403 with AI off, no
  genai-host request); a fully-filled row makes no provider call. **Draft all un-filled rows** is sequential,
  progress-visible, partial-failure-tolerant batch-propose only — it skips existing candidates and never bulk-accepts.
  No opaque score is shown on a candidate.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_65_workbench.md` + `screenshots/` (see `_TEMPLATE.md`).
