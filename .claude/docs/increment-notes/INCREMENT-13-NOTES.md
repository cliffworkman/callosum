# Increment 13 Notes

## Implemented

- Fixed PDF extraction line construction in `app/backend/pdf_processing/extraction.py`.
- Chunk text now preserves word-boundary whitespace across adjacent PyMuPDF spans.
- Added a geometry fallback: if adjacent non-whitespace spans have a horizontal gap large enough to indicate a word boundary, extraction inserts one space.
- Whitespace-only spans are used for text reconstruction but are not emitted as evidence spans in `bbox_json`.

## Approach

- The extractor no longer drops whitespace-only spans before building line text.
- Explicit PyMuPDF space spans are preserved as spaces.
- When PyMuPDF splits adjacent text into separate spans without an explicit space span, `_needs_space_between_spans` compares span bounding boxes and inserts a space only when the horizontal gap is at least `max(1.0, font_size * 0.15)`.
- This keeps chunk text whitespace-consistent with the quote-location path, which builds searchable text from PyMuPDF words joined by single spaces.

## Over-Correction Guard

- Added a generated-PDF test where one word is split across two spans by a font change.
- The test asserts `anomalous` remains intact and `anom alous` is not introduced.

## Chunk Version / Staleness

- This fix changes extracted chunk text for affected PDFs.
- Under the current version formula, `chunk_version` is based on chunking strategy, PyMuPDF version, and source checksum, so this code-only extractor fix does not automatically change `chunk_version`.
- Existing chunks extracted before this fix should be treated as stale and re-extracted/re-embedded for reliable quote verification.

## Raw Pytest Output

```text
pytest -q
.................................................                        [100%]
49 passed in 27.99s
```
