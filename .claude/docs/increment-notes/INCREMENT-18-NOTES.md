# Increment 18 Notes

## Implemented

- Split quote verification into three outcomes in `LocalCitationVerifier._quote_confidence`:
  1. Quote absent from the stored source chunk: `quote_confidence=0.0`, no coordinates, not verified.
  2. Quote present in the stored source chunk and exactly located in the PDF: `quote_confidence=1.0`, exact quote rectangles.
  3. Quote present in the stored source chunk but not exactly locatable in the PDF: `quote_confidence=1.0`, chunk region coordinates.
- Added `coordinate_precision` to the verification and citation persistence result dataclasses.
- Persisted coordinate precision inside `bbox_json` entries:
  - `coordinate_precision="exact"` for exact quote rectangles.
  - `coordinate_precision="region"` for chunk-level fallback regions.

## Semantics

- Grounding is established by canonical containment of the quote in the cited stored chunk.
- Exact PDF location is now a coordinate-quality attribute, not the quote-grounding gate.
- Region fallback uses the cited `SourceChunk.page_start`, `SourceChunk.page_end`, and `SourceChunk.bbox_json`.
- A citation with region fallback can be `verified` when retrieval and support also pass.

## Guardrails

- If the quote is not present in the stored chunk, verification still fails even if the PDF locator would return a match.
- Altered and fabricated quotes still produce `quote_confidence=0.0`.
- Canonicalization behavior from increments 14-17 is unchanged.
- Stored chunk text is unchanged.

## Legitimate Test Changes

- Exact-coordinate tests now additionally assert `coordinate_precision="exact"` in `bbox_json`.
- New region-fallback tests assert a formerly coordinate-failed but chunk-grounded citation is now verified with `coordinate_precision="region"`.
- Hallucination/altered-quote tests remain not verified.

## Pending

- Exact-coordinate correctness for multi-column PDFs is still pending.
- This increment implements Option A only: coordinate honesty with region fallback.
- Option B, reading-order correction for multi-column PDF token streams, remains future work.

## Raw Pytest Output

```text
pytest -q
................................................................         [100%]
64 passed in 32.99s
```
