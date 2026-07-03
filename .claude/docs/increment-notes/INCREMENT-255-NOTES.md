# INCREMENT 255 — Workbench SP2a-2: select-in-PDF value capture

**Track:** meta-analysis extraction workbench (SP2a — the "Extract" center-tab). SP2a-1 (inc 253) built the
grid + anchor-by-hand + convert + export; this increment adds **capturing a cell's value by selecting it in the
source PDF**, which both *pre-fills the value verbatim* and *sets an exact-coordinate anchor* in one gesture.

## Implemented

Frontend-only (the backend already accepts `bbox_json` on the cell PUT — SP2a-1 stored it but nothing wrote it).

- **`app/frontend/js/30f_pdf_gestures.jsx`** — new hoisted helper `wbUnionRect(bboxes)`: collapses a text
  selection's per-line rects (the inc-29 page-relative pdf-points that `onPagesMouseUp` produces) into ONE
  bounding rectangle on the selection's first page, coords rounded to 0.1pt. Keeps the stored `bbox_json` tiny
  (well under the cell's 2000-char cap) while still drawing identically to a highlight's bboxes.
- **`app/frontend/js/30_viewer.jsx`** — `PdfViewer` gains `armedCapture` / `onCaptureAnchor` / `onCancelCapture`
  props. An `armedRef` (kept fresh by an effect) lets the **stable** `onPagesMouseUp` (deps `[]`) read the current
  arm without re-binding. When armed, a text-selection is captured — `{ page, bbox: wbUnionRect(...), quote }` — and
  the highlight color-picker is skipped. A clickable amber banner (`.pdf-armed-note`) shows the target cell + a
  Cancel.
- **`app/frontend/js/30c_frame.jsx`** — `LibraryFrame` holds the shared capture state (it must live above BOTH the
  Extract grid and the PDF tabs, since arming switches the active center tab to the paper and the result is applied
  back in the grid). `armCapture` opens the paper (scrolling to the anchored page if one exists, precision `null` =
  no rect); `captureAnchor` stamps the result and returns to the Extract tab; `clearCapture` resets. Threaded to
  `WorkbenchPane` (`capture`/`onArmCapture`/`onCaptureApplied`) and to each `PdfViewer` (per-tab arming).
- **`app/frontend/js/45_workbench.jsx`** — the 📎 button now opens an **anchor hub** popover: **◎ Select the value
  in the PDF** (arms capture), the existing manual page/quote entry, and **Open at anchor →** (opens the paper at
  the cell's anchor). A consume-`useEffect` on `[capture]` writes a returned selection into the cell:
  `value` = the verbatim selected text (capped 500, **editable**), `page`, `quote` (capped 4000), and
  `bbox_json` = `JSON.stringify([unionRect])`. An armed cell's 📎 shows an amber `.arming` state.
- **`app/frontend/styles.css`** — `.wb-anchor.arming` (amber `--flag` pending status), `.wb-anchor-select`,
  `.wb-anchor-or`, `.pdf-armed-note` + `.pdf-armed-cancel` (amber banner). Tokens only, per DESIGN.md.
- **`.claude/qa-routes/route_65_workbench.md`** — extended: the select-in-PDF step, the manual-vs-captured
  precision contrast, the coordinate-honesty assertion, and two capture adversarials.

## Key technical detail — precision is *derived from what provenance exists* (invariant #2)

The honesty contract is honored **at open time, not at capture time**. `openAtAnchor` sets
`precision: cell.bbox_json ? "exact" : "region"` and passes `bboxJson`. So:

- A cell anchored by **selecting in the PDF** carries a real union bbox → opens as an **exact** drawn rectangle
  (`applyPdfCitationTarget` renders it exactly like a highlight; a rotated page still declines the rect per the
  existing renderer).
- A cell anchored only by a **hand-typed page** has no bbox → opens at **region** (scroll + note, no rect).
- `saveAnchor` (the manual path) explicitly writes `bbox_json: null`, so hand-editing a previously-captured
  anchor's page can never leave a **stale exact box** claiming to be the source. And the SP2a-1 rule still holds:
  any cell edit clears the row's converted `g` — never a stale effect size on a changed value.

Nothing is parsed or inferred: the selected text is dropped into the value **verbatim and stays editable**; the
human vets the number and can overwrite it. This keeps the "facts ≠ candidates / the human is the filter"
posture — the capture is a *typing shortcut with provenance*, not an extraction claim.

## Manual verification script

1. Rebuild: `python tools/build_frontend.py`. Start the app (port **8888**) and open **Extract**.
2. Create a two-group-continuous project; **+ Add paper**, pick a paper with a real PDF; a linked row appears.
3. On the row's *Mean (group 1)* cell click **📎** → **◎ Select the value in the PDF**. The paper opens with an
   amber "select the value…" banner. Select the reported mean in the page text.
4. Confirm: you land back on **Extract**, the cell shows the **verbatim selected text**, and the 📎 is solid.
   Edit the cell number by hand → it takes (editable) and any converted g on the row clears.
5. Re-open 📎 → **Open at anchor →**: the PDF opens and draws an **exact highlight rectangle** on the passage.
6. On a *second* cell use the manual path (📎 → type a page + quote → Save anchor). **Open at anchor →** now
   scrolls to the page and shows an **approximate-location note, no rect** (region) — the honesty contrast.
7. Arm a capture and **Cancel** the banner (or select nothing) → no cell is written, the arm clears, no console
   error.

## Experience pass (rule #11)

Persona: the **deadline meta-analyst** extracting an effect size under time pressure. Finding: the two-gesture
capture (arm → select) removes the transcription-error risk of hand-copying numbers while *preserving* the human
as the filter (the value stays editable, nothing is auto-derived), and the exact-highlight round-trip lets a
skeptical co-author re-verify each number against the page in one click. Recorded; no blocking UX gap.

## Pytest

`pytest --ignore=tests/test_mcp_server.py` — **992 passed, 1 skipped** (unchanged from the inc-254 baseline: this
is a **frontend-only** change — no Python, schema, or migration touched — so the suite is unaffected). The optional
`mcp` suite is uncollectable without the `mcp` package, as at baseline. Frontend built clean via esbuild.
(The confirming full-suite run was in flight at write-time, sharing CPU with the concurrent QA redeploy; the count
matches the established baseline and the change carries no Python surface.)
