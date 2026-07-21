# Increment 316 — per-attachment PDF serving (backlog #5 remainder)

## Context
`GET /papers/{paper_id}/pdf` always served the paper's single "primary" attachment. A paper can carry 2+ PDF
attachments after a non-destructive merge (#17/inc 161) combines two papers' files — the Details pane's "Files"
list already rendered one button per attachment, but every button's click ignored which one was clicked and
always opened the primary. This closes backlog #5's remainder: "serving a chosen attachment."

## Implemented
1. **`GET /papers/{paper_id}/pdf?attachment_id=`** (`paper_files.py`): an optional query param that opens a
   specific attachment instead of the primary. Looked up within `get_attachments_for_paper`'s own rows — ownership-
   safe by construction (a mismatched id simply isn't found, no separate check needed). Distinct honest 404s:
   "Attachment not found for this paper", "This attachment is not a PDF", "PDF not available locally for this
   attachment". Omitting the param is byte-identical to the prior behavior.
2. **Details pane "Files" list** (`25_detail.jsx`): each button's click now passes its own attachment id through
   `onOpenPaper`/`openPdf`/`PdfViewer` (a target with no `page`, so it selects the file without attempting any
   scroll/highlight). A non-PDF row still opens the primary — unchanged, out of scope.
3. **Citation-attachment fidelity** (found and fixed in the same pass, not assumed): `chunks.attachment_id`
   (non-nullable — every chunk already knows which attachment its text/coordinates came from) was never threaded
   through to a citation's `SummaryCitationResponse`. A citation whose evidence came from a *non-primary*
   attachment always opened the *primary* one — for two PDF renderings of "the same paper," page geometry isn't
   guaranteed to match, so an "exact" bbox highlight could land on the wrong document. `_summary_citation_rows`
   (`summaries.py`) now joins to `attachments` and surfaces `attachment_id` — **but only when the underlying
   attachment is an actual PDF** (`_is_pdf_attachment`, imported from `paper_files.py`). Non-PDF "supplementary-text"
   attachments (DOCX/HTML/JATS-XML, `role="supplementary-text"`) feed the same `chunks` table with placeholder
   `page_start=page_end=1`/`bbox_json=[]` — surfacing their attachment id would have made those citations 404 as
   "not a PDF" instead of today's honest fallback (open the primary, scroll to page 1, no highlight). Verified
   directly in `ingest.py`/`document_text.py` before writing the gating logic, not assumed.
4. **`PdfViewer`** (`30_viewer.jsx`): the PDF-bytes fetch appends `?attachment_id=` when `target.attachmentId` is
   set, and the fetch effect's dependency array gained it — a primitive, so switching between two citations that
   share the same attachment doesn't trigger a wasteful re-fetch, only an actual attachment change does.

## Key technical detail
Adding this pushed `30_viewer.jsx` to 604 lines (over the 600 cap, rule #1). Rather than a file split for a small
feature, the addition itself was made line-neutral: dropped a separate derived `const attachmentId` in favor of
referencing `target?.attachmentId` inline at both use sites (the fetch URL and the effect's dependency array),
and folded the explanatory comment to one line. Net result: exactly 600 lines — within the cap, matching the
project's own "599/600" convention. `python tools/check_line_budget.py` confirms clean.

## Deliberately out of scope (documented so it isn't rediscovered as a silent gap)
- Changing which attachment is "primary" outside of merge — the existing `primary_attachment_id` merge-time flow
  is untouched.
- Per-attachment PDF tabs — kept the existing one-tab-per-*paper* model; opening a different file replaces what
  the tab shows, exactly like a citation jump already replaces `target` in place.
- A "currently showing which file" indicator in the Files list — a possible low-priority follow-up.
- The same attachment-awareness for `methodEvidenceTarget()` (statcheck/GRIM/Bayes/LMM/meta-analysis/transparency/
  reference-integrity evidence links) and `37_cite.jsx`'s hand-built citation object — same latent risk class,
  confirmed safe-by-omission today (no attachmentId ⇒ graceful fallback to primary, identical to before this
  increment), but a separate, wider audit across ~8 files. Filed as a follow-up, not bundled in.

## Manual verification (Playwright, this session, against the real testing DB)
1. Restarted the dev uvicorn process pointed at the testing DB (no `--reload`, so the backend changes needed a
   fresh process) — confirmed via `GET /health`.
2. Seeded 2 scratch papers, each with a real local PDF carrying distinguishable byte content, and merged them via
   `POST /papers/merge` with an explicit `primary_attachment_id` — the actual scenario this backlog item exists
   for. Confirmed via `curl` that `?attachment_id=<each id>` served each file's own distinct bytes.
3. In the browser: selected the merged survivor, opened Details → Files (2 buttons: "scratch-preprint.pdf PRIMARY"
   and "scratch-published.pdf"). Clicked each and confirmed (via the network log) each click fired
   `GET /papers/240/pdf?attachment_id=111` then `?attachment_id=112` respectively — the exact attachment ids from
   the merge — with 0 console errors. The reader showed an honest "Couldn't open this PDF" (the scratch bytes are
   minimal stubs, not real enough for pdf.js to parse) — the correct, honest failure mode, not a wrong-file
   substitution or a silent error.
4. Cleaned up: un-merged, trashed, and permanently purged both scratch papers from the testing DB afterward.

## Pytest
Full suite **1302 passed, 1 skipped** (up from 1295; +7 new tests). `tests/test_papers.py` gained 5 new
`?attachment_id` cases (serves the chosen non-primary attachment; 404s for another paper's attachment, a
nonexistent id, a non-PDF attachment, and an unavailable-on-disk attachment). `tests/test_paper_merge.py` gained
an endpoint-level test proving a real merge survivor with 2 distinguishable on-disk PDFs serves each one correctly
by attachment id. `tests/test_summaries.py`: the citation exact-key-set assertion gained `attachment_id`, plus a
positive case (matches the seeded PDF attachment) and a negative case (a citation from a non-PDF
supplementary-text chunk has `attachment_id is None` despite the chunk's own FK being non-null — the regression
guard for the gating fix). `tests/api_helpers.py`'s `_seed_summarization_library` now returns
`facial_attachment_id`/`unrelated_attachment_id` (purely additive; no caller asserts its key set). `ruff check .`
/ `ruff format --check .` clean; `python tools/check_line_budget.py` clean (348 files).

## Gates
- **QA (#10):** `route_32_viewer_annotations.md` extended (a new step 8: merge-then-click-each-Files-button +
  citation-from-non-primary-attachment + non-PDF-citation-still-degrades-to-primary; `fe:` gained
  `25_detail.jsx`/`00_lib.jsx`; a header note on the new query param + the coordinate-honesty rationale).
  `route_24_duplicates.md`'s merge step extended to require each post-merge Files button opens its own distinct
  document (previously uncheckable — every button was identical).
- **Principles (#9):** the citation-attachment fix is a direct principle-fidelity fix (coordinate honesty,
  invariant #2) — named explicitly rather than treated as incidental, same treatment as the inc-314 `notice_url`
  fix.

## Next
The wider attachment-awareness audit (methods-evidence targets + `37_cite.jsx`) noted above as deliberately out
of scope — not urgent (today's fallback is safe), worth a look if a future feature increases how often a paper
carries multiple attachments.
