# Increment 03 Notes

## Implemented

- Zotero read-only adapter under `integrations/zotero/`.
- Import orchestration under `app/backend/importers/zotero.py`.
- Adapter copies `zotero.sqlite` to a temporary directory and opens the copy read-only.
- Reads Zotero-like items, item data fields, creators, collections, collection membership, tags, notes, annotations, and attachments.
- Branches attachment resolution on `itemAttachments.linkMode`.
- Normalizes Zotero records into Callosum Paper columns plus a preserved CSL-JSON blob.
- Uses existing identity resolution before creating papers, covering DOI and Zotero library/key cases.
- Imports stored, available PDF attachments through the Increment 2 PyMuPDF extraction and chunking path.
- Marks papers `fully-chunked` when an imported available PDF yields chunks.
- Records missing linked files as attachments with `availability="missing"`.
- Records linked URL attachments with `storage_mode="url"`.

## Deferred

- Mendeley import, Better BibTeX, Zotero 8 citation-key behavior, managed copy-on-import, embeddings, sqlite-vec, clustering, summarization, external metadata adapters, FastAPI routes, frontend/pdf.js, and full-text acquisition remain out of scope.
- GROBID remains deferred.
- Annotation position translation is deferred. The importer can preserve raw Zotero annotation position data with `coordinate_system="zotero-reader-json"`, but does not translate it into Callosum PDF-space bboxes.

## Library-Store Mode

- Chosen for this increment: linked-in-place for Zotero-imported PDFs.
- Rationale: this increment proves non-destructive Zotero reading plus PDF extraction. Managed/content-addressed copy mode is the documented V1 target, but implementing it cleanly needs the library-store layout work that is outside this increment.

## Zotero Schema Assumptions

- Fixture assumes these Zotero-like tables: `items`, `itemTypes`, `fields`, `itemData`, `itemDataValues`, `creators`, `itemCreators`, `itemAttachments`, `collections`, `collectionItems`, `tags`, `itemTags`, `itemNotes`, and optionally `itemAnnotations`.
- Link-mode constants used: imported file `0`, imported URL `1`, linked file `2`, linked URL `3`.
- Stored attachments use `storage:<filename>` and resolve to `storage/<attachment item key>/<filename>`.
- Linked file paths are treated as filesystem paths exactly as stored. Zotero path-prefix aliases such as `attachments:` are not implemented yet.

## Schema Gaps

- No schema change was needed.
- The current schema has no Zotero attachment external ID column or unique constraint, so the importer deduplicates attachments by paper, import source, original path, and role.

## Read-Only Safety

- Tests hash every file in the synthetic Zotero directory before and after import.
- The importer never opens the source DB directly; it reads a temporary copy.

## Raw Pytest Output

```text
============================= test session starts =============================
platform win32 -- Python 3.12.7, pytest-7.4.4, pluggy-1.0.0
rootdir: C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.2.0
collected 10 items

tests\test_pdf_processing.py ...                                         [ 30%]
tests\test_persistence_core.py ......                                    [ 90%]
tests\test_zotero_importer.py .                                          [100%]

============================= 10 passed in 9.05s ==============================
```
