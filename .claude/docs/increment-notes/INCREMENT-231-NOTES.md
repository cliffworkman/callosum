# Increment 231 — OCR scanned PDFs into a searchable copy (backlog B3)

The first of the design-gated B-items. A scanned / image-only PDF imports today with **zero chunks** (no text
layer) → invisible to search, embeddings, synthesis, and citation. This adds a manual per-paper **"OCR this paper"**
action that makes it fully first-class.

Maintainer decisions (AskUserQuestion): **local Tesseract, manual trigger, exact highlight boxes.**

## The load-bearing discovery (mid-build)

Exact citation highlights are produced by `summarization/verification.py` → `locate_quote_for_attachment` →
`quote_matching.locate_quote`, which **re-reads the PDF's text layer at display time** (`page.get_text("words")`).
A scanned PDF has no text layer, so *storing* OCR word-boxes in the database would never yield exact highlights —
the code would find nothing and fall back to region. The clean way to honor "exact" (a second AskUserQuestion; the
maintainer picked it) is a **searchable PDF**: embed the OCR text *inside* the PDF. Then a scanned paper behaves
exactly like a normal text PDF everywhere — search, exact citation highlights, selectable text — and it touches
**none** of the fragile quote-location / coordinate-honesty code. This reuses *more* of the existing pipeline than
the original plan (which parsed Tesseract TSV + synthesized chunks + would still have needed a quote-location patch).

## Implemented

- **`app/backend/pdf_processing/ocr.py`** (NEW) — `make_searchable_pdf(src, out, *, dpi=300, lang="eng", runner, on_progress)`:
  for each page (bounded to `MAX_OCR_PAGES=200`) render `page.get_pixmap(dpi=300).tobytes("png")` → `runner(png,lang)`
  returns a single-page searchable PDF → merge with `fitz` (`out.insert_pdf(fitz.open(stream=..., filetype="pdf"))`)
  → `out.save(garbage=3, deflate=True)`. `_default_page_runner` shells out to `tesseract stdin stdout -l <lang> pdf`
  (image piped via **stdin**, PDF read from **stdout**; `shutil.which` + fail-closed `subprocess.run`, per-page
  timeout). `TesseractUnavailable` (typed, mirrors `CitationEngineUnavailable`). `runner` is injectable so tests never
  need the binary. **No new pip dependency** — Tesseract is a system binary; PyMuPDF renders + merges without Pillow.
- **`app/backend/api/routers/ocr.py`** (NEW) — `POST /papers/ocr/run {paper_id}` (202; sync-validates 404 no paper /
  422 no local PDF / 422 already has a text layer) + `GET /papers/ocr/run/{job_id}` + the worker `_run_ocr_job`
  (resolve the PDF via the inc-91 `_local_attachment_path`/`_select_primary_pdf_attachment` → `make_searchable_pdf`
  into `library_dir()` [named per the library convention + an `(OCR)` marker, deduped] → **demote existing
  attachments to `secondary`, attach the searchable copy as `primary` with `import_source="ocr"`** →
  `attach_pdf_to_paper` [normal extract + chunk] → `embed_chunks(on_progress=mark_progress)`). Fail-closed: a
  `TesseractUnavailable` or any error → `mark_error`, never a crash. Async `ocr_jobs` JobStore, registered **before**
  `papers.router`.
- **`app/frontend/js/25_detail.jsx`** — `OcrRow` (mirrors `AcquireOaRow`, reuses `.detail-acquire`): the **"OCR this
  paper (scanned)"** button, a poll loop with the determinate `ProgressBar`, and a refetch on done. Rendered only
  when `hasPdf && p.chunk_count === 0` (the detail response already carries `chunk_count` — no backend field added).

## Key technical detail — non-destructive + no honesty-code change

The original scanned attachment is **kept** (demoted to `role="secondary"`); the OCR'd searchable copy becomes the
sole `role="primary"`, so the viewer + `locate_quote_for_attachment` read it. Because the copy has a **real,
correctly-positioned** text layer (Tesseract embeds it over the upright page image), exact highlights come from the
**unchanged** quote-location pipeline — no fabricated coordinates. The button is gated to `chunk_count == 0`, so the
worker only ever *adds* chunks — sidestepping the deferred inc-65 delete-chunks / orphan-vector-cleanup work entirely.

## Manual verification script (the maintainer's step — needs the binary)

1. `winget install UB-Mannheim.TesseractOCR` (or `brew install tesseract` / `apt install tesseract-ocr`), restart.
2. Import a **scanned** PDF (no text layer) → open **Details** → click **"OCR this paper (scanned)"** → watch the
   page-by-page progress → the button disappears and the paper is now searchable.
3. Full-text search finds a word from a page; open the PDF → a synthesis citation highlights **exactly** on the page,
   and text is selectable in the viewer. The original scanned file is still listed under Files.

## Pytest

`HF_HUB_OFFLINE=1 python -m pytest tests/test_ocr.py -q` → **5 passed** (hermetic — a fake page-runner returns a real
text PDF, so no Tesseract binary is needed): the engine builds a searchable PDF the normal extractor reads; the
endpoint 202→poll→done makes a scanned paper searchable + keeps the original + the OCR copy primary
(`import_source="ocr"`); 404/422; graceful when the binary is absent. Full suite **824 passed, 1 skipped**. QA
surface **167/167 API + 729/729 FE, 0 uncovered** (`route_52_ocr.md`). No migration, no new dependency, no egress;
audit `.claude/security-audits/2026-07-01_ocr.md` PASS.
