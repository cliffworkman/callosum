<!-- qa-coverage
api: /papers/ocr*
fe: 25_detail.jsx
-->

# ROUTE 52 - OCR a scanned PDF into a searchable copy (local, no egress)

**Tier:** 1 local-stateful
**Goal:** Exercise the per-paper OCR action while preserving the load-bearing posture: it is offered **only** for a
PDF paper with **no text layer** (chunk_count == 0), it runs **fully local** (Tesseract + local embeddings — no
egress), it is **non-destructive** (the original scanned attachment is kept; the searchable copy becomes primary),
and it **fails gracefully** when Tesseract isn't installed.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). A real OCR run needs the `tesseract` **system binary**; QA does
not assume it is installed — either it completes (binary present) or the job returns a graceful `error` with an
"install Tesseract" hint (binary absent). Register listeners before navigation. Note: OCR writes a searchable copy
under the isolated `CALLOSUM_LIBRARY_DIR`, never the real library.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No egress (veto-level here).** OCR is local (Tesseract binary + local embeddings). ANY request to a
  `generativelanguage`/Gemini/genai host during an OCR run is **Critical** (this is not the Gemini gate).
- **Offered only for scanned PDFs.** The "OCR this paper" control appears **only** when the paper has an available
  PDF attachment **and** `chunk_count == 0`. It must NOT appear for a paper with a text layer or with no PDF.
- **Non-destructive.** After a successful OCR the paper has ≥1 chunk (now searchable) and **≥2 attachments** (the
  original scanned file is kept; the OCR'd searchable copy is the new `role="primary"`, `import_source="ocr"`).
- **Graceful when the binary is absent.** With no `tesseract` on PATH, the job status is `error` with a clear
  install hint — never a 500 or a crash.
- **No uncompletable control.** The button either starts a job that reaches done/error, or is absent by the gate.

## Adversarial checklist

- POST `/papers/ocr/run` for a **nonexistent** paper → 404.
- POST for a paper with **no local PDF** → 422 ("no local PDF to OCR").
- POST for a paper that **already has a text layer** (chunk_count > 0) → 422; and the button is absent in the UI.
- Deep-link / GET a **nonexistent** OCR job id → 404.
- Resize to `375x812` — no horizontal overflow while the progress bar shows.

## Steps

1. Select a **scanned** paper (a PDF attachment, 0 chunks) → open METHODS → **Details**. Confirm the **"OCR this
   paper (scanned)"** button is present (it uses the `.detail-acquire` recipe).
2. Confirm the same button is **absent** on (a) a normal text PDF paper (chunk_count > 0) and (b) a paper with no PDF.
3. Click **OCR this paper**. A `POST /papers/ocr/run {paper_id}` returns 202 → poll `GET /papers/ocr/run/{job_id}`
   with the determinate `ProgressBar` ("Reading pages…" / "Embedding text…" · X / N). Confirm **no genai-host request**.
4. On **done** (binary present): the detail refreshes, `chunk_count` is now ≥1, the "OCR this paper" button is gone,
   and a full-text search finds a word from the page. On **error** (binary absent): a clear "Tesseract is not
   installed…" message; no crash.
5. Adversarial: the 404/422 cases above; mobile viewport → no overflow.

## Pass criteria

- The button is gated correctly (scanned PDFs only) and, when run, drives an async job to done/error with a
  determinate progress bar.
- **0 console/page errors; 0 genai-host requests** (fully local).
- Non-destructive: original attachment kept; the OCR'd copy is primary (`import_source="ocr"`); the paper becomes
  searchable.
- 404 (no paper) / 422 (no PDF / already has text) / 404 (unknown job) honored; graceful "install Tesseract" on a
  missing binary.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_52_ocr.md` + `screenshots/` (see `_TEMPLATE.md`).
