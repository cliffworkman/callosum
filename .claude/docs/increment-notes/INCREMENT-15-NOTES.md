# Increment 15 Notes

## Implemented

- Replaced document-side hyphenation matching with token-walking canonicalization in `app/backend/pdf_processing/extraction.py`.
- `locate_quote` now builds canonical document text from `_WordToken` records, preserving a canonical-character-to-token map for coordinates.
- `LocalCitationVerifier._quote_confidence` now uses `canonical_text_contains`, so the verifier precheck and `locate_quote` share the same quote-side hyphen/ligature/whitespace tolerance.

## Geometric Hyphen Decision

- The document-side canonicalizer walks adjacent `_WordToken`s.
- If a token ends with a hyphen-like character and the next token is on a different `(page_number, block_number, line_number)`, the pair is treated as a line-break continuation and joined with no whitespace.
- If a token ends with a hyphen-like character and the next token is on the same line with a small horizontal gap, it is treated as same-line compound continuation and joined with the hyphen preserved.
- Internal hyphens inside a single token, such as `anomalous-is-bad`, are preserved.

## Compound-Wrap Ambiguity

- Geometry alone cannot always distinguish a soft word break from a compound that wraps exactly at one of its own hyphens.
- To handle the real `beauty-is-` / `good` case without a dictionary, a line-break token ending in a hyphen preserves that final hyphen when the token already contains an earlier hyphen-like character.
- A plain soft break such as `beau-` / `tiful` still drops the break hyphen and canonicalizes to `beautiful`.

## Quote Side

- Quotes have no geometry, so `canonicalize_quote_text_variants` returns both safe variants for hyphen+whitespace:
  - remove the break hyphen (`beau- tiful -> beautiful`)
  - preserve the hyphen (`beauty-is- good -> beauty-is-good`)
- Ligature expansion and whitespace collapse from increment 14 are unchanged.

## Coordinates

- Canonical document characters map back to original `_WordToken` indices.
- After a canonical substring match, rectangles are computed from the original tokens, so hyphenated matches still span the correct lines/pages.

## Guardrails

- Same-line compounds retain internal hyphens.
- A quote that drops a real internal hyphen, such as `anomalous-isbad`, does not match `anomalous-is-bad`.
- Altered and fabricated quotes still return `found=False`; verifier quote confidence remains `0.0`.

## Raw Pytest Output

```text
pytest -q
.........................................................                [100%]
57 passed in 39.24s
```
