# Increment 484 — Native Zotero library import, shipped (backlog #57 Phase 1)

## Implemented

The already-built, full-fidelity Zotero importer (`app/backend/importers/zotero.py` +
`integrations/zotero/adapter.py`, previously reachable only from `tools/validation_harness.py` and the test
suite) gets a real, shipped entry point.

- `app/backend/api/routers/library_zotero.py` (new) — `POST /library/zotero/import {zotero_data_dir}` (async
  job through a new `zotero_import_jobs` `JobStore`) + `GET /library/zotero/import/{job_id}` (poll). The whole
  read+import runs inside one `engine.begin()` transaction (matching `import_zotero_library`'s own contract),
  then a separate per-paper post-processing loop embeds and retraction-checks what the import actually touched
  (see Key technical detail). Split into its own sibling router — `library.py` was already at the 600-line cap.
- `app/backend/importers/zotero.py` — two small additive fields on `ZoteroImportResult`
  (`created_paper_ids: tuple[int, ...]`, `chunk_ids_by_paper: dict[int, tuple[int, ...]]`) so the router can
  drive post-processing without re-deriving what changed. No behavior change to the importer's existing
  read/write logic.
- `app/backend/api/app.py` / `app/backend/api/routers/status.py` — `zotero_import_jobs` registered on
  `api.state`; `JOB_LABELS` ("Zotero library import"), `JOB_NAV_DEFAULTS`
  (`{"workspace": "library", "modal": "zotero-import"}`), `JOB_COMPUTE_KINDS` ("Local AI" — the local embedding
  model driving the post-processing loop, same label `library_import_jobs`/`library_bundle_import_jobs` already
  use, not an LLM).
- `app/frontend/js/27b_zotero_import.jsx` (new) — `ZoteroImportModal`/`ZoteroImportModalBody`, mirroring
  `27_scan.jsx`'s exact resume-on-remount `localStorage` poll lifecycle (`callosum.zoteroImportJob`). States the
  copy-before-read safety property and the known annotation-position gap directly in the modal body.
- `app/frontend/js/10b_libmenus.jsx` / `10_pdf_layer.jsx` — a new "Read Zotero library…" entry in the Library
  "+ Add" ▾ menu, above "Import file…"; demo-mode gets its own `explainDemoLock` message (the static browser
  demo has no filesystem or backend).
- `app/frontend/js/04e_onboarding.jsx` — a third choice ("Read my Zotero library…", now the leading option) on
  the onboarding wizard's Import step, reusing `ZoteroImportModalBody` unchanged.
- `app/frontend/js/40_app.jsx` — modal open/close state + nav-click wiring (`nav.modal === "zotero-import"`),
  following the existing `importOpen`/`bundleImportOpen` pattern exactly.
- `tests/test_zotero_importer.py` (+3 tests) / `tests/test_library_zotero_import.py` (new, 6 tests) — importer-
  level coverage of the two new result fields + progress reporting + the "previously-missing PDF resolves on a
  later run" case; endpoint-level coverage of the job lifecycle, request validation, and error surfacing through
  the real HTTP contract.
- `callosum-app.html` rebuilt (`python tools/build_frontend.py`) to pick up the new frontend chunk.

## Key technical detail

**The union-of-touched-paper-ids post-processing logic.** `import_zotero_library` returns two disjoint-but-
overlapping id sets: `created_paper_ids` (papers this run inserted — new metadata, so their embedding is
missing and their retraction status has never been checked) and `chunk_ids_by_paper` (every paper this run gave
brand-new chunks to, whether the paper itself was created or already existed). The router computes
`touched_ids = created_paper_ids ∪ chunk_ids_by_paper.keys()` (order-preserving, `dict.fromkeys`) and, per
touched paper: embeds any new chunks it has (searchability), and — **only if the paper was newly created** —
also embeds the paper-level record and runs a retraction check.

The reason a paper can land in `chunk_ids_by_paper` **without** being in `created_paper_ids` is a real,
concrete scenario the test fixtures model directly: a Zotero item whose only attachment is a *linked* file path
that doesn't exist on disk at first-import time (Zotero's `MISSLINK`-style linked-file attachments — the user's
external drive was unmounted, the file hadn't synced yet, etc.). That item still gets a paper row on the first
run (metadata-only, `attachment.availability == "missing"`, no chunks). If the same directory is imported again
later — after the file has since appeared on disk — `import_zotero_library` correctly resolves and extracts it
*this* time, giving the *already-existing* paper its first real chunks. That paper needs `embed_chunks` for the
newly-created chunks (or full-text search would silently miss them), but it does **not** need `embed_papers`
again (its title/abstract embedding was already created and is unchanged) or a fresh retraction check (retraction
status is a metadata fact, not an attachment fact, and was already checked when the paper was first created).
Getting this wrong in either direction would either silently under-embed a matched paper's new content or waste
a wholly redundant retraction lookup on every re-run — `tests/test_library_zotero_import.py::
test_zotero_import_matched_paper_embeds_newly_created_chunks` and `tests/test_zotero_importer.py::
test_zotero_importer_second_run_populates_chunk_ids_for_previously_missing_pdf` both exercise this exact path
end-to-end.

## Manual verification script

1. Start the app. Library → "+ Add" ▾ → confirm **"Read Zotero library…"** appears above "Import file…".
2. Point it at a real Zotero data directory (the folder containing `zotero.sqlite` — commonly `~/Zotero` or
   `Documents\Zotero`), or a synthetic one built via `tests.test_zotero_importer._make_zotero_fixture`. Click
   **Read library**.
3. Confirm a Status popover entry appears while the job runs, labeled "Zotero library import," and clicking it
   lands back on the Library workspace with this same modal reopened.
4. On completion, confirm the summary counts (new/matched/attachments/chunks/errors) are accurate against what
   the source library actually contains.
5. Open a newly-imported paper with a local PDF. Confirm its content is full-text searchable (the extraction
   actually ran, not just a metadata-only import) and that its Zotero tags/collection membership carried over.
6. Re-run the import against the **same** directory. Confirm the summary reports **0 new papers** — a clean,
   idempotent no-op, not duplicate rows.
7. Separately, open the first-run onboarding wizard's Import step (a fresh `onboarding_completed` state) and
   confirm the same "Read my Zotero library…" choice is present and works identically.

## Pytest

Targeted: `pytest tests/test_zotero_importer.py tests/test_library_zotero_import.py -q` → **11 passed** (9 new
in this plan: 3 added to `test_zotero_importer.py`, 6 in the new `test_library_zotero_import.py`, plus the 2
pre-existing `test_zotero_importer.py` tests from before this plan).
`pytest tests/test_frontend_assembly.py -q` → 67 passed (frontend-chunk edits, per the verification protocol).
`python tools/check_line_budget.py` → OK, all application-source files within the 600-line cap
(`library_zotero.py` sits at 150 lines, nowhere near it).
`python -m tach check` → OK, all modules validated.

Full suite (`pytest -n auto -q`, foreground, ~25 min): **2331 passed, 1 failed, 4 skipped in 1496.29s
(0:24:56).** The one failure, `tests/test_website_how_it_works.py::test_primary_local_destinations_exist
[demo/-target2]`, asserts that `dist-demo/` (a gitignored build artifact from the separate demo/website build
pipeline) exists on disk — it doesn't in this worktree because that build was never run here. Confirmed
unrelated to this increment: this task touches only `app/backend/importers/zotero.py`,
`app/backend/api/routers/library_zotero.py`, `app/backend/api/app.py`, `app/backend/api/routers/status.py`,
five `app/frontend/js/*` chunks, `callosum-app.html`, and two test files — nothing under `www/`, `demo/`, or the
build pipeline. The same pre-existing environment gap (not a regression) was already recorded verbatim in
`INCREMENT-483-NOTES.md`, a prior increment on this same machine. 2331 = the inc-483 baseline's 2322 plus this
plan's 9 new tests (3 added to `test_zotero_importer.py`, 6 in the new `test_library_zotero_import.py`); the 4
skipped count is unchanged from that same baseline.
