# Build Log

This document records the completed increments of Callosum, mapping implementation milestones to the original planning documents.

| Increment | Status | Focus | Key Deliverables | Notes |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Complete | Persistence Core | SQLAlchemy schema, Alembic migrations, Paper model with provenance. | [INCREMENT-01-NOTES.md](../INCREMENT-01-NOTES.md) |
| 2 | Complete | PDF Extraction | PyMuPDF integration, paragraph-like chunking, coordinate-aware quote location. | [INCREMENT-02-NOTES.md](../INCREMENT-02-NOTES.md) |
| 3 | Complete | Zotero Importer | Read-only Zotero DB adapter, non-destructive normalization, identity resolution. | [INCREMENT-03-NOTES.md](../INCREMENT-03-NOTES.md) |
| 4 | Complete | Embeddings & Vector Store | `sentence-transformers` integration, `sqlite-vec` virtual tables, stale detection. | [INCREMENT-04-NOTES.md](../INCREMENT-04-NOTES.md) |
| 5 | Complete | Validation & Scale | Real-data validation harness, 77-PDF library test run. | Fixed KNN cap and Windows Unicode issues. [INCREMENT-05-NOTES.md](../INCREMENT-05-NOTES.md) |
| 6 | Complete | Retrieval Correction | Candidate-scoped retrieval fix for `sqlite-vec`. | Fixed global KNN search universe bug. [INCREMENT-06-NOTES.md](../INCREMENT-06-NOTES.md) |
| 7 | Complete | Axis Scoring | Supervised axis assignment, nested axes, cosine metric alignment. | [INCREMENT-07-NOTES.md](../INCREMENT-07-NOTES.md) |

## Supplementary Work (June 2026)

### Enhanced Test Coverage
- **Persistence Trust-Spine:** Added `test_trust_spine_round_trip` and `test_summary_cascade_delete` to `tests/test_persistence_core.py` to verify the full summary-to-evidence chain and its deletion behavior.
- **Zotero Importer Edge Cases:** Added `test_zotero_importer_edge_cases` to `tests/test_zotero_importer.py` covering no-title fallbacks, linked-URL attachments, and DOI-casing idempotency.

### Validation Harness Enhancement
- **Per-Page Text Coverage:** Updated `tools/validation_harness.py` to report a per-page breakdown of extractable text presence.
- **Heuristic Diagnostic Hints:** Added evidence-based hints for text-free pages (e.g., "likely image/figure page" vs "empty page") derived from PyMuPDF page content inspection.
- **Debug Rendering:** Added optional rendering of text-free pages to small PNG images in the output directory for visual verification.

## Key Bug Fixes Found During Increments

- **KNN Cap (Inc 5/6):** Discovered that `sqlite-vec` caps global KNN at 4096. Corrected candidate-scoped search to apply constraints inside the KNN query rather than post-filtering.
- **Metric Mismatch (Inc 7):** Aligned `sqlite-vec` distance metric to `cosine` to match model expectations and ensure ranking parity across backends.
- **Windows Unicode (Inc 5):** Fixed CLI crashes when printing retrieved snippets with ligatures to a Windows console.

## Pending Tracks

The following high-level features from the original roadmap are not yet started:
- Abstract-first automatic clustering (Stage 3).
- Citation-grounded summarization & Gemini integration (Stage 4).
- OpenAlex/Semantic Scholar discovery & scoring (Stage 5).
- Frontend / UI development.
