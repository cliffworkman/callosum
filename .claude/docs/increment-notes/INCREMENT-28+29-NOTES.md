# Increment 29 Notes

## Implemented

- Added citation-to-PDF navigation in `callosum-app.html`.
  - Citation cards now expose an `Open source...` action.
  - Clicking a citation opens or focuses the cited paper's PDF tab.
  - If a page is known, the PDF tab scrolls to that page.
- Added PDF overlay support in the existing PDF.js viewer.
  - Exact citations with usable `bbox_json` draw all returned rectangles.
  - Region-level citations scroll to the cited page and show an approximate-location note, not a passage highlight.
  - Null/no-coordinate citations can open the page if one is known but draw no highlight and make no exact-location claim.
- No backend/API change was needed. The existing citation payload already includes `paper_id`, `paper_title`, `page_start`, `page_end`, `bbox_json`, and `coordinate_precision`.

## Coordinate Transform

Stored rectangles are interpreted as `pdf-points-top-left`, matching `COORDINATE_SYSTEM` in `app/backend/pdf_processing/extraction.py`.

For each rendered PDF.js page:

- `sourceWidth = viewport.width / scale`
- `sourceHeight = viewport.height / scale`
- `left% = rect.x0 / sourceWidth * 100`
- `top% = rect.y0 / sourceHeight * 100`
- `width% = (rect.x1 - rect.x0) / sourceWidth * 100`
- `height% = (rect.y1 - rect.y0) / sourceHeight * 100`

Highlights are positioned as percentages inside a page wrapper. This means they stay aligned when zoom changes or when the canvas is responsively constrained, because the overlay and canvas scale together. Zoom rerenders the page and reapplies the active citation target from the stored bbox data rather than reusing cached pixels.

Rotation handling is deliberately conservative: if PDF.js reports a nonzero page rotation, the viewer opens the page but does not draw an exact rectangle. The common upright case is handled; rotated-page exact overlay remains a known limitation.

## Precision Semantics

- `coordinate_precision === "exact"`: draw precise bbox rectangles when valid.
- `coordinate_precision === "region"`: show a region-level note only.
- `coordinate_precision === null` or no bbox: draw no highlight.

This preserves the existing honesty contract: region-level or absent coordinates are never presented as exact quote highlights.

## Manual Verification Script

1. Start the app:
   ```powershell
   $env:CALLOSUM_DB_URL = "sqlite:///C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/.local/validation-summarize/validation.sqlite"
   uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
   ```
2. Open `http://127.0.0.1:8080/`.
3. Load a saved synthesis from History.
4. Exact-placement check: use summary `#2`, paper `67`, page `2`, quote beginning `Compared with typical faces, facial anomalies were...`.
   - Click `Open source and highlight`.
   - Confirm the PDF tab for `Morality is in the eye of the beholder...` opens/focuses.
   - Confirm page 2 is brought into view and the indigo rectangles land on the quoted text.
   - Zoom in and out; confirm the rectangles stay aligned with the text.
5. Region-precision check: on a citation labeled `region-level · precise highlight pending`, click `Open source region`.
   - Confirm the page opens and shows the approximate region note.
   - Confirm no exact passage rectangle is drawn.
6. Null/flagged-location check: on a citation labeled `no coordinate claim`, click `Open source page` if a page is available.
   - Confirm the page opens but no highlight rectangle is drawn.

No headless screenshot was captured in this session; no browser automation dependency is present in the repo.

## Pytest

```text
........................................................................ [ 71%]
.............................                                            [100%]
101 passed in 63.35s (0:01:03)
```
