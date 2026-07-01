<!-- qa-coverage
api: GET /papers/{paper_id}/pdf, GET /papers/{paper_id}/annotations, POST /papers/{paper_id}/annotations, PATCH /annotations/{annotation_id}, DELETE /annotations/{annotation_id}
fe: 30_viewer.jsx, 30b_notes.jsx, 30f_pdf_gestures.jsx
-->

<!-- B5 mobile reader (inc 239): the highlight minimap (`MinimapTrack`) + pinch-to-zoom (`usePinchZoom`) live in
30f_pdf_gestures.jsx (split from 30_viewer.jsx, rule #1). On mobile the PDF defaults to fit-width, two-up is hidden,
and pinch-to-zoom drives the scale; a "← Synthesis" back pill (40_app.jsx) returns to the synthesis after a citation
jump. Coordinate honesty is unchanged — the minimap positions by page fraction, never a fabricated exact rect. -->


# ROUTE 32 - Viewer and annotations

**Tier:** 1 local-stateful
**Goal:** Exhaust PDF viewing, highlight creation, note/color editing, deletion, and citation/annotation coordinate honesty.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open a seeded paper with a PDF (`GET /papers/{paper_id}/pdf`). Confirm pages render, text layer aligns, and zoom in/out does not lose overlays.
2. Load annotations (`GET /papers/{paper_id}/annotations`). Confirm seeded annotations draw in the expected colors and notes.
3. Select text and create a highlight (`POST /papers/{paper_id}/annotations`). Confirm the saved bbox draws as an exact rect only when precision is exact.
4. Edit note and color (`PATCH /annotations/{annotation_id}`). Confirm persistence after reload and no duplicate overlay.
5. Delete the annotation (`DELETE /annotations/{annotation_id}`). Confirm it disappears after reload.
   - **inc 144 (Close reader):** with ≥1 highlight, the Notes panel head shows **Copy** + **Export .md** — they assemble a Markdown digest of the paper's highlights + notes (`# title`, `**p.N** — <highlighted text>`, a note as a `> blockquote`). Copy → the digest is on the clipboard; Export → a `*-notes.md` download. Frontend-only (no endpoint); the buttons appear only when there are highlights.
   - **inc 215 (minimap):** with ≥1 highlight and the Notes panel **closed**, a thin `.pdf-minimap` gutter shows one `.pdf-minimap-tick` per highlight, positioned by page fraction `((page-1+0.5)/numPages)` and tinted by the highlight's color. Clicking a tick jumps to + flashes that highlight (`jumpToAnnotation` — no fabricated coordinates; page-fraction is an honest navigation aid). Opening the Notes panel hides the minimap (the panel supersedes it). Frontend-only (no endpoint).
6. Try an oversized note, invalid color, negative/non-finite bbox, and missing anchor text through the UI or API-backed form state. Confirm 422-class handling, not a crash.
7. Exercise citation jumps from any visible page-routing source (synthesis citation, detail-pane Files, statcheck rows in the METHODS "Statistics check" section): `exact` draws a bbox, `region` scrolls and shows approximate note, `null` opens page without a rect.

## Pass criteria

- Viewer and annotation CRUD complete through the UI.
- 0 console/page errors and 0 genai-host requests.
- Coordinate honesty holds for exact/region/null locations.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_32_viewer_annotations.md` + `screenshots/` (see `_TEMPLATE.md`).

