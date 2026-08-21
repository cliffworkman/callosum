# Security audit — Zotero annotation-position fidelity

**Date:** 2026-08-21
**Scope:** backlog #57 Phase 4 — translate Zotero PDF highlight/underline positions into Callosum's exact
PDF-space annotation coordinates and surface them only on the matching attachment.
**Status:** PASS

## Trigger

This slice changes an existing import path and the response behavior of existing PDF/annotation endpoints across
multiple application files. It adds no endpoint, external service, dependency, schema migration, or new file-write
path, but it crosses the audit gate's multi-file feature threshold.

## Threat review

- **Untrusted input:** Zotero's `itemAnnotations.position` is external JSON stored in a copied SQLite database.
  Parsing must be bounded, shape-checked, finite-number-only, page-bounded, positive-area, and fail closed.
- **Coordinate honesty:** only documented highlight/underline rectangles on an available, unrotated PDF page may
  become `pdf-points-top-left` bboxes. Malformed, unsupported, out-of-page, missing-PDF, and rotated-page positions
  must retain raw provenance without an exact overlay.
- **Attachment ownership:** an imported annotation may surface only with the Callosum attachment created from its
  own Zotero parent attachment; cross-paper and wrong-attachment display must remain structurally unavailable.
  **Inc 489 hardening:** an already-exact row also stays pinned to that proven attachment if a later Zotero
  re-import relinks the same annotation key to a replacement PDF. Page-bounds validity on different bytes is not
  sufficient evidence to move an exact mark.
- **Output encoding:** annotation text/comment remains ordinary JSON API data and React text; no HTML injection path
  is added.
- **SQL/injection:** all reads/writes remain SQLAlchemy-bound or the adapter's fixed SQL; no user value becomes SQL.
- **Filesystem/path safety:** PDF geometry is read only from the already-resolved Zotero attachment path used by the
  existing importer. No new path input or path construction is introduced.
- **SSRF/egress:** translation is local PyMuPDF work. No network client or provider call is added.
- **Secrets:** none introduced or read.
- **Resource caps:** Zotero's own 65,000-byte position maximum is enforced before JSON parsing; a separate 2,048-
  rectangle structural cap applies after parsing. Each rectangle must be a four-number, finite, positive-area
  list wholly inside the transformed page (apart from a `1e-4` numeric tolerance).
- **Supply chain:** no dependency change; reuse the pinned PyMuPDF dependency.

## Primary-source basis

- Zotero's own `annotations.js` defines highlight/underline type constants and
  `ANNOTATION_POSITION_MAX_SIZE = 65000`:
  <https://github.com/zotero/zotero/blob/main/chrome/content/zotero/xpcom/annotations.js>.
- A Zotero team response identifies `rects` as standard PDF coordinates in
  `[left, bottom, right, top]` order with a bottom-left origin:
  <https://forums.zotero.org/discussion/105677/coordination-problem-about-annotation>.
- PyMuPDF documents `Page.transformation_matrix` as the PDF-to-MuPDF coordinate transformation:
  <https://pymupdf.readthedocs.io/en/latest/page.html#Page.transformation_matrix>.

## Checks run

- `pytest tests/test_zotero_importer.py -q` → **9 passed** after inc 489 hardening. Includes a real one-page PDF and Zotero SQLite
  annotation row producing the exact expected top-left bbox, plus malformed JSON, 65,001-byte input,
  non-finite values, out-of-page rectangles, unsupported type, and rotated-page fail-closed cases. The added
  integration cases cover two annotated sibling PDFs, importer-level rotated-page persistence, and a
  bounds-valid replacement PDF that must not steal an existing exact row.
- `pytest tests/test_annotations.py -q` → **14 passed**. Includes exact imported-row attachment ownership,
  fabricated/wrong-attachment exclusion, native attachment scoping, and backward-compatible unscoped behavior.
- `pytest tests/test_papers.py -q` → **68 passed**. Includes attachment identity on primary and explicit
  non-primary PDF responses.
- `pytest tests/test_library_zotero_import.py -q` → **6 passed**. Existing async import contract remains green.
- `pytest tests/test_frontend_assembly.py -q` → **68 passed**. Asserts the assembled viewer reads the attachment
  response header, attachment-scopes annotation listing, and writes the identity onto both ordinary and
  “highlight + note” marks.
- Direct `rg` across `zotero.py`, `zotero_annotation_position.py`, and `integrations/zotero/adapter.py` for
  `httpx|requests|urllib|socket|subprocess` → **no network/process client references**.
- `ruff format --check .` → **784 files already formatted**; `ruff check .` → **All checks passed**;
  `python -m tach check` → **All modules validated**;
  `PYTHONUTF8=1 python tools/check_line_budget.py --list` → **all 553 application-source files ≤ 600**.
- `python tools/qa/build_surface_map.py check` → **428/428 API and 1767/1767 frontend surfaces covered**.
- Full suite after inc 489 hardening, foreground: `pytest -n auto -q` → **2341 passed, 3 skipped in 932.07s
  (0:15:32)**.

## Result

**PASS.** Exact geometry is admitted only after bounded structural validation against the owning local PDF, and
the API/viewer require that same attachment identity to display it. Every ambiguity degrades to preserved raw
provenance with no drawn bbox. Inc 489's adversarial relink test exposed and fixed a real identity drift before
review: an existing exact row could previously move to a replacement attachment when the rectangle remained
page-valid. Exact rows are now pinned; raw-only rows retain the intended one-way upgrade path. No new egress,
secret, write, dependency, or executable-process surface exists.
