# Increment 22 Notes

## Implemented

- Added DOI extraction in `app/backend/metadata/doi.py`.
  - Source order: PDF embedded metadata first, then first-page and last-page visible text.
  - Regex: `10\.\d{4,9}/[-._;()/:A-Z0-9]+`, case-insensitive, with conservative trailing punctuation cleanup.
- Added a cached Crossref adapter in `integrations/crossref/`.
  - Uses `GET https://api.crossref.org/works/{doi}`.
  - Sends a `User-Agent`; `CALLOSUM_CROSSREF_MAILTO` is appended when configured.
  - Stores responses in `external_api_cache` with `provider="crossref"` and `cache_key=<normalized doi>`.
  - HTTP errors, timeouts, and 404s return unresolved results instead of raising.
- Added metadata enrichment orchestration in `app/backend/metadata/enrichment.py`.
  - Filename-only `pdf-scaffold` records can be resolved from DOI + Crossref.
  - Canonical fields populated from Crossref CSL-like JSON: title, DOI, year, venue, abstract, first author family name, publication date, item type, and full `csl_json`.
  - Existing non-scaffold authoritative sources such as Zotero are skipped.
- Added `tools/enrich_metadata.py` for idempotent in-place enrichment.

## Processing Tier Ladder

The existing schema enum is unchanged:

- `fully-chunked`: paper has stored chunks.
- `abstract-embedded`: paper has no chunks, but has abstract or resolved structured metadata such as DOI/year/venue/first author.
- `metadata-only`: paper has no chunks and no resolved structured metadata.

The PDF scaffold now refreshes the tier after chunk creation, so successfully extracted raw PDFs become `fully-chunked` instead of remaining at the default `metadata-only`.

## Provenance And Unresolved Semantics

- Resolved Crossref records use `papers.imported_source="crossref"`.
- Unresolved records use `papers.imported_source="crossref-unresolved"`, making them queryable as needing metadata.
- For unresolved papers, filename title is preserved and structured metadata columns remain empty/null. A DOI found in the PDF is returned in the enrichment result and cached through Crossref, but it is not promoted into canonical `papers.doi` unless Crossref resolves.

## Tests

- Tests use fake Crossref fetchers only; no network calls or real Crossref requests.
- Added coverage for metadata DOI extraction, text DOI extraction, no false match, Crossref caching, metadata population, 404/unresolved handling, missing-DOI unresolved handling, tier computation, and idempotency.

## Raw Pytest Output

```text
........................................................................ [ 84%]
.............                                                            [100%]
85 passed in 38.98s
```
