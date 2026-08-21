# Increment 485 — Zotero annotation-position fidelity (backlog #57 Phase 4)

## Implemented

- `app/backend/importers/zotero_annotation_position.py` (new) — a bounded, fail-closed translator for Zotero
  PDF highlight/underline `position` JSON. It accepts only finite positive-area rectangles on a valid page of the
  owning, unrotated PDF, then uses that page's PyMuPDF transformation matrix to convert standard PDF
  bottom-left coordinates into callosum's `pdf-points-top-left` basis. The 65,000-byte Zotero position limit is
  enforced before parsing and a 2,048-rectangle structural cap applies afterward. Unsupported/malformed/
  out-of-page/missing-PDF/rotated-page positions retain raw `zotero-reader-json` provenance but get no bbox.
- `integrations/zotero/adapter.py` — fixes a dormant ownership bug: `itemAnnotations.parentItemID` names the PDF
  attachment item, not the top-level bibliographic item. The snapshot now flattens each attachment's annotation
  children into its paper while preserving `parent_item_id`; imported color joins text/comment/raw position.
- `app/backend/importers/zotero.py` — annotation upsert now runs after attachment upsert, links each mark to its
  canonical attachment, stores exact page/bboxes/coordinate system plus anchor/note/color, and upgrades a legacy
  raw-only annotation on re-import when its PDF becomes available. A later missing/unreadable PDF never erases
  geometry already proven exact.
- `app/backend/persistence/annotations_repo.py` / `app/backend/api/routers/annotations.py` — the existing paper-
  annotation GET accepts an optional `attachment_id`. Its backward-compatible unscoped response stays native-
  only; an attachment-scoped request additionally exposes only exact Zotero rows owned by that attachment.
  Newly-created native marks are likewise scoped when they carry an attachment; legacy native rows with no
  attachment remain visible.
- `app/backend/api/routers/paper_files.py` / `app/frontend/js/30_viewer.jsx` — the streamed PDF identifies the
  attachment actually chosen in `X-Callosum-Attachment-Id`; the viewer uses that identity for annotation reads
  and new native highlights. Imported geometry therefore cannot appear on a sibling PDF merely because both
  attachments belong to one paper.
- `app/frontend/js/27b_zotero_import.jsx`, served Help, the Zotero integration README, and Route 93 now state and
  test the exact posture: supported marks are placed on the matching PDF; anything ambiguous stays preserved and
  undrawn. `callosum-app.html` was rebuilt. The website review maps Route 93 to `#cap-import`; the existing public
  Zotero-import/highlight/coordinate-honesty claims remain accurate and no current figure depicts the changed
  import-modal copy.

## Key technical detail

**Attachment identity is part of coordinate truth.** A bbox can be mathematically valid and still be false if
drawn over a different PDF revision or sibling attachment. Zotero supplies that identity indirectly:
`itemAnnotations.parentItemID` points to the attachment item whose `path` identifies the PDF. The adapter retains
that edge; the importer maps it to callosum's canonical attachment id while translating against the same resolved
path; the PDF response reports the attachment actually served; and the viewer sends that id back when listing
marks. The repository then admits an imported row only when `import_source == "zotero"`, its attachment id
matches, and exact bboxes exist. Page geometry alone is never sufficient.

The coordinate transform follows Zotero's own annotation-type constants/position bound and the Zotero team's
description of `rects` as standard PDF `[left, bottom, right, top]` coordinates. PyMuPDF documents
`Page.transformation_matrix` as the PDF-to-MuPDF coordinate transform. Rotated pages deliberately remain
raw-only in this slice: proving a transform across every rotation/crop combination is preferable to silently
painting a plausible but false rectangle.

Primary sources consulted:

- <https://github.com/zotero/zotero/blob/main/chrome/content/zotero/xpcom/annotations.js>
- <https://forums.zotero.org/discussion/105677/coordination-problem-about-annotation>
- <https://pymupdf.readthedocs.io/en/latest/page.html#Page.transformation_matrix>

## Experience pass

**Migrator + close reader, code/help-grounded walkthrough (the handoff's no-live-persona fallback):** I point
Callosum at my Zotero directory once, see the existing progress/receipt, then open an imported paper to check
whether the migration was trustworthy. The first supported highlight is already over the passage I marked in
Zotero, with its color/comment available through the familiar annotation interaction; I do not need a second
conversion workflow or per-mark repair. If I switch PDFs, the mark does not follow me. The import explanation
sets the right expectation that unsupported/ambiguous locations are kept but not guessed. The remaining friction
is that raw-only imported annotations still have no separate browse/repair surface, but Phase 4 did not create
one and presenting them as placed would violate coordinate honesty; no new backlog item is required for the
bounded position-fidelity promise.

## Manual verification script

1. Build `tests.test_zotero_importer._make_zotero_fixture` and import it through Library → **+ Add** → **Read
   Zotero library…**.
2. Open the imported DOI'd paper. Confirm its fixture highlight covers “Stored Zotero PDF quote appears here.”
   and retains `#ffd400` plus “Fixture annotation comment”.
3. Inspect the PDF response: `X-Callosum-Attachment-Id` must equal the attachment id used by the subsequent
   `/papers/{paper_id}/annotations?attachment_id=…` request.
4. Request the annotation endpoint without an attachment id, then with a fabricated/sibling id: the imported
   mark must be absent from both. It appears only for its owning attachment.
5. Import fixtures with malformed, out-of-page, unsupported-type, over-cap, non-finite, and rotated-page
   positions. Confirm raw position JSON remains stored and no exact overlay renders.
6. Re-import a legacy raw-only row after its PDF becomes locally available; confirm geometry is backfilled rather
   than a duplicate annotation being created.

## Verification

- `pytest tests/test_zotero_importer.py -q` → **6 passed**.
- `pytest tests/test_annotations.py -q` → **14 passed**.
- `pytest tests/test_papers.py -q` → **68 passed**.
- `pytest tests/test_frontend_assembly.py -q` → **67 passed**.
- `ruff format --check .` → **784 files already formatted**; `ruff check .` → **All checks passed**.
- `python -m tach check` → **All modules validated**.
- `PYTHONUTF8=1 python tools/check_line_budget.py --list` → **all 553 application-source files ≤ 600**;
  closest touched file is `app/frontend/js/30_viewer.jsx` at 581 lines.
- `python tools/qa/build_surface_map.py check` → **428/428 API and 1767/1767 frontend surfaces covered**.
- `python tools/qa/check_website_coverage.py` after reviewed refresh → **70 routes mapped, 1 excluded, 20
  current figures**.
- Full suite, foreground: `pytest -n auto -q` → **2336 passed, 3 skipped in 1208.00s (0:20:07)**.
