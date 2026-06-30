# Increment 214 — close-out mop-up: per-file scan progress + first-class extra URLs (+ a forced papers.py split)

Two of the small autonomous "dregs" the maintainer asked to clear (the 30_viewer split + minimap is inc 215).

## Implemented
- **#4 — per-file filename in scan progress.** `scan_library_folder`'s `on_progress` callback is now
  `(current, total, filename)` (was `(current, total)`); it passes `path.name` per file. The scan/watched-rescan
  job lambdas in `routers/library.py` put it in the label (`f"Reading {name}"`), so the existing `ProgressBar`
  (which renders `progress.label — X / N`) shows "Reading <file> — 12 / 80" for free — **no frontend change**.
- **#5 — first-class extra URLs.** A paper can record additional URLs beyond the primary CSL `URL`. Stored in
  `csl_json["extra_urls"]` (a list of strings; the primary `URL` stays canonical). `paper_edits.build_paper_update`
  gains an `extra_urls` field (`_apply_extra_urls`: cleaned, empties dropped, popped when empty) + `"extra_urls"`
  added to `RESERVED_CSL_KEYS` (so the generic "More" passthrough can't clobber it). `PaperUpdateRequest.extra_urls`
  (`list[str]`, ≤50; each ≤2000 via `_clean_urls`) + `PaperDetailResponse.extra_urls` (read from csl_json via
  `_extra_urls_from_csl`). Frontend: a **"More URLs"** `EditableText` (one-per-line) in `25_detail.jsx` →
  `saveExtraUrls` → `saveField("extra_urls", list)` — mirrors the Authors/Translators pattern, consistent with the
  pane's other editable URL/identifier fields. (Clickable-link rendering deferred — it'd be a pane-wide viewer
  change across all URL fields; the pane is an editor, so the primary URL isn't a link either.)

## Key technical detail (the forced split)
Adding `extra_urls` pushed `routers/papers.py` to **604 — over the 600-line cap.** Per rule #1 it MUST be
modularized before the feature lands, so the **request-normalisation cluster** (`edits_from_request` [was
`_edits_from_request`] + `_norm_str` / `_clean_authors` / `_clean_urls` / `_validate_csl_patch` + the caps
constants `CSL_PATCH_*` / `AUTHOR_MAX_LEN` / `URL_MAX_LEN` / `_CSL_KEY_RE`) was extracted **verbatim** to new
**`routers/paper_edit_input.py`** (111 lines; the inc-91/207 split pattern). `edits_from_request` is duck-typed on
the request (`model_fields_set` + `getattr`) so it needn't import `PaperUpdateRequest` → **no import cycle**.
`papers.py` 604 → **510** (imports `edits_from_request`; dropped the now-unused `import re` + `RESERVED_CSL_KEYS`).

## Manual verification script
- `python .local/visual/drive_inc214_extra_urls.py` (headed, no egress): seeds a paper → top auto-selects →
  Details → type two URLs into "More URLs" → blur → `GET /papers/{id}.extra_urls == [both]`; 0 console/page/genai.
- #4: `pytest tests/test_library_scan.py::test_scan_progress_reports_the_per_file_basename` — the callback receives
  the sorted basenames + the carried total.

## Pytest
**748 passed, 1 skipped** (+6 over inc-213's 742: `test_library_scan.py` +1, `test_paper_edits.py` +3,
`test_papers.py` +2). The papers.py split is behavior-preserving (the existing PATCH/edit tests pass unchanged).
`papers.py` 510; `paper_edit_input.py` 111; `25_detail.jsx` 529. QA surface unchanged (145/145 API + 685/685 FE —
a request/response field on existing endpoints + an `EditableText` reusing already-claimed elements; no new route).
ruff clean.

## Gates
No new endpoint / no migration / no egress / no new dependency → no audit-gate trigger; Principles non-triggering
(recording fields + a behavior-preserving split, no claim/signal). help corpus: the Details/editing section is
already general about editable fields; the "More URLs" field is self-describing (placeholder) — no corpus change.

## NEXT
inc 215 — a **minimap/scrollbar highlight marker** in the PDF viewer (its own headed check). NB `30_viewer.jsx` is
actually **557**, not 599/600 (inc-182's LibraryFrame extraction relieved it; the CLAUDE rule-#1 "MAXED" note was
stale), so the planned split is **unnecessary** — the minimap fits under the cap directly. After it, the autonomous
close-out band is empty and the remaining backlog is design-gated B-items.
