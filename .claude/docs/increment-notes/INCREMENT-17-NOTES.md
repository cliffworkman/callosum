# Increment 17 Notes

## Implemented

- Made the shared faithful-text canonicalization entry point explicit in `app/backend/pdf_processing/extraction.py`.
- `locate_quote` now canonicalizes the incoming quote with `canonicalize_faithful_text_variants`.
- `canonical_text_contains` now canonicalizes both the quote and stored chunk text through the same faithful-text variant helper.
- `LocalCitationVerifier._quote_confidence` continues to use `canonical_text_contains`, so the verifier precheck and PDF locator use the same comparison rules.
- Added a verifier round-trip regression for faithful stored chunk text containing `brain func- tioning`, `beau- tiful`, and `peo- ple`.

## Where Canonicalization Applies

- Quote side: `locate_quote` reduces the generator quote to faithful-text canonical variants.
- Stored chunk side: verifier precheck reduces the stored chunk text to faithful-text canonical variants.
- PDF side: `locate_quote` reduces `_word_tokens_for_pdf` output through the token/geometry-aware document canonicalizer and preserves the canonical-character-to-token map for coordinates.

## Storage

- Stored chunk text is unchanged and remains faithful to the PDF.
- No chunk-building, extraction text construction, schema, or stored data format changed.

## Coordinates

- The PDF-side match still maps canonical characters back to original `_WordToken` indices.
- The new regression verifies a quote spanning four line rectangles returns real coordinates for all four lines.

## Stale-Chunk Implication

- No migration is needed for chunks already ingested before this increment because stored text is unchanged.
- This increment changes only matching behavior, so existing faithful chunks can benefit immediately when quote verification is rerun.

## Guardrails

- Altered and fabricated quotes still fail to locate.
- Digit/prefix hyphen keep guards from increment 16 remain intact.
- Same-line compound hyphens remain kept.
- NFC-not-NFKC behavior remains unchanged.
- No fuzzy matching was added.

## Raw Pytest Output

```text
pytest -q
..............................................................           [100%]
62 passed in 28.53s
```
