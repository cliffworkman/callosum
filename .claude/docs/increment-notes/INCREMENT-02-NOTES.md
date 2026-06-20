# Increment 02 Notes

## Implemented

- PDF processing package under `app/backend/pdf_processing/`.
- PyMuPDF text extraction via `extract_pdf()`, preserving page number, span text, and span bounding boxes in `pdf-points-top-left` coordinate space.
- Paragraph-like chunking via PyMuPDF text blocks, written into the existing `chunks` schema with mandatory provenance/version fields populated.
- Quote-location via `locate_quote()`, using document-level whitespace-normalized word matching and returning page-aware rectangles for future pdf.js overlays.
- Temporary `ingest_pdf_scaffold()` helper and `app/backend/pdf_processing/cli.py` for one local PDF. This is throwaway scaffolding; the Zotero importer should replace paper and attachment creation later.
- Migration downgrade fix: SQLite migrations now commit after running, and the baseline downgrade explicitly drops created tables in dependency order.
- Generated-PDF tests for single-page quotes, two-line quotes, cross-page quotes, absent quotes, chunk provenance, chunk-version changes, and downgrade-to-base.

## Deferred

- GROBID integration is deferred. This increment proves the PyMuPDF text and coordinate path without any external service, as required.
- Zotero/Mendeley import, managed PDF copy layout, embeddings/sqlite-vec, clustering, summarization, external metadata adapters, FastAPI routes, frontend/pdf.js rendering, OCR, and section/reference parsing remain out of scope.

## Chunking Strategy

- Chosen strategy: `pymupdf-block-v1`.
- Rationale: PyMuPDF text blocks are a low-cost paragraph-like unit with native bbox provenance. They are more citation-verifiable than whole-page chunks and avoid sentence-window heuristics before the extraction baseline is stable.
- `chunk_version` is derived from chunking strategy, extraction tool/version, and source attachment checksum, so changing the strategy changes the version for the same PDF.

## Fixture Approach

- Tests generate a tiny two-page PDF programmatically with PyMuPDF under pytest temp directories.
- No copyrighted or generated PDF fixture files are committed.
- Fixture quotes:
  - Page 1: `Alpha beta gamma appears on page one.`
  - Page 1, two-line span: `This two line quote begins on the first row and continues on the second row for testing.`
  - Pages 1-2, cross-page span: `Cross page quote starts before the page break and finishes after the page break.`
  - Page 2: `Delta epsilon zeta appears on page two.`

## Interpretations

- `locate_quote()` returns one `QuoteMatch` with `page_start`, `page_end`, and a list of rectangles; each rectangle includes its own page number for multi-line and cross-page highlights.
- The temporary ingest helper uses `storage_mode="linked"` because it does not implement the future managed library-store copy behavior.
- `bbox_json` stores span-level boxes for chunks and line-level boxes for quote matches.

## License Note

- PyMuPDF is AGPL-licensed. The extraction code is kept behind a thin module boundary so a permissive-license fallback such as pdfplumber can be evaluated later, consistent with the risk register.

## Raw Pytest Output

```text
============================= test session starts =============================
platform win32 -- Python 3.12.7, pytest-7.4.4, pluggy-1.0.0
rootdir: C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.2.0
collected 9 items

tests\test_pdf_processing.py ...                                         [ 33%]
tests\test_persistence_core.py ......                                    [100%]

============================== 9 passed in 6.85s ==============================
```
