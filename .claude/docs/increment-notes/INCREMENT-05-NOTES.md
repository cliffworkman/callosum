# Increment 05 Notes

## Implemented

- Real-data validation harness under `tools/validation_harness.py`.
- Default scratch/output path: `.local/validation`, now covered by `.gitignore`.
- Standalone PDF folder validation:
  - page count
  - chunk count
  - pages with extractable text
  - zero-text / likely scanned flag
  - extraction errors
  - user-supplied quote checks through `locate_quote`
- Zotero validation:
  - schema/table/column presence report against importer assumptions
  - optional-table warnings for `creatorTypes`, `deletedItems`, and `itemAnnotations`
  - warning for `itemTags.type`
  - warning for `attachments:` linked-path prefixes
  - source `zotero.sqlite` before/after checksum check
  - import counts and attachment availability counts
- Retrieval spot-check:
  - embeds imported/extracted chunks and papers
  - runs user-provided queries
  - reports top-k title, paper ID, chunk ID, page, score, and snippet
- Graceful handling for corrupt/unreadable standalone PDFs.

## Small Fixes To Prior Increments

- `SentenceTransformerEmbeddingModel` now accepts `local_files_only`; the harness uses `True` so it does not download model weights.
- `import_zotero_library` now accepts an optional attachment extraction error callback and skips failed attachment extraction instead of failing the whole import.

## How To Invoke

Example with a PDF folder:

```powershell
python -m tools.validation_harness `
  --pdf-dir "C:\path\to\pdfs" `
  --output-dir ".local\validation" `
  --quote "paper.pdf::Known quote from the PDF" `
  --query "your retrieval query"
```

Example with Zotero:

```powershell
python -m tools.validation_harness `
  --zotero-dir "C:\Users\<you>\Zotero" `
  --output-dir ".local\validation" `
  --query "memory consolidation hippocampus"
```

The harness writes `validation.sqlite` and `validation-report.md` under the chosen output directory.

## Data Handling

- No real PDFs or Zotero files are copied into the repo.
- The working DB/report are written only to the selected scratch output directory.
- Zotero schema inspection copies `zotero.sqlite` to a temp directory and opens that copy read-only.
- Zotero import still uses the existing read-copy adapter.
- The harness makes no Gemini, OpenAlex, Semantic Scholar, or cloud API calls.
- The real sentence-transformers model is loaded with `local_files_only=True`; if weights are not already cached or provided as a local model path, retrieval reporting records an embedding error instead of downloading.

## Deferred

- Clustering/BERTopic.
- Summarization, Gemini/LLM calls, and NLI verification.
- OpenAlex/Semantic Scholar/full-text acquisition.
- FastAPI routes and frontend/pdf.js.
- OCR; zero-text PDFs are reported as likely scanned/needs OCR.
- Fixing real Zotero schema drift beyond reporting it.

## Test Strategy

- Tests are hermetic and network-free.
- Tests generate tiny PDFs and a blank PDF under pytest temp directories.
- Tests reuse the synthetic Zotero fixture from Increment 03.
- Tests use a fake embedding model and in-memory vector store for retrieval spot-checks.

## Real-Data Findings

- I ran the harness against the user-provided `library/` directory.
- Report path: `.local/validation-library-retrieval/validation-report.md`.
- Scratch DB path: `.local/validation-library-retrieval/validation.sqlite`.
- PDFs reported: 77.
- Total pages: 1037.
- Total chunks: 14352.
- Zero-text / likely scanned PDFs: 0.
- PDFs with partial text-layer coverage:
  - `Lythe et al. - 2015 - JAMA Psychiat.pdf`: 22/23 pages with extractable text.
  - `Zapatero et al. - 2022 - Plast Reconst Surg.pdf`: 10/11 pages with extractable text.
- Local `all-MiniLM-L6-v2` model weights were already available, so retrieval ran with `local_files_only=True` and no model download.
- Retrieval embeddings written in the scratch DB: 14352 chunk embeddings and 77 paper embeddings.
- Qualitative retrieval spot checks looked plausible:
  - `moral judgment theory of mind temporoparietal junction` returned Young/Saxe theory-of-mind and moral-judgment sources at the top.
  - `ketamine depression neurobiology aging` returned late-life depression / neurobiology / aging sources at the top.
  - `facial anomalies social perception` returned facial-anomaly and anomalous-face perception sources at the top.
  - `misinformation fake news belief sharing` returned Pennycook/Rand, Hartley/Khuong, and Lazer fake-news sources at the top.
- I did not run against a real Zotero directory in this pass.

## Bugs / Gaps Discovered

1. Real sentence-transformers loading needed an explicit local-only mode to honor the no-external-call constraint. Added `local_files_only`.
2. Zotero import could previously fail the whole import if one available PDF failed extraction. Added an optional callback and skip behavior for attachment extraction failures.
3. Real retrieval over 14k vectors exposed a sqlite-vec wrapper bug: the wrapper requested `k=14429`, but sqlite-vec caps KNN `k` at 4096. Fixed by capping sqlite-vec search requests and added a regression test.
4. The validation CLI initially crashed while printing retrieved snippets containing ligatures to a CP1252 Windows console. Fixed by configuring stdout for UTF-8 with replacement fallback.

No schema gap was encountered.

## Raw Pytest Output

```text
============================= test session starts =============================
platform win32 -- Python 3.12.7, pytest-7.4.4, pluggy-1.0.0
rootdir: C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.2.0
collected 17 items

tests\test_embeddings.py .....                                           [ 29%]
tests\test_pdf_processing.py ...                                         [ 47%]
tests\test_persistence_core.py ......                                    [ 82%]
tests\test_validation_harness.py ..                                      [ 94%]
tests\test_zotero_importer.py .                                          [100%]

============================= 17 passed in 15.89s =============================
```
