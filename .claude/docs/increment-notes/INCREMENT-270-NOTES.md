# Increment 270 — Precise-highlighting locator: reading-order word reconstruction

## Implemented
- `app/backend/pdf_processing/quote_matching.py` — `_word_tokens_for_pdf` now reconstructs each page from
  `page.get_text("words")` sorted by **reading order `(block, line, word)`** instead of the geometric
  `sort=True`. One-line behavioral change; `locate_quote` body unchanged (still strict canonical substring).
- `tests/test_pdf_processing.py` — `test_two_column_quote_locates_in_reading_order_not_geometric`: a
  two-column fixture where a single-column quote is interleaved (and thus unlocatable) under geometric sort
  but contiguous under reading order; also asserts the cross-column interleaving does **not** match (honesty).

## Key technical detail
`locate_quote` matches a citation's verbatim quote against a whitespace-canonicalized reconstruction of the
PDF. That reconstruction was built from `get_text("words", sort=True)`, whose geometric ordering interleaves
multi-column / floating text into the middle of a passage — so a quote that *is* verbatim inside its stored
chunk (chunk text is extracted in reading order) is not a contiguous substring of the words reconstruction →
`found=False` → the caller stamps `region` ("precise highlight pending"). Ordering the words by their
`(block, line, word)` indices reproduces the chunk's reading order, so genuine quotes locate. Rectangles are
derived per-token from each word's own bbox, so ordering never changes coordinate correctness — it only fixes
the *matching* string.

**Honesty boundary (invariant #2).** A "collapse both sides to alphanumerics" fallback was prototyped to
recover the last ~5% (mis-decoded en-dashes, spaced URLs). It was **rejected**: it broke three standing tests
(`test_same_line_compound_hyphen_is_preserved`, `test_digit_adjacent_line_break_hyphens_are_kept`,
`test_prefix_allow_list_line_break_hyphen_is_kept`) that deliberately keep significant hyphens distinct
(`5-HT` ≠ `5HT`). When the source text is genuinely garbled, `region` is the truthful precision.

## Measurement (read-only, `.claude/highlight_diag.py`)
Re-ran `locate_quote_for_attachment` over stored evidence quotes in three validation DBs with local PDFs
(`inc124_live` 115, `inc124` 40, `showcase` 12 = 167 citations, all pass `canonical_text_contains`):

| | located | rate |
|---|---|---|
| geometric sort (before) | 89 / 167 | 53% |
| reading order (after) | **159 / 167** | **~95%** |

Off-page / false matches: **0** before and after.

## Manual verification script
1. On `main` with this branch merged, open a synthesis whose citations previously showed
   *"region-level · precise highlight pending"* (multi-column PDFs are the common case).
2. Click such a citation → confirm it now scrolls to the page **and draws an exact highlight rectangle** on
   the cited passage (not just a region note).
3. Confirm a citation into genuinely garbled source (e.g. a reference-list entry with a mis-decoded dash)
   still shows the region note — not a wrong highlight.
4. Confirm a rotated-page citation still draws no exact overlay (unchanged).

## Pytest
`tests/test_pdf_processing.py` 15 passed; locate-consuming suites (summarization / summaries / statcheck /
summarize-selected) 54 passed. Full suite: green (see changes.md).
