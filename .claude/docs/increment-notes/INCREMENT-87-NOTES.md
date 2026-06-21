# Increment 87 — Scan / refresh a library folder

## Implemented
The user's top-priority `callosum_TDL.txt` item + the carrot: point Callosum at a folder of PDFs → ingest
**new** files, skip **unchanged**, flag **removed** — the Zotero-free way to keep a library current. The first
app-level "ingest a folder" path (previously only the Zotero importer + the dev validation harness did this).

**Backend**
- `app/backend/pdf_processing/library_scan.py` (NEW) — `scan_library_folder(conn, folder, *,
  import_source="library-scan")`: walks `folder.glob("*.pdf")`; per file: size-cap (80 MiB) → `file_sha256`. If
  the checksum is already in any `attachments` row → **unchanged**; else `create_paper(imported_source=
  "pdf-scaffold")` + `attach_pdf_to_paper(storage_mode="linked", import_source="library-scan")` (extract +
  chunk) inside a per-file **savepoint** (a corrupt PDF is isolated → `errors[]`, scan continues). A
  previously-scanned path no longer on disk → `availability="missing"` (**removed**, non-destructive). Returns
  `{added, unchanged, removed, errors}`.
- `app/backend/api/routers/library.py` (NEW) — `POST /library/scan {folder}` (validates an existing directory →
  else 422; async → 202 + job_id) + `GET /library/scan/{job_id}` (poll). The job: `scan_library_folder` → enrich
  each new paper from Crossref (resilient; unresolved → the inc-80 Unsorted view) → `embed_chunks` +
  `embed_papers` (so they're searchable). New `app.state.library_scan_jobs` JobStore; model/vector-store/Crossref
  resolved injected-or-default (mirrors the axis-suggest job). Registered in `create_app`.

**Frontend**
- `app/frontend/js/27_scan.jsx` (NEW) — `ScanModal`: a folder-path input (remembered in
  `localStorage["callosum.scanFolder"]`) + Scan → POST + poll (reuses the inc-79 `ProgressBar`) + a summary
  ("N added · N unchanged · N missing"). A **"Scan folder"** button in the library head (`10_pdf_layer.jsx`)
  opens it; `40_app.jsx` wires `scanOpen` + refreshes the library on done. Token CSS; rebuilt `callosum-app.html`.

## Key technical detail
All ingestion primitives already lived in `app/` (`attach_pdf_to_paper`, `file_sha256`, `embed_chunks`/
`embed_papers`, the indexed `attachments.checksum`); only the *orchestration* was harness-only — this lifts it
into a real service. PDFs are **linked in place** (nothing copied/moved). Dedup is by **content checksum**
(re-scan = all unchanged; a file already imported via any route is skipped). v1 handles **new / unchanged /
removed**; an in-place **changed** file is added as a new paper (its stale copy can be trashed) — true
changed-file re-ingest is deferred because it needs the inc-65 vector cleanup to avoid orphaned chunk
embeddings. The only egress is the per-new-paper Crossref DOI lookup (metadata, **not** the Gemini gate); the
folder is read **server-side**, which is the intent on a 127.0.0.1 single-user app (audit notes: gate before any
hosted deployment).

## Manual verification script
1. Hard-refresh; put a few PDFs in a folder.
2. Library head → **Scan folder** → enter the path → **Scan**: the papers appear (Crossref-enriched where the
   DOI resolves; the rest under **Unsorted**); the summary shows "N added".
3. Re-Scan → "all unchanged." Delete one PDF on disk + re-Scan → it's flagged missing. _(Visual check delegated.)_

## Pytest
**383 passed, 1 skipped** (+3: `scan_library_folder` add/unchanged/removed over fitz fixture PDFs; the endpoint
processes a folder → papers in the library + Unsorted; non-existent folder → 422). `ruff` clean; **no migration**
(reuses `attachments`). Audit `.claude/security-audits/2026-06-21_library-scan.md` **PASS**.
