# Increment 14 Notes

## Implemented

- Added tolerant quote-match canonicalization in `app/backend/pdf_processing/extraction.py`.
- Updated `locate_quote` to compare canonical quote text against canonical PDF word text.
- Preserved coordinate lookup by carrying a canonical-character-to-word-token map, then selecting the original `_WordToken` rectangles for the matched canonical span.
- Updated `LocalCitationVerifier._quote_confidence` to use the same canonicalization for its chunk-text precheck.

## Canonicalized Transformations

- Whitespace is collapsed to single spaces.
- Ligatures are expanded with targeted mappings plus Unicode NFKC normalization:
  - `ﬀ -> ff`
  - `ﬁ -> fi`
  - `ﬂ -> fl`
  - `ﬃ -> ffi`
  - `ﬄ -> ffl`
  - `ﬅ -> st`
  - `ﬆ -> st`
  - `ſ -> s`
- Hyphenation at line or word breaks is neutralized only when a hyphen-like character is followed by whitespace and then a continuing alphanumeric character.
- Covered hyphen-like break characters:
  - ASCII hyphen `-`
  - soft hyphen `\u00ad`
  - Unicode hyphens/dashes `\u2010`, `\u2011`, `\u2012`, `\u2013`, `\u2014`, `\u2212`

## Deliberately Not Canonicalized

- Stored chunk text is not rewritten or de-hyphenated.
- Internal punctuation is not stripped except for the explicit hyphen-at-break case.
- Alphanumeric content is not removed or fuzzy-matched.
- The matcher does not use edit distance, synonym matching, or semantic matching.

## Coordinate Mapping

- `_word_tokens_for_pdf` still builds the faithful PDF word stream and original token offsets.
- `locate_quote` builds a parallel canonical comparison string plus a token index for each canonical character.
- After `.find()` succeeds on the canonical string, the matched character span maps back to the original `_WordToken` indices.
- Rectangles are computed from those original tokens, so hyphenated matches still span the correct line/page boxes.

## Over-Tolerance Guard

- Added tests proving an altered quote still fails location and still records `quote_confidence=0.0` in the verifier.

## Raw Pytest Output

```text
pytest -q
.......................................................                  [100%]
55 passed in 23.47s
```
